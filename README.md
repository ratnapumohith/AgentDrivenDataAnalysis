# Agent-Driven Data Analysis

## About this project

This project was created to gain hands-on experience with **agent-driven data analysis** — using a coding agent (Claude Code) to perform end-to-end exploratory analysis on a real dataset, rather than writing every step of the pipeline by hand.

The goal was to learn how an AI agent collaborates on a typical data-analysis workflow: loading and inspecting a CSV, computing descriptive statistics, generating charts, and assembling a written report — and to develop the prompting, review, and iteration skills needed to direct that workflow effectively.

## What's in this repository

| File | Purpose |
|---|---|
| `AI_Impact_Student_Life_2026.csv` | The dataset — 1,500 students surveyed on AI tool usage and academic outcomes |
| `analysis.py` | Self-contained Python analysis script (with a stdlib fallback if pandas is unavailable) |
| `analysis_report.md` | Generated boardroom-style report with findings, recommendations, and 5 Mermaid charts |
| `analysis_report.pdf` | PDF version of the report (auto-generated alongside the markdown) |
| `pdf.css` | Print stylesheet used by `md-to-pdf` to keep headings glued to their content and prevent charts/tables from splitting across pages |
| `.gitignore` | Excludes Python bytecode caches and virtual environments from version control |

## How to run

```bash
python analysis.py
```

The script regenerates `analysis_report.md` from the CSV. Open the report in any Markdown viewer that supports Mermaid (e.g. GitHub, or VS Code with the Markdown Preview Mermaid Support extension) to see the charts rendered.

### Optional: PDF export

If [Node.js LTS](https://nodejs.org) and the `md-to-pdf` CLI are installed, the script will also produce `analysis_report.pdf` (with the Mermaid charts rendered as images, not code blocks).

One-time setup:

1. Install Node.js LTS from https://nodejs.org.
2. In a fresh **Command Prompt** terminal (not PowerShell — see note below), run:
   ```
   npm install -g md-to-pdf @mermaid-js/mermaid-cli
   ```
   - `md-to-pdf` is the markdown-to-PDF converter.
   - `@mermaid-js/mermaid-cli` provides the `mmdc` command, which the script uses to pre-render each Mermaid chart to an SVG before building the PDF — without it, the charts in the PDF would appear as raw code blocks.

> **PowerShell note:** PowerShell blocks running `npm.ps1` by default with a "running scripts is disabled" error. Easiest workaround is to use Command Prompt (`cmd`) instead. Alternatively, allow scripts for your user once with `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

If `md-to-pdf` isn't installed, the script still produces the markdown report and prints a `[skip] pdf export ...` notice instead of crashing.

## What I learned

- How to scope an analysis request precisely enough for an agent to act on it without over-asking
- How to recognize and correct mismatches between a vague prompt and the actual columns in a dataset
- How to iterate on output quality — pushing from a first-pass technical report to a presentation-ready boardroom document
- The limitations of declarative chart syntax (e.g. Mermaid `xychart-beta` cannot render grouped bars) and how to work around them
- That a real-world data-analysis pipeline often spans multiple ecosystems: the analysis itself runs in Python, but rendering the report to PDF (with charts as images, not code blocks) required reaching outside Python to the JavaScript world — installing Node.js and the npm-distributed `md-to-pdf` CLI, then orchestrating it from Python via `subprocess`
