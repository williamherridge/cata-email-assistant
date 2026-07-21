# Product Requirements: CATA Email Assistant

## 1. Purpose

Build a low-cost web application for CATA administrators that monitors a Gmail inbox, classifies and prioritizes incoming email, proposes replies when needed, and supports administrator review before sending any response.

The system should reduce manual inbox triage and improve consistency of responses while preserving human control over all outgoing communication.

## 2. Product goals

- Reduce time spent reviewing and sorting incoming email.
- Improve consistency of categorization and response quality.
- Help administrators answer rule-related questions with accurate source links.
- Maintain strict human review before any email is sent.
- Start with very low monthly operating cost and allow expansion later.

## 3. Non-goals for MVP

- Fully autonomous email replies
- Fully self-learning automation without administrator review
- Broad multi-user workflow orchestration
- Deep analytics dashboards beyond operationally useful views
- Complex mobile-native applications

## 4. Users

### Primary user

- CATA administrator

### Future users

- additional administrators with the same shared queue
- reviewers or assistants with limited permissions

## 5. Problem statement

CATA receives incoming email that varies widely in urgency, intent, and complexity. Some messages are simple and repetitive, some are informational only, and many involve questions about rules, league requirements, deadlines, and local procedures. Manual handling is time-consuming and inconsistent. Existing reporting and lookup processes are cumbersome. A structured assistant can help classify, prioritize, and draft responses while keeping a human in the loop.

## 6. Core capabilities

### 6.1 Inbox monitoring

The system shall:

- monitor a Gmail inbox for new or updated messages
- ingest message content and relevant metadata
- preserve thread context where possible
- avoid modifying or replying automatically during initial ingestion

### 6.2 Categorization

The system shall:

- assign a workflow-oriented category to each incoming email using an existing taxonomy when possible
- support workflow-oriented subcategory assignment when useful
- assign one or more topics to support RAG retrieval, reporting, and future analysis
- detect one or more questions, intents, or issues in a message when the sender asks about multiple things
- use deterministic rules when a message clearly matches a known pattern
- use an LLM when deterministic logic is insufficient
- record model confidence or a practical confidence tier
- assign only approved taxonomy categories as the official message category
- suggest a proposed category label when no approved category fits confidently
- keep proposed category labels separate from the approved taxonomy until an administrator promotes them

Each message should have exactly one primary category in MVP. Categories and subcategories should describe the primary type of work or request. Topics and detected questions should capture additional subject-matter complexity when a message asks about multiple things.

### 6.3 Prioritization

The system shall:

- assign a priority to each email
- support deterministic prioritization rules where appropriate
- use an LLM when priority depends on semantic interpretation
- surface the reason for the suggested priority when feasible

### 6.4 Informational-only tagging

The system shall:

- support a separate informational-only flag independent of category or priority
- allow deterministic and LLM-assisted assignment of this flag
- use this flag to suppress unnecessary reply drafting

### 6.5 Response recommendation

For emails that appear to need a reply, the system shall:

- generate a proposed response
- use internal metadata, such as category and priority, only to choose the appropriate drafting workflow and instructions
- avoid exposing internal category, priority, confidence, or routing metadata in the outgoing email body
- incorporate available rule context when the response depends on rules, regulations, deadlines, or local parameters
- include supporting citations or links when rule references are used
- prohibit automatic sending of generated replies in the MVP release

The no-auto-send constraint is critical for MVP. Generated replies must remain drafts inside the application until an administrator explicitly reviews and sends them.

### 6.6 Administrator review and editing

The system shall:

- support two administrator logins at launch for audit attribution
- use one shared work queue for all administrators in MVP
- avoid message assignment or ownership workflow in MVP
- present the original email, classification, priority, informational flag, and proposed response
- allow the administrator to edit category, priority, and tags
- allow the administrator to edit the proposed response
- allow the administrator to create a new category
- allow the administrator to override a proposed category
- allow the administrator to regenerate a proposed reply after changing the category, priority, informational flag, or relevant context
- route regenerated replies through the instructions associated with the updated category when applicable
- allow the administrator to mark a message as ignored without sending a reply from the application
- hide responded and ignored messages from the default queue view
- provide filters for status, category, priority, informational-only messages, reply-needed messages, and replies
- provide a manual refresh control in the portal
- show the last queue refresh timestamp
- refresh portal data after send actions and after draft generation completes
- avoid automatic refresh after mark-ignored actions or category/priority changes
- keep the final send action under explicit administrator control

