# AI HR Assistant — Architecture Document (v1)

**Project codename suggestion:** *Nexa* / *HRPilot* / *TeamDesk AI* (pick one, or keep working name)
**Scope for v1:** Single-tenant, designed so multi-tenancy can be added later without a schema rewrite.
**Vector store:** ChromaDB
**Primary backend language:** Python (FastAPI)

---

## 1. High-Level Project Overview

### What this application is
A self-service HR platform for small, HR-less startups (like Cogninest AI) — replacing "ask the CEO directly" with a portal plus an AI chatbot that can answer policy questions, handle leave requests, and keep department-specific knowledge properly access-controlled.

### Core features
- **AI Chatbot** — employees can ask natural-language questions about company policies, department-specific guidelines, and their own leave status/balance. Answers are grounded in uploaded documents (RAG) or live data (for things like leave balance), never guessed.
- **Knowledge Base management** — admins and the CEO can upload, edit, and organize policy documents. Documents are tagged as either org-wide (visible to everyone) or department-specific (visible only to that department).
- **Leave management** — employees apply for leave, track balances, view request history; admins/CEO approve or reject requests through a defined approval chain.
- **Role-based access control (RBAC)** — every feature (KB, leave, user management) respects who the requester is and what they're allowed to see or do.
- **Invite-based onboarding** — no open signup; every account is created via an invite from someone above them in the hierarchy.
- **Audit trail** — every sensitive action (leave decisions, KB changes, chatbot answers) is logged, so admins/CEO can review what happened and what the bot told people.

### Roles
- **Super Admin (CEO)** — one per organization. Full access: can manage all departments, invite department admins, upload/edit org-wide and any department's KB documents, approve/reject any leave request, and view all audit logs.
- **Department Admin** — the "department HR" equivalent (e.g., Engineering lead, Sales lead). Can invite employees into their own department only, manage their department's KB documents, and approve/reject leave requests from employees in their department.
- **Employee** — normal user. Can chat with the bot, view/apply for leave, see their own leave history and balance, and read KB documents belonging to their department plus any org-wide documents. No write access to KB or user management.

### How each role gets registered
- **Super Admin (CEO):** created through a one-time "Create Organization" signup — this is the *only* self-service registration path in the whole app, since there's no one above the CEO to issue an invite. This creates both the organization and the CEO's own account together.
- **Department Admin:** invited by the Super Admin, who specifies the person's email, assigns them to a department, and grants the Department Admin role. The invitee receives a link to set their password and activate their account.
- **Employee:** invited by their Department Admin (or by the Super Admin, if needed), scoped to that admin's own department. Same accept-invite-and-set-password flow.
- There is intentionally **no open "sign up" page** anywhere else in the app — every account beyond the founding CEO account is created by invitation from someone with the authority to do so, which keeps the org's membership fully controlled.

### How RBAC works (conceptually)
- Every user has exactly one **role** (Super Admin / Department Admin / Employee) and, except for the Super Admin, belongs to exactly one **department**.
- Role determines *what actions* a user can perform (invite people, upload documents, approve leave, etc.).
- Department membership determines *what scope* those actions apply to — a Department Admin's permissions are always bounded to their own department, never another one.
- Every feature in the app — the chatbot's document retrieval, the leave approval routing, the KB editing screens, the invite flow — checks against this same role + department combination, so the rules stay consistent everywhere rather than being reimplemented differently per feature.
- The guiding principle: permissions are enforced centrally and on the backend, never assumed from what the frontend chooses to show.

---

## 2. Goals & Non-Goals

**Goals**
- Replace "ask the CEO directly" with a self-service portal + AI assistant for policies, leave, and general HR queries.
- Enforce strict department-scoped access to knowledge base content — this is a security requirement, not a UX nicety.
- Be genuinely production-grade: proper auth, audit trails, tested, deployable, observable.
- Be a strong learning vehicle for DBMS, backend architecture, and RAG systems.

**Explicit non-goals for v1**
- Payroll/payslip generation (Ultimatix-style payslips) — out of scope initially, flag as a future module.
- Multi-tenant billing/subscription logic — design for it, don't build it yet.
- Mobile app — web-responsive only for v1.

---

## 3. High-Level Architecture

```
                        ┌─────────────────────┐
                        │   React Frontend     │
                        │  (role-aware UI)     │
                        └──────────┬───────────┘
                                   │ HTTPS/JWT
                        ┌──────────▼───────────┐
                        │   FastAPI Backend     │
                        │  ┌─────────────────┐  │
                        │  │ Auth Service     │  │
                        │  │ RBAC Middleware  │  │
                        │  │ Leave Service    │  │
                        │  │ KB Admin Service │  │
                        │  │ Chat/RAG Service │  │
                        │  └─────────────────┘  │
                        └──┬───────────┬────────┘
                           │           │
                 ┌─────────▼──┐   ┌────▼─────────┐
                 │ PostgreSQL │   │  ChromaDB     │
                 │ (system of │   │ (KB embeddings,
                 │  record)   │   │  metadata-    │
                 │            │   │  filtered)    │
                 └────────────┘   └───────────────┘
                                          │
                                   ┌──────▼───────┐
                                   │ LLM Provider  │
                                   │ (Claude API)  │
                                   └───────────────┘
```

