# Development Lifecycle

This project will follow a staged development lifecycle:

## 1. Requirements

Goal:
- Define product scope, workflows, constraints, risks, and success criteria.

Primary deliverables:
- `docs/product_requirements.md`
- `docs/requirements/mvp_scope.md`
- open questions list
- MVP scope definition
- initial backlog themes

Exit criteria:
- approved MVP scope
- agreed user roles
- agreed automation boundaries
- agreed cost envelope and operating model

## 2. Architecture

Goal:
- Select the technical architecture that satisfies cost, security, and usability goals.

Primary deliverables:
- context and container diagrams
- AWS service selection
- OpenAI integration approach
- data model overview
- security model
- cost estimate

Exit criteria:
- approved target architecture
- approved hosted environment approach
- approved Gmail, auth, and reply flow strategy

## 3. Design

Goal:
- Turn the architecture into implementable component and workflow designs.

Primary deliverables:
- UI flow designs
- inbox review workflow
- prompt and policy design
- rule engine design
- RAG ingestion and citation design
- admin editing and send flow
- observability and audit design

Exit criteria:
- approved component contracts
- approved data schemas
- approved MVP user experience

## 4. Development

Goal:
- Build the application iteratively with tight feedback loops.

Likely implementation tracks:
- inbox ingestion
- taxonomy and prioritization
- admin review UI
- draft generation
- reply send workflow
- rule/RAG ingestion
- deployment automation

Exit criteria:
- MVP feature complete in a non-production environment

## 5. Testing

Goal:
- Validate correctness, safety, cost, and usability.

Primary deliverables:
- test plan
- unit and integration coverage
- prompt evaluation samples
- manual UAT scenarios
- production readiness checklist

Exit criteria:
- admin review workflow validated
- no auto-send paths
- acceptable model quality and operating cost

## 6. Implementation

Goal:
- Deploy the application, onboard administrators, and operate safely.

Primary deliverables:
- deployment runbook
- admin onboarding guide
- rollback plan
- production monitoring and support checklist

Exit criteria:
- production deployment completed
- pilot feedback cycle started

## Working style

This project should remain interactive:

- each phase ends with explicit review and decisions
- open questions are surfaced early
- design choices should be revisited if cost or complexity grows too quickly
- GitHub remains the system of record for artifacts, code, and documentation
