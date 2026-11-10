"""
Skillora Offline Rule-Based Mock Interview Bot Package.
100% offline, zero external APIs, zero third-party NLP libraries.
"""

from server.bot.ast_checker import (
    ASTAntiPatternDetector,
    ASTConstructVisitor,
    analyze_code_ast,
    check_code_ast,
)
from server.bot.evaluator import (
    evaluate_answer,
    evaluate_lexical_structure,
)
from server.bot.keyword_matcher import (
    SYNONYM_DICTIONARY,
    TECHNICAL_SYNONYMS,
    compute_keyword_coverage,
    match_keywords,
    normalize_text,
    stem_token,
)

__all__ = [
    "evaluate_answer",
    "evaluate_lexical_structure",
    "match_keywords",
    "compute_keyword_coverage",
    "normalize_text",
    "stem_token",
    "analyze_code_ast",
    "check_code_ast",
    "ASTConstructVisitor",
    "ASTAntiPatternDetector",
    "SYNONYM_DICTIONARY",
    "TECHNICAL_SYNONYMS",
]
