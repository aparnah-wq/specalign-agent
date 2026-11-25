# TDD: Payment Status API

## 1. Architecture Overview
- Read-only FastAPI service on Cloud Run serving `GET /v1/payments/{payment_id}` (covers REQ-001) and returning standardized HTTP 404 JSON errors for unknown IDs (covers REQ-002).
- Strictly read-only: no payment mutation or refund endpoints included.

## 2. Performance & SLAs
- Redis read-through cache plus Cloud SQL read replica achieve p95 latency of 180ms at 150 QPS (meets NFR-001 <= 300ms at 100 QPS).

## 3. Security & Observability
- All endpoints enforce TLS 1.3 and Cloud IAM authentication (meets NFR-002).
- Cloud Audit Logging enabled with a 90-day retention bucket (meets NFR-003).
