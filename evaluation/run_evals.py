"""
evaluation/run_evals.py

End-to-end evaluation harness for the Noke Smart Entry agent.

Flow:
  1. Load evalConfig.yaml  →  agent config  +  judge config
  2. Load test_cases.json  →  list of test scenarios
  3. Invoke the deployed AgentCore runtime for each test case
  4. Score each response with a separate LLM-as-a-Judge (Bedrock Converse API)
  5. Save JSON results  →  evaluation/results/<run_id>/results.json
  6. Generate HTML report  →  evaluation/results/<run_id>/report.html
     (optionally opens in browser automatically)

Usage:
  cd evaluation
  python run_evals.py
"""

import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone

import boto3
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────────────
# Config & test-case loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    path = os.path.join(SCRIPT_DIR, "evalConfig.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_test_cases() -> list[dict]:
    path = os.path.join(SCRIPT_DIR, "test_cases.json")
    with open(path, "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Agent invocation
# ─────────────────────────────────────────────────────────────────────────────

def _strip_thinking(text: str) -> str:
    return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def invoke_agent(cfg: dict, input_text: str, session_id: str) -> str:
    """Invoke the deployed AgentCore runtime and return the answer text."""
    agent_cfg = cfg["agent"]
    client = boto3.client("bedrock-agentcore", region_name=agent_cfg["region"])

    payload = json.dumps({
        "prompt":        input_text,
        "session_id":    session_id,
        "user_id":       agent_cfg.get("user_id", 1034747),
        "site_id":       agent_cfg.get("site_id"),
        "company_uuid":  agent_cfg.get("company_uuid"),
    }).encode()

    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agent_cfg["endpoint_arn"],
        qualifier=agent_cfg.get("qualifier", "DEFAULT"),
        payload=payload,
    )
    result = json.loads(resp["response"].read())

    answer = (
        result.get("answer")
        or result.get("result")
        or result.get("response")
        or str(result)
    )
    return _strip_thinking(str(answer))


# ─────────────────────────────────────────────────────────────────────────────
# LLM-as-a-Judge
# ─────────────────────────────────────────────────────────────────────────────

_JUDGE_SYSTEM = """\
You are an expert evaluator for an AI assistant that manages smart entry
systems (locks, units, and sites). You will receive a user question, the
agent's response, and an expected ground truth description.

Score the agent's response on three metrics, each from 0.0 to 1.0:

  CORRECTNESS  — Does the answer satisfy the intent described in the ground truth?
                 1.0 = fully correct, 0.5 = partially, 0.0 = wrong or missing
  HELPFULNESS  — Is the answer clear, concise, and useful to the end user?
                 1.0 = excellent, 0.5 = adequate, 0.0 = unhelpful or confusing
  FAITHFULNESS — Does the answer avoid hallucination or unsupported claims?
                 1.0 = fully grounded, 0.5 = minor speculation, 0.0 = fabricated

Respond ONLY with a valid JSON object — no markdown, no extra text:
{
  "CORRECTNESS":  <float 0.0-1.0>,
  "HELPFULNESS":  <float 0.0-1.0>,
  "FAITHFULNESS": <float 0.0-1.0>,
  "reasoning":    "<one sentence explanation>"
}\
"""


