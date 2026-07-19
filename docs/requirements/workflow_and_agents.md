# Workflow and Agent Considerations

## Summary

The application should use workflow orchestration from the start. It may use agent-like components later, but the MVP should favor explicit, inspectable steps over autonomous agents.

The safest and lowest-cost shape is a pipeline of small workers:

- ingest email
- normalize and de-duplicate
- apply deterministic rules
- classify category
- assign priority
- determine whether a reply is needed
- retrieve rule context when needed
- prepare editable prework with deterministic context, RAG results, citations, and outline
- generate or select a draft
- wait for administrator review
- send only after administrator approval
- audit every important transition

## Why workflow-first fits this project

- It keeps costs predictable because each step can decide whether an LLM call is needed.
- It keeps behavior auditable because each step stores input, output, confidence, and reason.
- It supports category-routed drafting without stuffing every instruction into one large prompt.
- It makes the no-auto-send constraint enforceable as a state-machine rule.
- It allows slower draft generation without blocking inbox visibility.

## Where tools fit

Tools are a strong fit for bounded operations:

- Gmail read message
- Gmail send approved reply
- taxonomy lookup
- deterministic rule lookup
- RAG retrieval
- citation validation
- category-specific draft template lookup
- audit event creation
- notification dispatch

These should be narrow functions with clear permissions and logs.

## Where agents might fit

Agent-style behavior may be useful after the deterministic workflow is proven:

- choosing which category-specific drafting tool to call
- deciding whether rule retrieval is needed
- asking for missing context before drafting
- comparing conflicting rule citations
- summarizing a thread for administrator review

For MVP, any agent-like component should operate inside a constrained workflow and should never be able to send email directly.

## Recommended MVP stance

Use an explicit workflow engine or state-machine pattern, with LLM calls and tools inside specific steps. Treat the LLM as a reasoning component inside the workflow, not as the owner of the workflow.

This keeps us honest on the most important constraints: cost, auditability, and administrator control.
