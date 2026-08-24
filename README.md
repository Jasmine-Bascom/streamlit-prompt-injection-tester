# Agent Security Test Bench

A Streamlit capstone application for systematically testing AI applications against prompt-injection and agent-security failures.

The application supports both saved attacks and dynamically generated adversarial prompts grounded in a curated security knowledge base using Retrieval-Augmented Generation (RAG).

The primary real-world target is the **Secure LangGraph Content Assistant**.

## What Works Now

* Streamlit interface for configuring and running security tests
* Two attack modes:

  * saved attacks
  * RAG-generated attacks
* Five saved prompt-injection attack scenarios
* Editable adversarial prompts
* Demo vulnerable target for validating the test harness
* Integration with the existing **Secure LangGraph Content Assistant**
* Target selection from the Streamlit sidebar
* Adapter layer between Streamlit and the LangGraph target
* Capture of LangGraph security metadata
* Security-aware PASS / FAIL / REVIEW evaluation
* JSONL logging of test runs
* Test history
* Expandable execution traces
* Downloadable JSON results
* Error handling for target execution failures
* Curated prompt-injection attack knowledge base
* OpenAI embeddings for semantic retrieval
* Chroma vector store
* RAG-based adversarial prompt generation
* Display of retrieved attack techniques in the Streamlit UI
* RAG provenance stored with generated security tests
* Streamlit session-state handling for generated attacks

The saved-attack testing loop is:

`Saved Attack -> Target -> Security Controls -> Evaluator -> Result -> Trace/Log`

The RAG-generated attack loop is:

`Testing Goal -> Semantic Retrieval -> Attack Knowledge -> LLM Generation -> Editable Attack -> Target -> Evaluator -> Result`

## Project Structure

```text
streamlit-prompt-injection-tester/
├── app.py
├── requirements.txt
├── data/
│   ├── attacks.json
│   └── attack_knowledge.json
└── tester/
    ├── __init__.py
    ├── attacks.py
    ├── evaluators.py
    ├── rag.py
    ├── runner.py
    └── targets.py
```

The tester package is named `tester` rather than `src` because the existing LangGraph target also uses a Python package named `src`.

## Streamlit Interface

The Streamlit interface allows the user to select:

1. A target application
2. An attack source
3. An attack scenario or RAG attack category
4. A testing goal
5. The final adversarial prompt

Two target applications are currently available:

* `Demo vulnerable agent`
* `Secure LangGraph Content Assistant`

Two attack sources are available:

* `Saved Attack`
* `RAG-Generated Attack`

## Saved Attacks

The first attack mode uses predefined scenarios stored in:

```text
data/attacks.json
```

The current saved scenarios are:

### System Prompt Exfiltration

Attempts to expose hidden system instructions.

### Secret Extraction

Attempts to obtain credentials, secrets, or sensitive configuration.

### Role Hijacking

Attempts to assign the model a higher-privilege role and alter its instruction hierarchy.

### Context Dump

Attempts to expose hidden context or internal instructions.

### Unauthorized Tool Request

Attempts to cause an agent to invoke a privileged or unauthorized tool.

Saved prompts can be edited in Streamlit before they are sent to the target.

## RAG-Generated Attacks

The second attack mode uses Retrieval-Augmented Generation to create new adversarial prompts.

The user selects an attack category and provides a testing goal.

For example:

```text
Attack category:
Prompt Leakage

Testing goal:
Test whether the target can be coaxed into indirectly describing
its hidden system instructions.
```

The RAG system then:

1. Embeds the security-testing query.
2. Searches the prompt-injection knowledge base.
3. Retrieves the most semantically relevant attack techniques.
4. Supplies the retrieved techniques to an LLM.
5. Generates a new adversarial prompt.
6. Displays the generated prompt in Streamlit.
7. Allows the user to edit the prompt before testing.
8. Preserves the retrieved documents as test provenance.

The flow is:

```text
Attack Category
      +
Testing Goal
      ↓
Semantic Retrieval
      ↓
Relevant Security Techniques
      ↓
LLM Attack Generation
      ↓
Editable Adversarial Prompt
      ↓
Security Test
```

## Attack Knowledge Base

The RAG corpus is stored in:

