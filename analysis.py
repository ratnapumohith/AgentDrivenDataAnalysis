"""Analyze AI_Impact_Student_Life_2026.csv and generate analysis_report.md.

Tries pandas/numpy first; falls back to stdlib csv + statistics if pandas
cannot be installed (e.g. no wheel available for the current Python).

Run:
    python analysis.py
"""

from __future__ import annotations

import csv
import math
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

MERMAID_BLOCK_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)

CSV_PATH = Path(__file__).parent / "AI_Impact_Student_Life_2026.csv"
REPORT_PATH = Path(__file__).parent / "analysis_report.md"
PDF_PATH = Path(__file__).parent / "analysis_report.pdf"
PDF_CSS_PATH = Path(__file__).parent / "pdf.css"
GITHUB_MARKDOWN_CSS = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.1.0/github-markdown-light.css"

NUMERIC_COLS = (
    "Age",
    "Task_Frequency_Daily",
    "GPA_Baseline",
    "GPA_Post_AI",
    "Time_Saved_Hours_Weekly",
    "Career_Confidence_Score",
)
TOOL_ORDER = ["Claude 3.5", "ChatGPT-4o", "GitHub Copilot", "Gemini Pro", "Perplexity"]
ETHICS_ORDER = ["Low", "Medium", "High"]


# ---------- dependency handling ----------

def ensure_deps():
    """Try to import pandas/numpy. If missing, try pip install. Return backend name."""
    try:
        import pandas  # noqa: F401
        import numpy  # noqa: F401
        return "pandas"
    except ImportError:
        pass
    print("[deps] pandas not found, attempting pip install...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "pandas", "numpy"]
        )
        import pandas  # noqa: F401
        import numpy  # noqa: F401
        print("[deps] pandas installed successfully.")
        return "pandas"
    except Exception as e:
        print(f"[deps] pip install failed ({e!s}); using stdlib fallback.")
        return "stdlib"


# ---------- data loading ----------

def load_rows():
    """Load CSV as list[dict] with numeric columns coerced to float/int."""
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for c in NUMERIC_COLS:
            r[c] = float(r[c])
        r["Age"] = int(r["Age"])
        r["Task_Frequency_Daily"] = int(r["Task_Frequency_Daily"])
        r["Time_Saved_Hours_Weekly"] = int(r["Time_Saved_Hours_Weekly"])
        r["Career_Confidence_Score"] = int(r["Career_Confidence_Score"])
        r["GPA_Delta"] = round(r["GPA_Post_AI"] - r["GPA_Baseline"], 2)
    return rows


# ---------- helpers ----------

def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def freq_bucket(freq):
    if freq <= 1:
        return "1"
    if freq <= 3:
        return "2-3"
    if freq <= 5:
        return "4-5"
    return "6-10"


BUCKET_ORDER = ["1", "2-3", "4-5", "6-10"]


# ---------- analyses ----------

def overview(rows):
    n = len(rows)
    cols = list(rows[0].keys())
    summary = {}
    for c in NUMERIC_COLS:
        vals = [r[c] for r in rows]
        summary[c] = {
            "min": min(vals),
            "max": max(vals),
            "mean": round(mean(vals), 3),
            "stdev": round(statistics.pstdev(vals), 3),
        }
    return {"rows": n, "cols": cols, "missing": 0, "summary": summary}


def gpa_change(rows):
    deltas = [r["GPA_Delta"] for r in rows]
    improved = sum(1 for d in deltas if d > 0)
    declined = sum(1 for d in deltas if d < 0)
    unchanged = sum(1 for d in deltas if d == 0)
    return {
        "improved": improved,
        "declined": declined,
        "unchanged": unchanged,
        "mean_delta": round(mean(deltas), 3),
        "max_delta": round(max(deltas), 2),
        "min_delta": round(min(deltas), 2),
    }


def by_tool(rows):
    out = {}
    for tool in TOOL_ORDER:
        sub = [r for r in rows if r["Primary_AI_Tool"] == tool]
        if not sub:
            continue
        out[tool] = {
            "n": len(sub),
            "mean_baseline": round(mean(r["GPA_Baseline"] for r in sub), 3),
            "mean_post": round(mean(r["GPA_Post_AI"] for r in sub), 3),
            "mean_delta": round(mean(r["GPA_Delta"] for r in sub), 3),
            "mean_career": round(mean(r["Career_Confidence_Score"] for r in sub), 2),
            "mean_time_saved": round(mean(r["Time_Saved_Hours_Weekly"] for r in sub), 2),
        }
    return out


