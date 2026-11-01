"""Domain identification (§2.C).

Keyword-scored domain resolution. Multi-domain decisions return every domain
above threshold, primary first. The universal core never depends on a
particular domain — modules register into this resolver.
"""

from __future__ import annotations

import re

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "technology_cybersecurity": [
        "server", "migrate", "migration", "cloud", "deploy", "deployment",
        "security", "breach", "incident", "outage", "downtime", "kubernetes",
        "database", "infrastructure", "cyber", "attack", "ransomware",
        "firewall", "backup", "rollback", "vendor", "saas", "api", "stack",
        "data center", "latency", "failover", "disaster recovery",
    ],
    "business_operations": [
        "business", "startup", "launch", "revenue", "customer", "pricing",
        "subscription", "expand", "expansion", "hire", "hiring", "market",
        "sales", "runway", "burn", "profit", "company", "ecommerce",
        "e-commerce", "franchise", "partnership", "supplier", "inventory",
        "margin", "funding", "investor", "bootstrap", "b2b", "b2c", "churn",
    ],
    "personal_career": [
        "career", "job", "quit", "resign", "study", "degree", "mba",
        "relocate", "relocation", "move to", "family", "personal", "promotion",
        "salary", "course", "upskill", "freelance", "offer letter", "work life",
        "work-life", "internship", "higher studies", "abroad",
    ],
}

_DOMAIN_DISPLAY = {
    "technology_cybersecurity": "Technology & Cybersecurity",
    "business_operations": "Business & Operations",
    "personal_career": "Personal & Career",
    "general": "General reasoning",
}


def display_name(domain: str) -> str:
    return _DOMAIN_DISPLAY.get(domain, domain)


def resolve_domains(text: str) -> list[tuple[str, float]]:
    """Return [(domain, score)] sorted by score desc, only above threshold."""
    lowered = text.lower()
    scores: dict[str, float] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                score += 1.0 + (0.3 if " " in keyword else 0.0)
        if score > 0:
            scores[domain] = round(min(score / 4.0, 1.0), 3)
    if not scores:
        return [("general", 0.2)]
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def primary_domain(text: str) -> str:
    return resolve_domains(text)[0][0]
