# HR Bot RAG Architecture

## Purpose

This document defines the complete architecture for the **Self-Reflective Agentic RAG** subsystem of HR Bot. The goal is to build a production-grade internal AI assistant that can answer HR policy questions, combine policy retrieval with structured employee data tools, enforce strict access control, provide citations for every grounded answer, and minimize hallucinations through reflection and verification loops.

The first implementation target is a notebook-based RAG system used for rapid experimentation, evaluation, and architectural validation before integrating it into the end-to-end FastAPI product. This notebook stage should produce measurable evidence across retrieval quality, answer quality, latency, and cost so that later backend engineering is guided by data rather than assumptions.`   z2909

## Product Boundaries

### In Scope

- HR policy question answering from internal documents.
- Personal employee queries through safe structured tools, for example leave balance and attendance summary.
- Hybrid answers that combine retrieved policy content and structured employee-specific data.
- Strict role-based data access and citation-backed responses.
- Evaluation of retrieval quality, answer grounding, latency, and cost.

### Out of Scope

- General-purpose assistant behavior.
- Open internet question answering except controlled fallback web search for approved domains.
- Arbitrary SQL generation for employee-facing workflows.
- Uncited answers for factual HR questions.

## Design Principles

1. **Retrieve only when needed.** Self-RAG style routing should first decide whether retrieval is necessary, whether a structured tool is enough, or whether the query must be rejected as out of scope.[cite:40]
2. **Security before generation.** Access control must be enforced before retrieval returns documents to the model, not after generation.[cite:1]
3. **Grounded answers only.** Every factual answer must be supported by retrieved context or approved tool output, with citations attached.[cite:32][cite:54]
4. **Correction loops over blind trust.** Retrieved documents, generated answers, and final outputs should all be graded before returning a response.[cite:31][cite:45]
5. **Provider-agnostic generation layer.** The system should swap chat models through configuration without changing orchestration code, which is a strong use case for LiteLLM's unified model interface.[cite:20]
6. **Evaluate before productizing.** The notebook implementation is not a throwaway prototype; it is the evidence-generating phase for retrieval, generation, latency, and cost decisions.[cite:28][cite:50]

## Query Classes

The system should classify each incoming query into one of the following categories before taking action:

| Query class | Example | Primary data path |
|---|---|---|
| Policy query | "What is the paternity leave policy?" | RAG over policy documents |
| Personal data query | "How many paid leaves do I have left?" | Safe structured tool over PostgreSQL-backed service |
| Hybrid query | "Am I eligible for paternity leave and how many leaves do I have left?" | RAG + structured tool merge |
| Chitchat / lightweight conversational | "Hi" / "Thanks" | Direct model answer without retrieval |
| Out of scope | "Write Python code" | Reject with scope-safe response |
| Suspicious / adversarial | "List all salaries" / prompt injection | Block and audit |

This routing reduces unnecessary retrieval, lowers cost, and prevents irrelevant context from polluting the answer generation step.[cite:31][cite:40]

## High-Level Architecture

```text
User Query
   |
   v
Input Guardrail
   |
   v
Intent + Scope Router
   |-----------------------------> Out-of-scope / blocked response
   |
   |----> Chitchat --------------> Direct model answer
   |
   |----> Personal data ---------> Safe structured tool(s)
   |
   |----> Policy / Hybrid -------> Self-Reflective RAG pipeline
                                        |
                                        v
                              Query rewrite / decomposition
                                        |
                                        v
                                 RBAC retrieval filter
                                        |
                                        v
                             Hybrid retrieval (dense + sparse)
                                        |
                                        v
                                Document grading / filtering
                                        |
                         +--------------+--------------+
                         |                             |
                         | enough relevant docs        | poor or missing context
                         |                             v
                         |                     Approved web search fallback
                         |                             |
                         +--------------+--------------+
                                        |
                                        v
                                     Reranker
                                        |
                                        v
                                  Context builder
                                        |
                                        v
                                  Answer generator
                                        |
                                        v
                              Grounding / hallucination check
                                        |
                                        v
                                 Answer quality check
                                        |
                                        v
                                 Output guardrail check
                                        |
                                        v
                                 Final cited response