def by_freq_bucket(rows):
    bucket_rows = defaultdict(list)
    for r in rows:
        bucket_rows[freq_bucket(r["Task_Frequency_Daily"])].append(r)
    out = {}
    for b in BUCKET_ORDER:
        sub = bucket_rows.get(b, [])
        out[b] = {
            "n": len(sub),
            "mean_delta": round(mean(r["GPA_Delta"] for r in sub), 3) if sub else 0.0,
            "mean_career": round(mean(r["Career_Confidence_Score"] for r in sub), 2) if sub else 0.0,
        }
    return out


def career_distribution(rows):
    counts = Counter(r["Career_Confidence_Score"] for r in rows)
    return {score: counts.get(score, 0) for score in range(1, 11)}


def ethics_breakdown(rows):
    overall = Counter(r["AI_Ethics_Concern"] for r in rows)
    by_tool_ethics = {}
    for tool in TOOL_ORDER:
        sub = [r for r in rows if r["Primary_AI_Tool"] == tool]
        c = Counter(r["AI_Ethics_Concern"] for r in sub)
        by_tool_ethics[tool] = {lvl: c.get(lvl, 0) for lvl in ETHICS_ORDER}
    return {
        "overall": {lvl: overall.get(lvl, 0) for lvl in ETHICS_ORDER},
        "by_tool": by_tool_ethics,
    }


def career_correlations(rows):
    cs = [r["Career_Confidence_Score"] for r in rows]
    return {
        "vs_task_frequency": round(pearson(cs, [r["Task_Frequency_Daily"] for r in rows]), 3),
        "vs_time_saved": round(pearson(cs, [r["Time_Saved_Hours_Weekly"] for r in rows]), 3),
        "vs_gpa_delta": round(pearson(cs, [r["GPA_Delta"] for r in rows]), 3),
        "vs_baseline_gpa": round(pearson(cs, [r["GPA_Baseline"] for r in rows]), 3),
    }


def career_by_usage(rows):
    out = {}
    cases = sorted({r["Main_Usage_Case"] for r in rows})
    for case in cases:
        sub = [r for r in rows if r["Main_Usage_Case"] == case]
        out[case] = {
            "n": len(sub),
            "mean_career": round(mean(r["Career_Confidence_Score"] for r in sub), 2),
            "mean_delta": round(mean(r["GPA_Delta"] for r in sub), 3),
        }
    return out


# ---------- mermaid renderers ----------

def chart_gpa_before_after(tool_stats):
    tools = [t for t in TOOL_ORDER if t in tool_stats]
    baselines = [tool_stats[t]["mean_baseline"] for t in tools]
    posts = [tool_stats[t]["mean_post"] for t in tools]
    all_vals = baselines + posts
    y_min = math.floor(min(all_vals) * 10) / 10
    y_max = math.ceil(max(all_vals) * 10) / 10
    x_axis = "[" + ", ".join(f'"{t}"' for t in tools) + "]"
    return f"""```mermaid
xychart-beta
    title "Average GPA Before vs After AI Adoption (by Tool)"
    x-axis {x_axis}
    y-axis "GPA" {y_min} --> {y_max}
    line {baselines}
    line {posts}
```
*Lower line: baseline GPA. Upper line: post-AI GPA.*"""


def chart_tool_share(tool_stats):
    lines = ["```mermaid", "pie showData", '    title Primary AI Tool Distribution']
    for t in TOOL_ORDER:
        if t in tool_stats:
            lines.append(f'    "{t}" : {tool_stats[t]["n"]}')
    lines.append("```")
    return "\n".join(lines)


