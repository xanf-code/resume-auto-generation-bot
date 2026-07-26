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
