# P0 Fixtures

`run_events_demo.jsonl` is the first R2 replay fixture. It expresses one low-risk simulation-preparation flow without submitting a real AutoForm solve.

`r18_realtime_executor_events.jsonl` records the R18 realtime executor skeleton event order.

`r19_realtime_multi_agent_executor_events.jsonl` records the R19 tool-aware executor event order with a readonly AgentToolGateway call.

`r20_enterprise_process_executor_events.jsonl` records the R20 enterprise process executor closed-loop replay with enterprise evidence, candidate patch review, R19 tool events, result evidence, and a draft report boundary.

Rules:

- One JSON object per line.
- Every line follows `schemas/ui_event_schema.json`.
- Nested `TaskCard`, `ContextPatch`, `EvidenceBundle` and `TokenUsageSnapshot` payloads follow their matching schemas.
- Fixtures must not contain raw API keys, long source documents or real high-risk AutoForm commands.
- `result_review_report_rules_template_v1_1.json` is an optional report-rule input template for future engineering judgment reports. Empty threshold fields mean pass/fail report drafting should stay disabled.