Additional requirements for review screen usability should be developed during the design phase. The review screen is expected to be the primary working surface for administrators, so usability and speed matter.

### 6.7 Outbound sending

The system shall:

- send generated response replies only after explicit administrator approval
- send replies using the same Gmail account and credentials used to receive the incoming email
- support reply-all when the original email includes additional recipients
- automatically set the message status to `responded` when a reply is sent through the application
- preserve a record of what was drafted, edited, approved, and sent
- retain sent message content and metadata in the application for audit and future improvement analysis, if cost allows
- evaluate low-cost object storage, such as S3, for sent message bodies and related artifacts
- separate current message state from append-only audit/history records

### 6.8 Receipt replies

Receipt replies are deferred from MVP. The system may support optional receipt replies in a future phase after administrators have operated the system long enough to trust category and priority assignment.

Receipt replies are short acknowledgement messages, such as "Thank you for your email. We will reply when we have completed your request."

In a future phase, the system should:

- configure receipt-reply behavior at the category level
- allow different receipt-reply text by category
- send receipt replies only when the category configuration explicitly enables them
- audit any receipt reply that is sent
- keep receipt-reply behavior separate from the main drafted response workflow

For MVP, receipt replies must remain disabled. The administrator should first work with the system for a confidence-building period before any category-based automatic acknowledgement is considered.

### 6.9 Rule-aware knowledge retrieval

The system shall support a knowledge base for:

- national rules
- section rules
- local rules
- local operational parameters such as roster limits, deadlines, playoff details, and event dates

The system shall:

- respect rule precedence: national overrides section, section overrides local
- provide citations and working source URLs in generated replies when rule references are used
- support retrieval of both rule content and operational parameters

## 7. Functional requirements

### 7.1 Email ingestion

- Ingest sender, recipients, subject, body, date, thread id, and message id.
- Ingest `To`, `Cc`, and other original recipient metadata needed for reply-all behavior.
- Ingest stable Gmail API identifiers needed to retrieve or link back to the original email, including Gmail message id, Gmail thread id, history id, label ids, internal date, and mailbox account identity.
- Ingest RFC email headers needed for fallback lookup and reply threading, including `Message-ID`, `References`, `In-Reply-To`, `From`, `To`, `Cc`, `Subject`, and `Date`.
- Provide an `Open in Gmail` action from the application; exact Gmail browser URL construction should be validated during prototype, with fallback lookup using stored RFC/Gmail identifiers.
- Capture attachments metadata for future use, even if attachments are not processed in MVP.
- Surface attachment presence in the portal so administrators know when they may need to inspect Gmail directly.
- Preserve raw message content for audit and troubleshooting.
- Ingest enough Gmail thread metadata to detect whether a message was replied to outside the application in a later phase.

### 7.2 Classification workflow

- Apply deterministic rules before invoking an LLM.
- Apply taxonomy-based classification after deterministic screening.
- Route low-confidence outcomes to administrator review.
- Store both predicted and final administrator-approved values.

### 7.3 Priority workflow

- Support three priority levels in MVP: `critical`, `normal`, and `low`.
- Use priority for queue sorting, filtering, and administrator attention.
- Treat `critical` as the only priority that can trigger out-of-band administrator notification.
- Support SMS notification to an administrator phone number when an email meets critical priority rules.
- Include a link to the message in the portal when sending a critical SMS notification.
- Permit future expansion to additional priority levels without requiring a system redesign.
- Allow hard-coded escalation rules for urgent phrases, deadlines, or known senders.

### 7.4 Draft generation workflow

