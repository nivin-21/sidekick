# API Design Patterns

## REST vs GraphQL vs gRPC

### REST

**Choose REST when**:
- Public APIs (standard, widely understood)
- Simple CRUD resources
- Caching is important (HTTP cache works natively)
- Team is familiar and clients are diverse (browsers, mobile, third-party)

**REST pitfalls**:
- Over-fetching: endpoint returns more fields than needed
- Under-fetching: need multiple round-trips to assemble a view
- Versioning gets messy at scale

### GraphQL

**Choose GraphQL when**:
- Clients need flexible, varying data shapes (mobile vs web need different fields)
- You have complex, interconnected data (social graph, e-commerce with variants)
- Reducing round-trips and over-fetching is critical
- Frontend teams want autonomy over data fetching

**GraphQL pitfalls**:
- N+1 query problem — use DataLoader for batching
- Complex queries can hammer your database without depth/complexity limits
- Caching is harder (everything is POST to /graphql)
- Not ideal for file uploads or streaming

### gRPC

**Choose gRPC when**:
- Internal service-to-service communication
- High performance, low latency (binary protobuf, HTTP/2 multiplexing)
- Strongly typed contracts (proto files as source of truth)
- Streaming use cases (bidirectional streaming)
- Polyglot environments (generated clients in many languages)

**gRPC pitfalls**:
- Not human-readable (protobuf is binary)
- Browser support is limited (need gRPC-Web proxy)
- Tooling overhead vs REST

## API Versioning

### URL versioning (most common)
`/api/v1/users` → `/api/v2/users`

Pros: Explicit, easy to route, easy to document.
Cons: Clutters URLs, clients must update.

### Header versioning
`Accept: application/vnd.myapi.v2+json`

Pros: Clean URLs.
Cons: Less visible, harder to test in browser.

### Strategy
- Prefer URL versioning for public APIs
- Maintain N-1 versions (support current + previous)
- Deprecate with sunset headers: `Sunset: Sat, 31 Dec 2025 00:00:00 GMT`
- Never break a version — add new endpoints, don't modify existing

## Idempotency

Every mutating operation should be idempotent to handle retries safely.

**Pattern**: Client sends an `Idempotency-Key` header (UUID). Server stores key + response. On duplicate request with same key, return cached response without re-executing.

```
POST /payments
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

Store idempotency keys in Redis with TTL (24h typical). Critical for payment, order creation, and any side-effecting operation.

## Rate Limiting

### Algorithms

- **Fixed window**: Count requests per minute window. Simple but allows bursts at window boundary.
- **Sliding window**: More accurate, smooths out bursts. Higher memory cost.
- **Token bucket**: Tokens refill at a rate. Allows controlled bursts. Common in AWS.
- **Leaky bucket**: Requests queued and processed at fixed rate. Smoothest output.

### Implementation
Redis with atomic Lua scripts or `INCR` + `EXPIRE`. For distributed rate limiting across multiple API servers, Redis is the standard shared state store.

### Response
Return `429 Too Many Requests` with:
- `Retry-After: <seconds>`
- `X-RateLimit-Limit: 1000`
- `X-RateLimit-Remaining: 0`
- `X-RateLimit-Reset: <timestamp>`

## Pagination

### Offset pagination
`GET /users?offset=100&limit=20`

Simple but degrades with large offsets (DB scans rows up to offset). Inconsistent with concurrent writes (rows shift).

### Cursor pagination
`GET /users?cursor=<opaque_token>&limit=20`

Cursor encodes the last seen ID or timestamp. Stable with concurrent writes. Efficient (WHERE id > last_id). Recommended for large datasets.

### Keyset pagination
Like cursor but exposes the key: `GET /users?after_id=12345&limit=20`

## Error Design

Use standard HTTP status codes correctly:
- `400 Bad Request`: Client error, invalid input
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Authenticated but not authorized
- `404 Not Found`: Resource doesn't exist
- `409 Conflict`: State conflict (duplicate, version mismatch)
- `422 Unprocessable Entity`: Validation errors
- `429 Too Many Requests`: Rate limited
- `503 Service Unavailable`: Downstream dependency down

Return structured error bodies:
```json
{"error": {"code": "VALIDATION_ERROR", "message": "email is required", "field": "email"}}
```
