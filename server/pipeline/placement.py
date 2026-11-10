"""
Skillora Pure Functional Placement Pipeline Module.
Implements curried predicates, built-in filter pipelines, and map/reduce Placement Readiness Index (PRI)
with 100% mathematical purity, immutability, and zero side effects.
"""

from __future__ import annotations

import functools
import logging
import math
import operator
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("skillora.pipeline.placement")

# ---------------------------------------------------------------------------
# Canonical Placement Dimensions
# ---------------------------------------------------------------------------
DIMENSIONS: Tuple[str, ...] = (
    "aptitude",
    "coding",
    "technical",
    "communication",
    "academic",
)

# Standard Tier Weights (Sum = 1.00)
TIER_WEIGHTS: MappingProxyType[str, MappingProxyType[str, float]] = MappingProxyType({
    "Tier1": MappingProxyType({
        "coding": 0.35,
        "technical": 0.25,
        "aptitude": 0.15,
        "communication": 0.15,
        "academic": 0.10,
    }),
    "Tier2": MappingProxyType({
        "coding": 0.30,
        "technical": 0.25,
        "aptitude": 0.20,
        "communication": 0.15,
        "academic": 0.10,
    }),
    "Tier3": MappingProxyType({
        "aptitude": 0.35,
        "communication": 0.20,
        "technical": 0.20,
        "coding": 0.15,
        "academic": 0.10,
    }),
    "Baseline": MappingProxyType({
        "coding": 0.30,
        "technical": 0.25,
        "aptitude": 0.20,
        "communication": 0.15,
        "academic": 0.10,
    }),
})

# Dimensional Benchmarks per Tier (Percentage 0.0 - 100.0)
TIER_BENCHMARKS: MappingProxyType[str, MappingProxyType[str, float]] = MappingProxyType({
    "Tier1": MappingProxyType({
        "coding": 85.0,
        "technical": 80.0,
        "aptitude": 75.0,
        "communication": 75.0,
        "academic": 75.0,
    }),
    "Tier2": MappingProxyType({
        "coding": 70.0,
        "technical": 70.0,
        "aptitude": 70.0,
        "communication": 65.0,
        "academic": 65.0,
    }),
    "Tier3": MappingProxyType({
        "aptitude": 60.0,
        "communication": 60.0,
        "technical": 50.0,
        "coding": 50.0,
        "academic": 60.0,
    }),
})

# Tier Readiness Labels
TIER_LABEL_1: str = "Ready for Tier 1"
TIER_LABEL_2: str = "Ready for Tier 2"
TIER_LABEL_3: str = "Ready for Tier 3"
TIER_LABEL_NEEDS_DEV: str = "Needs Development"

# Universal branch wildcards indicating open eligibility across all disciplines
WILDCARD_BRANCHES: frozenset[str] = frozenset({"ALL", "OPEN", "ANY", "*", "ALL BRANCHES"})


# ---------------------------------------------------------------------------
# Immutable Domain Dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StudentProfile:
    """Immutable representation of a student placement candidate."""
    user_id: int
    username: str
    branch: str
    cgpa: float
    backlogs: int = 0
    full_name: str = ""
    skills: Tuple[str, ...] = ()
    dimension_scores: MappingProxyType[str, float] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class CompanyProfile:
    """Immutable representation of a recruiting company's eligibility criteria."""
    company_id: int
    name: str
    tier: str
    min_cgpa: float
    max_backlogs: int
    eligible_branches: Tuple[str, ...] = ()
    roles: Tuple[MappingProxyType[str, Any], ...] = ()


