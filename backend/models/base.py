from backend.db.database import Base

# Import every model here so Alembic's autogenerate can discover them via
# Base.metadata. A model class that's never imported never registers its
# table, and Alembic would silently omit it from the migration.
from backend.models.organization import Organization
from backend.models.organization_signup import OrganizationSignupRequest
from backend.models.department import Department
from backend.models.user import User
from backend.models.invite import Invite
from backend.models.leave import LeaveType, LeaveBalance, LeaveRequest
from backend.models.holiday import OrgHoliday
from backend.models.knowledge_base import KBDocument
from backend.models.audit import AuditLog
from backend.models.chat import ChatSession, ChatMessage