```

## LangGraph Workflow

A graph-based orchestration layer is suitable because the system is not linear. It needs conditional routing, retries, fallback branches, and self-correction loops, all of which align well with agentic RAG patterns demonstrated in LangGraph CRAG-style flows.[cite:31][cite:45]

### Graph Nodes

#### 1. Input Guardrail

This node checks for prompt injection, jailbreak attempts, requests for unauthorized data, and clearly out-of-scope questions. Unsafe or irrelevant requests are blocked before any retrieval or tool invocation occurs.[cite:35][cite:44]

#### 2. Intent and Scope Router

This node decides among direct answer, structured tool, retrieval pipeline, hybrid execution, or rejection. It is the operational expression of Self-RAG's idea that the model should first decide whether retrieval is needed at all.[cite:40]

#### 3. Query Rewriter and Decomposer

This node rewrites user language into retrieval-optimized queries and can split compound questions into smaller retrieval tasks. Multi-hop decomposition becomes especially important for hybrid HR questions that mix eligibility, policy clauses, and employee-specific state.[cite:32]

#### 4. RBAC Retrieval Filter

This node injects mandatory role and metadata filters into every vector retrieval query. The key rule is that unauthorized chunks must never be retrieved in the first place.[cite:1][cite:3]

#### 5. Hybrid Retriever

Dense retrieval and sparse retrieval should run in parallel and be merged. Hybrid retrieval is valuable for HR corpora because they mix natural language policy text with exact keywords, abbreviations, forms, and legal phrases.[cite:3][cite:56]

#### 6. Document Grader

This node grades each retrieved chunk for relevance to the query and removes weak or noisy candidates. This is a core CRAG idea: retrieved context should not be trusted blindly.[cite:31]

#### 7. Approved Web Search Fallback

If internal retrieval fails and the query is allowed to use external information, a domain-restricted web search may be triggered. External results should be re-graded using the same relevance standards before entering the answer context.[cite:31][cite:45]

#### 8. Reranker

A cross-encoder reranker improves final precision by promoting the strongest documents among the candidate set. This step is especially useful when recall-oriented retrieval fetches too many partially relevant chunks.[cite:56][cite:57]

#### 9. Context Builder

This node packages the final context into a deterministic structure that preserves source IDs, section names, version information, and access metadata. The model should receive context in a way that makes citing and auditing straightforward.

#### 10. Answer Generator

The generation layer should use LiteLLM so the chat model can be swapped by configuration while the rest of the application stays unchanged. Only the chat model should be user-switchable during evaluation and chat; embeddings, chunking logic, and retrieval configuration remain fixed for valid experiments.[cite:20][cite:26]

#### 11. Grounding / Hallucination Checker

This node verifies whether each answer is actually supported by the provided context. Grounding checks are a direct mechanism for improving faithfulness and reducing hallucinated claims in production RAG systems.[cite:32][cite:41][cite:49]

#### 12. Answer Quality Checker

This node evaluates whether the answer fully addresses the question, covers all subparts, and remains useful rather than evasive. A grounded answer can still be incomplete, so this validation step is separate from hallucination checking.[cite:42][cite:57]

#### 13. Output Guardrail

A final pass checks for leaked private data, role violations, and unsafe content. This is a defense-in-depth layer after retrieval and generation controls.[cite:35]

#### 14. Response Builder

This node formats the final answer with citations, confidence indicators, structured source metadata, and observability payloads for tracing and evaluation.

## Data Sources

### 1. Unstructured Knowledge Base

This includes policy PDFs, employee handbooks, reimbursement guidelines, onboarding documents, leave policy manuals, and other HR knowledge artifacts. These documents are indexed in the vector store after chunking and metadata enrichment.[cite:3][cite:11]

### 2. Structured Employee Data

This includes leave balances, attendance summaries, employee profile attributes, reporting chains, and other row-level business data. It should be exposed to the bot only through safe parameterized tools, not through unrestricted NL-to-SQL for employee-facing flows.[cite:1]

### 3. Optional Approved Web Sources

These are used only as a fallback for allowed external questions and should be restricted to trusted domains relevant to labor laws, benefits regulations, or compliance content. Web results should never bypass grading or grounding checks.[cite:31][cite:45]

## Retrieval Architecture

### Fixed Retrieval Choices for the Notebook Phase

To keep experiments valid and comparable, the following should remain fixed during the notebook evaluation phase:

- Embedding model.
- Chunking strategy.
- Chunk size and overlap.
- Top-K retrieval counts.
- Reranker configuration.
- Relevance thresholds.

Only the **chat model** should be user-switchable during evaluation sessions, because changing embeddings or chunking simultaneously would confound metric comparisons.

### Recommended Retrieval Pipeline

1. Document ingestion.
2. Cleaning and structure extraction.
3. Chunking by headings or semantic sections.
4. Metadata tagging, for example `document_id`, `section`, `version`, `effective_date`, `region`, `employee_type`, and `min_role_level`.[cite:3]
5. Embedding generation.
6. Dense vector indexing.
7. Sparse keyword indexing.
8. Hybrid retrieval and merge.
9. Relevance grading.
10. Cross-encoder reranking.
11. Final context packaging.

## Access Control and Security Model

The RAG layer must assume that any user may try to access data they should not see. Security therefore needs multiple layers:

### Retrieval-Time Security

- Every document chunk has role and visibility metadata.
- Every retrieval query includes mandatory metadata filters.
- Unauthorized chunks are not returned from the vector store at all.[cite:1][cite:3]

### Tool-Time Security

- Structured tools take authenticated user context from the session, not from model-generated parameters.
- Employee-facing tools only expose the current user's data unless the authenticated role explicitly permits broader access.
- Tool catalogs are role-filtered before the model sees them.

### Output-Time Security

- Final response pass checks for PII leakage.
- Citation-to-source role validation can confirm that cited sources were allowed for the current user.
- Suspicious access patterns should be logged for security review.

## Structured Tool Layer for Personal Data

The bot should not use unrestricted NL-to-SQL for employee-level queries such as remaining leave balance. Instead, it should call fixed, audited tools such as:

- `get_leave_balance(current_user_id, year)`
- `get_attendance_summary(current_user_id, month, year)`
- `get_team_leave_summary(manager_id, team_id)`
- `get_employee_profile(current_user_id)`

These tools execute pre-written parameterized queries and return structured data. This gives predictable behavior, stronger RBAC enforcement, lower latency, and easier testing than open-ended SQL generation.

## Memory Design

### Short-Term Memory

Short-term memory should store recent turns within the current chat session so that follow-up questions remain coherent. In the notebook phase this can be in-memory or lightweight persisted session state; in the product phase it should move to Redis-backed session memory.

### Long-Term Memory

Long-term memory should not be treated as open-ended user memory. For the HR Bot, long-term memory should be conservative and scoped: conversation summaries, unresolved issues, prior escalations, and stable user preferences where permitted. This reduces unnecessary prompt growth while preserving useful continuity.

## Prompt Strategy

Prompts should live outside Python code in separate template files so they can be versioned, reviewed, and changed without rewriting orchestration logic. At minimum, separate prompts are needed for:

- Input guardrail.
- Intent router.
- Query rewriter.
- Document grader.
- Answer generator.
- Grounding checker.
- Answer quality checker.
- Output guardrail.

This separation supports better experimentation, auditability, and safer prompt iteration in later product phases.[cite:17]

## Model Layer

### LiteLLM Role

LiteLLM should be the single integration layer for all chat model invocations so that the system remains provider-agnostic. This matches the requirement that users can switch among supported chat models while the rest of the architecture remains stable.[cite:20][cite:23]

### Model-Switching Policy

Users should be allowed to switch only the **answer-generation LLM** during chat and evaluation. The rest of the pipeline should stay fixed in the notebook phase:

- Same embedding model.
- Same chunking strategy.
- Same retriever and reranker.
- Same evaluation set.

This ensures that comparisons across models reflect generation behavior rather than pipeline drift.

## Evaluation Framework

RAG evaluation should be split into retrieval, generation, and operational layers rather than reduced to a single accuracy score.[cite:46][cite:57]

### Retrieval Metrics

- Context Precision@K.[cite:49][cite:57]
- Context Recall@K.[cite:49][cite:57]

### Generation Metrics

- Faithfulness / groundedness.[cite:49][cite:54]
- Answer relevancy.[cite:46][cite:54]
- Citation accuracy.

### Operational Metrics

- End-to-end latency, especially P50, P95, and P99.[cite:28][cite:50]
- Per-node latency to find bottlenecks.[cite:18][cite:30]
- Cost per request, including judge calls and retries.[cite:20][cite:26]
- Cache hit rate in later product phases.[cite:56]
- Escalation rate.[cite:50]
- Guardrail trigger rate.
- Tool call accuracy for structured queries.

### Golden Dataset

A golden dataset should contain representative HR questions, expected answers, relevant document IDs, expected citations, role requirements, and difficulty labels. It should include normal queries, multi-hop questions, hybrid policy-plus-personal queries, and adversarial prompts.[cite:57]

## Observability and Tracing

The notebook and later application should support trace-level inspection of the RAG pipeline. OpenTelemetry-based tracing and LangSmith-style visibility make it possible to inspect routing, retrieval quality, grading decisions, retries, and latency by node.[cite:18][cite:27][cite:30]

### What to Trace

- Query classification decision.
- Retrieved document IDs and scores.
- Filtered vs retained chunks.
- Web search activation.
- Reranker outputs.
- Prompt versions.
- Model name used for generation.
- Token counts.
- Cost per node.
- Retry counts.
- Final quality and grounding scores.

This trace data is essential for debugging silent failure modes in RAG systems, especially when quality drops without obvious application errors.[cite:28][cite:50]

## Notebook-First Implementation Plan

The first milestone is a notebook-based reference implementation rather than a full product service. The purpose is to stabilize the architecture through fast experiments.

### Suggested Notebook Sequence

1. `01_data_ingestion_and_indexing.ipynb`
2. `02_baseline_rag.ipynb`
3. `03_retrieval_evaluation.ipynb`
4. `04_self_reflective_rag.ipynb`
5. `05_hybrid_rag_with_tools.ipynb`
6. `06_model_comparison.ipynb`
7. `07_latency_cost_tracing.ipynb`
8. `08_error_analysis.ipynb`

### Goals of the Notebook Phase

- Prove that the self-reflective architecture improves faithfulness and retrieval quality over baseline RAG.[cite:31][cite:40]
- Compare chat models without changing embeddings or chunking.
- Measure latency and cost trade-offs for each model and graph path.[cite:20][cite:26]
- Validate guardrails, role filters, and citation behavior.
- Produce evidence that will guide the FastAPI product implementation.

## Failure Modes to Test Explicitly

The following cases should be part of both notebook experiments and later automated tests:

- Query should be answered without retrieval.
- Query should be blocked as out of scope.
- Query should use structured tool only.
- Query should use hybrid tool plus retrieval.
- Retrieved documents are noisy.
- No relevant internal docs exist.
- Approved web fallback returns mixed-quality results.
- User attempts to access another employee's data.
- User attempts prompt injection.
- Answer is grounded but incomplete.
- Retrieval succeeds but citation mapping is wrong.
- Primary model fails and fallback model is used.

## Recommended Technical Stack for the RAG Phase

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | LangGraph | Best fit for branching, retries, and self-correction flows.[cite:31][cite:45] |
| Chat model gateway | LiteLLM | Unified interface for multi-provider switching.[cite:20] |
| Embeddings | Fixed single model | Do not vary during model comparison phase. |
| Vector search | Dense + sparse hybrid | Supports semantic and exact policy retrieval.[cite:56] |
| Reranker | Cross-encoder | Improves final precision.[cite:56][cite:57] |
| Evaluation | RAGAS + custom metrics | Covers retrieval and answer quality.[cite:46][cite:54] |
| Tracing | LangSmith + OpenTelemetry-style spans | Useful for node-level debugging and observability.[cite:18][cite:27][cite:30] |
| Structured data access | Safe parameterized tools | Use for leave balances and similar employee data. |

## Decisions Locked for This Phase

The following decisions are fixed for the notebook RAG phase:

- The system focuses first on the RAG architecture, not the full product stack.
- The implementation starts in notebooks.
- The embedding model is fixed during notebook evaluation.
- Chunking strategy and chunk size are fixed during notebook evaluation.
- Users may switch chat LLMs during comparison and chat.
- LangSmith tracing is included from the evaluation stage.
- Retrieval, answer quality, latency, and cost are all first-class metrics.
- Structured employee data should be accessed through safe tools, not open employee-facing NL-to-SQL.

## Deliverables of the RAG Phase

By the end of this phase, the notebook system should produce:

- A working baseline RAG pipeline.
- A working self-reflective corrective RAG pipeline.
- A hybrid retrieval-plus-tool path for structured user data.
- A golden evaluation dataset.
- Metric dashboards or result tables for retrieval, generation, latency, and cost.
- Trace logs for representative runs.
- A clear recommendation for the best model and configuration to carry into the FastAPI product phase.

## Transition to Product Phase

Once the notebook phase demonstrates stable quality, the architecture can be moved into the first-phase application stack:

- FastAPI backend.
- PostgreSQL for persistence.
- Redis for caching and short-term memory.
- LangGraph orchestration layer.
- Secure tool services for employee data.
- Production logging, tracing, and exception handling.

The notebook phase should therefore be treated as the controlled engineering lab for the future production backend rather than as a disposable prototype.