Everything — leave requests, KB documents, audit logs — is scoped through the same permission layer. There is exactly **one** place in the code that decides "can this user see this thing," and both the REST API and the RAG retrieval path call into it. Don't duplicate this logic between the chatbot and the regular CRUD endpoints.

---

## 4. Data Model (PostgreSQL)

Core tables — this is also your DBMS practice ground for normalization, foreign keys, and transactions.

```sql
-- Organizations (kept even in single-tenant v1, so multi-tenant later = no migration pain)
organizations (
  id UUID PK,
  name TEXT,
  created_at TIMESTAMPTZ
)

departments (
  id UUID PK,
  org_id UUID FK -> organizations,
  name TEXT,              -- 'Engineering', 'Sales', 'Marketing'
  created_at TIMESTAMPTZ
)

users (
  id UUID PK,
  org_id UUID FK -> organizations,
  department_id UUID FK -> departments NULL,  -- NULL only for SUPER_ADMIN
  email TEXT UNIQUE,
  password_hash TEXT,
  full_name TEXT,
  role TEXT CHECK (role IN ('SUPER_ADMIN','DEPT_ADMIN','EMPLOYEE')),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ
)

leave_types (
  id UUID PK,
  org_id UUID FK,
  name TEXT,               -- 'Casual Leave', 'Sick Leave', 'Earned Leave'
  annual_quota INT
)

leave_balances (
  id UUID PK,
  user_id UUID FK,
  leave_type_id UUID FK,
  year INT,
  allocated NUMERIC,
  used NUMERIC,
  UNIQUE(user_id, leave_type_id, year)
)

leave_requests (
  id UUID PK,
  user_id UUID FK,
  leave_type_id UUID FK,
  start_date DATE,
  end_date DATE,
  status TEXT CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED')),
  approver_id UUID FK -> users NULL,
  reason TEXT,
  created_at TIMESTAMPTZ,
  decided_at TIMESTAMPTZ NULL
)

kb_documents (
  id UUID PK,
  org_id UUID FK,
  department_id UUID FK NULL,  -- NULL = org-wide document (visible to everyone)
  title TEXT,
  source_type TEXT,            -- 'policy_doc','faq','manual_entry'
  uploaded_by UUID FK -> users,
  chroma_collection TEXT,      -- which Chroma collection this lives in
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ
)

audit_logs (
  id UUID PK,
  org_id UUID FK,
  actor_id UUID FK -> users,
  action TEXT,             -- 'LEAVE_APPROVED','KB_DOC_UPLOADED','CHAT_QUERY', etc.
  target_type TEXT,
  target_id UUID NULL,
  metadata JSONB,           -- for chat: retrieved doc ids, department scope used
  created_at TIMESTAMPTZ
)

chat_sessions (
  id UUID PK,
  user_id UUID FK,
  started_at TIMESTAMPTZ
)

chat_messages (
  id UUID PK,
  session_id UUID FK,
  role TEXT CHECK (role IN ('user','assistant')),
  content TEXT,
  retrieved_doc_ids UUID[] NULL,   -- traceability: what the bot actually used
  created_at TIMESTAMPTZ
)
```

**Key DBMS lessons baked in here:** foreign key integrity, check constraints for enums, `UNIQUE` constraints to prevent duplicate balance rows, JSONB for flexible audit metadata, and transactional leave-balance updates (deduct `used` and insert `leave_requests` row in one transaction).

---

## 5. RBAC Model

| Role | KB Write | KB Read Scope | Leave Approve | User Mgmt | Org Policy Mgmt |
|---|---|---|---|---|---|
| SUPER_ADMIN (CEO) | All departments | All | All requests | Full | Full |
| DEPT_ADMIN | Own department only | Own dept + org-wide | Own dept's employees | View own dept | None |
| EMPLOYEE | None | Own dept + org-wide | Own requests only (create/cancel) | None | None |

Implementation approach: a single `check_permission(user, action, resource)` function used everywhere — API route dependencies in FastAPI (`Depends(require_permission(...))`) and inside the RAG retrieval service. Never re-implement scope logic separately in the chatbot code path.

---

## 6. RAG Pipeline with Access Control (the critical component)

**Ingestion:**
1. Admin/CEO uploads a document (or types an FAQ entry) → tagged with `department_id` (or `org_wide`).
2. Chunk the document, embed each chunk, store in ChromaDB **with metadata**: `{org_id, department_id, doc_id}`.
3. Store the document record in Postgres (`kb_documents`) for admin-facing management (edit/delete/versioning).