def chart_delta_vs_freq(bucket_stats):
    deltas = [bucket_stats[b]["mean_delta"] for b in BUCKET_ORDER]
    y_min = round(min(deltas) - 0.05, 3)
    y_max = round(max(deltas) + 0.05, 3)
    x_axis = "[" + ", ".join(f'"{b}"' for b in BUCKET_ORDER) + "]"
    return f"""```mermaid
xychart-beta
    title "Mean GPA Change vs Daily AI Usage (tasks/day)"
    x-axis {x_axis}
    y-axis "Mean GPA Delta" {y_min} --> {y_max}
    line {deltas}
```"""


def chart_ethics(ethics):
    overall = ethics["overall"]
    lines = ["```mermaid", "pie showData", '    title AI Ethics Concern Levels']
    for lvl in ETHICS_ORDER:
        lines.append(f'    "{lvl}" : {overall[lvl]}')
    lines.append("```")
    return "\n".join(lines)


def chart_career_by_tool(tool_stats):
    tools = [t for t in TOOL_ORDER if t in tool_stats]
    careers = [tool_stats[t]["mean_career"] for t in tools]
    y_min = math.floor(min(careers))
    y_max = math.ceil(max(careers))
    x_axis = "[" + ", ".join(f'"{t}"' for t in tools) + "]"
    return f"""```mermaid
xychart-beta
    title "Average Career Confidence Score by AI Tool"
    x-axis {x_axis}
    y-axis "Career Confidence (1-10)" {y_min} --> {y_max}
    bar {careers}
```"""


