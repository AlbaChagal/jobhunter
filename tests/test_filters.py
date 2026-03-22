"""Tests for post-fetch filtering logic."""

from datetime import datetime, timedelta, timezone

import pytest

from jobhunter.models import JobPost, JobSource, SalaryPeriod, SearchParams, WorkType
from jobhunter.search.filters import post_fetch_filter, salary_to_annual


# ---------------------------------------------------------------------------
# salary_to_annual
# ---------------------------------------------------------------------------

def test_annual_passthrough():
    assert salary_to_annual(100_000, SalaryPeriod.ANNUAL) == 100_000


def test_hourly_to_annual():
    assert salary_to_annual(50, SalaryPeriod.HOURLY) == pytest.approx(50 * 2080)


def test_monthly_to_annual():
    assert salary_to_annual(8_000, SalaryPeriod.MONTHLY) == pytest.approx(96_000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job(**kwargs) -> JobPost:
    defaults = dict(
        id="x:1",
        title="Engineer",
        company="Acme",
        location="NYC",
        description="",
        url="https://example.com/1",
        source=JobSource.LINKEDIN,
    )
    return JobPost(**{**defaults, **kwargs})


def _params(**kwargs) -> SearchParams:
    defaults = dict(location="NYC")
    return SearchParams(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# Work type filter
# ---------------------------------------------------------------------------

class TestWorkTypeFilter:
    def test_no_work_type_filter_keeps_all(self):
        jobs = [_job(work_type=WorkType.REMOTE), _job(work_type=WorkType.ON_SITE)]
        assert len(post_fetch_filter(jobs, _params())) == 2

    def test_filters_wrong_type(self):
        jobs = [_job(work_type=WorkType.REMOTE), _job(work_type=WorkType.ON_SITE)]
        result = post_fetch_filter(jobs, _params(work_type=[WorkType.REMOTE]))
        assert len(result) == 1
        assert result[0].work_type == WorkType.REMOTE

    def test_unknown_work_type_kept(self):
        jobs = [_job(work_type=None)]
        result = post_fetch_filter(jobs, _params(work_type=[WorkType.REMOTE]))
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Salary filter
# ---------------------------------------------------------------------------

class TestSalaryFilter:
    def test_no_salary_hidden_when_flag_false(self):
        jobs = [_job()]  # no salary
        result = post_fetch_filter(jobs, _params(is_show_no_salary_posts=False))
        assert result == []

    def test_no_salary_shown_when_flag_true(self):
        jobs = [_job()]
        result = post_fetch_filter(jobs, _params(is_show_no_salary_posts=True))
        assert len(result) == 1

    def test_salary_within_range_kept(self):
        jobs = [_job(salary_annual_min=100_000, salary_annual_max=130_000)]
        result = post_fetch_filter(
            jobs, _params(salary_min=90_000, salary_max=140_000, salary_period="annual")
        )
        assert len(result) == 1

    def test_salary_below_range_excluded(self):
        jobs = [_job(salary_annual_min=40_000, salary_annual_max=60_000)]
        result = post_fetch_filter(
            jobs, _params(salary_min=80_000, salary_period="annual")
        )
        assert result == []

    def test_salary_above_range_excluded(self):
        jobs = [_job(salary_annual_min=200_000, salary_annual_max=250_000)]
        result = post_fetch_filter(
            jobs, _params(salary_max=150_000, salary_period="annual")
        )
        assert result == []

    def test_hourly_salary_filter_normalises(self):
        # Job pays $100k/yr; filter requests min $40/hr (≈ $83k) → should keep
        jobs = [_job(salary_annual_min=100_000)]
        result = post_fetch_filter(
            jobs, _params(salary_min=40, salary_period="hourly")
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Post age filter
# ---------------------------------------------------------------------------

class TestPostAgeFilter:
    def test_recent_post_kept(self):
        posted = datetime.now(tz=timezone.utc) - timedelta(days=3)
        jobs = [_job(posted_date=posted)]
        result = post_fetch_filter(jobs, _params(max_post_age_days=7))
        assert len(result) == 1

    def test_old_post_excluded(self):
        posted = datetime.now(tz=timezone.utc) - timedelta(days=30)
        jobs = [_job(posted_date=posted)]
        result = post_fetch_filter(jobs, _params(max_post_age_days=7))
        assert result == []

    def test_unknown_date_kept(self):
        jobs = [_job(posted_date=None)]
        result = post_fetch_filter(jobs, _params(max_post_age_days=7))
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Applicant count filter
# ---------------------------------------------------------------------------

class TestApplicantFilter:
    def test_below_limit_kept(self):
        jobs = [_job(num_applicants=50)]
        result = post_fetch_filter(jobs, _params(max_num_applicants=200))
        assert len(result) == 1

    def test_above_limit_excluded(self):
        jobs = [_job(num_applicants=500)]
        result = post_fetch_filter(jobs, _params(max_num_applicants=200))
        assert result == []

    def test_unknown_applicants_kept(self):
        jobs = [_job(num_applicants=None)]
        result = post_fetch_filter(jobs, _params(max_num_applicants=200))
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Experience filter
# ---------------------------------------------------------------------------

class TestExperienceFilter:
    def test_overlapping_range_kept(self):
        jobs = [_job(experience_years_min=3, experience_years_max=6)]
        result = post_fetch_filter(
            jobs, _params(experience_level_years_min=2, experience_level_years_max=5)
        )
        assert len(result) == 1

    def test_non_overlapping_range_excluded(self):
        jobs = [_job(experience_years_min=8, experience_years_max=12)]
        result = post_fetch_filter(
            jobs, _params(experience_level_years_min=0, experience_level_years_max=3)
        )
        assert result == []

    def test_unknown_job_experience_kept(self):
        jobs = [_job(experience_years_min=None, experience_years_max=None)]
        result = post_fetch_filter(
            jobs, _params(experience_level_years_min=2, experience_level_years_max=5)
        )
        assert len(result) == 1
