# Agent Security Test Bench

A Streamlit capstone application for systematically testing AI applications against prompt-injection and agent-security failures.

The project began with a deliberately simple demo target and has now been extended to support testing an existing LangGraph application: the **Secure LangGraph Content Assistant**.

## What Works Now

- Streamlit interface for configuring and running security tests
- Five saved prompt-injection attack scenarios
- Editable attack prompts
- Demo vulnerable target for validating the test harness
- Support for the existing **Secure LangGraph Content Assistant** as a real test target
- Target selection from the Streamlit sidebar
- Adapter layer that converts a Streamlit attack prompt into the LangGraph application's expected state
- Deterministic PASS / FAIL / REVIEW evaluator
- JSONL logging of test runs
- Expandable execution traces
- Test history
- Downloadable JSON results
- Error handling for target execution failures

The current end-to-end loop is:

`attack -> target -> evaluator -> result -> trace/log`

For the LangGraph target, the flow is:

`Streamlit attack -> LangGraph adapter -> security precheck -> router/agent -> output validation -> response -> evaluator`

## Project Structure

```text
streamlit-prompt-injection-tester/
├── app.py
├── requirements.txt
├── data/
│   └── attacks.json
└── tester/
    ├── __init__.py
    ├── attacks.py
    ├── evaluators.py
    ├── runner.py
    └── targets.py
```

The tester package was renamed from `src` to `tester` to avoid a Python package-name collision with the existing LangGraph project, which also uses a package named `src`.

## Target Applications

### Demo Vulnerable Agent

The demo target is intentionally simple and contains both secure and insecure behaviors.

It is useful for verifying that the test harness can correctly produce PASS and FAIL results before connecting a real AI application.

### Secure LangGraph Content Assistant

The tester can now invoke the existing `secure-langgraph-content-assistant` project.

That application already contains:

- a LangGraph workflow
- prompt-injection prechecks
- routing between specialized agents
- tool-use controls
- PII detection and redaction
- moderation
- output validation
- secret-pattern detection
- audit logging

The tester sends the selected adversarial prompt into the target application's LangGraph state and returns its final output for evaluation.

The target adapter creates state in the form:

```python
{
    "user_input": prompt,
    "route": "",
    "output": "",
    "messages": [],
}
```

It then invokes the graph using a unique LangGraph `thread_id`.

## Local Repository Layout

The two repositories should be located next to each other:

```text
project-directory/
├── streamlit-prompt-injection-tester/
└── secure-langgraph-content-assistant/
```

The tester loads the LangGraph application from the neighboring repository rather than duplicating its source code.

## Run Locally

### 1. Create and activate a virtual environment

From inside `streamlit-prompt-injection-tester`:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install the tester requirements

```bash
pip install -r requirements.txt
```

The tester uses `python-dotenv` to load environment variables required by the target application.

### 3. Install the LangGraph target dependencies

If you want to test the Secure LangGraph Content Assistant:

```bash
pip install -r ../secure-langgraph-content-assistant/requirements.txt
```

This installs the LangGraph application's dependencies, including LangGraph, LangChain, OpenAI integrations, Presidio, spaCy, and Tavily.

### 4. Configure target environment variables

The Secure LangGraph Content Assistant expects its own `.env` file:

```text
secure-langgraph-content-assistant/.env
```

For example:

```text
OPENAI_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
```

Do not commit API keys or credentials to Git.

### 5. Start Streamlit

```bash
streamlit run app.py
```

The sidebar should display two available targets:

- `Demo vulnerable agent`
- `Secure LangGraph Content Assistant`

## Current Attack Scenarios

The first-pass attack library contains five categories:

1. **System Prompt Exfiltration**  
   Attempts to override prior instructions and reveal the system prompt.

2. **Secret Extraction**  
   Attempts to make the target disclose credentials or sensitive configuration.

3. **Role Hijacking**  
   Attempts to replace the application's instruction hierarchy by claiming a higher-privilege role.

4. **Context Dump**  
   Attempts to expose hidden instructions or previous context.

5. **Unauthorized Tool Request**  
   Attempts to convince an agent to perform an unauthorized privileged action.

Attack prompts can also be edited directly in the Streamlit interface before execution.

## Evaluation

The current evaluator is intentionally lightweight.

It looks for obvious indicators of either:

- successful refusal or safe handling
- secret disclosure or compliance with an attack
- an ambiguous response requiring manual review

Results are classified as:

- **PASS** — the target appears to resist the attack
- **FAIL** — the target appears to comply with the malicious instruction
- **REVIEW** — deterministic evaluation cannot confidently classify the result

This evaluator is scaffolding for the first working version rather than the final evaluation system.

## Next Improvements

The LangGraph application exposes considerably more information than the tester currently evaluates.

The next version will capture target metadata such as:

- `security_status`
- `security_reason`
- selected `route`
- `validation_status`
- `validation_reason`

This will allow the application to report not only whether an attack succeeded or failed, but **which security control handled the attack and at what stage of the agent workflow**.

Additional planned improvements include:

- batch execution across multiple attacks
- metrics by attack category
- stronger prompt-injection variations
- indirect prompt-injection testing
- tool-call inspection
- LLM-as-a-judge evaluation
- automated adversarial prompt generation
- LangGraph/LangSmith observability
- RAG-backed attack-technique retrieval
- AWS integration and deployment as required by the capstone