- Generate a reply only when the system believes a reply is required.
- Automatically generate drafts only for categories configured to do so.
- Provide a manual `Generate Draft` action for reply-needed messages that do not receive an automatic draft.
- Provide a collaborative response workbench where the administrator can review system analysis, prework, citations, outline, and the final draft.
- Prepare editable prework before draft generation when cost-effective.
- Include deterministic context, RAG retrieval results, citations, and a reply outline in prework when useful.
- Allow administrators to review and edit prework before generating the formal reply.
- Generate the formal reply from the current prework, including administrator edits.
- Allow prepared prework to be reused by automatic generation, manual generation, and regeneration.
- Allow administrators to request regeneration after manual edits or new context.
- Support category-routed draft generation so category-specific instructions can remain small and focused.
- Support category-level response configuration.
- Category configuration should support default draft behavior, instructions, examples, templates, RAG settings, reply-needed defaults, informational-only defaults, and priority hints.
- Tone and signature standards should be controlled through configurable system instructions.
- Initial generated reply tone should be professional, polite, direct, and concise.
- Generated replies should avoid flowery language, unnecessary reasoning, and over-explanation.
- Rule-related replies should provide the applicable rule or source and avoid interpreting rules beyond the documented text.
- Distinguish between draft provenance:
  - no draft
  - deterministic template
  - LLM-generated
  - hybrid template plus LLM

### 7.5 Admin console

The web application shall provide:

- inbox/work queue view
- message detail view
- classification and priority controls
- draft response editor
- send action
- ignore action
- category management interface
- search/filtering across message status, category, topic, and priority
- default filtering that excludes responded messages, ignored messages, and sent replies
- optional filter controls that can show sent replies, responded messages, and ignored messages when needed
- manual refresh control
- last refreshed timestamp
- action-triggered refresh after send and draft-generation completion

### 7.6 Taxonomy management

- Store a canonical category list.
- Store topics separately from categories and subcategories.
- Store exactly one primary category per message in MVP.
- Store zero or one subcategory per message in MVP.
- Permit administrators to create new categories.
- Permit administrators to rename or consolidate categories.
- Track proposed categories separately from approved categories.
- Require administrator approval before a proposed category becomes an official taxonomy category.
- Attach category rules, instructions, and templates only to approved taxonomy categories.
- Support one or more topics per message so RAG retrieval can target relevant rule and local-parameter content.
- Support one or more detected questions or intents per message so draft generation can answer multi-question emails.

### 7.7 Learning from admin corrections

For MVP:

- store corrections and overrides for later analysis
- store final sent message content and metadata for audit and future improvement analysis, if cost allows
- preserve enough draft/prework/edit history to compare system output to administrator-approved communication
- retain inbound message snapshots, system analysis, RAG/prework, draft history, final sent replies, and administrator action audit events

Post-MVP:

- use administrator corrections to improve prompts, rules, exemplars, or training data
- analyze final sent messages and administrator edits to improve category instructions, templates, prompts, and future automation confidence
- optionally use lightweight feedback loops before any model fine-tuning strategy

### 7.8 Gmail synchronization and polling

The system shall:

- process all email received by the single configured Gmail mailbox
- use configurable polling intervals
- poll every 15 minutes between 7:00 AM and 7:00 PM every day
- poll every 2 hours outside 7:00 AM to 7:00 PM
- provide an administrator-triggered `Poll now` button for immediate Gmail ingest, especially for mobile use
- make ingested emails visible in the portal even if classification, RAG lookup, or draft generation is still pending
- avoid timer-based portal auto-refresh in MVP
- provide manual refresh in MVP
- refresh portal data after send actions and after draft generation completes
- do not automatically refresh after mark-ignored actions or category/priority changes
- hide replies from the default inbox/work queue view
- support future detection of replies sent directly in Gmail so the corresponding application message can be marked `responded`

### 7.9 Message status and draft state

The system shall keep administrator disposition separate from background processing state.

Message status shall describe administrator disposition:

- `new`: the message has not been reviewed or dispositioned by an administrator
- `responded`: a response has been sent through the application or, in a future phase, detected from Gmail
- `ignored`: an administrator reviewed the message and chose not to respond

Draft state shall describe the proposed reply lifecycle separately from message status:

- `not_required`: no reply draft is expected
- `pending`: the system plans to generate a draft but it is not ready yet
- `ready`: a proposed draft is available for administrator review
- `failed`: draft generation failed or needs administrator intervention

Messages should remain `new` while draft generation is pending or ready. This keeps the default queue centered on administrator work instead of background system activity.

## 8. Business rules

- No generated response draft may be sent without explicit administrator action.
- For MVP, generated response drafts must never be sent automatically.
- Informational-only messages should not require a reply draft by default.
- Rule precedence must always be national > section > local.
- If conflicting guidance exists, the higher-precedence rule must be cited and followed.
- Generated replies that use rules should include source links when available.
- Rule-related replies should provide rule information and citations, not undocumented interpretations.
- Internal category, priority, confidence, and workflow metadata must not be included in customer-facing email responses unless explicitly written by the administrator.
- Responded and ignored messages should disappear from the default portal queue.
- Receipt replies are deferred from MVP and must remain disabled during the initial release.

