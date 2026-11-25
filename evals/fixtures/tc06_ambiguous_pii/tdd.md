# TDD: Support Triage Portal

## 1. Architecture Overview
- Single Cloud Run service handling ticket routing with an assumed 4-second timeout per request because the PRD did not define a numeric latency SLA.
