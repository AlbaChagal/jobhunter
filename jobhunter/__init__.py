"""
jobhunter — open-source job search and CV matching library.

Quick start::

    from jobhunter import JobSearcher, CVMatcher, SearchParams, MatchConfig

    searcher = JobSearcher(apify_api_key="...")
    params = SearchParams(location="New York", work_type=["remote"])
    jobs = searcher.search(params)

    matcher = CVMatcher(llm_api_key="...", llm_provider="claude")
    ranked = matcher.rank(cv="cv.pdf", jobs=jobs)
"""

from jobhunter.config import MatchConfig, MatchWeights
from jobhunter.matching.matcher import CVMatcher
from jobhunter.models import (
    JobPost,
    JobSource,
    MatchCategory,
    MatchResult,
    SalaryPeriod,
    SearchParams,
    WorkType,
)
from jobhunter.search.searcher import JobSearcher

__all__ = [
    # Main classes
    "JobSearcher",
    "CVMatcher",
    # Input models
    "SearchParams",
    "MatchConfig",
    "MatchWeights",
    # Output models
    "JobPost",
    "MatchResult",
    "MatchCategory",
    # Enums
    "WorkType",
    "SalaryPeriod",
    "JobSource",
]
