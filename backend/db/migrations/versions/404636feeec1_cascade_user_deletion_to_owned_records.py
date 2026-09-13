"""cascade user deletion to owned records

Revision ID: 404636feeec1
Revises: 98258e712cc2
Create Date: 2026-09-13 13:30:54.609054

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '404636feeec1'
down_revision: Union[str, Sequence[str], None] = '98258e712cc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    None of these FKs to users.id had an ON DELETE rule, so DELETE /users/{id}
    failed outright for any user with even one row in these tables (any admin
    who'd sent an invite, any employee with a chat/leave history). This makes
    deleting a user actually delete what THEY created/own along with them -
    except leave_requests.approver_id, which is deliberately SET NULL rather
    than CASCADE: that FK points at the approver, not the request's owner, so
    cascading it would delete a *different* employee's leave request just
    because the person who approved it was later removed.
    """
    op.drop_constraint("invites_invited_by_fkey", "invites", type_="foreignkey")
    op.create_foreign_key(
        "invites_invited_by_fkey", "invites", "users", ["invited_by"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("audit_logs_actor_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_actor_id_fkey", "audit_logs", "users", ["actor_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("chat_sessions_user_id_fkey", "chat_sessions", type_="foreignkey")
    op.create_foreign_key(
        "chat_sessions_user_id_fkey", "chat_sessions", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("kb_documents_uploaded_by_fkey", "kb_documents", type_="foreignkey")
    op.create_foreign_key(
        "kb_documents_uploaded_by_fkey", "kb_documents", "users", ["uploaded_by"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("leave_balances_user_id_fkey", "leave_balances", type_="foreignkey")
    op.create_foreign_key(
        "leave_balances_user_id_fkey", "leave_balances", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("leave_requests_user_id_fkey", "leave_requests", type_="foreignkey")
    op.create_foreign_key(
        "leave_requests_user_id_fkey", "leave_requests", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("leave_requests_approver_id_fkey", "leave_requests", type_="foreignkey")
    op.create_foreign_key(
        "leave_requests_approver_id_fkey", "leave_requests", "users", ["approver_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("leave_requests_approver_id_fkey", "leave_requests", type_="foreignkey")
    op.create_foreign_key(
        "leave_requests_approver_id_fkey", "leave_requests", "users", ["approver_id"], ["id"]
    )

    op.drop_constraint("leave_requests_user_id_fkey", "leave_requests", type_="foreignkey")
    op.create_foreign_key(
        "leave_requests_user_id_fkey", "leave_requests", "users", ["user_id"], ["id"]
    )

    op.drop_constraint("leave_balances_user_id_fkey", "leave_balances", type_="foreignkey")
    op.create_foreign_key(
        "leave_balances_user_id_fkey", "leave_balances", "users", ["user_id"], ["id"]
    )

    op.drop_constraint("kb_documents_uploaded_by_fkey", "kb_documents", type_="foreignkey")
    op.create_foreign_key(
        "kb_documents_uploaded_by_fkey", "kb_documents", "users", ["uploaded_by"], ["id"]
    )

    op.drop_constraint("chat_sessions_user_id_fkey", "chat_sessions", type_="foreignkey")
    op.create_foreign_key(
        "chat_sessions_user_id_fkey", "chat_sessions", "users", ["user_id"], ["id"]
    )

    op.drop_constraint("audit_logs_actor_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_actor_id_fkey", "audit_logs", "users", ["actor_id"], ["id"]
    )

    op.drop_constraint("invites_invited_by_fkey", "invites", type_="foreignkey")
    op.create_foreign_key(
        "invites_invited_by_fkey", "invites", "users", ["invited_by"], ["id"]
    )
