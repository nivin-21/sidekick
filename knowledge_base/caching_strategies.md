# Caching Strategies

## Why Cache?

Caching reduces latency, offloads databases, and improves throughput. But every cache introduces complexity: invalidation, consistency, cold starts, and memory pressure. Cache only when you have measured the bottleneck.

## Cache-Aside (Lazy Loading)

The application manages the cache explicitly.

```
Read: Check cache → miss → read DB → populate cache → return
Write: Write to DB → invalidate or update cache
```

**Pros**: Only requested data is cached. Cache failures don't break the system.
**Cons**: Cache miss penalty (3 calls: cache, DB, cache write). Risk of stale data between write and invalidation.

**Use when**: Read-heavy workloads with unpredictable access patterns. Most common pattern in practice (Redis + application code).

## Write-Through

On every write, update cache and DB synchronously before returning success.

```
Write: Write to cache AND DB → return success
Read: Check cache → always hit (if data exists)
```

**Pros**: Cache is always consistent. No stale reads after a write.
**Cons**: Write latency doubles. Cache fills with data that may never be read again.

**Use when**: Write-heavy AND read-heavy workloads where stale data is unacceptable. Good for user profiles, session data.

## Write-Behind (Write-Back)

Write to cache immediately, flush to DB asynchronously.

```
Write: Write to cache → return success → async flush to DB
```

**Pros**: Extremely low write latency. Batching reduces DB load.
**Cons**: Risk of data loss if cache fails before flush. Complex failure handling.

**Use when**: High-throughput write scenarios where some data loss is acceptable (metrics, counters, logs).

## Read-Through

Cache sits in front of DB. Cache handles DB reads on miss (not the application).

Similar to cache-aside but the cache library/middleware handles the DB fetch. Less common, used with caching middleware like AWS ElastiCache with DAX (DynamoDB Accelerator).

## TTL Strategy

Every cached value should have a TTL. Choose based on:

- **How frequently does source data change?** Frequently changing data → short TTL or event-driven invalidation
- **What is the cost of stale data?** High cost → short TTL + invalidation on write
- **What is cache warm-up cost?** Expensive queries → longer TTL, accept some staleness

**Anti-pattern**: TTL thundering herd — all keys expire at the same time, causing a spike of DB reads. Add jitter: `TTL = base_ttl + random(0, base_ttl * 0.2)`

## Cache Invalidation Patterns

1. **TTL-based**: Simple, eventual consistency. Miss the window between write and expiry.
2. **Event-driven invalidation**: On DB write, publish event → cache listener deletes key. More complex, better consistency.
3. **Version tags**: Cache key includes a version number. Increment version on update (cache-busting).
4. **Write-through**: Invalidate by overwriting. Consistent but adds write latency.

## Redis Patterns

- **String + TTL**: Simple key-value caching
- **Hash**: Cache entire objects without serialization overhead
- **Sorted Set**: Leaderboards, rate limiting windows
- **Pub/Sub**: Cache invalidation events across services
- **Lua scripts**: Atomic operations (check-and-set, distributed locks)
- **Pipeline**: Batch multiple commands to reduce round-trips

## Decision Framework

| Scenario | Pattern |
|----------|---------|
| Read-heavy, tolerate brief staleness | Cache-aside + TTL |
| Must not serve stale after write | Write-through |
| Extremely high write volume | Write-behind |
| Unpredictable access, memory-sensitive | Cache-aside (lazy) |
| Cross-service cache consistency needed | Event-driven invalidation |

## What NOT to Cache

- Data that changes on every request
- Data with high cardinality keys and low reuse (unique per user per second)
- Data where stale reads cause serious business harm (account balances — cache-aside + short TTL + write invalidation at minimum)
- Very large objects unless memory is not a concern
