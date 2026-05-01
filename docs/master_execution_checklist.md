# PlantMind AI Master Execution Checklist

This is the source-of-truth plan to finish PlantMind AI from current state to reliable factory deployment.

## Current Baseline

- [x] Full automated test suite passing (`217 passed`)
- [x] Real Ollama integration verified with `phi3:mini` model
- [x] Core V1+V2 flow implemented and running
- [x] TemplateResponse deprecation style updated in `v1_routes`

## Phase 1 - Runtime Reliability (Do First)

- [ ] Add startup self-check endpoint/script for:
  - DB connectivity
  - Ollama availability + required model
  - Gmail read auth health
  - Gmail send auth health
- [ ] Add structured correlation IDs (`message_id`, `order_id`, request id) in logs
- [ ] Add clear failure reason mapping in API responses for operator-facing actions
- [ ] Add retry strategy policy doc (which failures retry vs fail-fast)

## Phase 2 - Data Integrity and Schema Hardening

- [ ] Resolve FK cycle warning between `orders` and `email_log` cleanly
- [ ] Add migration(s) for schema consistency between SQLite tests and Postgres runtime
- [ ] Add uniqueness/constraint audit for key fields:
  - `gmail_message_id`
  - supplier/material mapping
  - machine status transitions
- [ ] Add seed script for realistic demo data (customers, materials, products, machines)

## Phase 3 - V2/V3 Completion and Production Logic

- [ ] Verify every V2 workflow against spec:
  - inventory check
  - reorder trigger and logging
  - scheduling assignment rules
  - progress updates and ETA recalculation
- [ ] Validate V3 dispatch trigger from `completed` orders
- [ ] Validate daily MIS 9:00 AM flow end-to-end with scheduler
- [ ] Add explicit fallback templates for AI failure in all outbound emails

## Phase 4 - Security and Operations

- [ ] Finalize session/cookie security settings for LAN deployment profile
- [ ] Add production `.env` profile presets (dev/test/prod-local)
- [ ] Add DB backup + restore script (daily local backup)
- [ ] Add incident runbook (`what to do if email/model/db fails`)

## Phase 5 - Acceptance Test for Factory Deployment

- [ ] Run 10 complete realistic order cycles:
  - email intake -> extraction -> inventory/scheduling -> tracking -> completion -> dispatch
- [ ] Run 3 failure simulations:
  - Ollama unavailable
  - Gmail send failure
  - DB restart during processing
- [ ] Verify role dashboards on laptop + phone + tablet over local network
- [ ] Freeze release candidate and tag deployment version

## Immediate Next 5 Tasks (Execution Order)

1. Build startup self-check module + endpoint.
2. Fix schema FK cycle warning in a migration-safe way.
3. Add structured logging IDs across V1 processor and V2 processor.
4. Validate scheduler/MIS and dispatch automation in one integration test file.
5. Execute 10-cycle acceptance test and capture report.

## Definition of Done

- Zero failing tests.
- No critical startup/runtime unknowns.
- Operator can diagnose failures from logs/dashboard without reading code.
- End-to-end demo succeeds repeatedly on real local hardware with `phi3:mini`.