@dataclass(frozen=True)
class PlacementReadinessResult:
    """Immutable evaluation result of candidate Placement Readiness Index (PRI)."""
    pri_score: float
    tier_readiness: str
    gap_analysis: Tuple[str, ...]
    dimension_scores: MappingProxyType[str, float]
    target_tier: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to plain mutable dictionary for serialization."""
        return {
            "pri_score": self.pri_score,
            "tier_readiness": self.tier_readiness,
            "gap_analysis": list(self.gap_analysis),
            "dimension_scores": dict(self.dimension_scores),
            "target_tier": self.target_tier,
        }


# ---------------------------------------------------------------------------
# Helper Extraction Functions (Pure & Non-Mutating)
# ---------------------------------------------------------------------------
def _extract_company_data(
    company: Union[Mapping[str, Any], CompanyProfile]
) -> Tuple[float, int, Set[str]]:
    """Extracts (min_cgpa, max_backlogs, eligible_branches_set) from company object."""
    if isinstance(company, CompanyProfile):
        min_cgpa = float(company.min_cgpa)
        max_backlogs = int(company.max_backlogs)
        branches = set(b.strip().upper() for b in company.eligible_branches if b and b.strip())
        return min_cgpa, max_backlogs, branches

    min_cgpa = float(company.get("min_cgpa", company.get("cutoff_cgpa", 0.0)))
    max_backlogs = int(company.get("max_backlogs", 0))

    raw_branches = company.get("eligible_branches", company.get("eligible_branches_csv", "ALL"))
    if isinstance(raw_branches, str):
        branches = set(b.strip().upper() for b in raw_branches.split(",") if b.strip())
    elif isinstance(raw_branches, (list, tuple, set, frozenset)):
        branches = set(str(b).strip().upper() for b in raw_branches if str(b).strip())
    else:
        branches = set()

    return min_cgpa, max_backlogs, branches


def _extract_student_data(
    student: Union[Mapping[str, Any], StudentProfile]
) -> Tuple[float, int, str]:
    """Extracts (cgpa, backlogs, branch_upper) from student object."""
    if isinstance(student, StudentProfile):
        return float(student.cgpa), int(student.backlogs), student.branch.strip().upper()

    cgpa = float(student.get("cgpa", 0.0))
    backlogs = int(student.get("backlogs", student.get("active_backlogs", 0)))
    raw_branch = student.get("branch", "")
    branch_upper = str(raw_branch).strip().upper() if raw_branch is not None else ""

    return cgpa, backlogs, branch_upper


# ---------------------------------------------------------------------------
# Curried Predicate & Company Filtering
# ---------------------------------------------------------------------------
# Sentinel for curried single-argument detection
_NOT_PROVIDED = object()


def is_eligible(
    company: Union[Mapping[str, Any], CompanyProfile],
    student: Any = _NOT_PROVIDED
) -> Union[bool, Callable[[Union[Mapping[str, Any], StudentProfile]], bool]]:
    """
    Curried pure predicate evaluating student eligibility for a target company.
    Supports both curried syntax: is_eligible(company)(student) -> bool
    and direct 2-arg syntax: is_eligible(company, student) -> bool.
    Also compatible with functools.partial(is_eligible, company).

    Eligibility criteria:
    - student.cgpa >= company.min_cgpa
    - student.backlogs <= company.max_backlogs
    - student.branch in company.eligible_branches (or company allows wildcard ALL/OPEN/*)
    """
    def _predicate(s: Optional[Union[Mapping[str, Any], StudentProfile]]) -> bool:
        if s is None:
            return False
        min_cgpa, max_backlogs, eligible_branches = _extract_company_data(company)
        student_cgpa, student_backlogs, student_branch = _extract_student_data(s)

        # 1. Academic CGPA cutoff check
        if student_cgpa < min_cgpa:
            return False

        # 2. Active backlogs check
        if student_backlogs > max_backlogs:
            return False

        # 3. Branch eligibility check
        # Check if wildcard ALL/OPEN/* is present
        if not eligible_branches or any(wild in eligible_branches for wild in WILDCARD_BRANCHES):
            return True

        # Check explicit branch membership
        return student_branch in eligible_branches

    if student is not _NOT_PROVIDED:
        return _predicate(student)
    return _predicate


def is_eligible_curried(
    company: Union[Mapping[str, Any], CompanyProfile]
) -> Callable[[Union[Mapping[str, Any], StudentProfile]], bool]:
    """
    Explicitly curried unary predicate returning Callable[[student], bool].
    Useful for functools pipelines, map(), and filter() chains.
    """
    return is_eligible(company)


def filter_eligible_companies(
    companies: Iterable[Union[Mapping[str, Any], CompanyProfile]],
    student: Union[Mapping[str, Any], StudentProfile]
) -> List[Dict[str, Any]]:
    """
    Filters a sequence of companies for eligibility using Python's built-in filter.
    Pure and non-mutating: leaves input sequence untouched and returns a fresh list of dicts.
    """
    if student is None or companies is None:
        return []

    # Built-in pure filter application using curried predicate
    eligible_items = filter(lambda comp: is_eligible(comp, student), companies)

    # Return pure copies as dictionaries
    def _to_clean_dict(c: Union[Mapping[str, Any], CompanyProfile]) -> Dict[str, Any]:
        if isinstance(c, CompanyProfile):
            return {
                "company_id": c.company_id,
                "name": c.name,
                "tier": c.tier,
                "min_cgpa": c.min_cgpa,
                "max_backlogs": c.max_backlogs,
                "eligible_branches": list(c.eligible_branches),
                "roles": [dict(r) for r in c.roles],
            }
        return dict(c)

    return list(map(_to_clean_dict, eligible_items))


def filter_eligible_students(
    company: Union[Mapping[str, Any], CompanyProfile],
    students: Iterable[Union[Mapping[str, Any], StudentProfile]]
) -> List[Dict[str, Any]]:
    """
    Filters a sequence of students eligible for a specific company using built-in filter.
    Pure and non-mutating: returns a fresh list of student dicts.
    """
    if company is None or students is None:
        return []

    eligible_items = filter(is_eligible(company), students)

    def _to_clean_dict(s: Union[Mapping[str, Any], StudentProfile]) -> Dict[str, Any]:
        if isinstance(s, StudentProfile):
            return {
                "user_id": s.user_id,
                "username": s.username,
                "full_name": s.full_name,
                "branch": s.branch,
                "cgpa": s.cgpa,
                "backlogs": s.backlogs,
                "skills": list(s.skills),
                "dimension_scores": dict(s.dimension_scores),
            }
        return dict(s)

    return list(map(_to_clean_dict, eligible_items))


# ---------------------------------------------------------------------------
# PRI Map & Reduce Pipeline
# ---------------------------------------------------------------------------
def _normalize_dimension_score(dim: str, raw_score: Any) -> float:
    """Normalizes score to [0.0, 100.0]. Automatically scales CGPA if <= 10.0."""
    try:
        val = float(raw_score)
    except (ValueError, TypeError):
        return 0.0

    if math.isnan(val) or math.isinf(val):
        return 0.0

    # Auto-scale collegiate CGPA (e.g. 8.45 <= 10.0) to percentage (84.5%)
    if dim.lower() == "academic" and 0.0 < val <= 10.0:
        val = val * 10.0

    return max(0.0, min(100.0, val))


def calculate_round_score(
    weights: Mapping[str, float],
    scores: Mapping[str, float]
) -> float:
    """
    Pure mapping and aggregation function to calculate a weighted round score.
    Uses map() to compute component products and functools.reduce() to sum them.
    Guarantees output is bounded in [0.0, 100.0].
    """
    if not weights:
        return 0.0

    # Clean and filter non-negative weights
    cleaned_weights = {k: float(v) for k, v in weights.items() if float(v) > 0.0}
    total_w = sum(cleaned_weights.values())
    if total_w <= 0.0:
        return 0.0

    # Normalize weights so sum is 1.0
    normalized_weights = {k: v / total_w for k, v in cleaned_weights.items()}

    # Pure map phase: compute weighted components
    def _compute_component(item: Tuple[str, float]) -> float:
        dim, w = item
        raw_val = scores.get(dim, 0.0) if scores else 0.0
        score = _normalize_dimension_score(dim, raw_val)
        return w * score

    weighted_components = map(_compute_component, normalized_weights.items())

    # Pure reduce phase: aggregate weighted products
    composite_score = functools.reduce(operator.add, weighted_components, 0.0)

    # Bounded to [0.0, 100.0] and rounded
    return round(max(0.0, min(100.0, composite_score)), 2)


def classify_tier_readiness(pri_score: float) -> str:
    """
    Pure classification function mapping a composite PRI score to tier readiness string.
    >= 85.0 -> 'Ready for Tier 1'
    >= 70.0 -> 'Ready for Tier 2'
    >= 50.0 -> 'Ready for Tier 3'
    <  50.0 -> 'Needs Development'
    """
    score = float(pri_score)
    if score >= 85.0:
        return TIER_LABEL_1
    if score >= 70.0:
        return TIER_LABEL_2
    if score >= 50.0:
        return TIER_LABEL_3
    return TIER_LABEL_NEEDS_DEV


def generate_gap_analysis(
    dimension_scores: Mapping[str, float],
    target_tier: str
) -> List[str]:
    """
    Pure functional mapping identifying dimensions where candidate falls below
    the target tier benchmarks.
    Uses filter() to detect deficits and map() to format diagnostic strings.
    """
    canonical_tier = "Tier1" if target_tier in ("Tier1", "Tier 1") else (
        "Tier2" if target_tier in ("Tier2", "Tier 2") else "Tier3"
    )
    benchmarks = TIER_BENCHMARKS.get(canonical_tier, TIER_BENCHMARKS["Tier3"])

    # Pure filter: detect dimensions below benchmark
    def _has_deficit(item: Tuple[str, float]) -> bool:
        dim, benchmark = item
        score = _normalize_dimension_score(dim, dimension_scores.get(dim, 0.0) if dimension_scores else 0.0)
        return score < benchmark

    def _format_diagnostic(item: Tuple[str, float]) -> str:
        dim, benchmark = item
        score = _normalize_dimension_score(dim, dimension_scores.get(dim, 0.0) if dimension_scores else 0.0)
        deficit = benchmark - score
        return (
            f"{dim.title()}: Score {score:.1f}% is below {canonical_tier} "
            f"benchmark {benchmark:.1f}% (Deficit: -{deficit:.1f}%)"
        )

    deficit_items = filter(_has_deficit, benchmarks.items())
    return list(map(_format_diagnostic, deficit_items))


def compute_placement_readiness_index(
    dimension_scores: Mapping[str, float],
    target_tier: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes composite Placement Readiness Index (PRI), determines tier readiness,
    and performs automated gap analysis.
    Uses map() for dimensional scoring and reduce() for score aggregation.
    Returns:
        {
            "pri_score": float,
            "tier_readiness": str,
            "gap_analysis": List[str],
            "dimension_scores": Dict[str, float],
            "target_tier": str
        }
    """
    # Select weights based on target tier
    tier_key = "Baseline"
    if target_tier:
        clean_target = target_tier.replace(" ", "")
        if clean_target in TIER_WEIGHTS:
            tier_key = clean_target

    weights = TIER_WEIGHTS[tier_key]

    # Calculate PRI via pure map & reduce
    pri = calculate_round_score(weights, dimension_scores)
    tier_readiness = classify_tier_readiness(pri)

    # Determine benchmark tier for gap analysis if not explicitly specified
    if target_tier:
        bench_tier = "Tier1" if "1" in target_tier else ("Tier2" if "2" in target_tier else "Tier3")
    else:
        # Step-up gap analysis roadmap
        if tier_readiness == TIER_LABEL_1:
            bench_tier = "Tier1"
        elif tier_readiness == TIER_LABEL_2:
            bench_tier = "Tier1"
        elif tier_readiness == TIER_LABEL_3:
            bench_tier = "Tier2"
        else:
            bench_tier = "Tier3"

    gaps = generate_gap_analysis(dimension_scores, bench_tier)

    # Prepare normalized dimension scores
    clean_dimension_scores = {
        dim: _normalize_dimension_score(dim, dimension_scores.get(dim, 0.0) if dimension_scores else 0.0)
        for dim in DIMENSIONS
    }

    result = PlacementReadinessResult(
        pri_score=pri,
        tier_readiness=tier_readiness,
        gap_analysis=tuple(gaps),
        dimension_scores=MappingProxyType(clean_dimension_scores),
        target_tier=bench_tier,
    )

    return result.to_dict()


def get_tier_weights(tier: str) -> MappingProxyType[str, float]:
    """Returns immutable mapping of dimensional weights for given tier."""
    clean_tier = tier.replace(" ", "")
    return TIER_WEIGHTS.get(clean_tier, TIER_WEIGHTS["Baseline"])


def get_tier_benchmarks(tier: str) -> MappingProxyType[str, float]:
    """Returns immutable mapping of benchmark scores for given tier."""
    clean_tier = "Tier1" if "1" in tier else ("Tier2" if "2" in tier else "Tier3")
    return TIER_BENCHMARKS.get(clean_tier, TIER_BENCHMARKS["Tier3"])
