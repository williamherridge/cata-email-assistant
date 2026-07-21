"""Add queue and history performance indexes."""

from alembic import op


revision = "20260721_03"
down_revision = "20260719_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_messages_status_received_id", "messages", ["status", "received_at", "id"], unique=False)
    op.create_index("ix_messages_status_responded_id", "messages", ["status", "responded_at", "id"], unique=False)
    op.create_index("ix_messages_status_ignored_id", "messages", ["status", "ignored_at", "id"], unique=False)
    op.create_index("ix_messages_assigned_category_id", "messages", ["assigned_category_id"], unique=False)
    op.create_index("ix_messages_priority", "messages", ["priority"], unique=False)
    op.create_index("ix_messages_reply_needed", "messages", ["reply_needed"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_reply_needed", table_name="messages")
    op.drop_index("ix_messages_priority", table_name="messages")
    op.drop_index("ix_messages_assigned_category_id", table_name="messages")
    op.drop_index("ix_messages_status_ignored_id", table_name="messages")
    op.drop_index("ix_messages_status_responded_id", table_name="messages")
    op.drop_index("ix_messages_status_received_id", table_name="messages")
