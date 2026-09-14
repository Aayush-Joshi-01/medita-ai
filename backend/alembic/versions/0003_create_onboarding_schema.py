"""create onboarding schema

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14

Creates: specializations, hospitals, hospital_admins, hcp_profiles,
hospital_affiliations, onboarding_documents, onboarding_status_events, and
two fresh native enums (onboarding_status, onboarding_owner_type) shared
across the hospitals/hcp_profiles and onboarding_documents/
onboarding_status_events tables respectively.

Safe as a single migration: everything here is a brand-new CREATE TYPE /
CREATE TABLE — unlike 0002, there's no "extend an enum already in use"
transactional hazard.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ONBOARDING_STATUS_VALUES = (
    "draft",
    "submitted",
    "under_review",
    "changes_requested",
    "approved",
    "rejected",
    "suspended",
)
ONBOARDING_OWNER_TYPE_VALUES = ("hospital", "hcp")


def upgrade() -> None:
    bind = op.get_bind()

    onboarding_status = sa.Enum(*ONBOARDING_STATUS_VALUES, name="onboarding_status")
    onboarding_owner_type = sa.Enum(*ONBOARDING_OWNER_TYPE_VALUES, name="onboarding_owner_type")
    onboarding_status.create(bind, checkfirst=True)
    onboarding_owner_type.create(bind, checkfirst=True)

    op.create_table(
        "specializations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_specializations_name", "specializations", ["name"], unique=True)

    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("registration_number", sa.String(length=120), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*ONBOARDING_STATUS_VALUES, name="onboarding_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_hospitals_registration_number", "hospitals", ["registration_number"], unique=True
    )
    op.create_index("ix_hospitals_status", "hospitals", ["status"])
    op.create_index("ix_hospitals_created_by_user_id", "hospitals", ["created_by_user_id"])

    op.create_table(
        "hospital_admins",
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_hospital_admins_user_id", "hospital_admins", ["user_id"])

    op.create_table(
        "hcp_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("license_number", sa.String(length=120), nullable=False),
        sa.Column("license_authority", sa.String(length=255), nullable=True),
        sa.Column(
            "primary_specialization_id",
            sa.Integer(),
            sa.ForeignKey("specializations.id"),
            nullable=False,
        ),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("consultation_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "consultation_fee_currency", sa.String(length=3), nullable=False, server_default="USD"
        ),
        sa.Column(
            "requested_hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=True
        ),
        sa.Column(
            "status",
            sa.Enum(*ONBOARDING_STATUS_VALUES, name="onboarding_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_hcp_profiles_user_id", "hcp_profiles", ["user_id"], unique=True)
    op.create_index("ix_hcp_profiles_status", "hcp_profiles", ["status"])
    op.create_index(
        "ix_hcp_profiles_requested_hospital_id", "hcp_profiles", ["requested_hospital_id"]
    )

    op.create_table(
        "hospital_affiliations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(length=30), nullable=False, server_default="onboarding"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_hospital_affiliations_user_id", "hospital_affiliations", ["user_id"])
    op.create_index(
        "ix_hospital_affiliations_active_unique",
        "hospital_affiliations",
        ["hospital_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "onboarding_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_type",
            sa.Enum(*ONBOARDING_OWNER_TYPE_VALUES, name="onboarding_owner_type", create_type=False),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_onboarding_documents_owner", "onboarding_documents", ["owner_type", "owner_id"]
    )
    op.create_index(
        "ix_onboarding_documents_owner_doc_type",
        "onboarding_documents",
        ["owner_type", "owner_id", "document_type"],
        unique=True,
    )

    op.create_table(
        "onboarding_status_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_type",
            sa.Enum(*ONBOARDING_OWNER_TYPE_VALUES, name="onboarding_owner_type", create_type=False),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_onboarding_status_events_owner",
        "onboarding_status_events",
        ["owner_type", "owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("onboarding_status_events")
    op.drop_table("onboarding_documents")
    op.drop_table("hospital_affiliations")
    op.drop_table("hcp_profiles")
    op.drop_table("hospital_admins")
    op.drop_table("hospitals")
    op.drop_table("specializations")

    bind = op.get_bind()
    sa.Enum(name="onboarding_owner_type").drop(bind, checkfirst=True)
    sa.Enum(name="onboarding_status").drop(bind, checkfirst=True)
