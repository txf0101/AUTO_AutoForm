# Backend P0 Boundary

## Purpose

The existing backend implementation remains in `autoform_agent/`. This directory records the P0 backend boundary required by the Vibecoding plan before a separate event gateway or adapter package is introduced.

## P0 responsibilities

- R4 exposes a server-side `RunEvent` stream through `autoform_agent/runtime_events.py` that follows `schemas/ui_event_schema.json`.
- R4 keeps API keys behind `autoform_agent/credentials.py`, `autoform_agent/provider_connection.py` and `autoform_agent/agent_runtime.py`, and exposes only masked status to `apps/workbench/`.
- R4 aggregates token usage into `TokenUsageSnapshot` objects through `autoform_agent/runtime_events.py` and runtime reply events.
- R5 connects `center_agent`, C0 context view building, patch review, Agent gateway calls and audit events through `autoform_agent/agent_system/kernel.py` and `autoform_agent/agent_system/tool_gateway.py`.

## Current source evidence

- `autoform_agent/http_bridge.py` is the existing local HTTP entry.
- `autoform_agent/agent_runtime.py` is the existing direct DeepSeek API backend runtime.
- `autoform_agent/agent_system/` contains deterministic role contracts, the R5 center Agent kernel and the Agent tool gateway.
- `schemas/` and `fixtures/` provide the P0 event and object contracts used by R4 and R5 tests.
