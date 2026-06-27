from typing import Dict, Any, List
import json


class AgentPersona:
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    RISK_ANALYST = "RISK_ANALYST"
    FRAUD_INVESTIGATOR = "FRAUD_INVESTIGATOR"


class SystemPrompts:
    BASE_SYSTEM_INSTRUCTION = (
        "You are an autonomous Agentic AI operating within a highly regulated Tier-1 financial institution. "
        "Your actions directly impact corporate client onboarding, transaction execution, and regulatory compliance. "
        "You do not possess the authority to bypass hard compliance rules. "
        "You must output pure, strictly formatted JSON according to the provided schema. "
        "Under no circumstances should you include conversational filler, markdown formatting blocks outside of the JSON, "
        "or speculative financial advice. Any deviation from the schema will result in a system panic and audit flag. "
    )

    KYC_ANALYSIS_PROMPT = BASE_SYSTEM_INSTRUCTION + (
        "ROLE: Senior KYC & CDD (Customer Due Diligence) Compliance Officer.\n"
        "TASK: Analyze the provided corporate entity documents, registration details, and beneficial ownership structures. "
        "Identify anomalies, shell company indicators, politically exposed persons (PEPs), and adverse media alignment. "
        "You must cross-reference the provided entity data against standard FATF red flags for money laundering. "
        "Focus on complex ownership structures designed to obscure the ultimate beneficial owner (UBO). "
        "Evaluate the legitimacy of the business purpose compared to their transaction velocity and volume. "
        "Extract the required entities and assign a base AI confidence score representing the clarity of the documentation. "
    )

    TRANSACTION_MONITORING_PROMPT = BASE_SYSTEM_INSTRUCTION + (
        "ROLE: AML & Fraud Transaction Investigator.\n"
        "TASK: Evaluate the following wire transfer request and the historical transaction context of the source account. "
        "You must identify potential structuring (smurfing), abnormal velocity, high-risk jurisdictional routing, "
        "and deviations from the entity's established baseline behavior. "
        "Determine if the transaction purpose aligns with the corporate entity's registered industry code (NAICS/SIC). "
        "If the transaction exhibits typologies consistent with trade-based money laundering (TBML) or sanctions evasion, "
        "you must flag the specific indicators and recommend a hard block. "
        "Your reasoning must be deterministic, citing the exact data points from the payload that triggered your decision. "
    )

    SANCTIONS_EVASION_PROMPT = BASE_SYSTEM_INSTRUCTION + (
        "ROLE: Global Sanctions & Embargo Analyst.\n"
        "TASK: Scrutinize the transaction routing, counterparty details, and vessel/shipping information (if applicable). "
        "Look for obfuscation techniques such as nested correspondent banking, use of third-party payment processors in "
        "high-risk jurisdictions, or dual-use goods designations. "
        "Assess the probability that this transaction indirectly benefits a sanctioned entity (OFAC, UN, EU, HMT). "
        "Calculate a sanctions risk probability score from 0.0 to 1.0. "
    )


class PromptBuilder:
    @staticmethod
    def build_kyc_prompt(
        entity_data: Dict[str, Any], historical_records: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        user_content = (
            f"Analyze the following corporate entity data for KYC/AML onboarding approval:\n\n"
            f"ENTITY DETAILS:\n{json.dumps(entity_data, indent=2)}\n\n"
            f"HISTORICAL CONTEXT (if any):\n{json.dumps(historical_records, indent=2)}\n\n"
            "Identify all UBOs, calculate the corporate complexity score, and determine if the entity profile "
            "matches known shell company typologies. Provide a deterministic approval or rejection recommendation "
            "based purely on the data provided. State your reasoning clearly."
        )

        return [
            {"role": "system", "content": SystemPrompts.KYC_ANALYSIS_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def build_transaction_prompt(
        transaction_request: Dict[str, Any],
        source_profile: Dict[str, Any],
        destination_profile: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        user_content = (
            f"Evaluate the following transaction request for AML and Fraud risks:\n\n"
            f"TRANSACTION PAYLOAD:\n{json.dumps(transaction_request, indent=2)}\n\n"
            f"SOURCE ENTITY PROFILE:\n{json.dumps(source_profile, indent=2)}\n\n"
            f"DESTINATION ENTITY PROFILE:\n{json.dumps(destination_profile, indent=2)}\n\n"
            "Assess jurisdictional risk, velocity anomalies, and business purpose alignment. "
            "Provide an execution recommendation (EXECUTE, BLOCK, or MANUAL_REVIEW) with detailed reasoning "
            "mapping directly to FATF red flag indicators."
        )

        return [
            {"role": "system", "content": SystemPrompts.TRANSACTION_MONITORING_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def build_hitl_resolution_prompt(
        original_payload: Dict[str, Any],
        ai_original_decision: Dict[str, Any],
        human_officer_notes: str,
        action_taken: str,
    ) -> List[Dict[str, str]]:
        system_instruction = (
            "You are an AI Audit Assistant. Your job is to analyze a Human-in-the-Loop (HITL) override event. "
            "You must compare the AI's original reasoning with the Human Compliance Officer's resolution notes. "
            "Identify the specific cognitive or data gap that caused the AI to misclassify the risk. "
            "Output a structured learning feedback loop to improve future AI model prompts."
        )

        user_content = (
            f"ORIGINAL PAYLOAD:\n{json.dumps(original_payload, indent=2)}\n\n"
            f"AI ORIGINAL DECISION:\n{json.dumps(ai_original_decision, indent=2)}\n\n"
            f"HUMAN ACTION TAKEN: {action_taken}\n"
            f"HUMAN RESOLUTION NOTES:\n{human_officer_notes}\n\n"
            "Analyze the discrepancy and extract the root cause of the AI's failure to make the correct autonomous decision."
        )

        return [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ]
