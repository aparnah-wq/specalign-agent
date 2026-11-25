# TDD: Retail Inventory Sync

## 1. Architecture Overview
- Warehouse events publish to Cloud Pub/Sub and a Cloud Run worker batches updates to the legacy ERP catalog API every 5 seconds with dead-letter retries (guaranteeing zero dropped updates per REQ-002).

## 2. Documented Engineering Trade-Offs
- **Async Pub/Sub Queue vs. Synchronous Real-Time Write (REQ-001):** The legacy ERP catalog API enforces a hard 10 QPS rate limit and throws HTTP 429 during peak warehouse scans. We intentionally replaced synchronous writes with an async Pub/Sub buffer (~5s eventual consistency) to prevent cascading write failures. **Action Requested:** PM confirmation to relax REQ-001 from < 1s sync to <= 10s eventual consistency.
