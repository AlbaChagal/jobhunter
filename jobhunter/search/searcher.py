"""JobSearcher — orchestrates Apify actor runs and normalises results."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from apify_client import ApifyClient

from jobhunter.models import JobPost, JobSource, SalaryPeriod, SearchParams, WorkType
from jobhunter.search.apify_actors import ACTOR_IDS, build_actor_inputs
from jobhunter.search.filters import post_fetch_filter, salary_to_annual

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_WORK_TYPE_ALIASES: dict[str, WorkType] = {
    "remote": WorkType.REMOTE,
    "hybrid": WorkType.HYBRID,
    "on-site": WorkType.ON_SITE,
    "onsite": WorkType.ON_SITE,
    "in-person": WorkType.ON_SITE,
    "on site": WorkType.ON_SITE,
}

_SALARY_PERIOD_ALIASES: dict[str, SalaryPeriod] = {
    "hour": SalaryPeriod.HOURLY,
    "hourly": SalaryPeriod.HOURLY,
    "hr": SalaryPeriod.HOURLY,
    "month": SalaryPeriod.MONTHLY,
    "monthly": SalaryPeriod.MONTHLY,
    "mo": SalaryPeriod.MONTHLY,
    "year": SalaryPeriod.ANNUAL,
    "annual": SalaryPeriod.ANNUAL,
    "annually": SalaryPeriod.ANNUAL,
    "yr": SalaryPeriod.ANNUAL,
}

_EXP_RE = re.compile(r"(\d+)\s*(?:\+|–|-|to)?\s*(\d+)?\s*(?:years?|yrs?)", re.IGNORECASE)


def _coerce_str(raw: Any) -> str | None:
    """Safely coerce a value to str — handles lists by joining with a space."""
    if raw is None:
        return None
    if isinstance(raw, list):
        raw = " ".join(str(v) for v in raw if v)
    return str(raw).strip() or None


def _parse_work_type(raw: Any) -> WorkType | None:
    s = _coerce_str(raw)
    if not s:
        return None
    for token in s.lower().split():
        result = _WORK_TYPE_ALIASES.get(token)
        if result:
            return result
    return None


def _parse_salary_period(raw: Any) -> SalaryPeriod | None:
    s = _coerce_str(raw)
    if not s:
        return None
    return _SALARY_PERIOD_ALIASES.get(s.lower(), SalaryPeriod.ANNUAL)


def _parse_salary_value(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[,$\s]", "", str(raw))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_experience_years(text: str) -> tuple[int | None, int | None]:
    """Try to extract a (min, max) years-of-experience requirement from free text."""
    match = _EXP_RE.search(text)
    if not match:
        return None, None
    lo = int(match.group(1))
    hi = int(match.group(2)) if match.group(2) else None
    return lo, hi


def _make_id(source: JobSource, raw: dict[str, Any]) -> str:
    for key in ("job_id", "id", "jobId", "joburl", "jobUrl"):
        if raw.get(key):
            return f"{source.value}:{raw[key]}"
    url = raw.get("apply_url") or raw.get("job_url") or raw.get("url") or raw.get("applyUrl", "")
    return f"{source.value}:{hashlib.md5(url.encode()).hexdigest()[:12]}"


_SALARY_RANGE_RE = re.compile(
    r"\$?([\d,]+)[Kk]?\s*[-–—to]+\s*\$?([\d,]+)[Kk]?"
    r"(?:.*?/(yr|year|hr|hour|mo|month))?",
    re.IGNORECASE,
)

def _parse_salary_range_string(raw: Any) -> tuple[float | None, float | None, SalaryPeriod | None]:
    """Parse strings like '$80K–$120K/yr' or '$45–$55/hr' into (min, max, period)."""
    if not raw:
        return None, None, None
    s = str(raw)
    m = _SALARY_RANGE_RE.search(s)
    if not m:
        return None, None, None
    lo = float(m.group(1).replace(",", ""))
    hi = float(m.group(2).replace(",", ""))
    # Detect K multiplier
    if "k" in s.lower() and lo < 1000:
        lo *= 1000
        hi *= 1000
    period_raw = m.group(3) or ""
    period = _parse_salary_period(period_raw) if period_raw else SalaryPeriod.ANNUAL
    return lo, hi, period


def _parse_posted_date(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        from dateutil import parser as dparser
        return dparser.parse(str(raw))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-source normalisers
# ---------------------------------------------------------------------------

_APPLICANT_NUM_RE = re.compile(r"(\d[\d,]*)")


def _parse_applicant_count(raw: Any) -> int | None:
    """Parse strings like 'Over 200 applicants' or '47 applicants' to int."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    m = _APPLICANT_NUM_RE.search(str(raw))
    return int(m.group(1).replace(",", "")) if m else None


