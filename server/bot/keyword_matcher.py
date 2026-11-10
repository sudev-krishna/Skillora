"""
Skillora Offline Rule-Based Mock Interview Bot: Keyword & Concept Matcher.
100% offline, zero external dependencies, Python standard library only.
Provides 4-stage matching ladder: exact match, synonym expansion, rule-based stemming,
and difflib SequenceMatcher typo tolerance.
"""

from __future__ import annotations

import difflib
import math
import re
import string
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Curated CS Domain Synonym Ontology
# ---------------------------------------------------------------------------
TECHNICAL_SYNONYMS: Dict[str, Set[str]] = {
    # Data Structures & Algorithms
    "hash map": {
        "hashmap", "hash map", "hash table", "hashtable", "dict", "dictionary", "map", "hash-table"
    },
    "two pointer": {
        "two pointer", "two pointers", "pointer pair", "two-pointer", "two-pointers", "left right pointers"
    },
    "in-place": {
        "in-place", "in place", "constant extra space", "o(1) space", "o(1) auxiliary space",
        "no extra memory", "in-situ"
    },
    "stack": {"stack", "lifo", "last in first out"},
    "queue": {"queue", "fifo", "first in first out"},
    "binary search": {
        "binary search", "half interval", "logarithmic search", "divide and conquer", "o(log n)"
    },
    "binary search tree": {
        "binary search tree", "bst", "ordered tree", "binary search-tree"
    },
    "dfs": {"dfs", "depth first search", "depth-first search"},
    "bfs": {"bfs", "breadth first search", "breadth-first search"},
    "cycle": {"cycle", "cyclic", "loop", "back edge", "circular reference"},
    "sliding window": {"sliding window", "two pointer window", "window", "sliding-window"},
    "invert": {"invert", "mirror", "swap children", "reverse tree", "inverted"},
    "linked list": {
        "linked list", "linked-list", "singly linked list", "doubly linked list", "pointer chain"
    },
    "recursion": {"recursion", "recursive", "self call", "self-calling", "base case", "recurse"},
    "dynamic programming": {
        "dynamic programming", "dp", "memoization", "tabulation", "optimal substructure",
        "overlapping subproblems"
    },
    "greedy": {"greedy", "locally optimal", "greedy choice"},
    "time complexity": {
        "time complexity", "runtime", "big-o time", "asymptotic time", "running time"
    },
    "space complexity": {
        "space complexity", "auxiliary space", "memory complexity", "big-o space"
    },

    # Complexity
    "time complexity": {
        "time complexity", "runtime", "big-o time", "asymptotic time", "running time", "time"
    },
    "space complexity": {
        "space complexity", "auxiliary space", "memory complexity", "big-o space", "space"
    },
    "o(1) space": {
        "o(1) space", "o(1) auxiliary space", "o(1) extra space", "o(1) extra auxiliary space",
        "constant space", "constant extra space", "o(1) memory", "in-place"
    },
    "o(n) time": {
        "o(n) time", "linear time", "o(n) runtime", "o(n) time complexity", "linear runtime"
    },

    # Operating Systems
    "pcb": {"pcb", "process control block"},
    "tcb": {"tcb", "thread control block"},
    "context switch": {
        "context switch", "context switching", "task switch", "cpu context switch"
    },
    "thread": {"thread", "lightweight process", "lwp"},
    "deadlock": {
        "deadlock", "dead lock", "circular wait", "deadlocks", "dead-lock"
    },
    "coffman conditions": {
        "coffman conditions", "coffman", "deadlock conditions", "four conditions"
    },
    "virtual memory": {
        "virtual memory", "paging", "swap", "demand paging", "page table"
    },
    "tlb": {"tlb", "translation lookaside buffer"},
    "thrashing": {"thrashing", "page thrashing", "high page fault rate", "excessive paging"},
    "ipc": {
        "ipc", "inter-process communication", "interprocess communication", "message passing", "shared memory"
    },
    "mutex": {"mutex", "mutual exclusion", "lock", "binary semaphore"},
    "semaphore": {"semaphore", "counting semaphore", "signaling mechanism"},
    "critical section": {"critical section", "shared resource", "race condition"},

    # Database Management Systems (DBMS)
    "acid": {
        "acid", "atomicity consistency isolation durability",
        "atomicity consistency isolation and durability", "acid properties"
    },
    "atomicity": {"atomicity", "all or nothing", "atomic"},
    "consistency": {"consistency", "integrity constraints", "valid state"},
    "isolation": {"isolation", "concurrency control", "isolated transactions"},
    "durability": {"durability", "persistence", "non-volatile", "survives crashes"},
    "wal": {
        "wal", "write-ahead logging", "write ahead log", "redo log", "journaling"
    },
    "normalization": {
        "normalization", "normal forms", "normal form", "normalizing", "1nf", "2nf", "3nf", "bcnf"
    },
    "b+ tree": {
        "b+ tree", "b+tree", "b plus tree", "b-tree", "btree", "balanced multiway tree"
    },
    "index": {
        "index", "indexing", "clustered index", "secondary index", "b-tree index"
    },
    "isolation levels": {
        "isolation levels", "transaction isolation", "read uncommitted", "read committed",
        "repeatable read", "serializable"
    },

    # Computer Networks
    "tcp": {"tcp", "transmission control protocol"},
    "udp": {"udp", "user datagram protocol"},
    "handshake": {
        "handshake", "3-way handshake", "syn ack", "three way handshake", "three-way handshake"
    },
    "time_wait": {
        "time_wait", "time wait", "2msl", "maximum segment lifetime"
    },
    "osi": {"osi", "osi model", "7 layers", "seven layers"},
    "dns": {"dns", "domain name system", "domain name resolution"},
    "tls": {"tls", "ssl", "transport layer security", "https"},

    # Python Core & Software Architecture
    "gil": {"gil", "global interpreter lock"},
    "mro": {"mro", "method resolution order", "c3 linearization", "c3"},
    "generator": {"generator", "yield", "lazy evaluation", "generator function", "generators"},
    "decorator": {"decorator", "wrapper", "higher order function", "@wraps", "decorators"},
    "solid": {
        "solid", "solid principles", "single responsibility", "open closed", "liskov",
        "interface segregation", "dependency inversion"
    },
    "garbage collector": {
        "garbage collector", "garbage collection", "gc", "reference counting", "cyclic gc"
    },
}