```text
data/attack_knowledge.json
```

It currently contains descriptions of techniques including:

* direct instruction override
* role hijacking
* system prompt exfiltration
* secret extraction
* tool manipulation
* indirect prompt injection
* obfuscated prompt injection
* multi-turn manipulation

These entries are converted into LangChain `Document` objects and embedded for semantic retrieval.

## Vector Retrieval

The RAG implementation is contained in:

```text
tester/rag.py
```

It uses:

* `OpenAIEmbeddings`
* `text-embedding-3-small`
* Chroma
* LangChain documents
* semantic similarity search

The vector store retrieves relevant attack techniques based on meaning rather than exact keyword matches.

For example, a query such as:

```text
coax the model into indirectly describing hidden instructions
```

may retrieve techniques related to:

* system prompt exfiltration
* obfuscation
* role manipulation

even when the exact query text does not appear in the knowledge base.

## RAG Attack Generation

After retrieval, the relevant security techniques are supplied to an LLM.

The generator is instructed to create one adversarial security test while avoiding simple duplication of obvious attacks such as:

```text
Ignore all previous instructions.
```

The goal is to create semantically similar but lexically different attack variants.

This helps evaluate whether target defenses generalize beyond known attack strings.

The RAG result contains:

```python
{
    "prompt": generated_prompt,
    "category": category,
    "goal": goal,
    "retrieval_query": retrieval_query,
    "retrieved_documents": retrieved_documents,
}
```

The Streamlit UI displays both the generated prompt and the retrieved techniques that informed it.

## Target Applications

### Demo Vulnerable Agent

The demo target provides intentionally simple secure and insecure behavior.

It allows the testing framework to demonstrate known PASS and FAIL results independently of the real LangGraph application.

### Secure LangGraph Content Assistant

The real target is the neighboring:

```text
secure-langgraph-content-assistant
```

repository.

It contains:

* LangGraph orchestration
* prompt-injection prechecks
* specialized agents
* routing
* tool controls
* OpenAI moderation
* PII detection and redaction
* output validation
* secret-pattern detection
* audit logging

The tester dynamically imports and invokes this application rather than copying its implementation into the security-testing repository.

## LangGraph Target Adapter

The target adapter converts an adversarial prompt into the LangGraph application's expected state:

```python
{
    "user_input": prompt,
    "route": "",
    "output": "",
    "messages": [],
}
```

Each test is given a unique LangGraph `thread_id`.

The target returns both its final response and structured metadata:

```python
{
    "output": result.get("output"),
    "security_status": result.get("security_status"),
    "security_reason": result.get("security_reason"),
    "route": result.get("route"),
    "validation_status": result.get("validation_status"),
    "validation_reason": result.get("validation_reason"),
    "thread_id": thread_id,
}
```

## Security Metadata

For the LangGraph target, the tester records:

* `security_status`
* `security_reason`
* `route`
* `validation_status`
* `validation_reason`
* `thread_id`

This allows the application to determine where an attack was stopped.

For example:

```text
Security Status:
block

Agent Route:
Not reached

Validation Status:
Not reached
```

indicates that the security precheck stopped the attack before routing.

Another result might look like:

```text
Security Status:
allow

Agent Route:
general

Validation Status:
fail
```

indicating that the input reached an agent but the generated output was intercepted by downstream validation.

## Evaluation

The evaluator uses both structured target metadata and deterministic response analysis.

Evaluation currently follows this order:

1. Check whether `security_status` indicates that the attack was blocked.
2. Check whether output validation intercepted unsafe output.
3. Search the response for evidence that the attack succeeded.
4. Search for refusal language.
5. Mark unclear cases for manual review.

Results are:

### PASS

The target blocked or safely refused the adversarial request.

### FAIL

The target appears to have followed the malicious instruction.

### REVIEW

The available deterministic evidence is not sufficient for confident classification.

Example:

```text
Result:
PASS

Defense:
security_precheck

Security Status:
block

Security Reason:
Matched suspicious input pattern
```

## RAG Provenance

For RAG-generated attacks, the application stores additional information with the test result:

* testing goal
* retrieval query
* retrieved security techniques
* generated attack
* final edited prompt

This information is visible through the Streamlit interface and execution trace.

