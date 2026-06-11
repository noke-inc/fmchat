import {
  AgentCoreApplication,
  AgentCoreMcp,
  AgentCoreRuntime,
  toPascalId,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
} from '@aws/agentcore-cdk';
import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwv2int from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { CfnOutput, Duration, Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as path from 'path';
export interface HarnessConfig {
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
}

export interface AgentCoreStackProps extends StackProps {
  /**
   * The AgentCore project specification containing agents, memories, and credentials.
   */
  spec: AgentCoreProjectSpec;
  /**
   * The MCP specification containing gateways and servers.
   */
  mcpSpec?: AgentCoreMcpSpec;
  /**
   * Credential provider ARNs from deployed state, keyed by credential name.
   */
  credentials?: Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;
  /**
   * Harness role configurations.
   */
  harnesses?: HarnessConfig[];
  /**
   * Environment variables to inject into MCP gateway compute runtimes.
   * The agentCoreGateways compute.runtime schema does not support envVars directly,
   * so we apply them programmatically via AgentCoreRuntime.addEnvironmentVariable().
   * Keys are gateway target names (as defined in agentCoreGateways[].targets[].name).
   * Omit or leave empty to skip.
   */
  mcpEnvVars?: Record<string, string>;
}

/**
 * CDK Stack that deploys AgentCore infrastructure.
 *
 * This is a thin wrapper that instantiates L3 constructs.
 * All resource logic and outputs are contained within the L3 constructs.
 */
export class AgentCoreStack extends Stack {
  /** The AgentCore application containing all agent environments */
  public readonly application: AgentCoreApplication;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);

    const { spec, mcpSpec, credentials, harnesses, mcpEnvVars } = props;

    // Create AgentCoreApplication with all agents and harness roles
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const appProps: Record<string, unknown> = { spec };
    if (harnesses?.length) {
      appProps.harnesses = harnesses;
    }
    this.application = new AgentCoreApplication(this, 'Application', appProps as any);

    // Create AgentCoreMcp if there are gateways configured
    if (mcpSpec?.agentCoreGateways && mcpSpec.agentCoreGateways.length > 0) {
      const mcp = new AgentCoreMcp(this, 'Mcp', {
        projectName: spec.name,
        mcpSpec,
        agentCoreApplication: this.application,
        credentials,
        projectTags: spec.tags,
      });

      // Apply DB credentials (and other env vars) to gateway compute runtimes.
      // The agentCoreGateways schema does not expose envVars for compute.runtime,
      // but AgentCoreRuntime.addEnvironmentVariable() lets us inject them after
      // the construct is created. mcp.runtimes is keyed by gateway target name.
      if (mcpEnvVars && Object.keys(mcpEnvVars).length > 0) {
        for (const [targetName, runtime] of mcp.runtimes) {
          for (const [key, value] of Object.entries(mcpEnvVars)) {
            runtime.addEnvironmentVariable(key, value);
          }
          console.log(`Applied ${Object.keys(mcpEnvVars).length} env vars to MCP runtime: ${targetName}`);
        }
      }

      // Fix empty Description on GatewayTarget resources.
      // CfnGatewayTarget requires Description with minLength=1, but the CDK
      // generates Description: "" when no toolDefinitions are provided.
      // We override each gateway target to use a non-empty description.
      //
      // Also fix invalid ProtocolConfiguration.Mcp.SearchType: "NONE" on the Gateway.
      // The CFN schema only accepts "SEMANTIC" as a valid SearchType value.
      // When enableSemanticSearch is false, ProtocolConfiguration must be omitted.
      for (const gateway of mcpSpec.agentCoreGateways) {
        // Fix Gateway ProtocolConfiguration (remove it when not using semantic search)
        if (!gateway.enableSemanticSearch) {
          try {
            const gatewayNodeId = toPascalId('Gateway', gateway.name);
            const cfnGateway = mcp.node.findChild(gatewayNodeId).node.findChild('Resource') as bedrockagentcore.CfnGateway;
            if (cfnGateway) {
              cfnGateway.addPropertyDeletionOverride('ProtocolConfiguration');
              console.log(`Removed invalid ProtocolConfiguration from Gateway: ${gateway.name}`);
            }
          } catch (e) {
            console.warn(`Could not fix ProtocolConfiguration for ${gateway.name}: ${e}`);
          }
        }

        for (const target of gateway.targets) {
          try {
            const gatewayNodeId = toPascalId('Gateway', gateway.name);
            const targetNodeId = toPascalId('Target', target.name);
            const targetConstruct = mcp.node.findChild(gatewayNodeId).node.findChild(targetNodeId) as bedrockagentcore.CfnGatewayTarget;
            if (targetConstruct) {
              const desc = `${target.name} gateway target`;
              targetConstruct.addPropertyOverride('Description', desc);
              console.log(`Fixed empty Description on GatewayTarget: ${gateway.name}/${target.name} => "${desc}"`);

              // For AgentCore Runtime targets (mcpServer with compute.host=AgentCoreRuntime),
              // do NOT specify CredentialProviderConfigurations. The Gateway authenticates
              // to internal AgentCore Runtimes automatically using its IAM role via the
              // service-internal invocations endpoint. Adding explicit CredentialProviderConfigurations
              // causes "Authorization error when sending message" because the Gateway applies
              // an additional credential flow at the MCP message level that is not expected.
              // The CDK construct's native iamRoleFallback=false for mcpServer is correct.
              targetConstruct.addPropertyDeletionOverride('CredentialProviderConfigurations');
              console.log(`Removed CredentialProviderConfigurations from GatewayTarget: ${gateway.name}/${target.name}`);
            }
          } catch (e) {
            console.warn(`Could not fix Description for ${gateway.name}/${target.name}: ${e}`);
          }
        }
      }
    } // end if (mcpSpec?.agentCoreGateways)

    // Remove opentelemetry-instrument from NokeMCP EntryPoint to speed up cold start.
    // The default EntryPoint ["opentelemetry-instrument", "main.py"] adds 30s+ of startup
    // time due to auto-instrumentation of all packages. Use just ["main.py"] instead.
    // Also injects the NokeMCP VPC security group (CDK schema reads subnets but drops securityGroups).
    try {
      const nokeMcpRuntime = this.application.node.findChild('AgentNokeMCP')
        .node.findChild('Runtime').node.defaultChild as bedrockagentcore.CfnRuntime;
      if (nokeMcpRuntime) {
        nokeMcpRuntime.addPropertyOverride(
          'AgentRuntimeArtifact.CodeConfiguration.EntryPoint', ['main.py']
        );
        // Force description change to trigger CloudFormation runtime update
        nokeMcpRuntime.addPropertyOverride(
          'Description', 'AgentCore Runtime: NokeAgent_NokeMCP (vpc-v1)'
        );
        // CDK drops securityGroups from networkConfig — inject directly via L1 override.
        nokeMcpRuntime.addPropertyOverride(
          'NetworkConfiguration.NetworkModeConfig.SecurityGroups',
          ['sg-0bbed7d400a9db657']
        );
        console.log('Removed opentelemetry-instrument from NokeMCP EntryPoint');
        console.log('Injected NokeMCP VPC security group sg-0bbed7d400a9db657');
      }
    } catch (e) {
      console.warn(`Could not override NokeMCP EntryPoint: ${e}`);
    }

    // Grant the NokeAgent execution role permission to invoke the NokeMCP runtime.
    // Uses AgentCoreRuntime.grantInvoke() which adds InvokeAgentRuntime + InvokeAgentRuntimeForUser
    // to the NokeAgent role scoped to the NokeMCP runtime ARN.
    try {
      const nokeAgentRuntime = this.application.node.findChild('AgentNokeAgent')
        .node.findChild('Runtime') as AgentCoreRuntime;
      const nokeMcpRuntime = this.application.node.findChild('AgentNokeMCP')
        .node.findChild('Runtime') as AgentCoreRuntime;
      nokeMcpRuntime.grantInvoke(nokeAgentRuntime.role);
      console.log('Granted NokeAgent role InvokeAgentRuntime on NokeMCP runtime via grantInvoke()');
    } catch (e) {
      console.warn(`Could not grant InvokeAgentRuntime permission: ${e}`);
    }

    // Stack-level output
    new CfnOutput(this, 'StackNameOutput', {
      description: 'Name of the CloudFormation Stack',
      value: this.stackName,
    });

    // ── Lambda chat proxy + HTTP API Gateway ─────────────────────────────────
    // Exposes a public HTTPS endpoint: POST /chat
    // Lambda calls invoke_agent_runtime → NokeAgent → NokeMCP → RDS
    // boto3 SigV4 signing is handled automatically by the Lambda execution role.
    try {
      // Get NokeAgent CfnRuntime to read its ARN dynamically
      const nokeAgentCfnRuntime = this.application.node.findChild('AgentNokeAgent')
        .node.findChild('Runtime').node.defaultChild as bedrockagentcore.CfnRuntime;

      // Lambda function — Python 3.12, boto3 pre-installed, no bundling needed
      const chatLambda = new lambda.Function(this, 'ChatProxyLambda', {
        functionName: 'NokeAgent-ChatProxy',
        runtime:      lambda.Runtime.PYTHON_3_12,
        handler:      'chat_proxy.handler',
        // lambda/ is at repo root. __dirname at runtime = agentcore/cdk/dist/lib/
        // so ../../../../lambda resolves to fm-chat/lambda/
        code:         lambda.Code.fromAsset(path.join(__dirname, '..', '..', '..', '..', 'lambda')),
        timeout:      Duration.seconds(90),
        memorySize:   256,
        environment: {
          NOKEAGENT_RUNTIME_ARN: nokeAgentCfnRuntime.attrAgentRuntimeArn,
        },
        description: 'Public chat proxy: API Gateway → Lambda → NokeAgent AgentCore runtime',
      });

      // Grant Lambda role permission to invoke NokeAgent runtime
      chatLambda.addToRolePolicy(new iam.PolicyStatement({
        sid:       'InvokeNokeAgentRuntime',
        actions:   ['bedrock-agentcore:InvokeAgentRuntime'],
        resources: [nokeAgentCfnRuntime.attrAgentRuntimeArn],
      }));

      // HTTP API Gateway with CORS
      const httpApi = new apigwv2.HttpApi(this, 'NokeChatHttpApi', {
        apiName: 'noke-agent-chat-api',
        corsPreflight: {
          allowHeaders: ['Content-Type', 'Authorization'],
          allowMethods: [apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
          allowOrigins: ['*'],
        },
      });

      httpApi.addRoutes({
        path:        '/chat',
        methods:     [apigwv2.HttpMethod.POST],
        integration: new apigwv2int.HttpLambdaIntegration('ChatLambdaIntegration', chatLambda),
      });

      new CfnOutput(this, 'ChatApiUrl', {
        description: 'Public chat endpoint — POST /chat with {"message":"..."}',
        value:       `${httpApi.apiEndpoint}/chat`,
      });

      new CfnOutput(this, 'ChatLambdaArn', {
        description: 'Lambda ARN for NokeAgent chat proxy',
        value:       chatLambda.functionArn,
      });

      console.log('Created Lambda ChatProxy + HTTP API Gateway /chat route');
    } catch (e) {
      console.warn(`Could not create Lambda/APIGW resources: ${e}`);
    }
  }
}
