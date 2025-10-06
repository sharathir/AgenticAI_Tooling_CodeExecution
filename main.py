# main.py

import autogen
from dotenv import load_dotenv
import os
import json
from typing import Dict, List
from db_tools import record_underwriting_decision
from data_tools import analyze_applicant_data
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

# --- Knowledge Base / RAG Context ---
UNDERWRITING_KNOWLEDGE_BASE = """
UNDERWRITING POLICY GUIDELINES FOR INSURANCE COVERAGE:

1. RISK STATUS ASSESSMENT:
   - LOW_RISK: Standard approval, minimal restrictions
   - MEDIUM_RISK: Conditional approval with enhanced monitoring or premium adjustments
   - HIGH_RISK: Requires detailed review, often DECLINED unless compensating factors present

2. COVERAGE AMOUNT THRESHOLDS:
   - Up to $2M: Standard underwriting process
   - $2M - $4M: Enhanced review required, additional medical/financial documentation
   - Above $4M: Executive underwriting, extensive due diligence mandatory

3. HIGH_RISK APPLICANT CRITERIA:
   Risk factors that warrant HIGH_RISK classification:
   - Hazardous occupation or lifestyle activities
   - Pre-existing medical conditions
   - Previous claims history
   - Financial instability indicators
   - Age and actuarial risk factors

4. DECISION FRAMEWORK FOR HIGH_RISK CASES:
   
   DECLINE if:
   - Coverage requested > $3M AND HIGH_RISK status
   - Multiple red flags without mitigation
   - Unacceptable risk-to-premium ratio
   - Policy violations or misrepresentation suspected
   
   CONDITIONALLY APPROVE if:
   - Coverage ≤ $3M with increased premium (25-50% surcharge)
   - Applicant accepts coverage limitations
   - Additional riders or exclusions can mitigate risk
   - Strong compensating factors present
   
   REFER TO SENIOR UNDERWRITER if:
   - Borderline cases requiring judgment
   - Coverage $3M-$4M with mixed risk indicators
   - Novel or complex risk scenarios

5. DOCUMENTATION REQUIREMENTS:
   - LOW_RISK: Basic application sufficient
   - MEDIUM_RISK: Medical records, financial statements
   - HIGH_RISK: Comprehensive evaluation including lifestyle assessment, medical exams, financial audit

6. PREMIUM ADJUSTMENTS:
   - LOW_RISK: Standard rates
   - MEDIUM_RISK: 10-25% premium increase
   - HIGH_RISK: 25-75% premium increase or decline
"""

# --- RAG Context Retrieval ---
def retrieve_relevant_policies(applicant: Dict) -> str:
    """
    Retrieves policy sections relevant to the applicant's risk profile.
    In production, this would use vector similarity search.
    """
    risk_status = applicant.get('risk_status', 'UNKNOWN')
    coverage = applicant.get('requested_coverage', 0)
    
    # Build focused context based on applicant characteristics
    context = f"""
APPLICABLE UNDERWRITING POLICIES:

Risk Classification: {risk_status}
Requested Coverage: ${coverage:,}

"""
    
    # Add relevant policy sections
    if risk_status == "HIGH_RISK":
        context += """
HIGH RISK EVALUATION CRITERIA:
- Coverage > $3M typically requires DECLINE for HIGH_RISK applicants
- Coverage $2M-$3M may be conditionally approved with 50-75% premium surcharge
- Coverage < $2M may be approved with 25-50% surcharge and exclusions

DECISION GUIDELINES:
1. Evaluate if coverage amount exceeds acceptable threshold for HIGH_RISK
2. Consider if compensating factors could justify conditional approval
3. Default to DECLINE if risk exposure is unacceptable
"""
    
    if coverage > 3000000:
        context += """
HIGH COVERAGE AMOUNT FLAGS:
- Coverage exceeding $3M requires executive underwriting approval
- HIGH_RISK applicants requesting >$3M coverage face strong presumption of DECLINE
- Enhanced due diligence mandatory for all >$3M applications
"""
    
    context += f"\n\nFULL POLICY REFERENCE:\n{UNDERWRITING_KNOWLEDGE_BASE}"
    
    return context