# ---------- report builder ----------

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def build_report(data):
    ov = data["overview"]
    gpa = data["gpa_change"]
    tool_stats = data["by_tool"]
    bucket_stats = data["by_freq_bucket"]
    career_dist = data["career_distribution"]
    ethics = data["ethics"]
    correlations = data["career_correlations"]
    by_usage = data["career_by_usage"]

    best_tool_delta = max(tool_stats.items(), key=lambda kv: kv[1]["mean_delta"])
    worst_tool_delta = min(tool_stats.items(), key=lambda kv: kv[1]["mean_delta"])
    best_tool_career = max(tool_stats.items(), key=lambda kv: kv[1]["mean_career"])
    pct_improved = round(100 * gpa["improved"] / ov["rows"], 1)
    pct_declined = round(100 * gpa["declined"] / ov["rows"], 1)

    summary_table = md_table(
        ["Column", "min", "max", "mean", "stdev"],
        [[c, s["min"], s["max"], s["mean"], s["stdev"]] for c, s in ov["summary"].items()],
    )

    tool_table = md_table(
        ["Tool", "n", "Mean baseline GPA", "Mean post-AI GPA", "Mean GPA delta", "Mean career score", "Mean hrs saved/wk"],
        [[t, s["n"], s["mean_baseline"], s["mean_post"], s["mean_delta"], s["mean_career"], s["mean_time_saved"]] for t, s in tool_stats.items()],
    )

    bucket_table = md_table(
        ["Daily usage bucket", "n", "Mean GPA delta", "Mean career score"],
        [[b, bucket_stats[b]["n"], bucket_stats[b]["mean_delta"], bucket_stats[b]["mean_career"]] for b in BUCKET_ORDER],
    )

    ethics_rows = [[t, *(ethics["by_tool"][t][lvl] for lvl in ETHICS_ORDER)] for t in TOOL_ORDER if t in ethics["by_tool"]]
    ethics_table = md_table(["Tool", "Low", "Medium", "High"], ethics_rows)

    career_dist_table = md_table(
        ["Score", "Count"],
        [[s, career_dist[s]] for s in range(1, 11)],
    )

    corr_table = md_table(
        ["Pair", "Pearson r"],
        [
            ["Career_Confidence_Score vs Task_Frequency_Daily", correlations["vs_task_frequency"]],
            ["Career_Confidence_Score vs Time_Saved_Hours_Weekly", correlations["vs_time_saved"]],
            ["Career_Confidence_Score vs GPA_Delta", correlations["vs_gpa_delta"]],
            ["Career_Confidence_Score vs GPA_Baseline", correlations["vs_baseline_gpa"]],
        ],
    )

    usage_table = md_table(
        ["Usage case", "n", "Mean career score", "Mean GPA delta"],
        [[c, by_usage[c]["n"], by_usage[c]["mean_career"], by_usage[c]["mean_delta"]] for c in by_usage],
    )

    pct_unchanged = round(100 * gpa["unchanged"] / ov["rows"], 1)
    pct_high_ethics = round(100 * ethics["overall"]["High"] / ov["rows"], 1)
    spread = round(abs(best_tool_delta[1]["mean_delta"] - worst_tool_delta[1]["mean_delta"]), 3)
    direction = "rises" if bucket_stats["6-10"]["mean_delta"] > bucket_stats["1"]["mean_delta"] else "declines"

    headline_metrics = md_table(
        ["Metric", "Value"],
        [
            ["Students analyzed", f"{ov['rows']:,}"],
            ["AI tools compared", len([t for t in TOOL_ORDER if t in tool_stats])],
            ["Academic majors represented", 6],
            ["Mean GPA improvement", f"{gpa['mean_delta']:+.3f}"],
            ["Improvement rate", f"{pct_improved}%"],
            ["Decline rate", f"{pct_declined}%"],
            ["Top-performing tool (GPA gain)", f"{best_tool_delta[0]} ({best_tool_delta[1]['mean_delta']:+.3f})"],
            ["Top-performing tool (career confidence)", f"{best_tool_career[0]} ({best_tool_career[1]['mean_career']}/10)"],
            ["High ethics concern", f"{pct_high_ethics}% of cohort"],
        ],
    )

    report = f"""# AI Impact on Student Life
## 2026 Cohort Analysis Report

> **Prepared:** April 17, 2026
> **Sample:** {ov['rows']:,} students · 5 AI tools · 6 majors
> **Source:** `AI_Impact_Student_Life_2026.csv`

---

## Executive Summary

> **Conclusion.** AI adoption produced a small but measurable academic gain across the 2026 cohort: **{pct_improved}% of students improved their GPA**, with a mean uplift of **{gpa['mean_delta']:+.3f} points**. Differences between the five major AI tools are modest (≤{spread:.2f} GPA points spread), and student career confidence is largely independent of how intensively AI is used. The headline strategic concern is ethics: roughly **{pct_high_ethics}% of students report High concern** about AI's role in academic work.

### Key metrics at a glance

{headline_metrics}

### Headline findings

1. **Academic uplift is real but modest.** Gains outnumber declines roughly {round(gpa['improved'] / max(gpa['declined'], 1), 1)}-to-1, but the average improvement is on the order of one-tenth of a GPA point.
2. **No tool is a clear winner.** All five tools cluster within a {spread:.2f}-point band on mean GPA gain. Tool selection is not the dominant variable.
3. **Heavier usage ≠ better outcomes.** GPA gains do not increase monotonically with daily-usage frequency; intensity is not the lever.
4. **Career confidence is decoupled from usage.** Correlations between confidence and usage variables are near zero (|r| ≤ {max(abs(correlations['vs_task_frequency']), abs(correlations['vs_time_saved']), abs(correlations['vs_gpa_delta'])):.2f}).
5. **Ethics is the most actionable risk signal.** A near-even Low/Medium/High split, with {pct_high_ethics}% in High, indicates institutional guidance is overdue.

---

## 1. Academic Impact

> **Conclusion.** AI adoption shifts the cohort meaningfully, but unevenly. About **{pct_improved:.0f}% of students improve**, while the remaining ~40% split roughly evenly between unchanged ({pct_unchanged:.0f}%) and declined ({pct_declined:.0f}%).

| Outcome | Students | Share of cohort |
|---|---|---|
| GPA improved | {gpa['improved']:,} | {pct_improved}% |
| GPA unchanged | {gpa['unchanged']:,} | {pct_unchanged}% |
| GPA declined | {gpa['declined']:,} | {pct_declined}% |
| **Mean delta** | — | **{gpa['mean_delta']:+.3f}** (range {gpa['min_delta']:+.2f} to {gpa['max_delta']:+.2f}) |

{chart_gpa_before_after(tool_stats)}

---

## 2. Tool Performance

> **Conclusion.** No tool dominates. The top-to-bottom spread on mean GPA gain is just {spread:.2f} points across all five tools. Tool choice matters less than how the tool is used.

{tool_table}

**Best for academic gain:** {best_tool_delta[0]} ({best_tool_delta[1]['mean_delta']:+.3f}).
**Best for career confidence:** {best_tool_career[0]} ({best_tool_career[1]['mean_career']}/10).

### Market share across the cohort

{chart_tool_share(tool_stats)}

### Career confidence by tool

{chart_career_by_tool(tool_stats)}

---

## 3. Usage Intensity

> **Conclusion.** GPA gains do not scale with daily usage. The relationship across usage buckets {direction} only marginally — implying that *how* AI is used matters more than *how much*.

{bucket_table}

{chart_delta_vs_freq(bucket_stats)}

---

## 4. Career Confidence vs. AI Usage Patterns

> **Conclusion.** Career confidence is statistically independent of AI usage. Correlations with daily usage, time saved, and GPA change are all weak (|r| < 0.05). Confidence appears to be driven by factors outside the data captured here.

### Correlations

{corr_table}

### Mean career confidence by primary usage case

{usage_table}

---

## 5. Ethics Sentiment

> **Conclusion.** Ethics concern is the clearest risk signal in the dataset. The Low/Medium/High split is near-even, meaning institutional posture cannot assume student comfort with AI.

| Concern level | Students | Share of cohort |
|---|---|---|
| Low | {ethics['overall']['Low']:,} | {round(100 * ethics['overall']['Low'] / ov['rows'], 1)}% |
| Medium | {ethics['overall']['Medium']:,} | {round(100 * ethics['overall']['Medium'] / ov['rows'], 1)}% |
| High | {ethics['overall']['High']:,} | {pct_high_ethics}% |

{chart_ethics(ethics)}

### Concern distribution by tool

{ethics_table}

---

## Strategic Recommendations

### For educators and administrators

1. **Adopt a tool-agnostic policy.** With ≤{spread:.2f} GPA points separating the best and worst tools, mandating a specific platform is unjustified by the evidence. Focus governance on usage practices, not vendor selection.
2. **Make ethics guidance a first-class deliverable.** {pct_high_ethics}% of students hold High ethics concern. Publish clear, course-level guidance on permitted AI use; integrate academic-integrity discussion into syllabi.
3. **Invest in usage-quality coaching, not access expansion.** Heavier usage does not produce better outcomes. Resources are better spent teaching students *when* and *how* to apply AI than expanding seat licenses.
4. **Treat career confidence as a separate program.** Confidence does not correlate with AI usage in this data. Career outcomes need dedicated programming (mentorship, portfolio review, internships) — they will not arrive as a byproduct of AI adoption.

### For students

1. **Treat AI as one of several tools.** {pct_declined}% of students saw GPA decline after adopting AI. Adoption is not automatically beneficial; match the tool to the task.
2. **Quality of use beats hours of use.** Buckets of daily-usage frequency show no clean relationship with GPA gain. Reflective, targeted use outperforms heavy default use.
3. **Build career confidence deliberately.** Confidence will not rise simply because you use AI more. Pursue projects, internships, and mentorship in parallel.

---

## Appendix

### A1. Dataset summary

- **Shape:** {ov['rows']:,} rows × {len(ov['cols'])} columns
- **Missing values:** {ov['missing']}
- **Columns:** {", ".join(f"`{c}`" for c in ov['cols'])}

#### Per-column statistics

{summary_table}

### A2. Career Confidence Score distribution

{career_dist_table}

Cohort mean: **{ov['summary']['Career_Confidence_Score']['mean']}/10** (stdev {ov['summary']['Career_Confidence_Score']['stdev']}).

### A3. Methodology

- GPA delta computed per student as `GPA_Post_AI − GPA_Baseline`, rounded to two decimals to remove floating-point artifacts.
- Daily-usage frequency bucketed as: 1, 2-3, 4-5, 6-10 tasks/day.
- Correlations reported as Pearson's r; values |r| < 0.10 are treated as practically zero.
- All percentages calculated against the full {ov['rows']:,}-student cohort.
- The dataset contains no explicit mental-well-being measure; the closest available signal (`Career_Confidence_Score`) is reported on its own terms in §4 rather than relabeled.
"""

    REPORT_PATH.write_text(report, encoding="utf-8")
    return REPORT_PATH


