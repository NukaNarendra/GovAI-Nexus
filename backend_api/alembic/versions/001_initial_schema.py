"""initial schema"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cost_center_code", sa.String(length=20), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_departments_name"), "departments", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("salt", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("requires_password_change", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("account_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_department_link",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "department_id"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("key_prefix", sa.String(length=10), nullable=False),
        sa.Column("hashed_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allowed_ips", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_keys_hashed_key"), "api_keys", ["hashed_key"], unique=True
    )
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"], unique=False)

    op.create_table(
        "login_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "login_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("location_country", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_login_history_user_id"), "login_history", ["user_id"], unique=False
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_ip_address", sa.String(length=45), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("action_details", sa.Text(), nullable=False),
        sa.Column("old_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("cryptographic_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("is_tampered", sa.Boolean(), nullable=False),
        sa.Column("compliance_frameworks", sa.JSON(), nullable=True),
        sa.Column("ai_model_version", sa.String(length=100), nullable=True),
        sa.Column("ai_prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("ai_completion_tokens", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cryptographic_hash"),
    )
    op.create_index(
        op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_correlation_id"),
        "audit_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_logs_event_type"), "audit_logs", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_resource_id"), "audit_logs", ["resource_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_timestamp"), "audit_logs", ["timestamp"], unique=False
    )

    op.create_table(
        "hitl_review_queue",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("task_status", sa.String(length=30), nullable=False),
        sa.Column("risk_category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("ai_confidence_score", sa.Float(), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("transaction_context", sa.JSON(), nullable=False),
        sa.Column("compliance_flags", sa.JSON(), nullable=False),
        sa.Column("ai_reasoning", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolution_action", sa.String(length=100), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_sla_breached", sa.Boolean(), nullable=False),
        sa.Column("audit_log_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["audit_log_id"], ["audit_logs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hitl_review_queue_created_at"),
        "hitl_review_queue",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_deadline_at"),
        "hitl_review_queue",
        ["deadline_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_priority"),
        "hitl_review_queue",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_resource_id"),
        "hitl_review_queue",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_reviewer_id"),
        "hitl_review_queue",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_risk_category"),
        "hitl_review_queue",
        ["risk_category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hitl_review_queue_task_status"),
        "hitl_review_queue",
        ["task_status"],
        unique=False,
    )

    op.create_table(
        "transaction_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("core_banking_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("source_entity_id", sa.String(length=100), nullable=False),
        sa.Column("source_account_id", sa.String(length=100), nullable=False),
        sa.Column("source_country", sa.String(length=3), nullable=False),
        sa.Column("destination_entity_id", sa.String(length=100), nullable=False),
        sa.Column("destination_account_id", sa.String(length=100), nullable=False),
        sa.Column("destination_country", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Float(), nullable=True),
        sa.Column("base_currency_amount", sa.Float(), nullable=True),
        sa.Column("ai_risk_score", sa.Float(), nullable=False),
        sa.Column("ai_confidence_score", sa.Float(), nullable=False),
        sa.Column("compliance_passed", sa.Boolean(), nullable=False),
        sa.Column("requires_hitl", sa.Boolean(), nullable=False),
        sa.Column("sanctions_screened", sa.Boolean(), nullable=False),
        sa.Column("aml_screened", sa.Boolean(), nullable=False),
        sa.Column("velocity_checked", sa.Boolean(), nullable=False),
        sa.Column("compliance_metadata", sa.JSON(), nullable=False),
        sa.Column("routing_metadata", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("audit_log_id", sa.String(length=36), nullable=True),
        sa.Column("hitl_queue_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["audit_log_id"], ["audit_logs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["hitl_queue_id"], ["hitl_review_queue.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_records_core_banking_id"),
        "transaction_records",
        ["core_banking_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transaction_records_created_at"),
        "transaction_records",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_records_destination_entity_id"),
        "transaction_records",
        ["destination_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_records_reference_id"),
        "transaction_records",
        ["reference_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_transaction_records_source_entity_id"),
        "transaction_records",
        ["source_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_records_status"),
        "transaction_records",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("transaction_records")
    op.drop_table("hitl_review_queue")
    op.drop_table("audit_logs")
    op.drop_table("login_history")
    op.drop_table("api_keys")
    op.drop_table("user_department_link")
    op.drop_table("users")
    op.drop_table("departments")
