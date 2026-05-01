# PlantMind AI Deployment Go/No-Go Report

Date: 2026-04-30  
Prepared by: Engineering validation pass

## Executive Decision

**Decision: CONDITIONAL GO**

The system is technically stable and functionally ready for controlled local deployment in a factory pilot environment.  
Production rollout is approved **with pre-launch ops checks completed**.

## Scope Evaluated

- V1 Smart Order Intake pipeline
- V2 Production & Inventory Brain
- V3 Dispatch + Daily MIS reporting (initial integrated implementation)
- Scheduler-driven automation jobs
- Startup readiness diagnostics
- Automated test and lint validation

## Evidence Summary

### Build and Test Health

- Full automated suite passing: **222 passed, 0 failed**
- Lint checks on modified files: **no linter errors**
- Real Ollama verification performed using `phi3:mini` (`4f2222927938`)

### Functional Readiness

- Email intake -> filtering -> extraction -> order creation: implemented and tested
- Inventory check + reorder flow: implemented and tested
- Production scheduling + tracking: implemented and tested
- V3 dispatch automation:
  - Completed orders auto-transition to `dispatched`
  - Outgoing dispatch entry logged in `email_log`
- V3 daily MIS:
  - Daily summary generation implemented
  - Scheduler trigger configured for 09:00 daily
  - Manual trigger endpoint available

### Operational Readiness

- Startup readiness endpoint available: `GET /health/startup`
- Checks included:
  - Database connectivity
  - Ollama reachability and model presence
  - Gmail reader config/token sanity
  - Gmail sender env readiness
  - Scheduler status

## Go/No-Go Gate Matrix

- **Code stability:** GO
- **Automated regression:** GO
- **Core workflow completeness (V1+V2):** GO
- **V3 baseline automation:** GO
- **Runtime observability:** GO
- **Configuration hygiene:** GO (after `.env` completion on target machine)
- **External dependency readiness (Gmail/Ollama/Postgres on deploy machine):** CONDITIONAL

## Open Risks (Non-blocking for Pilot, Important for Full Rollout)

1. `httpx` TestClient deprecation warnings remain in test stack.
2. `python_multipart` import deprecation warning from upstream dependency path.
3. Current V3 email sending path is represented via outbound log creation; direct SMTP send integration for dispatch/MIS should be finalized if mandatory for day-1 operations.
4. No completed 10-cycle real-world acceptance run report captured yet.

## Required Preconditions Before Launch

1. Ensure deploy `.env` includes:
   - `OLLAMA_MODEL=phi3:mini`
   - `GMAIL_CLIENT_SECRET`, `GMAIL_TOKEN_PATH`
   - `GMAIL_SMTP_EMAIL`, `GMAIL_APP_PASSWORD`
   - `OWNER_REPORT_EMAIL`
2. Validate target machine with:
   - `GET /health/startup` returns `status=ready`
3. Confirm scheduler running and jobs visible in startup report.
4. Execute at least one end-to-end smoke cycle on live infrastructure.

## Recommended Next Validation (High Priority)

- Run formal **10-cycle acceptance test** and archive outcomes:
  - success/fail per cycle
  - extraction accuracy notes
  - reorder/dispatch/MIS timestamps
  - failure reasons and corrective actions

## Final Recommendation

**GO for controlled pilot deployment** (single-site/local network),  
**NO-GO for broad rollout** until acceptance-cycle report and live email send verification are completed.

