import asyncio
import uuid
import json
from datetime import datetime
from src.infrastructure.database.session import db_manager
from src.infrastructure.database.models.user import User, UserRole
from src.infrastructure.database.models.hitl_queue import (
    HITLQueue,
    HITLTaskStatus,
    RiskCategory,
    PriorityLevel,
)
from src.infrastructure.database.models.audit_log import AuditLog
from sqlalchemy import select

async def add_mock_tasks():
    print("Connecting to database...")
    async for session in db_manager.get_session():
        # Get the admin user
        admin_stmt = select(User).where(User.email == "admin@nexus.local")
        admin_result = await session.execute(admin_stmt)
        admin = admin_result.scalars().first()

        if not admin:
            print("Error: Admin user not found. Run seed.py first.")
            return

       
        task1 = HITLQueue(
            id=str(uuid.uuid4()),
            task_status=HITLTaskStatus.PENDING_REVIEW,
            risk_category=RiskCategory.AML_FLAG,
            priority=PriorityLevel.CRITICAL,
            agent_id="AML_AGENT_V2",
            model_version="gpt-4",
            ai_confidence_score=0.92,
            resource_id="TXN-998822",
            resource_type="WIRE_TRANSFER",
            transaction_context={"amount": 500000, "currency": "USD", "destination": "High Risk Jurisdiction"},
            compliance_flags={
                "velocity_rule": "FAILED", 
                "sanctions_check": "PASSED",
                "feature_attribution": {
                    "high_risk_jurisdiction": 45,
                    "transaction_velocity": 35,
                    "amount_threshold": 20
                }
            },
            ai_reasoning="Large wire transfer to high risk jurisdiction flagged. Requires human review.",
            created_at=datetime.utcnow()
        )
        session.add(task1)

        task2 = HITLQueue(
            id=str(uuid.uuid4()),
            task_status=HITLTaskStatus.UNDER_REVIEW,
            risk_category=RiskCategory.KYC_ANOMALY,
            priority=PriorityLevel.HIGH,
            agent_id="KYC_AGENT_V1",
            model_version="gpt-4",
            ai_confidence_score=0.78,
            resource_id="USR-443322",
            resource_type="CORPORATE_ENTITY",
            transaction_context={"company_name": "Nexus Global Trading", "registration": "Offshore"},
            compliance_flags={
                "ubo_check": "INCONCLUSIVE", 
                "pep_match": "FALSE",
                "feature_attribution": {
                    "corporate_complexity": 50,
                    "offshore_registration": 30,
                    "missing_ubo_docs": 20
                }
            },
            ai_reasoning="Company ownership structure is overly complex. Confidence in UBO verification is low.",
            reviewer_id=admin.id,
            claimed_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        session.add(task2)

        # Create Task 3: Assigned to Admin (My Assignments)
        task3 = HITLQueue(
            id=str(uuid.uuid4()),
            task_status=HITLTaskStatus.UNDER_REVIEW,
            risk_category=RiskCategory.SANCTIONS_MATCH,
            priority=PriorityLevel.MEDIUM,
            agent_id="SANCTIONS_AGENT_V1",
            model_version="gpt-4",
            ai_confidence_score=0.85,
            resource_id="USR-112233",
            resource_type="INDIVIDUAL",
            transaction_context={"name": "John Doe", "country": "US"},
            compliance_flags={"sanctions_match": "PARTIAL"},
            ai_reasoning="Name matches a partial alias on the OFAC list. Manual clearance required.",
            reviewer_id=admin.id,
            claimed_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        session.add(task3)

        await session.commit()
        print("✅ Successfully added 3 mock tasks (1 in Global Queue, 2 in My Assignments)!")
        break

if __name__ == "__main__":
    asyncio.run(add_mock_tasks())
