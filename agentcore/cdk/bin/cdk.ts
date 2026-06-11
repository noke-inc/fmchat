#!/usr/bin/env node
import { AgentCoreStack } from '../lib/cdk-stack';
import { ConfigIO, type AwsDeploymentTarget } from '@aws/agentcore-cdk';
import { App, type Environment } from 'aws-cdk-lib';
import * as path from 'path';
import * as fs from 'fs';
import * as dotenv from 'dotenv';

function toEnvironment(target: AwsDeploymentTarget): Environment {
  return {
    account: target.account,
    region: target.region,
  };
}

function sanitize(name: string): string {
  return name.replace(/_/g, '-');
}

function toStackName(projectName: string, targetName: string): string {
  return `AgentCore-${sanitize(projectName)}-${sanitize(targetName)}`;
}

async function main() {
  // Config root is parent of cdk/ directory. The CLI sets process.cwd() to agentcore/cdk/.
  const configRoot = path.resolve(process.cwd(), '..');
  const configIO = new ConfigIO({ baseDir: configRoot });

  // Load .env from project root (one level above agentcore/) for local dev / CI.
  // In production, credentials come from pipeline env vars.
  const projectRoot = path.resolve(configRoot, '..');
  const envConfig = dotenv.config({ path: path.join(projectRoot, '.env') }).parsed ?? {};

  // DB credentials injected into the NokeMCP gateway compute runtime.
  // The agentCoreGateways compute.runtime has no envVars support in the CDK schema,
  // so we apply them programmatically via AgentCoreRuntime.addEnvironmentVariable().
  const mcpEnvVars: Record<string, string> = {
    DB_HOST:     process.env.DB_HOST     ?? envConfig['DB_HOST']     ?? '',
    DB_PORT:     process.env.DB_PORT     ?? envConfig['DB_PORT']     ?? '3306',
    DB_USER:     process.env.DB_USER     ?? envConfig['DB_USER']     ?? '',
    DB_PASSWORD: process.env.DB_PASSWORD ?? envConfig['DB_PASSWORD'] ?? '',
    DB_SCHEMA:   process.env.DB_SCHEMA   ?? envConfig['DB_SCHEMA']   ?? '',
    AGENT_AUTH_ENABLED: 'false',
  };

  const spec = await configIO.readProjectSpec();
  const targets = await configIO.readAWSDeploymentTargets();

  // Extract MCP configuration from project spec.
  // Gateway fields are stored in agentcore.json but may not yet be on the
  // AgentCoreProjectSpec type from @aws/agentcore-cdk, so we read them
  // dynamically and cast the resulting object.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const specAny = spec as any;
  const mcpSpec = specAny.agentCoreGateways?.length
    ? {
        agentCoreGateways: specAny.agentCoreGateways,
        mcpRuntimeTools: specAny.mcpRuntimeTools,
        unassignedTargets: specAny.unassignedTargets,
      }
    : undefined;

  // Read deployed state for credential ARNs (populated by pre-deploy identity setup)
  let deployedState: Record<string, unknown> | undefined;
  try {
    deployedState = JSON.parse(fs.readFileSync(path.join(configRoot, '.cli', 'deployed-state.json'), 'utf8'));
  } catch {
    // Deployed state may not exist on first deploy
  }

  if (targets.length === 0) {
    throw new Error('No deployment targets configured. Please define targets in agentcore/aws-targets.json');
  }

  // Read harness configs for role creation.
  const harnessConfigs: {
    name: string;
    executionRoleArn?: string;
    memoryName?: string;
    containerUri?: string;
    hasDockerfile?: boolean;
    dockerfile?: string;
    codeLocation?: string;
    tools?: { type: string; name: string }[];
    apiKeyArn?: string;
    efsAccessPoints?: { accessPointArn: string; mountPath: string }[];
    s3AccessPoints?: { accessPointArn: string; mountPath: string }[];
  }[] = [];
  for (const entry of specAny.harnesses ?? []) {
    const harnessDir = path.resolve(projectRoot, entry.path);
    const harnessPath = path.resolve(harnessDir, 'harness.json');
    try {
      const harnessSpec = JSON.parse(fs.readFileSync(harnessPath, 'utf-8'));
      harnessConfigs.push({
        name: entry.name,
        executionRoleArn: harnessSpec.executionRoleArn,
        memoryName: harnessSpec.memory?.name,
        containerUri: harnessSpec.containerUri,
        hasDockerfile: !!harnessSpec.dockerfile,
        dockerfile: harnessSpec.dockerfile,
        codeLocation: harnessSpec.dockerfile ? harnessDir : undefined,
        tools: harnessSpec.tools,
        apiKeyArn: harnessSpec.model?.apiKeyArn,
        efsAccessPoints: harnessSpec.efsAccessPoints,
        s3AccessPoints: harnessSpec.s3AccessPoints,
      });
    } catch (err) {
      throw new Error(
        `Could not read harness.json for "${entry.name}" at ${harnessPath}: ${err instanceof Error ? err.message : err}`
      );
    }
  }

  // Inject real DB credentials into the NokeMCP standalone runtime from .env.
  // The spec's envVars have empty placeholders; override them with actual values.
  const specRuntimes = (spec as any).runtimes as Array<{ name: string; envVars?: Array<{ name: string; value: string }> }>;
  const nokeMcpRuntime = specRuntimes?.find((r: any) => r.name === 'NokeMCP');
  if (nokeMcpRuntime && nokeMcpRuntime.envVars) {
    for (const ev of nokeMcpRuntime.envVars) {
      if (mcpEnvVars[ev.name] !== undefined) {
        ev.value = mcpEnvVars[ev.name];
      }
    }
  }

  const app = new App();

  for (const target of targets) {
    const env = toEnvironment(target);
    const stackName = toStackName(spec.name, target.name);

    // Extract credentials from deployed state for this target
    const targetState = (deployedState as Record<string, unknown>)?.targets as
      | Record<string, Record<string, unknown>>
      | undefined;
    const targetResources = targetState?.[target.name]?.resources as Record<string, unknown> | undefined;
    const credentials = targetResources?.credentials as
      | Record<string, { credentialProviderArn: string; clientSecretArn?: string }>
      | undefined;

    new AgentCoreStack(app, stackName, {
      spec,
      mcpSpec,
      credentials,
      mcpEnvVars,
      harnesses: harnessConfigs.length > 0 ? harnessConfigs : undefined,
      env,
      description: `AgentCore stack for ${spec.name} deployed to ${target.name} (${target.region})`,
      tags: {
        'agentcore:project-name': spec.name,
        'agentcore:target-name': target.name,
      },
    });
  }

  app.synth();
}

main().catch((error: unknown) => {
  console.error('AgentCore CDK synthesis failed:', error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
