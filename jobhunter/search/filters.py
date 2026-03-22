"""Post-fetch filtering of JobPost lists against SearchParams."""

from __future__ import annotations

from datetime import datetime, timezone

from jobhunter.models import JobPost, SalaryPeriod, SearchParams

# ---------------------------------------------------------------------------
# Salary normalisation
# ---------------------------------------------------------------------------

_HOURS_PER_YEAR = 2080   # 40h × 52 weeks
_MONTHS_PER_YEAR = 12


def salary_to_annual(amount: float, period: SalaryPeriod) -> float:
    """Convert a salary amount to an annual equivalent."""
    if period == SalaryPeriod.HOURLY:
        return amount * _HOURS_PER_YEAR
    if period == SalaryPeriod.MONTHLY:
        return amount * _MONTHS_PER_YEAR
    return amount  # already annual


# ---------------------------------------------------------------------------
# Individual filters  (each returns True if the post should be kept)
# ---------------------------------------------------------------------------

def _passes_work_type(job: JobPost, params: SearchParams) -> bool:
    if not params.work_type:
        return True
    if job.work_type is None:
        return True   # unknown → don't discard
    return job.work_type in params.work_type


def _passes_salary(job: JobPost, params: SearchParams) -> bool:
    has_salary = job.salary_annual_min is not None or job.salary_annual_max is not None

    if not has_salary:
        return params.is_show_no_salary_posts

    target_min = params.salary_min_annual
    target_max = params.salary_max_annual

    if target_min is None and target_max is None:
        return True

    job_lo = job.salary_annual_min or 0.0
    job_hi = job.salary_annual_max or float("inf")

    # Ranges overlap if job_lo <= target_max AND job_hi >= target_min
    if target_max is not None and job_lo > target_max:
        return False
    if target_min is not None and job_hi < target_min:
        return False
    return True


def _passes_post_age(job: JobPost, params: SearchParams) -> bool:
    if params.max_post_age_days is None:
        return True
    if job.posted_date is None:
        return True   # unknown age → don't discard

    now = datetime.now(tz=timezone.utc)
    posted = job.posted_date
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)

    age_days = (now - posted).days
    return age_days <= params.max_post_age_days


def _passes_applicants(job: JobPost, params: SearchParams) -> bool:
    if params.max_num_applicants is None:
        return True
    if job.num_applicants is None:
        return True   # unknown → don't discard
    return job.num_applicants <= params.max_num_applicants


def _passes_experience(job: JobPost, params: SearchParams) -> bool:
    want_min = params.experience_level_years_min
    want_max = params.experience_level_years_max

    if want_min is None and want_max is None:
        return True

    job_min = job.experience_years_min
    job_max = job.experience_years_max

    if job_min is None and job_max is None:
        return True   # job doesn't specify — don't discard

    job_lo = job_min if job_min is not None else 0
    job_hi = job_max if job_max is not None else float("inf")

    param_lo = want_min if want_min is not None else 0
    param_hi = want_max if want_max is not None else float("inf")

    # Keep if candidate range overlaps job requirement range
    return param_lo <= job_hi and param_hi >= job_lo


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def post_fetch_filter(jobs: list[JobPost], params: SearchParams) -> list[JobPost]:
    """
    Apply all filters in sequence and return only posts that pass every check.

    Filters applied:
    1. work_type
    2. salary (normalises to annual, handles is_show_no_salary_posts)
    3. max_post_age_days
    4. max_num_applicants
    5. experience_level_years
    """
    result = []
    for job in jobs:
        if not _passes_work_type(job, params):
            continue
        if not _passes_salary(job, params):
            continue
        if not _passes_post_age(job, params):
            continue
        if not _passes_applicants(job, params):
            continue
        if not _passes_experience(job, params):
            continue
        result.append(job)
    return result
