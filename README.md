# Agent Security Test Bench

A first-pass Streamlit capstone app for systematically testing AI applications
against prompt-injection and agent-security failures.

## What works now

- Streamlit interface
- Five saved attack scenarios
- Demo target application
- Deterministic PASS / FAIL / REVIEW evaluator
- JSONL logging of test runs
- Expandable execution traces
- Downloadable JSON result for each run

The current end-to-end loop is:

`attack -> target -> evaluator -> result -> trace/log`

## Run locally

### 1. Create and activate a virtual environment, install requirements, and start Streamlit


```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

streamlit run app.py