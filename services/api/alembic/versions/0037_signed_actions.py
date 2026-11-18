"""approval actions record the specimen signature that signed them

Revision ID: 0037
Revises: 0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approval_actions",
        sa.Column(
            "signature_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.signatures.id")
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("approval_actions", "signature_id", schema="core")
