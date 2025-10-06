# Program Flow Explanation

## Entry Point: `if __name__ == "__main__":`

### Phase 1: Data Loading & Analysis
```python
csv_path = "applicants.csv"
summary, high_risk_applicants = analyze_applicant_data(csv_path, "risk_status", "HIGH_RISK")
```

**What happens:**
- Reads CSV file with applicant data
- Filters for `risk_status == "HIGH_RISK"` 
- Returns summary statistics and list of high-risk applicants (Bruce Banner, Hal Jordan)

**Output:** 2 dictionaries with `application_id`, `name`, `risk_status`, `requested_coverage`

---

### Phase 2: Main Processing Loop

For each high-risk applicant, calls:
```python
process_with_llm_rag(applicant)
```

This is where the LLM/RAG workflow begins:

---

## `process_with_llm_rag(applicant)` Function Flow

### Step 1: Policy Retrieval (RAG)
```python
policy_context = retrieve_relevant_policies(applicant)
```

**What it does:**
- Takes applicant's `risk_status` and `requested_coverage`
- Filters the `UNDERWRITING_KNOWLEDGE_BASE` string to find relevant sections
- Builds focused context based on thresholds (e.g., coverage > $3M)

**Returns:** String containing relevant policy text (e.g., "HIGH_RISK with coverage > $3M typically requires DECLINE")

---

### Step 2: Risk Analysis (LLM)
```python
analysis_prompt = f"Analyze this application: {applicant_data} against {policy_context}"
risk_analysis = risk_analyst.generate_reply(messages=[{"role": "user", "content": analysis_prompt}])
```

**What it does:**
- Sends applicant data + policy context to `risk_analyst` agent
- LLM (llama3.2) analyzes:
  - Whether coverage amount exceeds thresholds
  - Risk factors present
  - Policy violations
  - Preliminary recommendation

**Returns:** Text-based risk assessment report (what you saw in output: "Risk Level: HIGH_RISK, Coverage exceeds $3M threshold...")

---

### Step 3: Decision Making & Function Execution
```python
decision_prompt = f"Make decision for {app_id}. Risk Analysis: {risk_analysis}. Policy: {policy_context}"
chat_result = executor.initiate_chat(decision_agent, message=decision_prompt, max_turns=8)
```

**What happens (multi-turn conversation):**

#### Turn 1: Executor → Decision Agent
- Sends decision prompt with full context

#### Turn 2: Decision Agent → Executor
- LLM decides: "DECLINED" 
- Generates function call:
```json
{
  "name": "record_underwriting_decision",
  "arguments": {
    "application_id": "APP-1003",
    "decision": "DECLINED", 
    "notes": "Coverage $5M exceeds $3M threshold..."
  }
}
```

#### Turn 3: Executor executes function
```python
record_underwriting_decision(application_id, decision, notes)
```

**What `record_underwriting_decision` does:**
- Connects to MongoDB
- Upserts document: `{"_id": "APP-1003", "decision": "DECLINED", "notes": "...", "timestamp": "..."}`
- Returns: "Decision successfully recorded for APP-1003. Status: Modified"

#### Turn 4: Executor → Decision Agent
- Sends function result back to LLM

#### Turn 5: Decision Agent → Executor
- LLM sees "Decision recorded"
- Responds: "TERMINATE"

**Conversation ends**

---

## Key Agents & Their Roles

### 1. `risk_analyst` (AssistantAgent)
- **Role:** Analyzes applicant against policies
- **Input:** Applicant data + policy context
- **Output:** Risk assessment text
- **LLM calls:** 1 per applicant

### 2. `decision_agent` (AssistantAgent with functions)
- **Role:** Makes final decision and calls database function
- **Input:** Risk analysis + policy context
- **Output:** Function call to `record_underwriting_decision()`
- **LLM calls:** 2 per applicant (initial decision + confirmation)

### 3. `executor` (UserProxyAgent)
- **Role:** Executes functions, manages conversation
- **Input:** Messages from decision_agent
- **Output:** Function execution results
- **No LLM calls** - just orchestration

---

## Data Flow Summary

```
CSV File
  ↓
analyze_applicant_data() → [HIGH_RISK applicants]
  ↓
Loop: process_with_llm_rag(applicant)
  ↓
retrieve_relevant_policies() → policy_context string
  ↓
risk_analyst.generate_reply() → risk_analysis text
  ↓
executor.initiate_chat(decision_agent) → conversation starts
  ↓
decision_agent generates function call → {app_id, decision, notes}
  ↓
executor executes record_underwriting_decision() → MongoDB write
  ↓
executor sends result back → "Decision recorded"
  ↓
decision_agent responds → "TERMINATE"
  ↓
Loop continues to next applicant
```

---

## Total LLM Calls Per Application

- **1 call** for risk analysis
- **2 calls** for decision making (decision + confirmation)
- **Total: 3 LLM calls per applicant**

For 2 applicants: 6 total LLM inference calls to Ollama server.