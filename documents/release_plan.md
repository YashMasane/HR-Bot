# HR Bot Platform: Architecture & Release Roadmap

## Executive Summary & Industry Impact
The HR Bot is a production-grade, Multi-Agent SaaS platform designed for early-stage startups (100–500 employees). By centralizing company knowledge, departmental policies, and HR workflows into an intelligent conversational interface, this platform automates routine operations. It reduces administrative overhead for founders, ensures compliance with organizational policies, and improves the employee experience through instant self-service.

## User Roles & Onboarding
* **Super Admin (CEO / Founder):** Creates the company tenant, manages global settings, handles the primary knowledge base, and assigns Department Admins.
* **Department Admin (Divisional HR):** Manages division-specific policies, oversees departmental leave requests, and views specific analytics.
* **Employee:** Interacts with the bot for queries, leave scheduling, and resource requests. Onboarded strictly via company email or SSO to prevent unauthorized access.

## Multi-Agent RAG Architecture
The backend utilizes LangGraph for agent orchestration, implementing strict RBAC at the vector-search level using PostgreSQL (`pgvector`).
* **Supervisor Agent (Router):** Analyzes user intent, verifies RBAC tokens, and routes the task to the appropriate worker agent.
* **Policy RAG Agent:** Executes vector searches with metadata filtering (e.g., matching the user's specific department ID or 'Global').
* **HR Operations Agent:** Handles structured PostgreSQL CRUD operations, such as checking leave balances or holiday calendars.
* **Ticketing & Communications Agent:** Gathers resource requirements and dispatches formatted emails to admins.
* **Security & Guardrails:** Sanitizes prompts against jailbreaks and masks PII before LLM processing.

## Version Release Strategy

| Version | Theme | Target Features |
| :--- | :--- | :--- |
| **v1.0 (MVP)** | Foundation & Global RAG | PostgreSQL schema, JWT Auth, Global Knowledge Base, simple chatbot for company-wide queries. |
| **v2.0** | Departmental Filtering | Department Admin roles, vector metadata filtering by division, leave balance querying, basic leave submission. |
| **v3.0** | Multi-Agent & Automations | LangGraph Supervisor, resource request SMTP/Email dispatch, security guardrails (PII masking). |
| **v4.0** | Observability & Scaling | Admin UI for leave approval, LangSmith tracing, full multi-tenant isolation, model-agnostic LLM toggling. |