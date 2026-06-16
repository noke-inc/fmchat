"""
evaluation/report.py

Generates a self-contained HTML evaluation report (with embedded Chart.js charts)
from a results.json file produced by run_evals.py.

Can be imported by run_evals.py OR run standalone:
  python report.py results/<run_id>/results.json
"""

import json
import os
import sys
import webbrowser
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Noke Agent Evaluation — {run_id}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f2f5;
      color: #1a1a2e;
    }}

    header {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
      color: #fff;
      padding: 28px 40px;
    }}
    header h1 {{ margin: 0 0 6px; font-size: 1.7rem; font-weight: 700; }}
    header p  {{ margin: 0; font-size: 0.88rem; opacity: .75; }}

    .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}

    /* ── Summary cards ── */
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      padding: 20px 18px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
    }}
    .card .value {{
      font-size: 2rem;
      font-weight: 700;
      line-height: 1.1;
    }}
    .card .label {{
      font-size: 0.78rem;
      color: #666;
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .card.pass  .value {{ color: #22c55e; }}
    .card.fail  .value {{ color: #ef4444; }}
    .card.score .value {{ color: #6366f1; }}
    .card.total .value {{ color: #0ea5e9; }}

    /* ── Section titles ── */
    h2 {{
      font-size: 1.1rem;
      font-weight: 600;
      margin: 32px 0 14px;
      color: #1a1a2e;
    }}

    /* ── Chart grid ── */
    .charts {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-bottom: 32px;
    }}
    @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}

    .chart-box {{
      background: #fff;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
    }}
    .chart-box h3 {{
      margin: 0 0 14px;
      font-size: 0.9rem;
      font-weight: 600;
      color: #555;
      text-transform: uppercase;
      letter-spacing: .05em;
    }}
    .chart-box canvas {{ max-height: 280px; }}

    /* ── Details table ── */
    .table-wrap {{
      background: #fff;
      border-radius: 12px;
      overflow-x: auto;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.86rem;
    }}
    thead th {{
      background: #1a1a2e;
      color: #fff;
      padding: 12px 14px;
      text-align: left;
      white-space: nowrap;
    }}
    tbody tr:nth-child(even) {{ background: #f9fafb; }}
    tbody tr:hover {{ background: #eef2ff; }}
    tbody td {{
      padding: 11px 14px;
      vertical-align: top;
      border-bottom: 1px solid #e5e7eb;
    }}
    .pill {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .pill.pass {{ background: #dcfce7; color: #15803d; }}
    .pill.fail {{ background: #fee2e2; color: #b91c1c; }}

    .score-bar {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .score-bar .bar {{
      height: 8px;
      border-radius: 4px;
      background: #6366f1;
      min-width: 2px;
    }}
    .score-bar .num {{ font-size: 0.82rem; color: #555; white-space: nowrap; }}

    .reasoning {{ font-style: italic; color: #555; font-size: 0.82rem; }}

    details summary {{
      cursor: pointer;
      color: #6366f1;
      font-size: 0.82rem;
      user-select: none;
    }}
    details p {{
      margin: 6px 0 0;
      white-space: pre-wrap;
      font-size: 0.82rem;
      color: #333;
    }}

    footer {{
      text-align: center;
      padding: 24px;
      font-size: 0.78rem;
      color: #999;
    }}
  </style>
</head>
<body>

<header>
  <h1>Noke Agent Evaluation Report</h1>
  <p>Run ID: {run_id} &nbsp;|&nbsp; {timestamp} &nbsp;|&nbsp; Agent model: {agent_model} &nbsp;|&nbsp; Judge model: {judge_model}</p>
</header>

<div class="container">

  <!-- ── Summary cards ── -->
  <div class="cards">
    <div class="card total">
      <div class="value">{total}</div>
      <div class="label">Test Cases</div>
    </div>
    <div class="card pass">
      <div class="value">{passed}</div>
      <div class="label">Passed (≥ {threshold})</div>
    </div>
    <div class="card fail">
      <div class="value">{failed}</div>
      <div class="label">Failed</div>
    </div>
    <div class="card score">
      <div class="value">{avg_weighted}</div>
      <div class="label">Avg Weighted Score</div>
    </div>
    {metric_cards}
  </div>

  <!-- ── Charts ── -->
  <h2>Score Charts</h2>
  <div class="charts">

    <div class="chart-box">
      <h3>Average Metric Scores</h3>
      <canvas id="avgChart"></canvas>
    </div>

    <div class="chart-box">
      <h3>Pass / Fail Split</h3>
      <canvas id="passChart"></canvas>
    </div>

    <div class="chart-box" style="grid-column: 1 / -1;">
      <h3>Weighted Score per Scenario</h3>
      <canvas id="perScenarioChart"></canvas>
    </div>

  </div>

  <!-- ── Detailed results table ── -->
  <h2>Detailed Results</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Intent</th>
          <th>Input</th>
          <th>Weighted</th>
          <th>C</th>
          <th>H</th>
          <th>F</th>
          <th>Status</th>
          <th>Agent Output</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>

</div>

<footer>Generated by Noke evaluation harness &mdash; {generated_at}</footer>

<script>
const PASS_COLOR  = "rgba( 34,197, 94, 0.8)";
const FAIL_COLOR  = "rgba(239, 68, 68, 0.8)";
const METRIC_COLORS = [
  "rgba( 99,102,241, 0.8)",
  "rgba( 14,165,233, 0.8)",
  "rgba(168, 85,247, 0.8)",
];

// ── 1. Average metric bar chart ──────────────────────────────────────────────
new Chart(document.getElementById("avgChart"), {{
  type: "bar",
  data: {{
    labels: {metric_labels_json},
    datasets: [{{
      label: "Average Score",
      data:  {avg_scores_json},
      backgroundColor: METRIC_COLORS,
      borderRadius: 6,
    }}],
  }},
  options: {{
    responsive: true,
    scales: {{
      y: {{ min: 0, max: 1, ticks: {{ stepSize: 0.2 }} }},
    }},
    plugins: {{ legend: {{ display: false }} }},
  }},
}});

// ── 2. Pass / Fail doughnut ───────────────────────────────────────────────────
new Chart(document.getElementById("passChart"), {{
  type: "doughnut",
  data: {{
    labels: ["Passed", "Failed"],
    datasets: [{{
      data: [{passed}, {failed}],
      backgroundColor: [PASS_COLOR, FAIL_COLOR],
      borderWidth: 0,
    }}],
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: "bottom" }},
    }},
    cutout: "60%",
  }},
}});

// ── 3. Per-scenario bar chart ─────────────────────────────────────────────────
new Chart(document.getElementById("perScenarioChart"), {{
  type: "bar",
  data: {{
    labels:   {scenario_labels_json},
    datasets: [{{
      label: "Weighted Score",
      data:  {scenario_scores_json},
      backgroundColor: {scenario_colors_json},
      borderRadius: 4,
    }}],
  }},
  options: {{
    responsive: true,
    scales: {{
      y: {{ min: 0, max: 1, ticks: {{ stepSize: 0.2 }} }},
    }},
    plugins: {{
      legend: {{ display: false }},
      annotation: {{
        annotations: {{
          threshold: {{
            type: "line",
            yMin: {threshold},
            yMax: {threshold},
            borderColor: "rgba(239,68,68,0.6)",
            borderWidth: 2,
            borderDash: [6, 4],
          }},
        }},
      }},
    }},
  }},
}});
</script>

</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_bar(value: float) -> str:
    pct = int(value * 100)
    return (
        f'<div class="score-bar">'
        f'<div class="bar" style="width:{pct}px"></div>'
        f'<span class="num">{value:.2f}</span>'
        f'</div>'
    )


def _build_rows(results: list[dict]) -> str:
    rows = []
    for r in results:
        scores  = r.get("scores", {})
        passed  = r.get("passed", False)
        pill    = '<span class="pill pass">PASS</span>' if passed else '<span class="pill fail">FAIL</span>'
        output  = r.get("agent_output", "")
        truncated = output[:200] + ("…" if len(output) > 200 else "")
        reasoning = r.get("reasoning", "")

        rows.append(
            f"<tr>"
            f"<td><strong>{r['scenario_id']}</strong></td>"
            f"<td>{r.get('intent','')}</td>"
            f"<td>{r['input']}</td>"
            f"<td>{_score_bar(r['weighted_score'])}</td>"
            f"<td>{scores.get('CORRECTNESS',0):.2f}</td>"
            f"<td>{scores.get('HELPFULNESS',0):.2f}</td>"
            f"<td>{scores.get('FAITHFULNESS',0):.2f}</td>"
            f"<td>{pill}</td>"
            f"<td>"
            f"  <details><summary>Show response</summary><p>{truncated}</p></details>"
            + (f'  <div class="reasoning">{reasoning}</div>' if reasoning else "")
            + f"</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _metric_cards(avg_scores: dict) -> str:
    card_colors = {"CORRECTNESS": "score", "HELPFULNESS": "pass", "FAITHFULNESS": "total"}
    cards = []
    for name, val in avg_scores.items():
        cls = card_colors.get(name, "score")
        cards.append(
            f'<div class="card {cls}">'
            f'<div class="value">{val:.2f}</div>'
            f'<div class="label">Avg {name.capitalize()}</div>'
            f'</div>'
        )
    return "\n".join(cards)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(results_json_path: str, open_browser: bool = True) -> str:
    """
    Build an HTML report from a results.json file.

    Parameters
    ----------
    results_json_path : str
        Absolute path to the results.json produced by run_evals.py.
    open_browser : bool
        If True, open the generated report in the default web browser.

    Returns
    -------
    str
        Absolute path to the generated report.html file.
    """
    with open(results_json_path, "r") as f:
        data = json.load(f)

    results       = data["results"]
    avg_scores    = data["avg_scores"]
    metric_labels = list(avg_scores.keys())
    threshold     = data.get("pass_threshold", 0.7)
    passed        = data["passed"]
    failed        = data["total_cases"] - passed

    scenario_labels = [r["scenario_id"] for r in results]
    scenario_scores = [r["weighted_score"] for r in results]
    scenario_colors = [
        "rgba(34,197,94,0.8)" if r["passed"] else "rgba(239,68,68,0.8)"
        for r in results
    ]

    ts = data.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    html = _HTML.format(
        run_id              = data["run_id"],
        timestamp           = ts,
        agent_model         = data.get("agent_model", "—"),
        judge_model         = data.get("judge_model", "—"),
        total               = data["total_cases"],
        passed              = passed,
        failed              = failed,
        threshold           = threshold,
        avg_weighted        = data["avg_weighted"],
        metric_cards        = _metric_cards(avg_scores),
        rows                = _build_rows(results),
        generated_at        = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        metric_labels_json  = json.dumps(metric_labels),
        avg_scores_json     = json.dumps([avg_scores[k] for k in metric_labels]),
        scenario_labels_json= json.dumps(scenario_labels),
        scenario_scores_json= json.dumps(scenario_scores),
        scenario_colors_json= json.dumps(scenario_colors),
    )

    report_dir  = os.path.dirname(results_json_path)
    report_path = os.path.join(report_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    if open_browser:
        webbrowser.open(f"file:///{report_path.replace(os.sep, '/')}")

    return report_path


# ─────────────────────────────────────────────────────────────────────────────
# Standalone entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find the most recent results.json automatically
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(script_dir, "results")
        candidates  = []
        if os.path.isdir(results_dir):
            for run_dir in os.listdir(results_dir):
                p = os.path.join(results_dir, run_dir, "results.json")
                if os.path.isfile(p):
                    candidates.append(p)
        if not candidates:
            print("Usage: python report.py <path/to/results.json>")
            sys.exit(1)
        results_path = sorted(candidates)[-1]   # most recent by name (YYYYMMDD_HHMMSS)
        print(f"Using most recent results: {results_path}")
    else:
        results_path = sys.argv[1]

    out = generate_report(results_path, open_browser=True)
    print(f"Report generated → {out}")