**Retrieval (on every chat query):**
1. Resolve the requesting user's accessible `department_id`s: `[user.department_id, None]` (None = org-wide docs). SUPER_ADMIN gets all department IDs.
2. Query Chroma with a **metadata filter** (`where={"department_id": {"$in": accessible_ids}}`) — the filter must be applied *at query time*, not by post-filtering the results after retrieval. This is the difference between "the LLM never sees the disallowed content" and "we hope the LLM ignores it."
3. Pass only the filtered chunks into the LLM context, along with a system prompt that instructs the model to answer only from provided context and to say "I don't have that information" rather than guessing.
4. Log the query + the exact `doc_ids` retrieved into `chat_messages.retrieved_doc_ids` and `audit_logs` — this gives admins an audit trail of what the bot told whom, and lets you debug wrong answers.

**Why this matters:** if you filter *after* retrieval (e.g., fetch top-10 chunks across all departments, then discard the ones the user can't see), the LLM's context window may still have seen disallowed content before you strip it, and a clever prompt could get it to leak details anyway. Filter at the vector-store query, not after.

---

## 7. Chat Flow (end to end)

1. User sends message → FastAPI `/chat` endpoint (JWT validates identity + role + department).
2. Retrieve conversation history from `chat_sessions`/`chat_messages` for context.
3. Run access-scoped retrieval against Chroma (Section 6).
4. Construct prompt: system instructions + retrieved chunks + chat history + user query.
5. Call Claude API, stream response back to frontend.
6. Persist assistant message + `retrieved_doc_ids` + write `audit_logs` entry.
7. Optional: thumbs up/down feedback stored against the message, surfaced to the relevant DEPT_ADMIN for KB improvement.

---

## 8. Auth & Security

- **Password auth:** bcrypt/argon2 hashing, never store plaintext.
- **Tokens:** short-lived JWT access token (~15 min) + refresh token (httpOnly cookie), rotate refresh tokens on use.
- **Authorization:** enforced server-side via FastAPI dependency injection, never trust frontend role checks.
- **Rate limiting:** per-user rate limit on `/chat` (cost control + abuse prevention).
- **Input validation:** Pydantic schemas on every endpoint.
- **Secrets:** environment variables / secrets manager, never committed.
- **Transport:** HTTPS everywhere, secure cookies.
- **Stretch goal:** OAuth2/OIDC SSO support (Google Workspace login) — realistic for a startup context.

---

## 9. Leave Request State Machine

```
PENDING --approve--> APPROVED
PENDING --reject--> REJECTED
PENDING --cancel (by requester)--> CANCELLED
APPROVED --cancel (by requester, before start_date)--> CANCELLED
```

Balance deduction happens only on `APPROVED`, inside a DB transaction alongside the status update, so balance and status can never drift out of sync.

---

## 10. Suggested Project Structure

```
backend/
  app/
    core/           # config, security, db session
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    api/
      auth.py
      users.py
      departments.py
      leave.py
      kb.py
      chat.py
    services/
      rbac.py       # single source of truth for permission checks
      rag_service.py
      leave_service.py
    db/
      migrations/   # Alembic
  tests/
frontend/
  src/
    pages/
    components/
    hooks/
    api/
```

---

## 11. Multi-Tenancy Readiness (for later)

Because `organizations` and `org_id` are already on every table, moving to multi-tenant later mainly means: adding an org-selection/signup flow, enforcing `org_id` scoping in every query (already required for RBAC anyway), and separate Chroma collections or metadata namespacing per org. No schema rewrite needed if you follow this from day one.

---

## 12. Phased Build Roadmap

**Phase 1 — Foundations**
- Postgres schema + Alembic migrations
- Auth (signup/login/JWT), RBAC middleware
- User & department CRUD (SUPER_ADMIN only)

**Phase 2 — Leave Management**
- Leave types, balances, request/approve/reject flow
- Audit logging for approvals

**Phase 3 — Knowledge Base + RAG core**
- Document upload/ingestion pipeline
- ChromaDB integration with metadata filtering
- Basic chat endpoint (no history yet), access-scoped retrieval

**Phase 4 — Full Chat Experience**
- Conversation history, streaming responses
- Feedback loop (thumbs up/down → routed to DEPT_ADMIN)
- Audit trail UI for admins

**Phase 5 — Polish for "production-grade"**
- Tests (unit + integration, especially RBAC boundary tests)
- Rate limiting, logging/observability (structured logs, maybe OpenTelemetry)
- Dockerize, CI/CD, deployment (Render/Railway/AWS)
- Basic admin analytics dashboard (leave trends, most-asked bot questions)

---

## 13. Testing Priorities (don't skip these)

The highest-value tests for this project are **RBAC boundary tests** — e.g., "Sales employee queries the bot about Engineering's on-call policy → must not receive that content." Write these before you write the happy-path tests; they're what makes this "production-grade" rather than "demo-grade."

---

## 14. Onboarding & Invite Flow

**High-level application flow (agreed):**
1. CEO creates the organization, invites department admins, uploads org-wide policy documents.
2. Each DEPT_ADMIN invites employees into their department, uploads department-specific KB documents.
3. Employees use the app, interact with the chatbot, apply for leave.

### 13.1 Org bootstrapping (CEO signup)
- One-time "Create Organization" flow — no invite required, since no admin exists yet.
- CEO submits org name + their own email/password.
- Backend creates `organizations` row + a `users` row with `role = SUPER_ADMIN`, `department_id = NULL`, in a single transaction.
- Recommended: email verification on this step specifically, since it's the highest-privilege account in the system.

### 13.2 Everyone else joins via invite only — no public signup endpoint
- SUPER_ADMIN invites DEPT_ADMINs (assigns department + role). DEPT_ADMIN invites EMPLOYEEs into their own department only (enforce via RBAC — a DEPT_ADMIN cannot invite into a department they don't own).
- Backend creates a `users` row with `is_active = FALSE` and a signed, time-limited invite token.
- Invite email sent with a link (`/accept-invite?token=...`).
- Invitee sets password, backend verifies token, flips `is_active = TRUE`, marks `invites.accepted_at`.
- No open `/register` endpoint should exist — this is what prevents unauthorized signups into the org.

**Schema addition:**
```sql
invites (
  id UUID PK,
  org_id UUID FK,
  email TEXT,
  department_id UUID FK NULL,
  role TEXT,
  token_hash TEXT,          -- store hashed, never raw
  invited_by UUID FK -> users,
  expires_at TIMESTAMPTZ,
  accepted_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ
)
```
Re-invites/expiry: issue a new token row rather than mutating the old one, to keep a clean audit trail of every invite attempt.

---

## 15. Leave Application & Approval Workflow

### 14.1 Approval routing (resolved at request-creation time, stored explicitly)
```
EMPLOYEE's leave     → approved by their DEPT_ADMIN
DEPT_ADMIN's leave   → approved by SUPER_ADMIN (CEO)
SUPER_ADMIN's leave  → self-approved / auto-logged
```
Store the resolved `approver_id` directly on the `leave_requests` row rather than recomputing it later, so history stays accurate even if org admins change afterward.

**Edge case:** if a department currently has no active DEPT_ADMIN, escalate the approver to SUPER_ADMIN automatically rather than leaving it unresolved.

### 14.2 Request creation — server-side validation (never trust the frontend)
1. **Balance check**: `allocated - used >= requested_days` for that leave type/year; reject before row creation if insufficient.
2. **Date sanity**: `end_date >= start_date`; policy decision needed on whether backdated requests (e.g., sick leave) are allowed.
3. **Overlap check**: no existing `PENDING`/`APPROVED` request for the same user with overlapping dates.
4. **Working-days calculation**: decide whether weekends/holidays count against balance — if yes, requires an `org_holidays` table for accuracy.

On success: insert `leave_requests` with `status = PENDING`; write `audit_logs` (`LEAVE_REQUESTED`).

### 14.3 Approval action
- Endpoint-level RBAC: a DEPT_ADMIN may only act on requests where `approver_id = self`.
- **On approve** (single DB transaction):
  - `leave_requests.status = 'APPROVED'`, `decided_at = now()`
  - `leave_balances.used += requested_days`
  - `audit_logs` entry (`LEAVE_APPROVED`)
- **On reject**: update status + reason + audit log only, no balance change.

Transactional coupling of status update + balance deduction is required — without it, a crash mid-operation can produce an approved leave with no balance deducted.

### 14.4 Cancellation
- `PENDING`: requester self-cancels anytime, no approver involvement.
- `APPROVED`: requester may cancel before `start_date`; balance is restored in a transaction. (v1 policy: auto-cancel, no re-approval required.)

### 14.5 Notifications (v1 scope)
- In-app "pending approvals" badge for admins/CEO (`COUNT(*) WHERE approver_id = me AND status = 'PENDING'`).
- Email notifications on submit/decision — defer to Phase 5, reuse the invite email mechanism.

### 14.6 Chatbot integration for leave queries
Route chatbot intents into two paths:
- **Structured data queries** ("how many leaves do I have left?", "what's the status of my last request?") → direct SQL query against `leave_balances`/`leave_requests`, not RAG. Live numbers must never be embedded into KB documents, since they'd drift out of date immediately.
- **Policy questions** ("how much notice do I need to give?") → RAG pipeline against the KB (Section 6).

The chat service needs an intent-routing step before deciding whether to hit structured data or the vector store.

