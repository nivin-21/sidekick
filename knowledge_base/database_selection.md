# Database Selection Guide

## The Core Question

Don't start with "SQL or NoSQL?" Start with:
1. What is the shape of my data?
2. What are my access patterns?
3. What are my consistency and availability requirements?
4. What is my scale (reads/writes per second, data volume)?

The database should fit the access pattern — not the other way around.

## Relational Databases (PostgreSQL, MySQL)

**Choose when**:
- Data has clear relationships and you need JOINs
- ACID transactions are required (financial records, order management)
- Schema is well-defined and stable
- Complex queries with aggregations, filtering, sorting
- Team has strong SQL expertise

**PostgreSQL strengths**: JSONB for hybrid workloads, full-text search, extensions (PostGIS, TimescaleDB), excellent MVCC, strong community.

**Avoid when**: Write throughput exceeds what a single primary can handle (~10k-50k writes/sec), horizontal write scaling is needed, data is fundamentally unstructured or highly variable schema.

## Document Databases (MongoDB, Firestore)

**Choose when**:
- Data is naturally document-shaped (nested, variable structure)
- Schema evolves rapidly (startups, prototypes)
- Each entity's data is accessed together (no JOINs needed)
- You need flexible indexing on arbitrary fields

**MongoDB strengths**: Rich query language, aggregation pipeline, atlas search, horizontal sharding built-in.

**Avoid when**: You need multi-document ACID transactions frequently (MongoDB supports it but at a cost). Relational data with many JOINs. Strong consistency across collections.

## Wide-Column Databases (Cassandra, HBase)

**Choose when**:
- Write throughput is extreme (millions of writes/sec)
- Data has a clear partition key and time-series or sorted access pattern
- Geographical distribution and multi-region writes are needed
- You can model all queries upfront (Cassandra tables are query-first)

**Cassandra strengths**: Linear horizontal scalability, no single point of failure, tunable consistency, excellent for time-series, IoT, activity feeds.

**Avoid when**: You need ad-hoc queries, JOINs, or flexible querying. Schema changes are frequent. Team doesn't have Cassandra expertise.

## Key-Value Stores (Redis, DynamoDB)

**Redis — use for**:
- Caching (the primary use case)
- Session storage
- Rate limiting, leaderboards (sorted sets)
- Pub/sub messaging
- Distributed locks
- Real-time analytics

**DynamoDB — use for**:
- Serverless applications (fully managed, scales to zero)
- High-throughput key-value or simple query patterns
- When you know your access patterns upfront
- AWS-native applications

**Avoid Redis as primary DB** unless data loss on restart is acceptable (use AOF persistence if not). DynamoDB gets expensive with complex queries or large scans.

## Search Engines (Elasticsearch, OpenSearch)

**Use for**: Full-text search, log aggregation, complex filtering + ranking, autocomplete, faceted search.

**Not a primary database** — always keep source of truth elsewhere and sync to ES. ES is eventually consistent and not ACID.

## Time-Series Databases (InfluxDB, TimescaleDB, Prometheus)

**Use for**: Metrics, monitoring, IoT sensor data, financial time-series. Optimized for time-based queries and downsampling.

TimescaleDB is Postgres + time-series optimizations — good if you want SQL + time-series.

## Decision Matrix

| Need | Database |
|------|----------|
| ACID transactions, relational data | PostgreSQL |
| Flexible schema, document data | MongoDB |
| Extreme write scale, time-series | Cassandra |
| Caching, sessions, real-time | Redis |
| Full-text search | Elasticsearch |
| Serverless, AWS-native | DynamoDB |
| Metrics, monitoring | Prometheus + TimescaleDB |

## Polyglot Persistence

Most production systems use multiple databases. Common combo:
- PostgreSQL (source of truth for relational data)
- Redis (caching + sessions)
- Elasticsearch (search)
- Cassandra or DynamoDB (high-volume events/logs)

The key is keeping the source of truth clear and maintaining consistency between stores through events or dual-writes.