def judge_response(cfg: dict, question: str, agent_response: str, ground_truth: str) -> dict:
    """Call the judge LLM via Bedrock Converse and return a scores dict."""
    judge_cfg = cfg["judge"]
    bedrock = boto3.client("bedrock-runtime", region_name=judge_cfg["region"])

    # Prepend any custom instructions from config
    system_text = judge_cfg.get("instructions", "").strip()
    system_text = (system_text + "\n\n" + _JUDGE_SYSTEM) if system_text else _JUDGE_SYSTEM

    user_message = (
        f"Question: {question}\n\n"
        f"Agent Response: {agent_response}\n\n"
        f"Expected Ground Truth: {ground_truth}\n\n"
        "Please evaluate the agent's response."
    )

    response = bedrock.converse(
        modelId=judge_cfg["model_id"],
        system=[{"text": system_text}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        inferenceConfig={
            "temperature": judge_cfg.get("temperature", 0),
            "maxTokens":   512,
        },
    )

    raw = response["output"]["message"]["content"][0]["text"].strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.warning("Judge returned non-JSON output: %s", raw[:200])
    return {
        "CORRECTNESS":  0.0,
        "HELPFULNESS":  0.0,
        "FAITHFULNESS": 0.0,
        "reasoning":    raw,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

def compute_weighted_score(cfg: dict, scores: dict) -> float:
    total_weight = sum(m["weight"] for m in cfg["metrics"])
    weighted = sum(
        scores.get(m["name"], 0.0) * m["weight"]
        for m in cfg["metrics"]
    )
    return round(weighted / total_weight, 3) if total_weight else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Results persistence
# ─────────────────────────────────────────────────────────────────────────────

def save_results(cfg: dict, case_results: list[dict], run_id: str) -> str:
    results_dir = os.path.join(SCRIPT_DIR, cfg["output"]["results_dir"], run_id)
    os.makedirs(results_dir, exist_ok=True)

    metric_names = [m["name"] for m in cfg["metrics"]]
    n = len(case_results)

    summary = {
        "run_id":       run_id,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "agent_model":  cfg["agent"]["model_id"],
        "judge_model":  cfg["judge"]["model_id"],
        "total_cases":  n,
        "passed":       sum(
            1 for r in case_results
            if r["weighted_score"] >= cfg.get("pass_threshold", 0.7)
        ),
        "pass_threshold": cfg.get("pass_threshold", 0.7),
        "avg_scores": {
            name: round(sum(r["scores"].get(name, 0.0) for r in case_results) / n, 3)
            for name in metric_names
        },
        "avg_weighted": round(
            sum(r["weighted_score"] for r in case_results) / n, 3
        ),
        "results": case_results,
    }

    path = os.path.join(results_dir, "results.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)

    log.info("Results saved → %s", path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Main evaluation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation_suite() -> str:
    cfg        = load_config()
    test_cases = load_test_cases()
    run_id     = datetime.now().strftime("%Y%m%d_%H%M%S")

    log.info(
        "Starting evaluation run %s | %d test cases | agent=%s | judge=%s",
        run_id, len(test_cases),
        cfg["agent"]["model_id"],
        cfg["judge"]["model_id"],
    )

    case_results = []

    for tc in test_cases:
        scenario_id  = tc["scenarioId"]
        input_text   = tc["input"]
        ground_truth = tc.get("groundTruth", "")
        session_id   = f"eval-{uuid.uuid4().hex[:8]}"

        # ── Invoke agent ───────────────────────────────────────────────────
        log.info("[%s] → invoking agent: %r", scenario_id, input_text)
        try:
            agent_output = invoke_agent(cfg, input_text, session_id)
        except Exception as exc:
            log.error("[%s] Agent invocation failed: %s", scenario_id, exc)
            agent_output = f"ERROR: {exc}"

        # ── Judge response ─────────────────────────────────────────────────
        log.info("[%s] → judging response…", scenario_id)
        try:
            scores_raw = judge_response(cfg, input_text, agent_output, ground_truth)
        except Exception as exc:
            log.error("[%s] Judge failed: %s", scenario_id, exc)
            scores_raw = {
                "CORRECTNESS":  0.0,
                "HELPFULNESS":  0.0,
                "FAITHFULNESS": 0.0,
                "reasoning":    str(exc),
            }

        reasoning = scores_raw.pop("reasoning", "")
        scores    = {k: round(float(v), 3) for k, v in scores_raw.items()}
        weighted  = compute_weighted_score(cfg, scores)
        passed    = weighted >= cfg.get("pass_threshold", 0.7)

        case_result = {
            "scenario_id":    scenario_id,
            "intent":         tc.get("intent", ""),
            "tags":           tc.get("tags", []),
            "input":          input_text,
            "ground_truth":   ground_truth,
            "agent_output":   agent_output,
            "scores":         scores,
            "weighted_score": weighted,
            "passed":         passed,
            "reasoning":      reasoning,
            "session_id":     session_id,
        }
        case_results.append(case_result)

        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"\n{'─'*62}")
        print(f"  [{status}] {scenario_id}  (weighted={weighted})")
        print(f"  Input    : {input_text}")
        print(f"  Agent    : {agent_output[:200]}{'…' if len(agent_output) > 200 else ''}")
        print(f"  Scores   : {json.dumps(scores)}")
        print(f"  Reasoning: {reasoning}")

    # ── Persist and report ─────────────────────────────────────────────────
    results_path = save_results(cfg, case_results, run_id)

    if cfg["output"].get("html_report", True):
        # Import here so report.py can also be run standalone
        sys.path.insert(0, SCRIPT_DIR)
        from report import generate_report
        report_path = generate_report(
            results_path,
            open_browser=cfg["output"].get("open_browser", True),
        )
        print(f"\n  HTML report  → {report_path}")

    n      = len(case_results)
    passed = sum(1 for r in case_results if r["passed"])
    avg    = round(sum(r["weighted_score"] for r in case_results) / n, 3)

    print(f"\n{'='*62}")
    print(f"  EVALUATION COMPLETE  |  run_id: {run_id}")
    print(f"  Passed: {passed}/{n}   Avg weighted score: {avg}")
    print(f"  Results JSON → {results_path}")
    print(f"{'='*62}\n")

    return results_path


if __name__ == "__main__":
    run_evaluation_suite()
