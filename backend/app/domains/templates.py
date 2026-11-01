"""Domain possibility templates.

These templates are the deterministic discovery corpus behind the mock
provider. They encode plausible, non-contradictory outcome structures for the
three initial validation domains (§14) plus a general fallback.

Probability discipline (§7.1): most possibilities are returned
``unquantified`` with ``estimate = None``. A minority carry ``model_based``
estimates produced by explicit, disclosed arithmetic models (see
``app/simulation/engine.py``) or simple transparent formulas stated in the
rationale. Nothing here fabricates a number to look confident.

Determinism: ``seed`` drives stable variant selection so repeated analyses
with fixed inputs reproduce identical graphs (§16.5).
"""

from __future__ import annotations

import random
from typing import Any

from app.domains.resolver import primary_domain, resolve_domains

Unquantified = {"status": "unquantified"}


def _pick(rng: random.Random, options: list[Any]) -> Any:
    return options[rng.randrange(len(options))]


def _prio(impact: float, relevance: float, evidence: float, uncertainty: float,
          info_value: float, cost: float) -> dict[str, float]:
    return {
        "impact": impact,
        "relevance": relevance,
        "evidence_availability": evidence,
        "uncertainty": uncertainty,
        "information_value": info_value,
        "computational_cost": cost,
    }


# ---------------------------------------------------------------------------
# Technology & cybersecurity
# ---------------------------------------------------------------------------