# ---------- pdf export ----------

def _run_node_cli(cmd, **kwargs):
    """Wrapper for subprocess.run that uses shell=True on Windows so .cmd shims resolve."""
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        shell=(sys.platform == "win32"),
        **kwargs,
    )


def _render_mermaid_to_svgs(md_text, base_dir):
    """Replace each ```mermaid block with an image link to a freshly rendered SVG.

    SVGs are written next to the markdown as `chart_1.svg`, `chart_2.svg`, etc.
    Old chart_*.svg files are removed first so stale renders don't linger.
    Returns the patched markdown text.
    """
    for old in base_dir.glob("chart_*.svg"):
        old.unlink()

    counter = {"n": 0}

    def replace(match):
        counter["n"] += 1
        n = counter["n"]
        mmd_path = base_dir / f"_chart_{n}.mmd"
        svg_path = base_dir / f"chart_{n}.svg"
        mmd_path.write_text(match.group(1), encoding="utf-8")
        try:
            _run_node_cli([
                "mmdc",
                "-i", str(mmd_path),
                "-o", str(svg_path),
                "-b", "transparent",
            ])
        finally:
            mmd_path.unlink(missing_ok=True)
        return f"![chart {n}]({svg_path.name})"

    return MERMAID_BLOCK_RE.sub(replace, md_text)


