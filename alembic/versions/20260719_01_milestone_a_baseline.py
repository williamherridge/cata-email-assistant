"""Create the Milestone A pilot schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260719_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "mailboxes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gmail_address", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("gmail_profile_id", sa.Text(), nullable=True),
        sa.Column("last_successful_history_id", sa.Text(), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "poll_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mailbox_id", sa.Integer(), sa.ForeignKey("mailboxes.id"), nullable=False),
        sa.Column("trigger_source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("history_id_start", sa.Text(), nullable=True),
        sa.Column("history_id_end", sa.Text(), nullable=True),
        sa.Column("messages_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_enqueued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "message_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mailbox_id", sa.Integer(), sa.ForeignKey("mailboxes.id"), nullable=False),
        sa.Column("gmail_thread_id", sa.Text(), nullable=False),
        sa.Column("subject_canonical", sa.Text(), nullable=True),
        sa.Column("latest_message_received_at", sa.DateTime(), nullable=True),
        sa.Column("latest_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mailbox_id", "gmail_thread_id", name="uq_message_threads_mailbox_thread"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mailbox_id", sa.Integer(), sa.ForeignKey("mailboxes.id"), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_threads.id"), nullable=True),
        sa.Column("gmail_message_id", sa.Text(), nullable=False),
        sa.Column("gmail_history_id", sa.Text(), nullable=True),
        sa.Column("rfc_message_id", sa.Text(), nullable=True),
        sa.Column("gmail_internal_date", sa.DateTime(), nullable=True),
        sa.Column("from_display", sa.Text(), nullable=True),
        sa.Column("from_address", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("draft_state", sa.Text(), nullable=False, server_default="not_started"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="normal"),
        sa.Column("informational_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reply_needed", sa.Boolean(), nullable=True),
        sa.Column("assigned_category_id", sa.Integer(), nullable=True),
        sa.Column("assigned_subcategory_id", sa.Integer(), nullable=True),
        sa.Column("proposed_category_label", sa.Text(), nullable=True),
        sa.Column("proposed_subcategory_label", sa.Text(), nullable=True),
        sa.Column("latest_analysis_id", sa.Integer(), nullable=True),
        sa.Column("latest_prework_id", sa.Integer(), nullable=True),
        sa.Column("latest_draft_id", sa.Integer(), nullable=True),
        sa.Column("latest_sent_reply_id", sa.Integer(), nullable=True),
        sa.Column("opened_in_portal_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("ignored_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mailbox_id", "gmail_message_id", name="uq_messages_mailbox_message"),
    )

    op.create_table(
        "work_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("mailbox_id", sa.Integer(), sa.ForeignKey("mailboxes.id"), nullable=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("poll_run_id", sa.Integer(), sa.ForeignKey("poll_runs.id"), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_token", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "message_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("participant_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("email_address", sa.Text(), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "message_headers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("header_name", sa.Text(), nullable=False),
        sa.Column("header_value", sa.Text(), nullable=False),
    )

    op.create_table(
        "message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("gmail_attachment_id", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("is_inline", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "message_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("mailbox_id", sa.Integer(), sa.ForeignKey("mailboxes.id"), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("message_artifacts")
    op.drop_table("message_attachments")
    op.drop_table("message_headers")
    op.drop_table("message_participants")
    op.drop_table("work_items")
    op.drop_table("messages")
    op.drop_table("message_threads")
    op.drop_table("poll_runs")
    op.drop_table("mailboxes")
    op.drop_table("users")