# Alias for external imports
SYNONYM_DICTIONARY: Dict[str, Set[str]] = TECHNICAL_SYNONYMS


# ---------------------------------------------------------------------------
# Text Normalization & Suffix Stemmer (Standard Library)
# ---------------------------------------------------------------------------
_BIG_O_PATTERN = re.compile(r"\b[oO]\s*\(\s*([^)]+)\s*\)")
_PUNCTUATION_TRANS = str.maketrans(string.punctuation, " " * len(string.punctuation))


def normalize_text(text: str) -> str:
    """
    Normalizes candidate response or keywords for technical concept matching:
    - Lowercases text
    - Collapses Big-O spacing: 'O( n log n )' -> 'o(n log n)', 'O(1)' -> 'o(1)'
    - Unifies hyphens and replaces special punctuation with single whitespace
    - Strips leading/trailing and redundant whitespace
    """
    if not text:
        return ""

    lowered = text.lower()

    # Canonicalize Big-O notations: collapse internal spaces
    def _clean_big_o(match: re.Match[str]) -> str:
        inside = match.group(1).replace(" ", "")
        return f"o({inside})"

    canonical_big_o = _BIG_O_PATTERN.sub(_clean_big_o, lowered)

    # Replace hyphens with spaces for compound terms (e.g. "three-way" -> "three way")
    unhyphenated = canonical_big_o.replace("-", " ")

    # Strip punctuation except parenthesis when part of Big-O
    # We replace punctuation with spaces
    cleaned = unhyphenated.translate(_PUNCTUATION_TRANS)

    # Collapse repeated whitespace
    return " ".join(cleaned.split())


def stem_token(token: str) -> str:
    """
    Lightweight rule-based suffix stemmer using Python standard library.
    Handles common CS plurals, participles, and derivations.
    Enforces minimum token length >= 4 and root length >= 3.
    """
    token = token.lower().strip()
    if len(token) < 4:
        return token

    # Suffix reduction rules in priority order
    rules: List[Tuple[str, str]] = [
        ("ization", ""),
        ("izing", ""),
        ("ized", ""),
        ("ize", ""),
        ("ies", "y"),
        ("sses", "ss"),
        ("xes", "x"),
        ("zes", "z"),
        ("ches", "ch"),
        ("shes", "sh"),
        ("es", ""),
        ("s", ""),
        ("e", ""),
        ("ing", ""),
        ("ed", ""),
        ("tion", "t"),
        ("sion", "s"),
        ("ment", ""),
        ("able", ""),
        ("ible", ""),
        ("ity", ""),
        ("ive", ""),
        ("al", ""),
        ("ness", ""),
        ("ly", ""),
    ]

    for suffix, replacement in rules:
        if token.endswith(suffix):
            root = token[:-len(suffix)] + replacement
            # Consonant collapsing (e.g. "stopping" -> "stopp" -> "stop")
            if len(root) >= 3 and root[-1] == root[-2] and root[-1] not in "aeioulsz":
                root = root[:-1]
            if len(root) >= 3:
                return root

    return token