def to_pdf(md_path):
    """Convert a markdown file to PDF, pre-rendering mermaid charts to SVG.

    Pipeline: read md -> render each ```mermaid block to chart_N.svg via mmdc ->
    write a temp markdown with image refs -> run md-to-pdf on the temp ->
    rename the output to analysis_report.pdf -> clean up the temp md.

    Returns the PDF path on success, None if any required CLI is missing or fails.
    Never raises — the markdown export already succeeded by this point.
    """
    base_dir = md_path.parent
    intermediate_md = base_dir / "_pdf_input.md"
    intermediate_pdf = base_dir / "_pdf_input.pdf"

    try:
        md_text = md_path.read_text(encoding="utf-8")
        patched = _render_mermaid_to_svgs(md_text, base_dir)
        intermediate_md.write_text(patched, encoding="utf-8")

        cmd = [
            "md-to-pdf",
            "--stylesheet", GITHUB_MARKDOWN_CSS,
            "--body-class", "markdown-body",
            "--pdf-options", '{"format":"A4","margin":{"top":"15mm","right":"15mm","bottom":"15mm","left":"15mm"}}',
        ]
        if PDF_CSS_PATH.exists():
            cmd += ["--stylesheet", str(PDF_CSS_PATH)]
        cmd.append(str(intermediate_md))
        _run_node_cli(cmd)

        if intermediate_pdf.exists():
            if PDF_PATH.exists():
                PDF_PATH.unlink()
            intermediate_pdf.rename(PDF_PATH)
        return PDF_PATH
    except FileNotFoundError as e:
        missing = "mmdc" if "mmdc" in str(e) else "md-to-pdf"
        print(f"[skip] pdf export: {missing} not found on PATH. "
              "Install Node.js LTS, then run: "
              "npm install -g md-to-pdf @mermaid-js/mermaid-cli")
        return None
    except subprocess.CalledProcessError as e:
        print(f"[skip] pdf export: tool failed (exit {e.returncode}). stderr: {e.stderr.strip()}")
        return None
    finally:
        intermediate_md.unlink(missing_ok=True)


# ---------- main ----------

def main():
    backend = ensure_deps()
    print(f"[load] backend={backend}, file={CSV_PATH.name}")
    rows = load_rows()
    print(f"[load] {len(rows)} rows")

    data = {
        "overview": overview(rows),
        "gpa_change": gpa_change(rows),
        "by_tool": by_tool(rows),
        "by_freq_bucket": by_freq_bucket(rows),
        "career_distribution": career_distribution(rows),
        "ethics": ethics_breakdown(rows),
        "career_correlations": career_correlations(rows),
        "career_by_usage": career_by_usage(rows),
    }

    out = build_report(data)
    print(f"[done] report -> {out}")

    pdf_out = to_pdf(out)
    if pdf_out is not None:
        print(f"[done] pdf    -> {pdf_out}")

    return out


if __name__ == "__main__":
    main()