def _tech_possibilities(rng: random.Random, decision: str) -> list[dict]:
    migration_flavor = _pick(rng, ["data loss window", "cost overrun", "skill gap"])
    return [
        {
            "key": "smoother_migration",
            "title": "Migration completes within the planned window",
            "description": (
                "Cutover finishes inside the scheduled maintenance window with "
                "only minor, quickly reversed issues."
            ),
            "conditions": [
                "Staging environment faithfully mirrors production",
                "Rollback plan is tested before cutover",
                "Runbook ownership is assigned per service",
            ],
            "triggers": ["Cutover window opens"],
            "causes": ["Thorough rehearsal reduces unknown failure modes"],
            "consequences": [
                "Team confidence in the new platform increases",
                "Operational toil drops once legacy systems are retired",
            ],
            "time_horizon": {"minimum": 1, "maximum": 3, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Planned outcome; modest positive value."},
            "priorities": _prio(0.5, 0.9, 0.6, 0.3, 0.4, 0.2),
        },
        {
            "key": "extended_downtime",
            "title": "Cutover overruns and causes extended downtime",
            "description": (
                f"Unexpected incompatibilities extend the cutover; customers "
                f"experience an outage longer than the announced window "
                f"(risk concentrates around {migration_flavor})."
            ),
            "conditions": [
                "Undocumented dependencies exist between services",
                "Rollback is slower than fail-forward",
            ],
            "triggers": ["Critical dependency fails during cutover"],
            "causes": ["Incomplete dependency mapping", "Time pressure at end of window"],
            "consequences": [
                "SLA credits or penalties may apply",
                "On-call burnout and trust erosion",
                "Executive scrutiny of the migration programme",
            ],
            "time_horizon": {"minimum": 0, "maximum": 1, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Direct customer and reputation impact."},
            "priorities": _prio(0.85, 0.9, 0.5, 0.6, 0.8, 0.3),
        },
        {
            "key": "cost_overrun",
            "title": "Cloud spend exceeds the migration budget",
            "description": (
                "Egress fees, dual-running costs and reserved-capacity "
                "mistakes push spend beyond plan."
            ),
            "conditions": ["Dual-run period extends beyond plan", "No FinOps guardrails in place"],
            "triggers": ["First monthly bill after cutover"],
            "causes": ["Unbudgeted egress", "Over-provisioned instances"],
            "consequences": [
                "Pressure to cut observability or redundancy",
                "Delayed retirement of legacy systems",
            ],
            "time_horizon": {"minimum": 1, "maximum": 6, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Budget variance, usually recoverable."},
            "priorities": _prio(0.6, 0.8, 0.7, 0.4, 0.6, 0.2),
        },
        {
            "key": "security_regression",
            "title": "Migration temporarily weakens the security posture",
            "description": (
                "New network paths, widened security groups or secrets "
                "mishandling create exposure during and after cutover."
            ),
            "conditions": [
                "Infrastructure-as-code review is rushed",
                "Credentials are re-used across environments",
            ],
            "triggers": ["New exposure is reachable from the public internet"],
            "causes": ["Configuration drift during dual-running"],
            "consequences": [
                "Increased attack surface",
                "Possible compliance findings",
                "Emergency hardening work",
            ],
            "time_horizon": {"minimum": 0, "maximum": 3, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "critical", "explanation": "Security regressions can compound silently."},
            "priorities": _prio(0.9, 0.85, 0.5, 0.65, 0.9, 0.4),
        },
        {
            "key": "talent_bottleneck",
            "title": "Key engineers become a bottleneck",
            "description": (
                "The people who understand the legacy system are overloaded "
                "with cutover work; other initiatives stall."
            ),
            "conditions": ["Legacy knowledge concentrated in 1–2 people"],
            "triggers": ["Cutover critical path names the same engineers repeatedly"],
            "causes": ["Bus-factor risk in the existing architecture"],
            "consequences": [
                "Delivery slips in adjacent projects",
                "Retention risk for those engineers",
            ],
            "time_horizon": {"minimum": 1, "maximum": 4, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Organisational, not strictly technical."},
            "priorities": _prio(0.55, 0.7, 0.6, 0.45, 0.5, 0.2),
        },
    ]


def _tech_children(rng: random.Random, parent_key: str, decision: str) -> list[dict]:
    catalog: dict[str, list[dict]] = {
        "extended_downtime": [
            {
                "key": "sla_credits",
                "title": "SLA credits trigger contractual review",
                "description": "Downtime crosses the SLA threshold; finance processes credits and legal reviews force-majeure clauses.",
                "conditions": ["Contractual SLA with credits exists"],
                "triggers": ["Measured availability drops below the SLA floor"],
                "causes": ["Extended downtime from the cutover"],
                "consequences": ["Revenue recognition impact", "Tougher renewal negotiation"],
                "time_horizon": {"minimum": 0, "maximum": 2, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Financial and legal overhead."},
                "priorities": _prio(0.5, 0.75, 0.55, 0.4, 0.55, 0.2),
            },
            {
                "key": "trust_repair",
                "title": "Proactive communication converts damage into trust",
                "description": "Transparent postmortem and credits retain most customers despite the outage.",
                "conditions": ["Status page and postmortem published quickly", "Credits offered without dispute"],
                "triggers": ["Customer escalation volume rises"],
                "causes": ["Outage + honest response"],
                "consequences": ["Stronger customer relationships", "Postmortem becomes org standard"],
                "time_horizon": {"minimum": 1, "maximum": 3, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Recovery path with positive upside."},
                "priorities": _prio(0.45, 0.7, 0.5, 0.5, 0.6, 0.3),
            },
        ],
        "security_regression": [
            {
                "key": "pen_test_finding",
                "title": "Post-migration pen test finds the new exposure",
                "description": "A scheduled or triggered assessment catches the widened attack surface before adversaries do.",
                "conditions": ["Assessment scheduled within the exposure window"],
                "triggers": ["Scanner or red-team probes the new paths"],
                "causes": ["Configuration drift"],
                "consequences": ["Remediation sprint", "Policy change for future cutovers"],
                "time_horizon": {"minimum": 0, "maximum": 2, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Costly but contains the risk."},
                "priorities": _prio(0.6, 0.8, 0.6, 0.45, 0.7, 0.3),
            },
            {
                "key": "external_intrusion",
                "title": "Adversary exploits the exposure before it is closed",
                "description": "Internet-facing misconfiguration is discovered and abused by an external actor.",
                "conditions": ["Exposure is internet-reachable", "No runtime detection on new paths"],
                "triggers": ["Repeated probing followed by authenticated access attempts"],
                "causes": ["Security group widened during cutover"],
                "consequences": ["Incident response activation", "Possible data exfiltration review"],
                "time_horizon": {"minimum": 0, "maximum": 3, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "critical", "explanation": "Full incident territory."},
                "priorities": _prio(0.95, 0.8, 0.45, 0.7, 0.95, 0.5),
            },
        ],
        "cost_overrun": [
            {
                "key": "finops_controls",
                "title": "FinOps guardrails bring spend back under plan",
                "description": "Budgets, alerts and right-sizing reverse most of the overrun within a quarter.",
                "conditions": ["Cost allocation tags applied at cutover"],
                "triggers": ["Budget alert fires"],
                "causes": ["Overspend detected early"],
                "consequences": ["Sustainable unit economics", "Showback culture"],
                "time_horizon": {"minimum": 1, "maximum": 3, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Management response, bounded cost."},
                "priorities": _prio(0.35, 0.75, 0.65, 0.35, 0.5, 0.2),
            },
        ],
        "smoother_migration": [
            {
                "key": "legacy_retirement",
                "title": "Legacy systems retire on schedule",
                "description": "Old environment decommissioned, releasing licences and operational load.",
                "conditions": ["Data migration validated", "No dual-run extensions"],
                "triggers": ["Stability checkpoint passed"],
                "causes": ["Successful migration"],
                "consequences": ["Run-rate savings", "Simplified architecture"],
                "time_horizon": {"minimum": 2, "maximum": 6, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Positive, incremental."},
                "priorities": _prio(0.3, 0.7, 0.6, 0.25, 0.35, 0.1),
            },
        ],
        "talent_bottleneck": [
            {
                "key": "knowledge_transfer",
                "title": "Formal knowledge-transfer programme unblocks the team",
                "description": "Pairing, docs and shadow on-call spread legacy knowledge before cutover peaks.",
                "conditions": ["Management prioritises the programme"],
                "triggers": ["Bottleneck identified in critical path review"],
                "causes": ["Concentrated legacy knowledge"],
                "consequences": ["Higher bus factor", "Calmer on-call"],
                "time_horizon": {"minimum": 1, "maximum": 3, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Preventive, low downside."},
                "priorities": _prio(0.35, 0.7, 0.55, 0.3, 0.5, 0.25),
            },
        ],
    }
    return catalog.get(parent_key, [])


# ---------------------------------------------------------------------------
# Business & operations
# ---------------------------------------------------------------------------

def _business_possibilities(rng: random.Random, decision: str) -> list[dict]:
    return [
        {
            "key": "slow_growth",
            "title": "Customer acquisition is slower than expected",
            "description": (
                "Early demand exists but conversion and word-of-mouth take "
                "longer to compound than the plan assumes."
            ),
            "conditions": [
                "Acquisition depends on a single channel",
                "Product-market fit is still unproven",
            ],
            "triggers": ["First two months miss the acquisition target by >30%"],
            "causes": ["Unfamiliar positioning", "Long trust-building cycle in this market"],
            "consequences": [
                "Runway pressure increases",
                "Team pivots messaging or channel mix",
            ],
            "time_horizon": {"minimum": 3, "maximum": 9, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Directly threatens survival in early stages."},
            "priorities": _prio(0.8, 0.95, 0.5, 0.6, 0.85, 0.2),
            "simulate": {"kind": "cash_runway"},
        },
        {
            "key": "strong_traction",
            "title": "Early customers convert and refer others",
            "description": "Retention and referrals exceed plan, pulling revenue forward.",
            "conditions": ["Onboarding delivers value in the first week", "Pricing matches willingness to pay"],
            "triggers": ["Referral share of signups crosses ~20%"],
            "causes": ["Strong initial fit with a narrow niche"],
            "consequences": ["Hiring decisions brought forward", "Possible funding interest"],
            "time_horizon": {"minimum": 2, "maximum": 6, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Opens expansion options."},
            "priorities": _prio(0.75, 0.9, 0.55, 0.55, 0.7, 0.2),
        },
        {
            "key": "cash_strain",
            "title": "Cash flow tightens before revenue stabilises",
            "description": "Fixed costs and payment delays squeeze the runway despite decent demand.",
            "conditions": ["Monthly burn exceeds contribution margin", "Receivables > 45 days"],
            "triggers": ["Two consecutive months of negative operating cash flow"],
            "causes": ["Growth spending ahead of revenue", "Invoice terms with larger customers"],
            "consequences": [
                "Scope cut or deferral of planned hires",
                "Emergency financing discussion",
            ],
            "time_horizon": {"minimum": 2, "maximum": 8, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "critical", "explanation": "Existential if unaddressed."},
            "priorities": _prio(0.9, 0.9, 0.6, 0.6, 0.9, 0.25),
        },
        {
            "key": "operational_strain",
            "title": "Operations strain under growth",
            "description": "Support load, fulfilment errors or quality issues rise faster than the team.",
            "conditions": ["Manual processes still dominate fulfilment"],
            "triggers": ["Support first-response time doubles"],
            "causes": ["Volume growth outpaces process maturity"],
            "consequences": ["Churn risk rises", "Emergency tooling or hiring"],
            "time_horizon": {"minimum": 3, "maximum": 10, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Manageable with early investment."},
            "priorities": _prio(0.6, 0.75, 0.55, 0.45, 0.6, 0.3),
        },
        {
            "key": "competitive_response",
            "title": "An established competitor responds",
            "description": "A larger player bundles a similar offer or drops price in your segment.",
            "conditions": ["Segment is visible to incumbents"],
            "triggers": ["Competitor announces a comparable product or promotion"],
            "causes": ["Your traction becomes observable"],
            "consequences": [
                "Sales cycle lengthens",
                "Differentiation work accelerates",
            ],
            "time_horizon": {"minimum": 4, "maximum": 14, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Common but not automatically fatal."},
            "priorities": _prio(0.65, 0.7, 0.45, 0.6, 0.65, 0.3),
        },
    ]


def _business_children(rng: random.Random, parent_key: str, decision: str) -> list[dict]:
    catalog: dict[str, list[dict]] = {
        "cash_strain": [
            {
                "key": "cost_reset",
                "title": "A deliberate cost reset extends runway",
                "description": "Non-core spend frozen, hiring paused; runway lengthens enough to reach the next milestone.",
                "conditions": ["Fixed costs can be reduced by ≥20% within 60 days"],
                "triggers": ["Runway estimate drops below 6 months"],
                "causes": ["Cash flow tightening"],
                "consequences": ["Slower feature velocity", "Renewed focus on paying segments"],
                "time_horizon": {"minimum": 1, "maximum": 3, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Painful but preserves options."},
                "priorities": _prio(0.55, 0.85, 0.65, 0.4, 0.7, 0.2),
            },
            {
                "key": "bridge_financing",
                "title": "Bridge financing or a credit line closes the gap",
                "description": "Founder network or existing investors provide short-term capital on acceptable terms.",
                "conditions": ["Investor relationships are warm", "Story shows a clear path to milestone"],
                "triggers": ["Runway below board-agreed threshold"],
                "causes": ["Cash strain"],
                "consequences": ["Dilution or debt service", "Time bought to prove retention"],
                "time_horizon": {"minimum": 1, "maximum": 4, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Buys time at a price."},
                "priorities": _prio(0.6, 0.8, 0.5, 0.55, 0.75, 0.4),
            },
            {
                "key": "wind_down",
                "title": "The business winds down in an orderly way",
                "description": "If the gap cannot be closed, assets are liquidated and obligations met in order.",
                "conditions": ["No viable financing or cost reset path"],
                "triggers": ["Runway below ~30 days with no inbound terms"],
                "causes": ["Unresolved cash strain"],
                "consequences": ["Founder learning and network retained", "Creditor obligations settled"],
                "time_horizon": {"minimum": 3, "maximum": 9, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "critical", "explanation": "Terminal branch for the venture, not the founder."},
                "priorities": _prio(0.95, 0.7, 0.4, 0.65, 0.8, 0.5),
            },
        ],
        "slow_growth": [
            {
                "key": "pivot_segment",
                "title": "A segment pivot unlocks faster growth",
                "description": "Evidence points to a narrower niche with sharper willingness to pay; positioning is re-cut.",
                "conditions": ["Qualitative interviews repeatedly surface the same niche"],
                "triggers": ["Acquisition cost in the original segment stays above target"],
                "causes": ["Slow growth in the broad segment"],
                "consequences": ["Clearer messaging", "Smaller initial TAM but higher conversion"],
                "time_horizon": {"minimum": 2, "maximum": 5, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "high", "explanation": "Strategic course change."},
                "priorities": _prio(0.7, 0.9, 0.55, 0.55, 0.85, 0.35),
            },
        ],
        "strong_traction": [
            {
                "key": "raise_round",
                "title": "Traction attracts a priced funding round",
                "description": "Growth metrics support a raise that funds hiring ahead of demand.",
                "conditions": ["Retention and growth rates above category medians"],
                "triggers": ["Inbound interest from two or more investors"],
                "causes": ["Strong early traction"],
                "consequences": ["Higher expectations", "Hiring plan accelerates"],
                "time_horizon": {"minimum": 3, "maximum": 9, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "high", "explanation": "Changes the company's trajectory and obligations."},
                "priorities": _prio(0.75, 0.75, 0.5, 0.6, 0.7, 0.5),
            },
        ],
        "operational_strain": [
            {
                "key": "process_investment",
                "title": "Early process investment prevents a quality spiral",
                "description": "Tooling, checklists and a support hire keep quality stable through the growth spurt.",
                "conditions": ["Budget for one ops hire exists"],
                "triggers": ["Error rate crosses an agreed threshold"],
                "consequences": ["Sustainable scaling", "Lower churn"],
                "causes": ["Operational strain detected early"],
                "time_horizon": {"minimum": 1, "maximum": 4, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Bounded investment."},
                "priorities": _prio(0.4, 0.75, 0.6, 0.35, 0.55, 0.2),
            },
        ],
        "competitive_response": [
            {
                "key": "differentiation_focus",
                "title": "Deep differentiation neutralises the response",
                "description": "Focus on a workflow the incumbent cannot bundle keeps the core segment.",
                "conditions": ["Switching costs can be raised legitimately (integrations, data)"],
                "triggers": ["Win-rate holds steady for a quarter"],
                "causes": ["Competitor response"],
                "consequences": ["Stronger moat", "Possible niche consolidation"],
                "time_horizon": {"minimum": 4, "maximum": 12, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Defensive success with upside."},
                "priorities": _prio(0.6, 0.7, 0.5, 0.5, 0.65, 0.35),
            },
        ],
    }
    return catalog.get(parent_key, [])


# ---------------------------------------------------------------------------
# Personal & career
# ---------------------------------------------------------------------------

def _career_possibilities(rng: random.Random, decision: str) -> list[dict]:
    return [
        {
            "key": "smooth_transition",
            "title": "The transition lands roughly as planned",
            "description": "Timeline, finances and energy hold up; the move produces its main intended benefit.",
            "conditions": ["Savings cover the planned gap", "Support network is in place"],
            "triggers": ["First major milestone of the new path is completed"],
            "causes": ["Realistic planning and steady execution"],
            "consequences": ["New baseline established", "Optionality improves"],
            "time_horizon": {"minimum": 6, "maximum": 18, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Reshapes the medium-term trajectory."},
            "priorities": _prio(0.7, 0.95, 0.55, 0.4, 0.6, 0.2),
        },
        {
            "key": "financial_pressure",
            "title": "Financial pressure exceeds the plan",
            "description": "Cost of living, tuition or lost income outruns the budget built into the decision.",
            "conditions": ["Savings buffer < 6 months of fixed costs", "Income gap is larger than assumed"],
            "triggers": ["Two consecutive months over budget"],
            "causes": ["Optimistic cost assumptions"],
            "consequences": [
                "Part-time work or a slower pace",
                "Stress affecting performance in the new path",
            ],
            "time_horizon": {"minimum": 2, "maximum": 9, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Can force a change of plan mid-way."},
            "priorities": _prio(0.8, 0.9, 0.6, 0.5, 0.8, 0.2),
        },
        {
            "key": "opportunity_cost",
            "title": "The path not taken proves costly",
            "description": "Meanwhile, staying put would have produced a promotion, income rise or simpler logistics.",
            "conditions": ["Current employer retains strong upward momentum"],
            "triggers": ["Former peer is promoted into the role you considered"],
            "causes": ["Forgone counterfactual path"],
            "consequences": ["Regret and second-guessing", "Revised comparison of alternatives"],
            "time_horizon": {"minimum": 6, "maximum": 24, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Psychological and comparative, not an actual loss."},
            "priorities": _prio(0.5, 0.7, 0.4, 0.65, 0.6, 0.15),
        },
        {
            "key": "skill_compounding",
            "title": "New skills compound into better options",
            "description": "The capabilities built early start attracting better roles, projects or clients than before.",
            "conditions": ["Practice is deliberate, not just exposure"],
            "triggers": ["First external validation (offer, project, publication)"],
            "causes": ["Structured skill investment"],
            "consequences": ["Higher earning power", "Broader network"],
            "time_horizon": {"minimum": 9, "maximum": 30, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "The main compounding upside of the decision."},
            "priorities": _prio(0.75, 0.85, 0.5, 0.5, 0.75, 0.25),
        },
        {
            "key": "identity_social_strain",
            "title": "Identity and social strain build",
            "description": "Being off the conventional track creates friction with family expectations or self-image.",
            "conditions": ["Social circle maps status to title or employer"],
            "triggers": ["A family conversation turns tense"],
            "causes": ["Divergence from the norm of the peer group"],
            "consequences": ["Motivation fluctuates", "Need for a new peer community"],
            "time_horizon": {"minimum": 1, "maximum": 12, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Often underestimated in initial planning."},
            "priorities": _prio(0.5, 0.65, 0.45, 0.6, 0.55, 0.15),
        },
    ]


def _career_children(rng: random.Random, parent_key: str, decision: str) -> list[dict]:
    catalog: dict[str, list[dict]] = {
        "financial_pressure": [
            {
                "key": "income_bridge",
                "title": "A bridge income covers the gap",
                "description": "Freelance, part-time or contract work keeps the plan solvent without abandoning it.",
                "conditions": ["Marketable skill with short sales cycle"],
                "triggers": ["Buffer drops below the agreed floor"],
                "causes": ["Financial pressure"],
                "consequences": ["Slower main-path progress but plan survives"],
                "time_horizon": {"minimum": 1, "maximum": 6, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Trade speed for survivability."},
                "priorities": _prio(0.55, 0.85, 0.6, 0.4, 0.7, 0.3),
            },
            {
                "key": "plan_abandoned",
                "title": "The plan is paused or abandoned for now",
                "description": "Financial or family pressure wins; the path is deferred until conditions change.",
                "conditions": ["Buffer exhausted without bridge income"],
                "triggers": ["A concrete financial shock (rent, tuition, medical)"],
                "causes": ["Unsustainable cash gap"],
                "consequences": ["Return to previous track", "Revised plan with a larger buffer next time"],
                "time_horizon": {"minimum": 2, "maximum": 8, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "high", "explanation": "Reversal, but with learned constraints."},
                "priorities": _prio(0.7, 0.7, 0.55, 0.5, 0.7, 0.35),
            },
        ],
        "skill_compounding": [
            {
                "key": "portfolio_leverage",
                "title": "A visible portfolio pulls in unsolicited offers",
                "description": "Public work becomes a magnet for roles and projects you did not apply for.",
                "conditions": ["Work is published with your name on it"],
                "triggers": ["First inbound recruiter or client approach"],
                "causes": ["Compounded skills + visibility"],
                "consequences": ["Negotiating position improves"],
                "time_horizon": {"minimum": 12, "maximum": 36, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "high", "explanation": "Changes the default opportunity set."},
                "priorities": _prio(0.7, 0.75, 0.5, 0.45, 0.7, 0.2),
            },
        ],
        "identity_social_strain": [
            {
                "key": "new_community",
                "title": "A new peer community restores belonging",
                "description": "Cohort, meetups or mentors on the same path replace the lost status anchor.",
                "conditions": ["Regular contact with people on similar paths"],
                "triggers": ["Feeling of isolation peaks then eases after joining a group"],
                "causes": ["Divergence from old peer group"],
                "consequences": ["Motivation stabilises", "Network effects compound"],
                "time_horizon": {"minimum": 2, "maximum": 9, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Recovery branch with lasting upside."},
                "priorities": _prio(0.4, 0.6, 0.5, 0.45, 0.55, 0.15),
            },
        ],
        "smooth_transition": [
            {
                "key": "new_baselines",
                "title": "The new path becomes the new normal",
                "description": "Identity, routine and income stabilise at the new level.",
                "conditions": ["No major external shock in the first year"],
                "triggers": ["Annual review point reached"],
                "causes": ["Successful transition"],
                "consequences": ["Attention freed for the next goal"],
                "time_horizon": {"minimum": 9, "maximum": 18, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "moderate", "explanation": "Consolidation of the decision."},
                "priorities": _prio(0.45, 0.7, 0.55, 0.3, 0.4, 0.1),
            },
        ],
        "opportunity_cost": [
            {
                "key": "revised_comparison",
                "title": "A sober comparison replaces regret",
                "description": "Once both paths are visible with real data, the comparison becomes decision-quality rather than rumination.",
                "conditions": ["You track outcomes on both paths deliberately"],
                "triggers": ["Enough elapsed time for real numbers"],
                "causes": ["Opportunity-cost awareness"],
                "consequences": ["Better future decisions", "Regret loses its charge"],
                "time_horizon": {"minimum": 12, "maximum": 24, "unit": "months"},
                "probability": Unquantified,
                "impact": {"level": "low", "explanation": "Meta-skill improvement."},
                "priorities": _prio(0.35, 0.6, 0.5, 0.4, 0.5, 0.1),
            },
        ],
    }
    return catalog.get(parent_key, [])


# ---------------------------------------------------------------------------
# General fallback
# ---------------------------------------------------------------------------

def _general_possibilities(rng: random.Random, decision: str) -> list[dict]:
    return [
        {
            "key": "intended_outcome",
            "title": "The decision produces its intended primary effect",
            "description": "Core assumptions hold and the main goal is achieved within the expected horizon.",
            "conditions": ["Stated preconditions remain true", "No major external shock"],
            "triggers": ["Execution reaches the first checkpoint"],
            "causes": ["Plan executed against stable conditions"],
            "consequences": ["Goal progress", "Confidence in related decisions rises"],
            "time_horizon": {"minimum": 3, "maximum": 12, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "The outcome the decision is for."},
            "priorities": _prio(0.7, 0.95, 0.5, 0.4, 0.5, 0.2),
        },
        {
            "key": "underperformance",
            "title": "Results underperform expectations",
            "description": "The decision works partially; benefits arrive later or smaller than hoped.",
            "conditions": ["Some assumptions were optimistic"],
            "triggers": ["Mid-point review shows gaps"],
            "causes": ["Optimistic base rates or slow feedback loops"],
            "consequences": ["Adjustments needed", "Timeline extends"],
            "time_horizon": {"minimum": 3, "maximum": 15, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "moderate", "explanation": "Recoverable with course correction."},
            "priorities": _prio(0.55, 0.85, 0.5, 0.55, 0.7, 0.2),
        },
        {
            "key": "external_shock",
            "title": "An external shock disrupts the plan",
            "description": "Market, regulatory, health or organisational events outside your control intervene.",
            "conditions": ["Plan has limited shock absorption"],
            "triggers": ["External event lands in the critical path"],
            "causes": ["Exogenous factors"],
            "consequences": ["Re-planning required", "Stress on contingency resources"],
            "time_horizon": {"minimum": 0, "maximum": 18, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Low control, requires resilience design."},
            "priorities": _prio(0.8, 0.7, 0.35, 0.7, 0.8, 0.3),
        },
        {
            "key": "second_order_win",
            "title": "A second-order benefit outweighs the original goal",
            "description": "Skills, relationships or options created along the way become more valuable than the initial objective.",
            "conditions": ["You stay open to adjacent opportunities"],
            "triggers": ["An unexpected door opens because of the decision"],
            "causes": ["Side effects of executing the decision"],
            "consequences": ["Path diverges upward from the original plan"],
            "time_horizon": {"minimum": 6, "maximum": 24, "unit": "months"},
            "probability": Unquantified,
            "impact": {"level": "high", "explanation": "Hard to plan for, valuable when it happens."},
            "priorities": _prio(0.65, 0.6, 0.4, 0.65, 0.7, 0.15),
        },
    ]


_DOMAIN_HANDLERS = {
    "technology_cybersecurity": (_tech_possibilities, _tech_children),
    "business_operations": (_business_possibilities, _business_children),
    "personal_career": (_career_possibilities, _career_children),
    "general": (_general_possibilities, lambda rng, key, dec: []),
}


# ---------------------------------------------------------------------------
# Public API used by the mock provider
# ---------------------------------------------------------------------------

def discover_possibilities(decision: str, seed: int) -> dict:
    rng = random.Random(seed)
    domain = primary_domain(decision)
    root_fn, _ = _DOMAIN_HANDLERS.get(domain, _DOMAIN_HANDLERS["general"])
    possibilities = root_fn(rng, decision)
    return {
        "domain": domain,
        "domains_scored": [
            {"domain": d, "score": s} for d, s in resolve_domains(decision)
        ],
        "variables": _extract_variables(domain),
        "possibilities": possibilities,
    }


def expand_possibility(decision: str, parent: dict, seed: int) -> dict:
    rng = random.Random(seed)
    domain = parent.get("domain") or primary_domain(decision)
    _, children_fn = _DOMAIN_HANDLERS.get(domain, _DOMAIN_HANDLERS["general"])
    children = children_fn(rng, parent.get("key", ""), decision)
    return {
        "domain": domain,
        "parent_key": parent.get("key"),
        "possibilities": children,
    }


def _extract_variables(domain: str) -> list[str]:
    return {
        "technology_cybersecurity": [
            "cutover_window", "rollback_readiness", "dependency_map_coverage",
            "exposure_surface", "cloud_spend_variance",
        ],
        "business_operations": [
            "monthly_burn", "acquisition_rate", "conversion_rate",
            "retention", "receivable_days", "competitive_visibility",
        ],
        "personal_career": [
            "savings_buffer", "income_gap", "support_network",
            "skill_transferability", "opportunity_cost",
        ],
        "general": ["assumption_stability", "external_shock_probability", "execution_capacity"],
    }.get(domain, [])