## 9. Quality attributes and non-functional requirements

### 9.1 Cost

- Initial monthly operating cost target: under $20/month where feasible
- Later expected budget if value is proven: approximately $200-$300/month
- Architecture decisions should prefer low idle cost and usage-based pricing
- The application should avoid timer-based UI auto-refresh and repeated expensive queries.
- MVP portal refresh should be manual by default, with narrow action-triggered refresh after send actions and draft-generation completion.
- LLM use should be minimized through deterministic rules, category-routed prompts, smaller models where acceptable, and deferred draft generation when practical.

### 9.2 Security

- Access must require authentication.
- Administrator functions must be protected with strong credentials.
- Message content and drafts must be stored securely.
- Sent message content, prework, drafts, and administrator edits must be stored securely when retained.
- Secrets must not be committed into the repository.
- The system must support auditable actions for message review and sending.

### 9.3 Availability and access

- The application should be accessible inside and outside the local network.
- The UI should work on laptop and phone browsers.
- MVP may prioritize responsive web over native mobile.

### 9.4 Safety

- No automatic sending of generated response drafts in MVP
- No hidden background send flow
- Clear separation between draft generation and send approval
- Receipt replies must remain disabled in MVP.

### 9.5 Maintainability

- Project artifacts should remain organized by lifecycle phase
- Rules and prompts should be editable without major code changes
- Taxonomy updates should not require redeploying the entire application where possible

### 9.6 Resilience and error handling

- The application should never crash for recoverable faults caused by malformed data, stale external references, unexpected user interactions, or partial local artifact corruption.
- Request handlers should return a controlled browser response for recoverable faults instead of surfacing raw server errors.
- Batch and polling workflows should fail the smallest safe unit of work rather than aborting the full run when one message or artifact is malformed.
- All local file reads should assume files may be missing, partially written, corrupt, or non-UTF-8.
- All Gmail and third-party payload parsing should assume incomplete or malformed structures.
- Caught exceptions must either rollback and re-raise or rollback/log and return a deliberate fallback.
- Broad exception handling is allowed only at resilience boundaries such as routes, polling loops, and external-service integration boundaries.
- User-visible errors should avoid implying success when an operation did not complete.
- Database, filesystem, and external API outages may fail the affected operation, but the application should still degrade as safely as practical.

## 10. Recommended MVP scope

### Included

- Gmail inbox polling or sync
- message queue/work list
- category suggestion
- priority suggestion
- informational-only flag
- draft reply generation
- admin review and edit flow
- manual send action
- basic taxonomy management
- initial rules/knowledge retrieval with citations
- configurable polling schedule with 15-minute daytime polling and 2-hour off-hours polling
- administrator-triggered immediate Gmail poll
- manual portal refresh with last refreshed timestamp
- action-triggered portal refresh after send and draft-generation completion
- `responded` and `ignored` statuses with default queue filtering

### Deferred

- advanced analytics dashboards
- multi-admin role hierarchy
- assignment or ownership workflow
- automated learning loop
- attachment understanding beyond metadata
- complex workflow automation
- automatic `responded` status based on replies sent directly in Gmail
- automatic receipt replies

## 11. Suggested initial AWS and OpenAI direction

This is not a final architecture decision, but the requirements suggest:

- AWS-hosted web application
- low-idle-cost services
- OpenAI API for classification and draft generation
- a compact knowledge store for rule retrieval and citations
- workflow components that route email through deterministic rules, classification, retrieval, drafting, and admin review

The architecture phase should explicitly compare low-cost options such as:

- serverless-first deployment
- small containerized deployment
- lightweight relational storage versus document storage
- simple vector or hybrid retrieval strategies

## 12. Risks and concerns

- LLM operating cost may rise if every email requires large prompts or retrieval context.
- Incorrect rule interpretation could create trust issues.
- Gmail integration must preserve thread context without introducing send risk.
- Taxonomy drift may occur if category creation is too loose.
- RAG quality depends heavily on document quality, freshness, and metadata hygiene.
- Frequent polling, portal auto-refresh, or expensive database queries could exceed the nonprofit cost target.
- Future receipt replies create an automation exception and should be handled with extra caution.