def _normalise_linkedin(raw: dict[str, Any]) -> JobPost:
    # worldunboxer/rapid-linkedin-scraper field names
    title = raw.get("job_title") or raw.get("title", "")
    company = raw.get("company_name") or raw.get("company", "")
    location = raw.get("location", "")
    description = raw.get("job_description") or raw.get("description", "")
    url = raw.get("apply_url") or raw.get("job_url") or raw.get("url", "")

    # Actor returns relative strings like "3 days ago"; not ISO dates → skip
    posted_date = _parse_posted_date(raw.get("postedAt") or raw.get("publishedAt"))
    num_applicants = _parse_applicant_count(raw.get("num_applicants") or raw.get("applicantsCount"))

    # employment_type = "Full-time" / "Part-time" — not remote/hybrid, so check description
    work_type = _parse_work_type(raw.get("work_schedule") or raw.get("workplaceType"))

    # salary_range is a raw string like "$80K–$120K/yr" or null
    salary_min, salary_max, period = _parse_salary_range_string(raw.get("salary_range"))

    exp_min, exp_max = _extract_experience_years(description)

    annual_min = salary_to_annual(salary_min, period) if salary_min and period else None
    annual_max = salary_to_annual(salary_max, period) if salary_max and period else None

    return JobPost(
        id=_make_id(JobSource.LINKEDIN, raw),
        title=title,
        company=company,
        location=location,
        work_type=work_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=period,
        salary_annual_min=annual_min,
        salary_annual_max=annual_max,
        description=description,
        posted_date=posted_date,
        num_applicants=num_applicants,
        url=url,
        source=JobSource.LINKEDIN,
        experience_years_min=exp_min,
        experience_years_max=exp_max,
    )


def _normalise_indeed(raw: dict[str, Any]) -> JobPost:
    title = raw.get("positionName") or raw.get("title", "")
    company = raw.get("company", "")
    location = raw.get("location", "")
    description = raw.get("description", "")
    url = raw.get("url", "")
    posted_date = _parse_posted_date(raw.get("postedAt") or raw.get("datePosted"))
    num_applicants = raw.get("applicantsCount")
    work_type_raw = raw.get("jobType") or raw.get("workType")
    work_type = _parse_work_type(work_type_raw)

    salary_min = _parse_salary_value(raw.get("salaryMin"))
    salary_max = _parse_salary_value(raw.get("salaryMax"))
    period = _parse_salary_period(raw.get("salaryType") or raw.get("salaryPeriod"))

    exp_min, exp_max = _extract_experience_years(description)

    annual_min = salary_to_annual(salary_min, period) if salary_min and period else None
    annual_max = salary_to_annual(salary_max, period) if salary_max and period else None

    return JobPost(
        id=_make_id(JobSource.INDEED, raw),
        title=title,
        company=company,
        location=location,
        work_type=work_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=period,
        salary_annual_min=annual_min,
        salary_annual_max=annual_max,
        description=description,
        posted_date=posted_date,
        num_applicants=int(num_applicants) if num_applicants else None,
        url=url,
        source=JobSource.INDEED,
        experience_years_min=exp_min,
        experience_years_max=exp_max,
    )


