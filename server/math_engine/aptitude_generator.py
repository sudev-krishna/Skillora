"""
Skillora Dynamic Aptitude Math Generator (server/math_engine/aptitude_generator.py)
Synthesizes quantitative placement problems with step-by-step symbolic proofs
and 2-pass deduplicated distractors across 4 campus placement domains:
  1. Compound vs Simple Interest Differences (CI/SI)
  2. Harmonic Work Collaboration (Time & Work)
  3. Urn Model Combinatorics & Hypergeometric Probability
  4. Cayley's Tree Formula (Spanning Trees in Complete Graphs)
Strictly 100% offline (standard library + SymPy only).
"""

from dataclasses import asdict, dataclass
from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import sympy as sp


class AptitudeTopic(str, Enum):
    INTEREST_DIFFERENCE = "INTEREST_DIFFERENCE"
    WORK_COLLABORATION = "WORK_COLLABORATION"
    URN_PROBABILITY = "URN_PROBABILITY"
    CAYLEY_TREES = "CAYLEY_TREES"


TOPIC_ALIASES: Dict[str, AptitudeTopic] = {
    "interest_difference": AptitudeTopic.INTEREST_DIFFERENCE,
    "interest": AptitudeTopic.INTEREST_DIFFERENCE,
    "ci_si": AptitudeTopic.INTEREST_DIFFERENCE,
    "ci": AptitudeTopic.INTEREST_DIFFERENCE,
    "compound_interest": AptitudeTopic.INTEREST_DIFFERENCE,
    "simple_interest": AptitudeTopic.INTEREST_DIFFERENCE,
    "work_collaboration": AptitudeTopic.WORK_COLLABORATION,
    "work": AptitudeTopic.WORK_COLLABORATION,
    "time_and_work": AptitudeTopic.WORK_COLLABORATION,
    "collaboration": AptitudeTopic.WORK_COLLABORATION,
    "pipes": AptitudeTopic.WORK_COLLABORATION,
    "urn_probability": AptitudeTopic.URN_PROBABILITY,
    "urn": AptitudeTopic.URN_PROBABILITY,
    "probability": AptitudeTopic.URN_PROBABILITY,
    "combinatorics": AptitudeTopic.URN_PROBABILITY,
    "cayley_trees": AptitudeTopic.CAYLEY_TREES,
    "cayley": AptitudeTopic.CAYLEY_TREES,
    "trees": AptitudeTopic.CAYLEY_TREES,
    "spanning_trees": AptitudeTopic.CAYLEY_TREES,
}


@dataclass(frozen=True)
class ProofStep:
    step_number: int
    title: str
    latex: str
    text: str
    explanation: str


