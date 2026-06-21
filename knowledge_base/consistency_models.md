# Consistency Models & Distributed Transactions

## The Consistency Spectrum

From strongest to weakest:

### Linearizability (Strong Consistency)
Every operation appears to take effect instantaneously at some point between its invocation and response. All clients see the same, up-to-date state.

**Cost**: High latency (requires coordination), low availability under partition.
**Systems**: Zookeeper, etcd, Spanner, CockroachDB.
**Use for**: Leader election, distributed locks, financial balances, configuration that must be exact.

### Sequential Consistency
All operations appear in some sequential order that all nodes agree on, but not necessarily real-time order.

**Use for**: Systems where global order matters but real-time is not required.

### Causal Consistency
Causally related operations are seen in order by all nodes. Unrelated operations may be seen in any order.

"If A happened before B (A caused B), then everyone sees A before B."

**Systems**: MongoDB causal sessions, some distributed databases.
**Use for**: Comment threads, collaborative editing, social features where causal order matters.

### Read-Your-Writes
A client always sees its own writes immediately, even if others might not see them yet.

Implementable by: routing reads to the primary after a write, or by tagging writes with a timestamp and waiting for replica to catch up.

### Eventual Consistency
All replicas will converge to the same value given no new updates. No guarantees on when.

**Systems**: DynamoDB (default), Cassandra, DNS.
**Use for**: Shopping carts, social feeds, DNS updates, analytics, anything where brief staleness is acceptable.

## Distributed Transactions

### Two-Phase Commit (2PC)

Coordinator asks all participants to prepare, then commits if all say yes.

**Phase 1 (Prepare)**: Coordinator sends prepare to all. Each node locks resources and votes yes/no.
**Phase 2 (Commit)**: If all yes → commit. If any no → abort.

**Problems**:
- Coordinator SPOF — if coordinator crashes between phases, participants block holding locks
- Slow — requires 2 round trips + disk writes
- Doesn't scale well

**Use 2PC**: Within a single database system (Postgres does this internally). Avoid for cross-service distributed transactions.

### Saga Pattern

Break a distributed transaction into a sequence of local transactions. Each step publishes an event or triggers the next step. On failure, execute compensating transactions (undo previous steps).

**Example**: Order placement saga
1. Create order (PENDING)
2. Reserve inventory
3. Charge payment
4. Confirm order

On payment failure: compensate by releasing inventory, marking order FAILED.

**Choreography**: Services react to events. No central coordinator.
**Orchestration**: Central saga orchestrator manages the flow.

Saga does NOT provide isolation (other transactions can see intermediate states). Use for long-running business processes where locking across services is not feasible.

### Outbox Pattern

Atomically write business data + outgoing event to the same DB transaction. A relay process reads the outbox and publishes to the message broker. Guarantees at-least-once delivery.

```sql
BEGIN;
INSERT INTO orders VALUES (...);
INSERT INTO outbox (event, payload) VALUES ('ORDER_CREATED', {...});
COMMIT;
-- Separate process polls and publishes outbox events
```

## Conflict Resolution in Eventual Consistent Systems

When two nodes accept conflicting writes:

- **Last Write Wins (LWW)**: Highest timestamp wins. Simple, but loses data.
- **Vector Clocks**: Track causality. Detect conflicts. Application resolves.
- **CRDTs (Conflict-free Replicated Data Types)**: Data structures that merge automatically. Counters, sets, registers. No conflicts by design.

## Idempotency at the System Level

Idempotent consumers: processing the same message twice has the same effect as processing it once.

Implement by storing processed message IDs in a deduplication table. Before processing: check if ID exists. If yes, skip. If no, process and insert ID atomically.

## Choosing Consistency Level

| Scenario | Consistency Needed |
|----------|-------------------|
| Bank balance read | Linearizable |
| Inventory check before purchase | Read-your-writes minimum |
| User profile display | Eventual (with read-your-writes) |
| Social feed | Eventual |
| Distributed config / feature flags | Linearizable |
| Shopping cart | Eventual (merge on conflict) |
| Distributed lock | Linearizable |
