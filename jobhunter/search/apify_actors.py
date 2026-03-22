"""Apify actor IDs and input-building helpers for each job source."""

from __future__ import annotations

from typing import Any

from jobhunter.models import JobSource, SearchParams, WorkType

# ---------------------------------------------------------------------------
# Actor registry
# ---------------------------------------------------------------------------

ACTOR_IDS: dict[JobSource, str] = {
    JobSource.LINKEDIN: "worldunboxer/rapid-linkedin-scraper",
    JobSource.INDEED: "misceres/indeed-scraper",
    JobSource.GLASSDOOR: "bebity/glassdoor-jobs-scraper",
}

# ---------------------------------------------------------------------------
# Work-type string mappings per source
# ---------------------------------------------------------------------------

# worldunboxer/rapid-linkedin-scraper: work_schedule "1"=On-site "2"=Remote "3"=Hybrid
_LINKEDIN_WORK_SCHEDULE: dict[WorkType, str] = {
    WorkType.ON_SITE: "1",
    WorkType.REMOTE: "2",
    WorkType.HYBRID: "3",
}

# worldunboxer/rapid-linkedin-scraper: experience_level codes
# "2"=Entry level  "3"=Associate  "4"=Mid-Senior  "5"=Director  "6"=Executive
_LINKEDIN_EXP_LEVEL: list[tuple[int, str]] = [
    (0,  "2"),   # 0 yrs → Entry
    (2,  "3"),   # 1–2 yrs → Associate
    (5,  "4"),   # 3–5 yrs → Mid-Senior
    (9,  "5"),   # 6–9 yrs → Director
    (999,"6"),   # 10+ yrs → Executive
]

# worldunboxer/rapid-linkedin-scraper: job_post_time codes
_LINKEDIN_POST_TIME: list[tuple[int, str]] = [
    (1,  "r86400"),    # ≤1 day
    (7,  "r604800"),   # ≤1 week
    (30, "r2592000"),  # ≤1 month
]

_INDEED_WORK_TYPE: dict[WorkType, str] = {
    WorkType.ON_SITE: "fulltime",   # Indeed bundles remote as a filter flag
    WorkType.HYBRID: "fulltime",
    WorkType.REMOTE: "remote",
}

_GLASSDOOR_WORK_TYPE: dict[WorkType, str] = {
    WorkType.ON_SITE: "onsite",
    WorkType.HYBRID: "hybrid",
    WorkType.REMOTE: "remote",
}


# ---------------------------------------------------------------------------
# Posted-age helpers
# ---------------------------------------------------------------------------

def _linkedin_posted_at(max_days: int | None) -> str | None:
    if max_days is None:
        return None
    if max_days <= 1:
        return "past-24h"
    if max_days <= 7:
        return "past-week"
    if max_days <= 30:
        return "past-month"
    return None  # LinkedIn doesn't support > 30 days as a filter


def _indeed_posted_at(max_days: int | None) -> int | None:
    """Indeed accepts fromage (days) directly."""
    return max_days


def _glassdoor_posted_at(max_days: int | None) -> str | None:
    if max_days is None:
        return None
    if max_days <= 1:
        return "1"
    if max_days <= 3:
        return "3"
    if max_days <= 7:
        return "7"
    if max_days <= 14:
        return "14"
    if max_days <= 30:
        return "30"
    return None


# ---------------------------------------------------------------------------
# Input builders
# ---------------------------------------------------------------------------

def build_linkedin_input(params: SearchParams, max_results: int = 50) -> list[dict[str, Any]]:
    """Returns one input dict per requested work_type (actor only accepts one per run)."""
    search_term = params.job_title or " ".join(params.keywords)

    base: dict[str, Any] = {
        "job_title": search_term,
        "location": params.location,
        "jobs_entries": max_results,
    }

    if params.experience_level_years_min is not None:
        yrs = params.experience_level_years_min
        for threshold, code in _LINKEDIN_EXP_LEVEL:
            if yrs <= threshold:
                base["experience_level"] = code
                break

    if params.max_post_age_days is not None:
        for threshold, code in _LINKEDIN_POST_TIME:
            if params.max_post_age_days <= threshold:
                base["job_post_time"] = code
                break

    if not params.work_type:
        return [base]

    return [{**base, "work_schedule": _LINKEDIN_WORK_SCHEDULE[wt]}
            for wt in params.work_type if wt in _LINKEDIN_WORK_SCHEDULE]


def build_indeed_input(params: SearchParams, max_results: int = 50) -> dict[str, Any]:
    search_term = params.job_title or " ".join(params.keywords) or ""
    actor_input: dict[str, Any] = {
        "position": search_term,
        "location": params.location,
        "country": params.country.upper(),
        "maxItems": max_results,
    }

    if params.work_type and WorkType.REMOTE in params.work_type:
        actor_input["remote"] = True

    fromage = _indeed_posted_at(params.max_post_age_days)
    if fromage is not None:
        actor_input["fromage"] = fromage

    return actor_input


def build_glassdoor_input(params: SearchParams, max_results: int = 50) -> dict[str, Any]:
    search_term = params.job_title or " ".join(params.keywords) or ""
    actor_input: dict[str, Any] = {
        "keyword": search_term,
        "location": params.location,
        "maxResults": max_results,
    }

    if params.work_type:
        actor_input["workType"] = _GLASSDOOR_WORK_TYPE.get(params.work_type[0], "")

    posted_at = _glassdoor_posted_at(params.max_post_age_days)
    if posted_at:
        actor_input["postedAt"] = posted_at

    return actor_input


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_BUILDERS = {
    JobSource.LINKEDIN: build_linkedin_input,
    JobSource.INDEED: build_indeed_input,
    JobSource.GLASSDOOR: build_glassdoor_input,
}


def build_actor_inputs(source: JobSource, params: SearchParams, max_results: int = 50) -> list[dict[str, Any]]:
    """Return a list of actor run_input dicts (LinkedIn may return >1 for multiple work types)."""
    result = _BUILDERS[source](params, max_results)
    return result if isinstance(result, list) else [result]
