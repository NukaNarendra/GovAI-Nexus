import asyncio
import uuid
from src.infrastructure.database.session import db_manager
from src.infrastructure.database.models.user import User, UserRole, Department
from src.core.security import generate_salt, hash_password_with_salt


async def seed_db():
    print("Connecting to database...")
    async for session in db_manager.get_session():
        dept_id = str(uuid.uuid4())
        dept = Department(
            id=dept_id,
            name="Global Compliance",
            cost_center_code="COMP-100",
            region="NAMER",
        )
        session.add(dept)

        salt = generate_salt()

        hashed_pw = hash_password_with_salt("Admin123!", salt)

        admin = User(
            id=str(uuid.uuid4()),
            email="admin@nexus.local",
            hashed_password=hashed_pw,
            salt=salt,
            first_name="Test",
            last_name="Admin",
            role=UserRole.SYSTEM_ADMIN,
            is_active=True,
            requires_password_change=False,
        )
        session.add(admin)

        await session.commit()
        print(
            "✅ Successfully seeded database with user: admin@nexus.local / Admin123!"
        )
        break


if __name__ == "__main__":
    asyncio.run(seed_db())
