# PRD: Order Fulfillment Tracker

## 1. Business Goals
- Give warehouse ops real-time visibility into shipment delays.

## 2. Functional Requirements
- REQ-001 (Must-Have): Provide order lookup by `order_id` showing carrier and ETA.

## 3. Non-Functional Requirements & Compliance
- NFR-001 (Must-Have): Query response latency must remain p95 <= 2.0 seconds.
- NFR-002 (Must-Have): Write immutable audit logs for every operator lookup to satisfy SOC 2 compliance.
