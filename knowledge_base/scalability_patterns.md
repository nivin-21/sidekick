# Scalability Patterns

## Horizontal vs Vertical Scaling

### Vertical Scaling (Scale Up)
Add more CPU, RAM, or disk to a single machine.

**Pros**: Simple — no code changes, no distributed system complexity.
**Cons**: Hard limit (biggest machine available), single point of failure, downtime for upgrades, expensive at the top end.

**Use for**: Databases where horizontal scaling is complex (start vertical, shard later), stateful services early in growth.

### Horizontal Scaling (Scale Out)
Add more machines. Distribute load across them.

**Pros**: Theoretically unlimited scale, fault tolerant (one node down doesn't kill the system), cheaper commodity hardware.
**Cons**: Requires stateless services (or distributed state), introduces network complexity, consistency challenges.

**Use for**: Stateless application servers (HTTP APIs), read replicas, workers/consumers.

## Load Balancing

### Algorithms
- **Round Robin**: Equal distribution. Good for homogeneous requests.
- **Least Connections**: Route to server with fewest active connections. Better for variable-duration requests.
- **IP Hash**: Same client always goes to same server (sticky sessions). Use sparingly — breaks if server goes down.
- **Weighted**: Some servers get more traffic (handle capacity differences).

### Layer 4 vs Layer 7
- **L4 (TCP)**: Routes by IP/port. Fast, no request inspection. Use for raw TCP, databases.
- **L7 (HTTP)**: Routes by URL, headers, cookies. Enables path-based routing, A/B testing, header injection. Use for HTTP APIs (nginx, AWS ALB).

### Health Checks
Load balancers must probe backends. Remove unhealthy nodes automatically. Configure: check interval, unhealthy threshold, healthy threshold.

## Database Sharding

Horizontal partitioning — split data across multiple database instances.

### Sharding Strategies

**Range sharding**: Shard by value range (user_id 1-1M on shard 1, 1M-2M on shard 2).
- Pros: Range queries stay on one shard
- Cons: Hotspots if distribution is uneven

**Hash sharding**: `shard = hash(shard_key) % num_shards`
- Pros: Even distribution
- Cons: Range queries hit all shards, resharding is painful

**Directory sharding**: Lookup table maps key → shard.
- Pros: Flexible, can rebalance
- Cons: Lookup table becomes a bottleneck/SPOF

### Choosing a Shard Key
- High cardinality (many unique values)
- Even distribution of writes
- Queries mostly filter by this key
- Avoid hotspots (don't shard by timestamp if all writes go to "now")

### When to Shard
Shard only when you've exhausted: vertical scaling, read replicas (for read scaling), and caching. Sharding adds enormous complexity. Many companies don't need it until 100M+ rows with high write throughput.

## Connection Pooling

Every DB connection is expensive (memory, file descriptors, auth overhead). Connection pooling maintains a pool of reused connections.

**PgBouncer** (Postgres): Sits between app and DB. Modes:
- Session pooling: Connection held for entire client session (least efficient)
- Transaction pooling: Connection returned to pool after each transaction (recommended)
- Statement pooling: Most efficient but disables transactions

Rule of thumb: `pool_size = num_cores * 2 + effective_spindle_count`. Don't open 1000 app server connections to Postgres directly — use a pooler.

## Read Replicas

Offload read traffic to replicas. Replicate from primary (leader) to one or more read replicas (followers).

**Use for**: Analytics queries, reporting, read-heavy endpoints where slight staleness is acceptable.

**Replication lag**: Replicas lag behind primary (ms to seconds). Never read from replica for data that was just written. Use sticky sessions (route same user to primary for N seconds after write) or read-your-writes pattern.

## CDN for Static and Dynamic Content

- **Static**: Images, JS, CSS — always CDN. No reason not to.
- **Dynamic with caching**: Cache API responses at edge for seconds/minutes (useful for public, non-personalized data)
- **Geographic distribution**: Route users to nearest edge node — reduces latency significantly for global users

## Circuit Breaker

Prevent cascading failures when a downstream service is slow or down.

States: **Closed** (normal) → **Open** (failing, reject fast) → **Half-Open** (test one request) → back to Closed.

Implement with: Resilience4j (Java), Polly (.NET), or a service mesh (Envoy/Istio). Never let a slow dependency hold threads/connections indefinitely — always set timeouts first, then add circuit breakers.