# Build reverse lookup map for fast synonym matching
_REVERSE_SYNONYM_MAP: Dict[str, Set[str]] = {}
for canonical_key, syn_set in TECHNICAL_SYNONYMS.items():
    combined = set(syn_set) | {canonical_key}
    for item in combined:
        clean_item = normalize_text(item)
        if clean_item not in _REVERSE_SYNONYM_MAP:
            _REVERSE_SYNONYM_MAP[clean_item] = set()
        _REVERSE_SYNONYM_MAP[clean_item].update(combined)


# ---------------------------------------------------------------------------
# 4-Stage Single Keyword Matcher
# ---------------------------------------------------------------------------
def match_single_keyword(
    target: str,
    normalized_text: str,
    tokens: List[str],
    stemmed_tokens: Set[str],
    stemmed_target: str,
    target_synonyms: Set[str],
    fuzzy_threshold: float = 0.82
) -> Tuple[float, str]:
    """
    Evaluates a single expected keyword against student text using 4-stage matching ladder:
    1. Exact phrase/token match -> Score 1.0 ('exact')
    2. Domain synonym set match -> Score 1.0 ('synonym')
    3. Rule-based suffix stemmed match -> Score 1.0 ('stemmed')
    4. Fuzzy typo match via difflib.SequenceMatcher -> Score 0.85 ('fuzzy')

    Returns (score: 0.0 to 1.0, match_type: 'exact'|'synonym'|'stemmed'|'fuzzy'|'none').
    """
    clean_target = normalize_text(target)
    if not clean_target:
        return 0.0, "none"

    # Stage 1: Exact whole-word / token match
    # Check whole word / phrase boundary
    pattern = r"\b" + re.escape(clean_target) + r"\b"
    if re.search(pattern, normalized_text):
        return 1.0, "exact"

    # Stage 2: Technical synonym expansion match
    if target_synonyms:
        for syn in target_synonyms:
            clean_syn = normalize_text(syn)
            if not clean_syn:
                continue
            syn_pattern = r"\b" + re.escape(clean_syn) + r"\b"
            if re.search(syn_pattern, normalized_text):
                return 1.0, "synonym"

            # For multi-word synonym expansions (e.g. ACID -> atomicity, consistency, isolation, durability)
            syn_words = clean_syn.split()
            if len(syn_words) >= 3:
                content_words = [
                    stem_token(w) for w in syn_words
                    if w not in ("and", "or", "the", "of", "in", "to", "a", "an", "is", "with")
                ]
                if content_words and all(w in stemmed_tokens for w in content_words):
                    return 1.0, "synonym"

    # Stage 3: Stemmed token match (for single-word target)
    target_words = clean_target.split()
    if len(target_words) == 1:
        if stemmed_target in stemmed_tokens:
            return 1.0, "stemmed"
    else:
        # Multi-word target: check if all stemmed target words are present in text
        stemmed_target_words = [stem_token(w) for w in target_words]
        if all(w in stemmed_tokens for w in stemmed_target_words):
            # Check sequential presence if possible
            target_joined = " ".join(stemmed_target_words)
            text_stemmed_joined = " ".join(stem_token(t) for t in tokens)
            if target_joined in text_stemmed_joined:
                return 1.0, "stemmed"

    # Stage 4: Fuzzy sequence ratio via difflib.SequenceMatcher
    if len(target_words) == 1:
        # Single-word fuzzy check across all candidate tokens
        best_ratio = 0.0
        for tok in tokens:
            if abs(len(tok) - len(clean_target)) <= 3:
                ratio = difflib.SequenceMatcher(None, clean_target, tok).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
        if best_ratio >= fuzzy_threshold:
            return round(max(0.80, best_ratio), 2), "fuzzy"
    else:
        # Multi-word phrase fuzzy check using sliding n-gram window
        n = len(target_words)
        best_ratio = 0.0
        if len(tokens) >= n:
            for i in range(len(tokens) - n + 1):
                window_str = " ".join(tokens[i:i + n])
                ratio = difflib.SequenceMatcher(None, clean_target, window_str).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
        if best_ratio >= fuzzy_threshold:
            return round(max(0.80, best_ratio), 2), "fuzzy"

    return 0.0, "none"


