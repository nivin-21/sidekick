# CAP Theorem & PACELC

## Core Concept

The CAP theorem states that a distributed system can guarantee at most two of three properties simultaneously:

- **Consistency (C)**: Every read receives the most recent write or an error. All nodes see the same data at the same time.
- **Availability (A)**: Every request receives a response (not necessarily the latest data). The system remains operational.
- **Partition Tolerance (P)**: The system continues operating despite network partitions (message loss or delay between nodes).

In practice, partition tolerance is non-negotiable in distributed systems — networks fail. So the real choice is **CP vs AP**.

## CP Systems (Consistency over Availability)

When a partition occurs, the system refuses to respond rather than return stale data.

**Examples**: HBase, Zookeeper, etcd, MongoDB (with strong read concern), Redis Cluster (in some configs)

**Use when**:
- Financial transactions — you cannot show a user a stale balance
- Inventory systems — overselling stock is worse than a temporary outage
- Leader election, distributed locks — correctness is critical

## AP Systems (Availability over Consistency)

When a partition occurs, the system continues responding but may return stale data. Nodes reconcile later.

**Examples**: Cassandra, DynamoDB, CouchDB, DNS

**Use when**:
- Social feeds — slightly stale content is acceptable
- Shopping carts — availability matters more than perfect consistency
- Metrics/analytics — approximate counts are fine
- Systems where the user experience degrades worse from downtime than from stale data

## PACELC: The Realistic Extension

PACELC extends CAP by acknowledging that even without partitions, there is a latency vs consistency tradeoff:

- **P** (Partition): choose **A** (Availability) or **C** (Consistency)
- **E** (Else, no partition): choose **L** (Latency) or **C** (Consistency)

Strong consistency requires coordination (locks, quorum reads) which adds latency even in healthy conditions.

| System | Partition | Else |
|--------|-----------|------|
| DynamoDB | AP | EL |
| Cassandra | AP | EL |
| MongoDB | CP | EC |
| Spanner | CP | EC |
| MySQL | CP | EC |

## Consistency Spectrum

Between strong and eventual consistency there are intermediate levels:

1. **Strong/Linearizable**: All reads see the latest write immediately
2. **Sequential**: All nodes see operations in the same order, not necessarily real-time
3. **Causal**: Causally related operations are seen in order
4. **Read-your-writes**: You always see your own writes
5. **Eventual**: All replicas will converge given no new updates

## Decision Framework

Ask these questions in order:

1. **Can the business tolerate stale reads?** If no → CP. If yes → consider AP.
2. **Is the feature financial or inventory-critical?** If yes → always CP.
3. **What is the cost of downtime vs wrong data?** Weigh both.
4. **What is the read/write ratio and latency requirement?** High read volume + low latency tolerance → lean AP with caching.

## Common Mistakes

- Choosing strong consistency everywhere "to be safe" — you pay latency costs you don't need
- Using an AP database for financial records
- Confusing database replication lag (a latency issue) with the CAP partition scenario
- Assuming SQL = CP and NoSQL = AP — this is false. MongoDB can be AP, Spanner is CP.