def _normalise_glassdoor(raw: dict[str, Any]) -> JobPost:
    title = raw.get("jobTitle") or raw.get("title", "")
    company = raw.get("employerName") or raw.get("company", "")
    location = raw.get("location", "")
    description = raw.get("description", "")
    url = raw.get("jobListingUrl") or raw.get("url", "")
    posted_date = _parse_posted_date(raw.get("discoveredAt") or raw.get("postedDate"))
    work_type_raw = raw.get("workType") or raw.get("locationType")
    work_type = _parse_work_type(work_type_raw)

    salary_min = _parse_salary_value(raw.get("payPeriodMin") or raw.get("salaryMin"))
    salary_max = _parse_salary_value(raw.get("payPeriodMax") or raw.get("salaryMax"))
    period_raw = raw.get("payPeriod") or raw.get("salaryPeriod")
    period = _parse_salary_period(period_raw)

    exp_min, exp_max = _extract_experience_years(description)

    annual_min = salary_to_annual(salary_min, period) if salary_min and period else None
    annual_max = salary_to_annual(salary_max, period) if salary_max and period else None

    return JobPost(
        id=_make_id(JobSource.GLASSDOOR, raw),
        title=title,
        company=company,
        location=location,
        work_type=work_type,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=period,
        salary_annual_min=annual_min,
        salary_annual_max=annual_max,
        description=description,
        posted_date=posted_date,
        url=url,
        source=JobSource.GLASSDOOR,
        experience_years_min=exp_min,
        experience_years_max=exp_max,
    )


_NORMALISERS = {
    JobSource.LINKEDIN: _normalise_linkedin,
    JobSource.INDEED: _normalise_indeed,
    JobSource.GLASSDOOR: _normalise_glassdoor,
}

# ---------------------------------------------------------------------------
# JobSearcher
# ---------------------------------------------------------------------------


class JobSearcher:
    """
    Searches for jobs across multiple sources via Apify actors.

    Args:
        apify_api_key: Your Apify API token.
    """

    def __init__(self, apify_api_key: str) -> None:
        self._client = ApifyClient(apify_api_key)

    def search(
        self,
        params: SearchParams,
        sources: list[str] | list[JobSource] | None = None,
        max_results_per_source: int = 50,
    ) -> list[JobPost]:
        """
        Run a job search across one or more sources.

        Args:
            params: Search parameters (location, salary, filters, etc.).
            sources: List of source names or JobSource enums. Defaults to all three.
            max_results_per_source: Maximum results to fetch from each source.

        Returns:
            Filtered list of JobPost objects, deduplicated by URL.
        """
        if sources is None:
            sources = [JobSource.LINKEDIN, JobSource.INDEED, JobSource.GLASSDOOR]

        resolved: list[JobSource] = []
        for s in sources:
            resolved.append(JobSource(s) if isinstance(s, str) else s)

        all_jobs: list[JobPost] = []
        seen_urls: set[str] = set()

        for source in resolved:
            try:
                jobs = self._search_source(source, params, max_results_per_source)
                for job in jobs:
                    if job.url and job.url in seen_urls:
                        continue
                    if job.url:
                        seen_urls.add(job.url)
                    all_jobs.append(job)
            except Exception as exc:
                print(f"[jobhunter] Warning: {source.value} search failed — {exc}")

        return post_fetch_filter(all_jobs, params)

    def _search_source(
        self,
        source: JobSource,
        params: SearchParams,
        max_results: int,
    ) -> list[JobPost]:
        actor_id = ACTOR_IDS[source]
        run_inputs = build_actor_inputs(source, params, max_results)
        normalise = _NORMALISERS[source]

        all_items: list[dict] = []
        for run_input in run_inputs:
            run = self._client.actor(actor_id).call(run_input=run_input)
            all_items.extend(self._client.dataset(run["defaultDatasetId"]).list_items().items)

        jobs = []
        for raw in all_items:
            try:
                jobs.append(normalise(raw))
            except Exception as exc:
                print(f"[jobhunter] Warning: could not normalise {source.value} item — {exc}")
        return jobs