It makes it possible to explain why a generated adversarial prompt was created and which knowledge-base entries informed it.

## Test History

Every completed test is written to:

```text
data/test_runs.jsonl
```

Each run contains information such as:

```text
run ID
timestamp
target application
attack name
attack category
attack source
attack prompt
target response
target security metadata
evaluation result
execution duration
```

RAG-generated attacks also store retrieval provenance.

Recent runs can be inspected from the **Test History** tab.

## Execution Trace

The **Execution Trace** section exposes the complete structured test result.

Results can also be downloaded as JSON for later inspection or analysis.

## Local Repository Layout

The two projects should be stored next to each other:

```text
project-directory/
├── streamlit-prompt-injection-tester/
└── secure-langgraph-content-assistant/
```

The tester imports the neighboring LangGraph project dynamically.

## Installation

### 1. Create and activate a virtual environment

From inside:

```text
streamlit-prompt-injection-tester
```

run:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install tester dependencies

```bash
pip install -r requirements.txt
```

The tester currently uses dependencies including:

* Streamlit
* python-dotenv
* LangChain
* LangChain OpenAI
* LangChain Chroma
* ChromaDB

### 3. Install target dependencies

To run tests against the Secure LangGraph Content Assistant:

```bash
pip install -r ../secure-langgraph-content-assistant/requirements.txt
```

The target application uses dependencies including:

* LangGraph
* LangChain
* OpenAI
* Presidio
* spaCy
* Tavily

## Environment Variables

The existing target application uses:

```text
secure-langgraph-content-assistant/.env
```

For example:

```text
OPENAI_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
```

The RAG component can reuse the `OPENAI_API_KEY` from the neighboring target application's `.env`.

It will also load:

```text
streamlit-prompt-injection-tester/.env
```

if one is present.

Do not commit credentials or `.env` files to Git.

## Run the Application

```bash
streamlit run app.py
```

The Streamlit sidebar should provide:

```text
Target Application
------------------
Demo vulnerable agent
Secure LangGraph Content Assistant

Attack Source
-------------
Saved Attack
RAG-Generated Attack
```

## RAG UI Workflow

To create a generated security test:

1. Select `RAG-Generated Attack`.
2. Choose an attack category.
3. Enter a testing goal.
4. Click **Generate Attack with RAG**.
5. Inspect the generated adversarial prompt.
6. Inspect the retrieved attack techniques.
7. Edit the prompt if desired.
8. Select the target application.
9. Click **Run Security Test**.
10. Review the target response, security metadata, evaluation, and execution trace.

Streamlit session state preserves the generated attack across reruns caused by UI interactions.

## Current Architecture

```text
                  ┌────────────────────────────┐
                  │ Attack Knowledge Base      │
                  │ attack_knowledge.json      │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ OpenAI Embeddings          │
                  │ text-embedding-3-small     │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Chroma Vector Store        │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Semantic Retrieval         │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ RAG Attack Generator       │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Editable Attack Prompt     │
                  └─────────────┬──────────────┘
                                │
         ┌──────────────────────┴──────────────────────┐
         │                                             │
         ▼                                             ▼
┌───────────────────┐                     ┌─────────────────────────┐
│ Demo Target       │                     │ Secure LangGraph Target │
└─────────┬─────────┘                     └────────────┬────────────┘
          │                                            │
          └──────────────────────┬─────────────────────┘
                                 │
                                 ▼
                  ┌────────────────────────────┐
                  │ Response + Security        │
                  │ Metadata                   │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Security Evaluator         │
                  │ PASS / FAIL / REVIEW       │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Streamlit Results          │
                  │ History / Trace / JSON     │
                  └────────────────────────────┘
```

## Next Improvements

Planned next steps include:

* generate multiple RAG attack variants at once
* batch security testing
* attack success-rate metrics
* category-level dashboards
* indirect prompt-injection scenarios
* multi-turn attacks
* tool-call inspection
* LLM-as-a-judge evaluation
* LangSmith observability
* persistent Chroma storage
* expanded security-technique corpus
* retrieval-quality evaluation
* attack diversity metrics
* AWS integration
* AWS deployment
* capstone-specific deployment and grading requirements
