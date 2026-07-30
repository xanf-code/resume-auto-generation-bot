"""JD Tagger agent - raw job description -> role/domains classification.

A cheap, fast (Haiku) pass that splits the JD into an exclusive ``role`` (the
job function) and 0-3 secondary ``domains`` (tech/industry flavor). The split
lets retrieval hard-filter on ``role`` and only rank on ``domains`` (no
partial credit, no embeddings). Reuses the existing fast-model plumbing - no
new infrastructure.
"""
import logging
from dataclasses import dataclass, field

from src.pipeline.llm import parse_fast
from src.pipeline.schemas import JDTags
from src.prompts.jd_tagger import DOMAIN_VOCAB, JD_TAGGER_SYSTEM, ROLE_VOCAB

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class JdClassification:
    """The tagger's role/domain classification, ready to feed retrieval and tuning."""

    role: str | None  # exactly one ROLE_VOCAB member, or None on failure/out-of-vocab
    domains: list[str] = field(default_factory=list)  # deduped, in-vocab, order-preserved, <=3

    @property
    def combined_tags(self) -> list[str]:
        """Flat tag list for Loop B tuning (``[role, *domains]``); role first, deduped."""
        tags = [self.role] if self.role else []
        for d in self.domains:
            if d not in tags:
                tags.append(d)
        return tags


def classify_jd_type(jd_raw: str) -> JdClassification:
    """Classify a raw JD into an exclusive ``role`` plus in-vocabulary ``domains``.

    Never fails the run: any error from the model (or an entirely out-of-vocab
    response) yields ``JdClassification(role=None, domains=[])`` rather than
    propagating.
    """
    try:
        result = parse_fast(JD_TAGGER_SYSTEM, jd_raw, JDTags)
    except Exception as exc:
        log.warning("jd_tagger    | call failed (%s) - emitting no classification", exc)
        return JdClassification(role=None, domains=[])

    role = result.role if result.role in ROLE_VOCAB else None

    seen: set[str] = set()
    domains: list[str] = []
    for domain in result.domains:
        if domain in DOMAIN_VOCAB and domain not in seen:
            seen.add(domain)
            domains.append(domain)
        if len(domains) == 3:
            break

    return JdClassification(role=role, domains=domains)