# --- Agents Configuration ---

# RAG Agent for policy retrieval
rag_agent = autogen.AssistantAgent(
    name="Policy_Specialist",
    system_message=(
        "You are a policy expert who retrieves and explains relevant underwriting guidelines. "
        "When given applicant information, identify which policy sections apply and explain "
        "the key decision criteria. Focus on risk status, coverage thresholds, and decision rules."
    ),
    llm_config={"config_list": config_list_ollama},
)

# Risk Analysis Agent
risk_analyst = autogen.AssistantAgent(
    name="Risk_Analyst",
    system_message=(
        "You are a risk assessment specialist. Analyze applicants against underwriting policies. "
        "For each applicant, evaluate:\n"
        "1. Risk level appropriateness for requested coverage\n"
        "2. Whether coverage amount exceeds thresholds for their risk category\n"
        "3. Likelihood of approval vs decline\n"
        "4. Potential conditions or premium adjustments\n"
        "Provide clear, structured analysis with specific policy references."
    ),
    llm_config={"config_list": config_list_ollama},
)

# Decision Agent with function calling
decision_agent = autogen.AssistantAgent(
    name="Underwriting_Decision_Maker",
    system_message=(
        "You are the final decision authority for underwriting. Based on risk analysis:\n\n"
        "DECISION RULES:\n"
        "- HIGH_RISK with coverage > $3M: DECLINE (cite excessive risk exposure)\n"
        "- HIGH_RISK with coverage $2M-$3M: CONDITIONALLY APPROVED (50%+ premium surcharge)\n"
        "- HIGH_RISK with coverage < $2M: CONDITIONALLY APPROVED (25-50% surcharge)\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "1. Make decision: APPROVED / CONDITIONALLY APPROVED / DECLINED / REFER\n"
        "2. Call record_underwriting_decision() with:\n"
        "   - application_id: The exact APP-XXXX identifier\n"
        "   - decision: Your final decision\n"
        "   - notes: MUST be detailed (minimum 100 characters) including:\n"
        "     * Specific policy violations or reasons\n"
        "     * Coverage amount vs risk threshold analysis\n"
        "     * Risk factors identified\n"
        "     * Regulatory/compliance citations\n"
        "3. Wait for function execution confirmation\n"
        "4. After successful recording, respond with 'Decision recorded successfully. TERMINATE'\n\n"
        "NEVER provide empty notes. NEVER use placeholder text. Be thorough and policy-compliant."
    ),
    llm_config={
        "config_list": config_list_ollama,
        "functions": [
            {
                "name": "record_underwriting_decision",
                "description": "Records final underwriting decision to MongoDB database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application_id": {
                            "type": "string",
                            "description": "Application ID (e.g., APP-1003)"
                        },
                        "decision": {
                            "type": "string",
                            "enum": ["APPROVED", "CONDITIONALLY APPROVED", "DECLINED", "REFER"],
                            "description": "Final underwriting decision"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Detailed rationale with policy references"
                        }
                    },
                    "required": ["application_id", "decision", "notes"]
                }
            }
        ],
    },
)

# Tool Executor
executor = autogen.UserProxyAgent(
    name="Function_Executor",
    human_input_mode="NEVER",
    code_execution_config=False,
    max_consecutive_auto_reply=10,  # Allow function execution
    is_termination_msg=lambda msg: "TERMINATE" in msg.get("content", ""),
)

# Register function
register_function(
    record_underwriting_decision,
    caller=decision_agent,
    executor=executor,
    name="record_underwriting_decision",
    description="Records underwriting decision to database"
)

