# main.py

import autogen
from dotenv import load_dotenv
import os
import json

from db_tools import record_underwriting_decision
from data_tools import analyze_applicant_data   # unified function
from autogen import register_function

# Load environment variables
load_dotenv()

# Ollama LLM config
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

config_list_ollama = [
    {
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "api_key": "ollama",
    }
]

# --- Tool Executor Agent ---
executor_agent = autogen.UserProxyAgent(
    name="Tool_Executor",
    human_input_mode="NEVER",
    function_map={
        "record_underwriting_decision": record_underwriting_decision,
    },
    code_execution_config={"use_docker": False},
)

# --- Underwriting Agent ---
underwriting_agent = autogen.AssistantAgent(
    name="Underwriting_Agent",
    system_message=(
        "You are an expert Underwriter. Your task is to DECLINE high-risk applications. "
        "When you receive applicant data, your FIRST response MUST be the exact function call: "
        "record_underwriting_decision(application_id='APP-XXXX', decision='DECLINED', notes='[Detailed rationale]'). "
        "DO NOT include TERMINATE in your first response. "
        "In your SECOND response, after the function execution result, "
        "you MUST confirm the decision was recorded and end the conversation with 'TERMINATE'. "
        "Do not define functions or print variables."
    ),
    llm_config={
        "config_list": config_list_ollama,
        "functions": [
            {
                "name": "record_underwriting_decision",
                "description": "Writes the final underwriting decision to MongoDB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application_id": {"type": "string"},
                        "decision": {"type": "string"},
                        "notes": {"type": "string"}
                    },
                    "required": ["application_id", "decision", "notes"]
                }
            }
        ],
    },
)

# Register function
register_function(
    record_underwriting_decision,
    caller=underwriting_agent,
    executor=executor_agent,
    name="record_underwriting_decision",
    description="Records the final underwriting decision to MongoDB"
)

# --- Analysis Phase ---
csv_path = os.path.join(os.path.dirname(__file__), "applicants.csv")
summary, high_risk_applicants = analyze_applicant_data(csv_path, "risk_status", "HIGH_RISK")

print("--- Analysis Phase ---")
print(summary)
print(f"--- Found {len(high_risk_applicants)} high-risk applicants to process ---")

# --- Underwriting Workflow ---
for applicant in high_risk_applicants:
    app_id = applicant.get("application_id", "UNKNOWN")
    print(f"\n--- Processing applicant {app_id} ---")

    initial_prompt = f"The following application is ready for final decision: {json.dumps(applicant)}"

    chat_result = executor_agent.initiate_chat(
        underwriting_agent,
        message=initial_prompt,
        max_turns=3,
        is_termination_msg=lambda x: "Decision recorded" in x.get("content", "")
    )
    #print(chat_result)
