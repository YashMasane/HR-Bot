from sqlalchemy import Column, DateTime, Enum, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import ChatMessageRole
from backend.models.mixins import UUIDPKMixin, utcnow


class ChatSession(Base, UUIDPKMixin):
    """A conversation. `langgraph_thread_id` is the *only* link to LangGraph's
    own state - the actual conversation graph/checkpoint data lives in tables
    managed entirely by LangGraph's PostgresSaver, not here. This table exists
    so we can list/scope/RBAC-filter conversations without touching LangGraph
    internals at all.
    """

    __tablename__ = "chat_sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    langgraph_thread_id = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_active_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base, UUIDPKMixin):
    __tablename__ = "chat_messages"

    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        Enum(ChatMessageRole, name="chat_message_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    # Which kb_documents fed this answer - the traceability piece from
    # architecture doc section 6/7. Nullable because user messages and
    # structured-data answers (leave balance lookups) won't have any.
    retrieved_doc_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    # Which LangGraph node produced this message - e.g. "policy_rag_agent" vs
    # "hr_ops_agent" - useful once we're routing between multiple agents.
    agent_route = Column(String(50), nullable=True)
    feedback = Column(SmallInteger, nullable=True)  # -1 / 0 / 1
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    session = relationship("ChatSession", back_populates="messages")