# --- LLM/RAG Workflow ---
def process_with_llm_rag(applicant: Dict) -> None:
    """
    Processes application using LLM reasoning with RAG policy context.
    """
    app_id = applicant.get("application_id", "UNKNOWN")
    name = applicant.get("name", "Unknown")
    risk_status = applicant.get("risk_status", "UNKNOWN")
    coverage = applicant.get("requested_coverage", 0)
    
    print(f"\n{'='*70}")
    print(f"📋 APPLICATION: {app_id} | {name}")
    print(f"   Risk Status: {risk_status} | Coverage Requested: ${coverage:,}")
    print(f"{'='*70}")
    
    # STEP 1: Retrieve relevant policies (RAG)
    print("\n[STEP 1/3] 🔍 Retrieving relevant underwriting policies...")
    policy_context = retrieve_relevant_policies(applicant)
    
    # STEP 2: LLM-driven risk analysis
    print("[STEP 2/3] 🤖 Performing AI risk analysis...")
    
    analysis_prompt = f"""
Analyze this insurance application against underwriting policies:

APPLICANT INFORMATION:
- Application ID: {app_id}
- Name: {name}
- Risk Classification: {risk_status}
- Requested Coverage: ${coverage:,}

{policy_context}

Provide a structured risk assessment that evaluates:
1. Whether the coverage amount is appropriate for this risk level
2. Key policy considerations for this application
3. Preliminary recommendation (approve/conditional/decline)
"""
    
    risk_analysis = risk_analyst.generate_reply(
        messages=[{"role": "user", "content": analysis_prompt}]
    )
    
    print(f"\n📊 Risk Analysis Summary:")
    print(f"{'-'*70}")
    print(risk_analysis)
    print(f"{'-'*70}\n")
    
    # STEP 3: Final decision with function execution
    print("[STEP 3/3] ⚖️  Making final underwriting decision...\n")
    
    decision_prompt = f"""
Make the final underwriting decision for application {app_id}.

APPLICANT DATA:
{json.dumps(applicant, indent=2)}

RISK ANALYSIS:
{risk_analysis}

POLICY CONTEXT:
{policy_context}

Execute record_underwriting_decision() with your decision and comprehensive rationale.
"""
    
    # Multi-turn conversation for decision and recording
    chat_result = executor.initiate_chat(
        decision_agent,
        message=decision_prompt,
        max_turns=8,
        silent=False,
    )
    
    print(f"\n{'='*70}")
    print(f"✅ Completed processing: {app_id}")
    print(f"{'='*70}\n")

# --- Main Execution ---
if __name__ == "__main__":
    # Load and analyze data
    csv_path = os.path.join(os.path.dirname(__file__), "applicants.csv")
    
    print("\n" + "="*70)
    print("🏛️  INTELLIGENT UNDERWRITING SYSTEM - LLM/RAG ENABLED")
    print("="*70)
    
    summary, high_risk_applicants = analyze_applicant_data(
        csv_path, 
        "risk_status", 
        "HIGH_RISK"
    )
    
    print(f"\n📈 Data Analysis Summary:")
    print(summary)
    print(f"\n🎯 Identified {len(high_risk_applicants)} HIGH_RISK applications for processing\n")
    
    if not high_risk_applicants:
        print("⚠️  No HIGH_RISK applications found. Exiting.")
    else:
        # Process each high-risk applicant with LLM/RAG workflow
        for idx, applicant in enumerate(high_risk_applicants, 1):
            print(f"\n\n{'#'*70}")
            print(f"# Processing Application {idx}/{len(high_risk_applicants)}")
            print(f"{'#'*70}")
            
            try:
                process_with_llm_rag(applicant)
            except Exception as e:
                print(f"❌ Error processing {applicant.get('application_id')}: {str(e)}")
                continue
        
        print("\n" + "="*70)
        print("🎉 ALL HIGH-RISK APPLICATIONS PROCESSED")
        print("="*70)