# ---------------------------------------------------------------------------
# Full Keyword Coverage & Scoring
# ---------------------------------------------------------------------------
def compute_keyword_coverage(
    student_text: str,
    expected_keywords: Iterable[str],
    keyword_weights: Optional[Mapping[str, float]] = None,
    fuzzy_threshold: float = 0.82
) -> Dict[str, Any]:
    """
    Computes normalized Tier 1 keyword coverage score (0.0 - 100.0%) and concept density.
    Returns:
        {
            "keyword_score": float,          # 0.0 - 100.0
            "matched_keywords": List[str],
            "missing_keywords": List[str],
            "match_details": Dict[str, Dict[str, Any]],
            "concept_density": float,
            "total_expected": int,
            "total_matched": int
        }
    """
    if not expected_keywords:
        return {
            "keyword_score": 100.0,
            "matched_keywords": [],
            "missing_keywords": [],
            "match_details": {},
            "concept_density": 0.0,
            "total_expected": 0,
            "total_matched": 0,
        }

    raw_keywords = [str(k).strip() for k in expected_keywords if str(k).strip()]
    if not raw_keywords:
        return {
            "keyword_score": 100.0,
            "matched_keywords": [],
            "missing_keywords": [],
            "match_details": {},
            "concept_density": 0.0,
            "total_expected": 0,
            "total_matched": 0,
        }

    normalized_text = normalize_text(student_text or "")
    tokens = normalized_text.split()
    stemmed_tokens = set(stem_token(t) for t in tokens)

    # Weights normalization
    weights: Dict[str, float] = {}
    total_custom_weight = 0.0
    for kw in raw_keywords:
        w = 1.0
        if keyword_weights and kw in keyword_weights:
            try:
                w = float(keyword_weights[kw])
            except (ValueError, TypeError):
                w = 1.0
        weights[kw] = max(0.1, w)
        total_custom_weight += weights[kw]

    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    match_details: Dict[str, Dict[str, Any]] = {}
    weighted_score_accum = 0.0

    for kw in raw_keywords:
        clean_target = normalize_text(kw)
        stemmed_target = stem_token(clean_target)

        # Retrieve synonyms for target
        target_synonyms: Set[str] = set()
        if clean_target in _REVERSE_SYNONYM_MAP:
            target_synonyms.update(_REVERSE_SYNONYM_MAP[clean_target])
        for syn_key, syn_set in TECHNICAL_SYNONYMS.items():
            if clean_target == syn_key or clean_target in syn_set:
                target_synonyms.update(syn_set)
                target_synonyms.add(syn_key)

        score, match_type = match_single_keyword(
            target=kw,
            normalized_text=normalized_text,
            tokens=tokens,
            stemmed_tokens=stemmed_tokens,
            stemmed_target=stemmed_target,
            target_synonyms=target_synonyms,
            fuzzy_threshold=fuzzy_threshold,
        )

        match_details[kw] = {
            "score": score,
            "match_type": match_type,
            "weight": weights[kw],
        }

        if score > 0.0:
            matched_keywords.append(kw)
            weighted_score_accum += score * weights[kw]
        else:
            missing_keywords.append(kw)

    # Raw coverage percentage
    base_coverage = (weighted_score_accum / total_custom_weight) * 100.0 if total_custom_weight > 0 else 0.0

    # Concept density bonus (rewards concise, high-signal technical articulation)
    # Density = matched concepts / word count
    word_count = len(tokens)
    concept_density = (len(matched_keywords) / max(1, word_count)) if word_count > 0 else 0.0

    density_bonus = 0.0
    if len(matched_keywords) >= 3 and 15 <= word_count <= 250:
        # Modest bonus for concise precision
        density_bonus = min(5.0, round(concept_density * 25.0, 2))

    final_score = min(100.0, max(0.0, base_coverage + density_bonus))

    return {
        "keyword_score": round(final_score, 2),
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "match_details": match_details,
        "concept_density": round(concept_density, 4),
        "total_expected": len(raw_keywords),
        "total_matched": len(matched_keywords),
    }


def match_keywords(
    student_text: str,
    expected_keywords: Iterable[str]
) -> Dict[str, Any]:
    """
    Convenience wrapper returning keyword matching results adhering to interface requirements.
    """
    return compute_keyword_coverage(student_text, expected_keywords)
