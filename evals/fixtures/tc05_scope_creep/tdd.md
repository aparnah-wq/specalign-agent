# TDD: Internal HR FAQ Bot

## 1. Architecture Overview
- Multi-region GKE Autopilot clusters across US, EU, and APAC connected via self-managed Apache Kafka event streams.
- Custom nightly LoRA fine-tuning pipeline running on 8x A100 GPUs to retrain an open-weights LLM on the 20-page HR handbook.
- Custom GraphQL federation gateway in front of three microservices.
