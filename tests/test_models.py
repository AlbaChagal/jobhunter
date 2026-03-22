"""Tests for data models and MatchConfig."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from jobhunter.config import MatchConfig, MatchWeights
from jobhunter.models import (
    JobPost,
    JobSource,
    MatchResult,
    SalaryPeriod,
    SearchParams,
    WorkType,
)


# ---------------------------------------------------------------------------
# SearchParams
# ---------------------------------------------------------------------------

class TestSearchParams:
    def test_minimal(self):
        p = SearchParams(location="London")
        assert p.location == "London"
        assert p.work_type == []
        assert p.salary_period == SalaryPeriod.ANNUAL
        assert p.is_show_no_salary_posts is True

    def test_salary_annual_passthrough(self):
        p = SearchParams(location="NYC", salary_min=100_000, salary_period="annual")
        assert p.salary_min_annual == 100_000

    def test_salary_hourly_to_annual(self):
        p = SearchParams(location="NYC", salary_min=50, salary_period="hourly")
        assert p.salary_min_annual == pytest.approx(50 * 2080)

    def test_salary_monthly_to_annual(self):
        p = SearchParams(location="NYC", salary_max=8_000, salary_period="monthly")
        assert p.salary_max_annual == pytest.approx(8_000 * 12)

    def test_none_salary_annual(self):
        p = SearchParams(location="NYC")
        assert p.salary_min_annual is None
        assert p.salary_max_annual is None


# ---------------------------------------------------------------------------
# MatchWeights
# ---------------------------------------------------------------------------

class TestMatchWeights:
    def test_defaults_sum_to_one(self):
        w = MatchWeights()
        total = sum(w.as_dict().values())
        assert abs(total - 1.0) < 1e-6

    def test_custom_weights_sum_to_one(self):
        w = MatchWeights(
            tech_stack=0.40,
            experience=0.30,
            location=0.05,
            education=0.05,
            soft_skills=0.10,
            work_type=0.05,
            salary=0.05,
        )
        assert abs(sum(w.as_dict().values()) - 1.0) < 1e-6

    def test_weights_not_summing_to_one_raises(self):
        with pytest.raises(ValidationError):
            MatchWeights(tech_stack=0.5, experience=0.5, location=0.5)

    def test_category_names(self):
        w = MatchWeights()
        assert "tech_stack" in w.category_names
        assert len(w.category_names) == 7


# ---------------------------------------------------------------------------
# MatchConfig
# ---------------------------------------------------------------------------

class TestMatchConfig:
    def test_defaults(self):
        cfg = MatchConfig()
        assert cfg.minimum_score_to_apply == 60.0
        assert cfg.strict_experience_match is False

    def test_from_dict(self):
        cfg = MatchConfig.from_dict({
            "weights": {"tech_stack": 0.40, "experience": 0.25, "location": 0.10,
                        "education": 0.05, "soft_skills": 0.10, "work_type": 0.05, "salary": 0.05},
            "minimum_score_to_apply": 70.0,
        })
        assert cfg.minimum_score_to_apply == 70.0
        assert cfg.weights.tech_stack == 0.40

    def test_from_json(self, tmp_path):
        data = {
            "weights": {"tech_stack": 0.35, "experience": 0.25, "location": 0.10,
                        "education": 0.10, "soft_skills": 0.10, "work_type": 0.05, "salary": 0.05},
            "minimum_score_to_apply": 65.0,
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data))
        cfg = MatchConfig.from_json(path)
        assert cfg.minimum_score_to_apply == 65.0

    def test_effective_weights_with_salary(self):
        cfg = MatchConfig()
        weights = cfg.effective_weights(has_salary=True)
        assert "salary" in weights
        assert weights["salary"] == pytest.approx(0.05)

    def test_effective_weights_no_salary_redistributed(self):
        cfg = MatchConfig()
        weights = cfg.effective_weights(has_salary=False)
        assert weights["salary"] == 0.0
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_effective_weights_include_no_salary(self):
        cfg = MatchConfig(include_no_salary_in_scoring=True)
        weights = cfg.effective_weights(has_salary=False)
        assert weights["salary"] == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# JobPost
# ---------------------------------------------------------------------------

class TestJobPost:
    def _make_job(self, **kwargs) -> JobPost:
        defaults = dict(
            id="test:1",
            title="Software Engineer",
            company="Acme",
            location="NYC",
            description="Test job",
            url="https://example.com/job/1",
            source=JobSource.LINKEDIN,
        )
        return JobPost(**{**defaults, **kwargs})

    def test_has_salary_false(self):
        job = self._make_job()
        assert job.has_salary is False

    def test_has_salary_true(self):
        job = self._make_job(salary_annual_min=100_000)
        assert job.has_salary is True

    def test_salary_display_none(self):
        job = self._make_job()
        assert job.salary_display == "Not listed"

    def test_salary_display_range(self):
        job = self._make_job(salary_annual_min=100_000, salary_annual_max=150_000)
        assert "$100,000" in job.salary_display
        assert "$150,000" in job.salary_display