## 13. Success criteria for MVP

- Administrator can review new emails in one queue.
- System provides useful category and priority suggestions for a meaningful portion of messages.
- System clearly distinguishes informational-only messages.
- System generates editable draft responses for reply-needed messages.
- Administrator can approve and send a reply from the application.
- Administrator can mark a message ignored without sending a reply.
- Responded messages, ignored messages, and sent replies are hidden from the default queue view.
- Rule-based replies can cite relevant sources with working links.
- Monthly operating cost remains within the initial budget target during pilot usage.

## 14. Current requirements decisions

- Initial taxonomy source: categories created through the existing taxonomy review app.
- Taxonomy shape: categories and subcategories describe workflow or request type; topics describe subject matter for RAG, reporting, and analysis.
- Category cardinality: MVP uses exactly one primary category and zero or one subcategory per message.
- Multi-question handling: use multiple topics and detected questions or intents rather than multiple categories.
- Proposed category model: `assigned_category_id` references only approved categories; proposed category labels are stored separately until promoted by an administrator.
- Category governance: rules, instructions, and templates attach only to approved categories.
- Category response configuration: MVP architecture must support category-level defaults for draft behavior, instructions, examples, templates, RAG settings, reply-needed defaults, informational-only defaults, and priority hints.
- Draft generation trigger: automatically generate drafts only for configured categories; provide manual generation for other reply-needed messages.
- Two-stage drafting: prepare editable prework first, then generate the formal reply from the current prework.
- Response workbench: message detail should act as a collaborative workbench where system prework and administrator edits produce the final communication.
- Tone standard: configurable system instructions, initially professional, polite, direct, and concise.
- Rule-response constraint: provide applicable rules and citations without undocumented interpretation.
- Gmail mailbox scope: one Gmail mailbox for MVP and foreseeable production use.
- Sent message retention: retain sent message content and metadata in the application for audit and future improvement analysis, if cost allows.
- Sent message storage direction: architecture should evaluate low-cost object storage, such as S3, for message bodies and related artifacts.
- Administrator users: two users at launch, both with full admin capabilities.
- Administrator workflow: one shared queue with separate logins used for audit attribution.
- Audit logging: track application actions by user.
- Audit/retention model: separate current message state from append-only audit/history records.
- Retained MVP records: inbound message snapshots, system analysis, RAG/prework, draft history, final sent replies, and administrator action audit events.
- Response time preference: cost is more important than immediate draft availability, but draft generation should generally complete within a few minutes.
- Message processing scope: all received email should be processed so administrators can rely on the portal as the primary inbox workflow.
- Attachment scope: ingest attachment metadata for MVP, but do not process attachment content initially.
- Rule document ownership: CATA will provide authoritative rule and local-parameter documents.
- MVP authoritative regulation sources: use the CATA-curated National, Section, and Local PDFs listed in `data/rules_sources/sources_manifest.json`.
- Local parameters: treat as a launch content prerequisite and store with the same metadata/precedence model when provided.
- Knowledge updates: architecture should consider S3-based document storage, document replacement workflows, and automated or semi-automated re-indexing.
- Message status model: use `new`, `responded`, and `ignored` for administrator disposition.
- Draft readiness model: track draft lifecycle separately from message status.
- Priority model: use `critical`, `normal`, and `low` for MVP.
- Priority purpose: drive queue sorting, filtering, visual attention, and critical SMS notification.
- Receipt replies: deferred from MVP until administrators have built confidence in category and priority accuracy.
- Gmail linking metadata: store stable Gmail API ids, RFC message headers, and mailbox identity; validate the exact `Open in Gmail` URL format during prototype.
- Gmail polling default: poll every 15 minutes between 7:00 AM and 7:00 PM every day, poll every 2 hours otherwise, and provide a portal `Poll now` button for immediate ingest.
- OpenAI cost guardrail: use a $10/month MVP soft budget and a $15-$20/month hard cap.
- AI budget behavior: pause non-essential AI draft generation at the hard cap while preserving Gmail ingest, deterministic rules, queue review, editing, and sending.
- Error-handling standard: future code must follow the resilience and error-handling rules in section 9.6 and the implementation guidance in `docs/design/error_handling_assessment.md`.

## 15. Open questions

- After the MVP confidence period, which categories can use receipt replies and what approval controls are required?