@dataclass
class AptitudeProblem:
    question_id: str
    topic: str
    topic_display: str
    difficulty: str
    question_text: str
    parameters: Dict[str, Any]
    correct_answer: str
    correct_value: Any
    options: List[str]
    correct_option_index: int
    correct_option_label: str
    distractors: List[str]
    misconception_map: Dict[str, str]
    proof_steps: List[Dict[str, Any]]
    latex_proof: str
    text_proof: str
    formula_symbolic: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assemble_options_and_distractors(
    correct_str: str,
    raw_distractor_candidates: List[Tuple[str, str]],
    is_probability: bool = False,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """
    Assembles exactly 4 strictly unique options (1 correct + 3 distinct distractors)
    with guaranteed deduplication, mathematical jitter fallback, and random shuffling.
    """
    if rng is None:
        rng = random.Random()

    selected_distractors: List[str] = []
    misconception_map: Dict[str, str] = {}
    seen = {correct_str}

    # Pass 1: Select non-colliding candidates from misconception taxonomy
    for cand_val, explanation in raw_distractor_candidates:
        cand_str = str(cand_val).strip()
        if cand_str and cand_str not in seen:
            seen.add(cand_str)
            selected_distractors.append(cand_str)
            misconception_map[cand_str] = explanation
        if len(selected_distractors) == 3:
            break

    # Pass 2: Jitter fallback if collisions reduced count below 3
    jitter_attempts = 0
    while len(selected_distractors) < 3 and jitter_attempts < 40:
        jitter_attempts += 1
        if is_probability:
            num = rng.randint(1, 12)
            den = rng.randint(num + 1, 24)
            cand = str(sp.Rational(num, den))
            explanation = "Plausible alternative probability estimate"
        else:
            try:
                base_val = int(correct_str)
                delta = rng.choice([-5, -3, -2, -1, 1, 2, 3, 5, 10])
                cand_int = max(1, base_val + delta)
                cand = str(cand_int)
                explanation = f"Arithmetic variation offset ({delta:+d})"
            except ValueError:
                try:
                    rat = sp.Rational(correct_str)
                    cand = str(rat + rng.choice([1, -1, 2, -2]))
                    explanation = "Rational arithmetic perturbation"
                except Exception:
                    cand = f"{correct_str}_{jitter_attempts}"
                    explanation = "Heuristic alternative choice"

        if cand not in seen:
            seen.add(cand)
            selected_distractors.append(cand)
            misconception_map[cand] = explanation

    # Build and shuffle 4 options
    options = [correct_str] + selected_distractors
    rng.shuffle(options)
    correct_index = options.index(correct_str)
    labels = ["A", "B", "C", "D"]

    return {
        "options": options,
        "distractors": selected_distractors,
        "correct_option_index": correct_index,
        "correct_option_label": labels[correct_index],
        "misconception_map": misconception_map,
    }


# ==============================================================================
# Domain 1: Compound vs Simple Interest Differences
# ==============================================================================

def generate_interest_problem(
    seed: Optional[int] = None,
    years: Optional[int] = None,
    difficulty: str = "Medium",
) -> AptitudeProblem:
    """
    Generates CI vs SI difference problems for 2 or 3 years.
    Uses exact sp.Rational arithmetic and produces clean integer rupee differences.
    """
    rng = random.Random(seed)
    if years is None:
        years = 2 if difficulty == "Easy" else rng.choice([2, 3])

    rates = [4, 5, 6, 8, 10, 12, 15, 20]
    R = rng.choice(rates)

    # To guarantee clean integer difference, pick Principal as multiple of base denominator
    # For 2-year: denom = (100 / gcd(R, 100))^2
    # For 3-year: denom = (100 / gcd(R, 100))^3
    g = math.gcd(R, 100)
    base_denom_2 = (100 // g) ** 2
    base_denom_3 = (100 // g) ** 3

    if years == 2:
        k = rng.choice([1, 2, 3, 4, 5])
        P = base_denom_2 * k * 10
        if P < 1000:
            P = 5000 * rng.choice([1, 2, 3, 4])
    else:
        # For 3-year, match exact simplified denominator to guarantee integer rupee difference
        denom_3 = sp.Rational(R**2 * (300 + R), 1000000).q
        mult = rng.choice([5, 10, 15, 20]) if denom_3 <= 1000 else rng.choice([1, 2, 3, 4])
        P = denom_3 * mult

    P_rat = sp.Rational(P, 1)
    R_rat = sp.Rational(R, 100)

    if years == 2:
        delta_rat = P_rat * (R_rat ** 2)
        delta_val = int(delta_rat) if delta_rat.q == 1 else float(delta_rat)
        correct_str = str(delta_val)

        question_text = (
            f"The difference between the compound interest (compounded annually) and simple interest "
            f"on a sum of ₹{P:,} for 2 years at an annual interest rate of {R}% is:"
        )

        # Distractor candidates based on misconceptions
        d1 = str(int(P_rat * R_rat))  # 1-year SI
        d2 = str(int(2 * P_rat * R_rat))  # Total 2-year SI
        d3 = str(max(1, int(delta_val * 2)))  # Doubled difference
        d4 = str(max(1, int(delta_val + P * R // 1000)))

        raw_distractors = [
            (d1, "Calculated 1-year Simple Interest instead of compounding interest-on-interest."),
            (d2, "Calculated the total 2-year Simple Interest rather than the CI-SI difference."),
            (d3, "Multiplied the compounding difference by 2 unnecessarily."),
            (d4, "Arithmetic estimation error in compounding factor."),
        ]

        steps = [
            ProofStep(
                step_number=1,
                title="Formula Definition",
                latex=r"\Delta_2 = CI_2 - SI_2 = P \cdot \left(\frac{R}{100}\right)^2",
                text="The 2-year difference formula is: Delta_2 = P * (R / 100)^2",
                explanation="For 2 years, the difference between CI and SI equals interest on the first year's interest.",
            ),
            ProofStep(
                step_number=2,
                title="Parameter Substitution",
                latex=rf"\Delta_2 = {P} \cdot \left(\frac{{{R}}}{{100}}\right)^2",
                text=f"Substitute P = {P} and R = {R}%: Delta_2 = {P} * ({R}/100)^2",
                explanation="Substituted given principal sum and rate of interest.",
            ),
            ProofStep(
                step_number=3,
                title="Algebraic Simplification",
                latex=rf"\Delta_2 = {P} \cdot \frac{{{R**2}}}{{10000}} = \frac{{{P * R**2}}}{{10000}}",
                text=f"Evaluate square: Delta_2 = {P} * ({R**2}/10000) = {P * R**2}/10000",
                explanation="Computed rate squared divided by 10,000.",
            ),
            ProofStep(
                step_number=4,
                title="Final Exact Value",
                latex=rf"\Delta_2 = \text{{₹}}{correct_str}",
                text=f"The exact difference between CI and SI for 2 years is ₹{correct_str}.",
                explanation="Final evaluated difference.",
            ),
        ]
        formula_sym = "Delta_2 = P * (R / 100)^2"

    else:
        # 3 years
        delta_rat = P_rat * (R_rat ** 2) * (3 + R_rat)
        delta_val = int(delta_rat) if delta_rat.q == 1 else float(delta_rat)
        correct_str = str(delta_val)

        question_text = (
            f"The difference between the compound interest (compounded annually) and simple interest "
            f"on a principal amount of ₹{P:,} for 3 years at {R}% per annum is:"
        )

        d2_val = P_rat * (R_rat ** 2)
        d1 = str(int(d2_val))  # Used 2-year formula
        d2 = str(int(3 * d2_val))  # Omitted 3rd year compounding term
        d3 = str(int(3 * P_rat * R_rat))  # Total 3-year SI
        d4 = str(max(1, int(delta_val * 1.5)))

        raw_distractors = [
            (d1, "Applied the 2-year difference formula P*(R/100)^2 to a 3-year problem."),
            (d2, "Omitted the 3rd-year compounding term P*(R/100)^3, computing only 3*Delta_2."),
            (d3, "Calculated the total 3-year Simple Interest instead of the CI-SI difference."),
            (d4, "Miscalculated the multiplier term (3 + R/100)."),
        ]

        steps = [
            ProofStep(
                step_number=1,
                title="Formula Definition",
                latex=r"\Delta_3 = CI_3 - SI_3 = P \cdot \left(\frac{R}{100}\right)^2 \cdot \left(3 + \frac{R}{100}\right)",
                text="The 3-year difference formula is: Delta_3 = P * (R / 100)^2 * (3 + R / 100)",
                explanation="For 3 years, Delta_3 includes 3 times the 2-year difference plus the compounding of interest on interest.",
            ),
            ProofStep(
                step_number=2,
                title="Parameter Substitution",
                latex=rf"\Delta_3 = {P} \cdot \left(\frac{{{R}}}{{100}}\right)^2 \cdot \left(3 + \frac{{{R}}}{{100}}\right)",
                text=f"Substitute P = {P} and R = {R}%: Delta_3 = {P} * ({R}/100)^2 * (3 + {R}/100)",
                explanation="Substituted principal and interest rate.",
            ),
            ProofStep(
                step_number=3,
                title="Algebraic Simplification",
                latex=rf"\Delta_3 = {P} \cdot \frac{{{R**2}}}{{10000}} \cdot \frac{{{300 + R}}}{{100}} = \frac{{{P * R**2 * (300 + R)}}}{{1000000}}",
                text=f"Simplify terms: Delta_3 = {P} * ({R**2}/10000) * ({300 + R}/100)",
                explanation="Combined fractions to compute exact difference.",
            ),
            ProofStep(
                step_number=4,
                title="Final Exact Value",
                latex=rf"\Delta_3 = \text{{₹}}{correct_str}",
                text=f"The exact difference between CI and SI for 3 years is ₹{correct_str}.",
                explanation="Final evaluated difference.",
            ),
        ]
        formula_sym = "Delta_3 = P * (R / 100)^2 * (3 + R / 100)"

    opt_pack = assemble_options_and_distractors(correct_str, raw_distractors, rng=rng)

    latex_proof = (
        "\\begin{aligned}\n"
        + "\n".join(f"\\textbf{{Step {s.step_number} ({s.title}):}} & \\quad {s.latex} \\\\" for s in steps)
        + "\n\\end{aligned}"
    )
    text_proof = "\n".join(f"Step {s.step_number} [{s.title}]: {s.text} ({s.explanation})" for s in steps)

    return AptitudeProblem(
        question_id=f"apt_ci_{uuid.uuid4().hex[:8]}",
        topic=AptitudeTopic.INTEREST_DIFFERENCE.value,
        topic_display="Compound vs Simple Interest Differences",
        difficulty=difficulty,
        question_text=question_text,
        parameters={"P": P, "R": R, "years": years},
        correct_answer=correct_str,
        correct_value=delta_val,
        options=opt_pack["options"],
        correct_option_index=opt_pack["correct_option_index"],
        correct_option_label=opt_pack["correct_option_label"],
        distractors=opt_pack["distractors"],
        misconception_map=opt_pack["misconception_map"],
        proof_steps=[asdict(s) for s in steps],
        latex_proof=latex_proof,
        text_proof=text_proof,
        formula_symbolic=formula_sym,
    )


# ==============================================================================
# Domain 2: Harmonic Work Collaboration (Time & Work)
# ==============================================================================

def generate_work_problem(
    seed: Optional[int] = None,
    variant: str = "COLLABORATION",
    difficulty: str = "Medium",
) -> AptitudeProblem:
    """
    Generates joint work problems with exact integer completion times
    using the Babylonian divisor formulation A = T + m, B = T + T^2/m.
    """
    rng = random.Random(seed)

    # Pick a target completion time T in typical placement ranges (3 to 12 days)
    target_times = [4, 6, 8, 10, 12]
    T = rng.choice(target_times)

    # Find divisors m of T^2 such that 1 <= m < T
    t_sq = T ** 2
    divisors = [d for d in range(1, T) if t_sq % d == 0]
    m = rng.choice(divisors) if divisors else 2

    A = T + m
    B = T + (t_sq // m)
    if A > B:
        A, B = B, A

    correct_str = str(T)

    worker_names = [
        ("Aarav", "Vihaan"),
        ("Rohan", "Priya"),
        ("Ananya", "Karthik"),
        ("Worker A", "Worker B"),
    ]
    name_a, name_b = rng.choice(worker_names)

    question_text = (
        f"{name_a} can complete a piece of work alone in {A} days, and {name_b} can complete "
        f"the same work alone in {B} days. Working together at their respective constant rates, "
        f"in how many days will they finish the entire work?"
    )

    # Common misconceptions
    d_arithmetic = str((A + B) // 2)
    d_additive = str(A + B)
    d_harmonic_full = str(round((2 * A * B) / (A + B)))
    d_diff = str(abs(B - A))

    raw_distractors = [
        (d_arithmetic, "Arithmetic Mean Error: Averaged individual times instead of adding reciprocal work rates."),
        (d_additive, "Additive Misconception: Falsely assumed two people take longer together than alone."),
        (d_harmonic_full, "Full Harmonic Mean: Confused joint completion time (H/2) with speed harmonic mean (H)."),
        (d_diff, "Subtracted individual days instead of solving harmonic rate balance."),
    ]

    steps = [
        ProofStep(
            step_number=1,
            title="Rate Formulation",
            latex=r"r_A = \frac{1}{A}, \quad r_B = \frac{1}{B}, \quad r_{\text{total}} = r_A + r_B = \frac{1}{T}",
            text=f"Individual rates: rate_{name_a} = 1/{A}, rate_{name_b} = 1/{B}. Total rate = 1/A + 1/B.",
            explanation="Work rate equals reciprocal of completion time.",
        ),
        ProofStep(
            step_number=2,
            title="Parameter Substitution",
            latex=rf"r_{{\text{{total}}}} = \frac{{1}}{{{A}}} + \frac{{1}}{{{B}}} = \frac{{{B} + {A}}}{{{A} \times {B}}} = \frac{{{A + B}}}{{{A * B}}}",
            text=f"Total rate = 1/{A} + 1/{B} = ({A} + {B}) / ({A} * {B}) = {A + B} / {A * B}.",
            explanation="Summed fractional rates using a common denominator.",
        ),
        ProofStep(
            step_number=3,
            title="Inversion for Collaboration Time",
            latex=rf"T = \frac{{{A} \times {B}}}{{{A} + {B}}} = \frac{{{A * B}}}{{{A + B}}}",
            text=f"Time T = 1 / total_rate = ({A} * {B}) / ({A} + {B}) = {A * B} / {A + B}.",
            explanation="Joint time is the reciprocal of total rate (half of harmonic mean).",
        ),
        ProofStep(
            step_number=4,
            title="Final Exact Value",
            latex=rf"T = {correct_str}\text{{ days}}",
            text=f"They will finish the work together in exactly {correct_str} days.",
            explanation="Evaluated quotient yielding integer days.",
        ),
    ]

    opt_pack = assemble_options_and_distractors(correct_str, raw_distractors, rng=rng)

    latex_proof = (
        "\\begin{aligned}\n"
        + "\n".join(f"\\textbf{{Step {s.step_number} ({s.title}):}} & \\quad {s.latex} \\\\" for s in steps)
        + "\n\\end{aligned}"
    )
    text_proof = "\n".join(f"Step {s.step_number} [{s.title}]: {s.text} ({s.explanation})" for s in steps)

    return AptitudeProblem(
        question_id=f"apt_work_{uuid.uuid4().hex[:8]}",
        topic=AptitudeTopic.WORK_COLLABORATION.value,
        topic_display="Harmonic Work Collaboration",
        difficulty=difficulty,
        question_text=question_text,
        parameters={"A": A, "B": B, "target_days": T},
        correct_answer=correct_str,
        correct_value=T,
        options=opt_pack["options"],
        correct_option_index=opt_pack["correct_option_index"],
        correct_option_label=opt_pack["correct_option_label"],
        distractors=opt_pack["distractors"],
        misconception_map=opt_pack["misconception_map"],
        proof_steps=[asdict(s) for s in steps],
        latex_proof=latex_proof,
        text_proof=text_proof,
        formula_symbolic="T = (A * B) / (A + B)",
    )


# ==============================================================================
# Domain 3: Urn Model Combinatorics & Hypergeometric Probability
# ==============================================================================

def generate_urn_problem(
    seed: Optional[int] = None,
    variant: str = "SAME_COLOR",
    difficulty: str = "Medium",
) -> AptitudeProblem:
    """
    Generates hypergeometric draw-without-replacement probability problems.
    Uses sp.binomial and returns irreducible sp.Rational fractions.
    """
    rng = random.Random(seed)

    # Colors: Red, Green, Blue
    r_count = rng.randint(4, 7)
    g_count = rng.randint(3, 6)
    b_count = rng.randint(2, 5)
    total_balls = r_count + g_count + b_count
    k = 2  # Draw 2 balls without replacement

    total_comb = sp.binomial(total_balls, k)
    fav_r = sp.binomial(r_count, k)
    fav_g = sp.binomial(g_count, k)
    fav_b = sp.binomial(b_count, k)
    fav_total = fav_r + fav_g + fav_b

    prob_rat = sp.Rational(fav_total, total_comb)
    correct_str = str(prob_rat)

    question_text = (
        f"An urn contains {r_count} red balls, {g_count} green balls, and {b_count} blue balls "
        f"(total {total_balls} balls). If 2 balls are drawn at random without replacement, "
        f"what is the probability that both drawn balls are of the same color?"
    )

    # Distractor misconceptions
    # 1. With replacement: (r^2 + g^2 + b^2) / N^2
    d_with_rep = sp.Rational(r_count**2 + g_count**2 + b_count**2, total_balls**2)
    # 2. Ordered denominator: fav / (N * (N - 1)) = prob / 2
    d_ordered = sp.Rational(fav_total, total_balls * (total_balls - 1))
    # 3. Omitted third color (only red + green)
    d_omit = sp.Rational(fav_r + fav_g, total_comb)
    # 4. Complement: 1 - prob
    d_comp = 1 - prob_rat

    raw_distractors = [
        (str(d_with_rep), "Treated draws as independent with replacement: (r^2 + g^2 + b^2) / N^2."),
        (str(d_ordered), "Used permutations N*(N-1) for denominator but combinations for numerator."),
        (str(d_omit), "Omitted blue balls from favorable outcome union."),
        (str(d_comp), "Calculated complement probability P(different colors) instead of P(same color)."),
    ]

    steps = [
        ProofStep(
            step_number=1,
            title="Sample Space Formulation",
            latex=rf"\Omega = \binom{{N}}{{k}} = \binom{{{total_balls}}}{{2}} = \frac{{{total_balls} \times {total_balls - 1}}}{{2}} = {total_comb}",
            text=f"Total ways to choose 2 balls from {total_balls} balls: C({total_balls}, 2) = {total_comb}.",
            explanation="Unordered sampling without replacement formula.",
        ),
        ProofStep(
            step_number=2,
            title="Favorable Outcomes by Color",
            latex=(
                rf"W = \binom{{{r_count}}}{{2}} + \binom{{{g_count}}}{{2}} + \binom{{{b_count}}}{{2}} "
                rf"= {fav_r} + {fav_g} + {fav_b} = {fav_total}"
            ),
            text=f"Ways to draw same color: Red: C({r_count}, 2) = {fav_r}, Green: C({g_count}, 2) = {fav_g}, Blue: C({b_count}, 2) = {fav_b}. Total = {fav_total}.",
            explanation="Summed mutually exclusive combinations for each color.",
        ),
        ProofStep(
            step_number=3,
            title="Probability Fraction & Reduction",
            latex=rf"P = \frac{{W}}{{\Omega}} = \frac{{{fav_total}}}{{{total_comb}}} = {prob_rat}",
            text=f"Probability P = favorable / total = {fav_total} / {total_comb} = {prob_rat}.",
            explanation="Divided favorable outcomes by sample space and reduced to lowest terms.",
        ),
        ProofStep(
            step_number=4,
            title="Final Exact Value",
            latex=rf"P(\text{{same color}}) = {correct_str}",
            text=f"The exact probability is {correct_str}.",
            explanation="Canonical irreducible fraction.",
        ),
    ]

    opt_pack = assemble_options_and_distractors(correct_str, raw_distractors, is_probability=True, rng=rng)

    latex_proof = (
        "\\begin{aligned}\n"
        + "\n".join(f"\\textbf{{Step {s.step_number} ({s.title}):}} & \\quad {s.latex} \\\\" for s in steps)
        + "\n\\end{aligned}"
    )
    text_proof = "\n".join(f"Step {s.step_number} [{s.title}]: {s.text} ({s.explanation})" for s in steps)

    return AptitudeProblem(
        question_id=f"apt_urn_{uuid.uuid4().hex[:8]}",
        topic=AptitudeTopic.URN_PROBABILITY.value,
        topic_display="Urn Model Hypergeometric Combinatorics",
        difficulty=difficulty,
        question_text=question_text,
        parameters={"red": r_count, "green": g_count, "blue": b_count, "total": total_balls, "drawn": k},
        correct_answer=correct_str,
        correct_value=float(prob_rat),
        options=opt_pack["options"],
        correct_option_index=opt_pack["correct_option_index"],
        correct_option_label=opt_pack["correct_option_label"],
        distractors=opt_pack["distractors"],
        misconception_map=opt_pack["misconception_map"],
        proof_steps=[asdict(s) for s in steps],
        latex_proof=latex_proof,
        text_proof=text_proof,
        formula_symbolic="P = (C(R, 2) + C(G, 2) + C(B, 2)) / C(N, 2)",
    )


# ==============================================================================
# Domain 4: Cayley's Tree Formula (Spanning Trees in Complete Graphs)
# ==============================================================================

def generate_cayley_problem(
    seed: Optional[int] = None,
    n: Optional[int] = None,
    difficulty: str = "Medium",
) -> AptitudeProblem:
    """
    Generates Cayley's spanning tree problems T(K_n) = n^(n - 2) for complete graphs.
    Bounds n to [3, 7] to ensure realistic placement questions.
    """
    rng = random.Random(seed)
    if n is None:
        n_choices = [3, 4] if difficulty == "Easy" else ([4, 5, 6] if difficulty == "Medium" else [5, 6, 7])
        n = rng.choice(n_choices)

    trees = n ** (n - 2)
    correct_str = str(trees)

    question_text = (
        f"According to Cayley's Tree Formula, how many distinct labeled spanning trees "
        f"can be formed on {n} labeled vertices (i.e. in the complete graph K_{n})?"
    )

    # Distractor misconceptions
    d_full_power = str(n ** n)
    d_edge_power = str(n ** (n - 1))
    d_factorial = str(math.factorial(n))
    d_edges = str(n * (n - 1) // 2)

    raw_distractors = [
        (d_edge_power, "Used tree edge count (n - 1) as exponent instead of Prüfer length (n - 2)."),
        (d_edges, "Confused total edge count of complete graph n*(n-1)/2 with spanning tree count."),
        (d_full_power, "Omitted the -2 offset in exponent, using n^n instead of n^(n - 2)."),
        (d_factorial, "Confused tree topologies with linear vertex permutations (n!)."),
    ]

    steps = [
        ProofStep(
            step_number=1,
            title="Theorem Statement",
            latex=r"T(K_n) = n^{n-2}",
            text=f"Cayley's Tree Formula: The number of labeled spanning trees on n vertices is n^(n - 2).",
            explanation="Proven via the Prüfer sequence bijection where every tree maps to a unique sequence of length (n - 2).",
        ),
        ProofStep(
            step_number=2,
            title="Parameter Substitution",
            latex=rf"T(K_{{{n}}}) = {n}^{{{n} - 2}} = {n}^{{{n - 2}}}",
            text=f"Substitute n = {n}: T(K_{n}) = {n}^({n} - 2) = {n}^{n - 2}.",
            explanation="Substituted vertex count into exponent.",
        ),
        ProofStep(
            step_number=3,
            title="Exponential Evaluation",
            latex=rf"{n}^{{{n - 2}}} = {trees}",
            text=f"Compute {n}^{n - 2}: {trees}.",
            explanation="Evaluated exponential power.",
        ),
        ProofStep(
            step_number=4,
            title="Final Exact Value",
            latex=rf"T(K_{{{n}}}) = {correct_str}",
            text=f"There are exactly {correct_str} distinct labeled spanning trees on {n} vertices.",
            explanation="Final verified tree count.",
        ),
    ]

    opt_pack = assemble_options_and_distractors(correct_str, raw_distractors, rng=rng)

    latex_proof = (
        "\\begin{aligned}\n"
        + "\n".join(f"\\textbf{{Step {s.step_number} ({s.title}):}} & \\quad {s.latex} \\\\" for s in steps)
        + "\n\\end{aligned}"
    )
    text_proof = "\n".join(f"Step {s.step_number} [{s.title}]: {s.text} ({s.explanation})" for s in steps)

    return AptitudeProblem(
        question_id=f"apt_cayley_{uuid.uuid4().hex[:8]}",
        topic=AptitudeTopic.CAYLEY_TREES.value,
        topic_display="Cayley's Labeled Spanning Tree Formula",
        difficulty=difficulty,
        question_text=question_text,
        parameters={"n": n, "exponent": n - 2},
        correct_answer=correct_str,
        correct_value=trees,
        options=opt_pack["options"],
        correct_option_index=opt_pack["correct_option_index"],
        correct_option_label=opt_pack["correct_option_label"],
        distractors=opt_pack["distractors"],
        misconception_map=opt_pack["misconception_map"],
        proof_steps=[asdict(s) for s in steps],
        latex_proof=latex_proof,
        text_proof=text_proof,
        formula_symbolic="T(K_n) = n^(n - 2)",
    )


# ==============================================================================
# Unified Public Generator Factory
# ==============================================================================

def generate_problem(
    topic: Optional[str] = None,
    difficulty: str = "Medium",
    seed: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Main entry point invoked by server dispatcher, CLI, and client Math Studio view.

    Args:
        topic: One of 'INTEREST_DIFFERENCE', 'WORK_COLLABORATION', 'URN_PROBABILITY', 'CAYLEY_TREES',
               or alias (e.g. 'ci_si', 'work', 'urn', 'cayley').
               If None, picks randomly across all 4 topics.
        difficulty: 'Easy', 'Medium', 'Hard'.
        seed: Deterministic integer seed for reproducible testing.
        **kwargs: Optional topic-specific parameter overrides (e.g. years, n).

    Returns:
        AptitudeProblem as a dictionary.

    Raises:
        ValueError: If topic string is unrecognized.
    """
    rng = random.Random(seed)

    resolved_topic: AptitudeTopic
    if topic is None:
        resolved_topic = rng.choice(list(AptitudeTopic))
    else:
        norm = topic.strip().lower()
        if norm in TOPIC_ALIASES:
            resolved_topic = TOPIC_ALIASES[norm]
        else:
            # Check direct enum value
            try:
                resolved_topic = AptitudeTopic(topic.upper())
            except ValueError:
                valid_topics = list(TOPIC_ALIASES.keys()) + [e.value for e in AptitudeTopic]
                raise ValueError(
                    f"Unknown aptitude topic '{topic}'. Supported topics: {sorted(set(valid_topics))}"
                )

    problem: AptitudeProblem
    if resolved_topic == AptitudeTopic.INTEREST_DIFFERENCE:
        years = kwargs.get("years")
        problem = generate_interest_problem(seed=seed, years=years, difficulty=difficulty)
    elif resolved_topic == AptitudeTopic.WORK_COLLABORATION:
        variant = kwargs.get("variant", "COLLABORATION")
        problem = generate_work_problem(seed=seed, variant=variant, difficulty=difficulty)
    elif resolved_topic == AptitudeTopic.URN_PROBABILITY:
        variant = kwargs.get("variant", "SAME_COLOR")
        problem = generate_urn_problem(seed=seed, variant=variant, difficulty=difficulty)
    elif resolved_topic == AptitudeTopic.CAYLEY_TREES:
        n = kwargs.get("n")
        problem = generate_cayley_problem(seed=seed, n=n, difficulty=difficulty)
    else:
        raise ValueError(f"Unhandled topic: {resolved_topic}")

    return problem.to_dict()
