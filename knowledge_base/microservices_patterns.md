# Microservices Patterns

## When to Use Microservices

Microservices are not a default — they are a solution to specific scaling problems. Start with a monolith. Move to microservices when you have:
- Independent scaling needs for different components
- Multiple teams that need to deploy independently
- Truly different SLAs for different parts of the system
- Genuine domain boundaries that map to separate services

Conway's Law: your architecture will mirror your team communication structure. Microservices only make sense when your team is large enough to justify it.

## Service Decomposition

### By Business Capability
Each service owns a business capability: OrderService, PaymentService, InventoryService.

Align with domain-driven design (DDD) bounded contexts. Each context has its own ubiquitous language, data model, and team.

### Strangler Fig Pattern
Incrementally migrate a monolith to microservices. New features go into new services. Existing monolith features are migrated one at a time. A facade (API gateway or proxy) routes to old monolith or new service.

Never rewrite the entire monolith at once. The strangler fig pattern is the only proven path.

## API Gateway

Single entry point for all clients. Handles:
- Request routing to downstream services
- Authentication / JWT validation
- Rate limiting
- SSL termination
- Request/response transformation
- Aggregating multiple service calls into one response

Examples: AWS API Gateway, Kong, Nginx, Envoy.

**Don't put business logic in the API gateway.** It should be a dumb router/policy enforcer, not a service.

## Circuit Breaker

Prevents cascading failures when downstream services fail.

States:
- **Closed**: Normal operation. Calls pass through. Failures counted.
- **Open**: Failure threshold exceeded. Calls rejected immediately (fast fail). Timer starts.
- **Half-Open**: Timer expired. One test request sent. If success → Closed. If failure → Open again.

Configure: failure threshold (e.g., 50% of last 10 requests), wait duration in open state, test request count in half-open.

**Always pair with**: timeouts (circuit breaker is useless if calls hang forever), fallbacks (return cached data or default response when open).

## Bulkhead Pattern

Isolate resources for different services or operations so one failure doesn't exhaust shared resources.

Example: If service A calls services B and C, use separate thread pools or connection pools for each. B being slow doesn't starve connections for C.

Named after ship bulkheads that compartmentalize flooding. Limit blast radius.

## Service Mesh

Infrastructure layer for service-to-service communication. Deployed as sidecar proxies (e.g., Envoy) alongside each service.

Provides: mTLS encryption, observability (traces, metrics), traffic management, circuit breaking, retries — all without application code changes.

**Istio / Linkerd**: Popular implementations.

**Use when**: You have many services and want consistent policy enforcement and observability without polluting application code. Adds operational complexity — only worthwhile at sufficient scale.

## Observability in Microservices

A distributed system without observability is a black box. The three pillars:

**Metrics**: Aggregated numbers over time (Prometheus + Grafana). Track: request rate, error rate, latency percentiles (p50, p99), saturation.

**Logs**: Structured JSON logs with correlation IDs. Every service log must include: trace_id, span_id, service_name, environment. Use: ELK Stack, Loki, Datadog.

**Distributed Tracing**: End-to-end request flow across services. OpenTelemetry is the standard. Jaeger or Zipkin as backend. Critical for debugging latency in multi-service flows.

**Correlation IDs**: Generate a unique request ID at the API gateway. Propagate it through all service calls via headers. Log it everywhere. This is the minimum viable observability step.

## Data Ownership

Each microservice must own its data. Never share databases between services.

If service A needs data from service B:
- Call service B's API (synchronous)
- Subscribe to events from service B and maintain a local read model (asynchronous, eventual consistency)

Sharing a database between services creates tight coupling — schema changes in one service break others.

## Health Checks

Every service should expose:
- `GET /health/live`: Is the process alive? (liveness probe)
- `GET /health/ready`: Is the service ready to accept traffic? (readiness probe — checks DB connections, dependencies)

Kubernetes uses these for rolling deployments and auto-restart.
