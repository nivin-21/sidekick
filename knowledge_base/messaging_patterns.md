# Messaging Patterns

## When to Use Messaging

Use async messaging when:
- The producer doesn't need an immediate response from the consumer
- You want to decouple services so they can scale independently
- You need to handle traffic bursts (queue absorbs spikes)
- You want guaranteed delivery with retry semantics
- Multiple consumers need the same event (fan-out)

Don't use messaging for: synchronous request-response flows, simple CRUD where HTTP is sufficient, when latency requirements are < 10ms end-to-end.

## Kafka

**What it is**: Distributed commit log. Topics are partitioned and replicated. Messages are retained for a configurable period (not deleted on consume).

**Key properties**:
- High throughput (millions of messages/sec)
- Persistent storage — consumers can replay from any offset
- Consumer groups — multiple consumers read independently
- Ordering guaranteed within a partition
- Pull-based consumers (consumers control their pace)

**Use Kafka when**:
- Event streaming at high volume (clickstreams, logs, metrics)
- Multiple independent consumers need the same events
- You need replay — reprocessing historical events
- Event sourcing — Kafka as the source of truth log
- Cross-datacenter replication

**Avoid Kafka when**: You need complex routing, message priorities, or per-message TTL. Operational overhead is high. Small teams without Kafka expertise. Low-volume use cases (it's overkill).

## RabbitMQ

**What it is**: Traditional message broker with exchanges and queues. Push-based (broker pushes to consumers). Messages are typically deleted after acknowledgment.

**Key properties**:
- Flexible routing via exchanges (direct, topic, fanout, headers)
- Message priorities
- Per-message TTL and dead letter queues
- Excellent for RPC-over-messaging patterns
- Lower throughput than Kafka but simpler operationally

**Use RabbitMQ when**:
- Complex routing logic (route by message type, headers)
- Task queues (background jobs, email sending)
- Request-reply messaging
- You need message priorities
- Smaller scale, simpler operations

## AWS SQS

**What it is**: Fully managed queue service. Standard (at-least-once, best-effort ordering) and FIFO (exactly-once, strict ordering).

**Use SQS when**:
- AWS-native infrastructure
- You want zero operational overhead
- Decoupling microservices at moderate scale
- FIFO queues for ordered, deduplicated processing

**SQS + SNS**: SNS for fan-out (pub/sub), SQS for queue per subscriber. Common AWS pattern.

## Kafka vs RabbitMQ Decision

| Factor | Kafka | RabbitMQ |
|--------|-------|---------|
| Throughput | Millions/sec | Thousands/sec |
| Message replay | Yes | No (deleted on ack) |
| Multiple consumers | Native (consumer groups) | Requires queue per consumer |
| Routing | By partition/topic | Flexible exchanges |
| Operational complexity | High | Medium |
| Use case | Streaming, event log | Task queues, RPC |

## Saga Pattern

For distributed transactions across microservices — replace 2PC with a sequence of local transactions and compensating transactions.

**Choreography-based Saga**: Services emit events, other services react. No central coordinator. Simpler, but hard to track overall saga state.

**Orchestration-based Saga**: Central saga orchestrator tells each service what to do and handles failures with compensating transactions. More complex but easier to monitor and debug.

**Use Saga when**: You need to maintain data consistency across services without distributed transactions (2PC is fragile and doesn't scale).

## Outbox Pattern

Problem: Writing to DB and publishing to message queue are two separate operations — one can fail.

Solution: Write the event to an `outbox` table in the same DB transaction as the business data. A separate poller reads the outbox and publishes to the broker, marking as published.

This guarantees at-least-once delivery without distributed transactions. Combine with idempotent consumers for exactly-once semantics.

```
Transaction {
  INSERT INTO orders (...)
  INSERT INTO outbox (event_type, payload, published=false)
}
-- Separate process:
SELECT * FROM outbox WHERE published=false
→ publish to Kafka/RabbitMQ
→ UPDATE outbox SET published=true
```

## Dead Letter Queues

Always configure a DLQ. Messages that fail repeatedly (after N retries) go to the DLQ for inspection and manual reprocessing. Without a DLQ, failed messages block queues or are silently dropped.
