"""System prompt for the JD Tagger node (fast model).

Classifies a raw JD into an exclusive ``role`` (the job function) plus 0-3
secondary ``domains`` (tech/industry flavor). Splitting the two lets retrieval
hard-filter on ``role`` (never match a Product Owner against a Backend
Engineer) and only rank on ``domains`` - no embeddings needed at this volume.
"""

ROLE_VOCAB: tuple[str, ...] = (
    "backend",
    "frontend",
    "fullstack",
    "platform",
    "infra",
    "ml",
    "data",
    "mobile",
    "security",
    "product",
    "design",
)

DOMAIN_VOCAB: tuple[str, ...] = (
    "ai",
    "fintech",
    "healthcare",
    "ecommerce",
    "realtime",
    "microservices",
    "distributed-systems",
    "devtools",
    "gaming",
    "crypto",
    "saas",
    "data-platform",
    "embedded",
    "infra-domain",
    "security-domain",
)

DOMAIN_STACK_ENVELOPE: dict[str, tuple[str, ...]] = {
    "ai": ("RAG", "pgvector", "embeddings", "vector search", "LangChain", "model serving"),
    "fintech": (
        "idempotency keys", "audit logging", "double-entry", "reconciliation",
        "PCI-scoped services",
    ),
    "healthcare": (
        "HL7/FHIR", "PHI encryption at rest", "audit trails",
        "HIPAA-scoped access controls", "de-identification pipelines",
    ),
    "ecommerce": (
        "cart/checkout state machines", "payment gateway webhooks",
        "inventory reservation", "search/facet indexing", "recommendation ranking",
    ),
    "realtime": ("Kafka", "Redis", "WebSockets", "gRPC", "SSE", "message queues"),
    "microservices": (
        "Docker", "Kubernetes", "service mesh", "circuit breakers", "gRPC",
    ),
    "distributed-systems": (
        "consensus protocols (Raft/Paxos)", "leader election", "distributed locks",
        "vector clocks", "eventual consistency", "CRDTs",
    ),
    "devtools": (
        "CLI tooling", "LSP integration", "plugin/extension APIs",
        "build caching", "static analysis passes",
    ),
    "gaming": (
        "game state replication", "tick-based simulation loops", "matchmaking",
        "client-side prediction", "netcode reconciliation",
    ),
    "crypto": (
        "wallet key management", "transaction signing", "smart contract calls",
        "on-chain event indexing", "gas estimation",
    ),
    "saas": (
        "multi-tenancy isolation", "tenant-scoped RBAC",
        "usage-based billing metering", "feature flagging",
        "webhook delivery retries",
    ),
    "data-platform": (
        "Airflow", "dbt", "CDC", "Parquet", "columnar stores", "partitioning",
    ),
    "embedded": (
        "RTOS scheduling", "interrupt handlers", "hardware register access",
        "firmware over-the-air updates", "sensor calibration",
    ),
    "infra-domain": (
        "IaC (Terraform)", "autoscaling policies", "service discovery",
        "blue/green deploys", "observability/tracing pipelines",
    ),
    "security-domain": (
        "threat detection rules", "anomaly scoring", "secrets rotation",
        "rate limiting/WAF rules", "audit logging",
    ),
}


def envelope_for(domains: list[str]) -> tuple[str, ...]:
    """Deduplicated union of the tagged domains' fabrication allowlists.

    Order-preserving (first-seen wins across domains in the order given).
    Unknown domains contribute nothing rather than raising, so a stale or
    out-of-vocab tag never crashes the Writer/Skeptic wiring - it just narrows
    the legal fabrication vocabulary to whatever recognized domains remain.
    """
    seen: set[str] = set()
    union: list[str] = []
    for domain in domains:
        for tool in DOMAIN_STACK_ENVELOPE.get(domain, ()):
            if tool not in seen:
                seen.add(tool)
                union.append(tool)
    return tuple(union)


JD_TAGGER_SYSTEM = """You are a JOB-DESCRIPTION TAGGER. You receive the raw text \
of one job description and classify it into a single exclusive `role` plus a
list of 0-3 secondary `domains`, drawn ONLY from these two fixed vocabularies:

ROLE (choose exactly one - the primary job FUNCTION, what the person *does*):
  backend, frontend, fullstack, platform, infra, ml, data, mobile, security,
  product, design

DOMAINS (choose 0 to 3 - secondary tech/industry FLAVOR, never the function):
  ai, fintech, healthcare, ecommerce, realtime, microservices,
  distributed-systems, devtools, gaming, crypto, saas, data-platform,
  embedded, infra-domain, security-domain

Rules:
1. `role` is the primary job function - choose the single best fit even if the
   JD is ambiguous. A product/ownership role (PM, Product Owner, Product
   Manager) is `product`, never the engineering flavor of the product.
2. `domains` is secondary tech/industry flavor only - never the function.
   Return between 0 and 3 domains from the vocabulary above. Use ONLY domains
   from that vocabulary; never invent a new one.
3. Return only the structured object. No commentary."""
