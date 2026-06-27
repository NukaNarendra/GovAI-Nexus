from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_audit_indexes"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_audit_logs_timestamp_id_desc",
        "audit_logs",
        [sa.text("timestamp DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "idx_audit_logs_actor_type_timestamp",
        "audit_logs",
        ["actor_type", sa.text("timestamp DESC")],
    )
    op.create_index(
        "idx_audit_logs_event_type_severity", "audit_logs", ["event_type", "severity"]
    )


def downgrade() -> None:
    op.drop_index("idx_audit_logs_event_type_severity", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor_type_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_timestamp_id_desc", table_name="audit_logs")
