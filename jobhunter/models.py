"""Core data models for jobhunter."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class WorkType(str, Enum):
    ON_SITE = "on-site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class SalaryPeriod(str, Enum):
    HOURLY = "hourly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


class JobSource(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"


# ---------------------------------------------------------------------------
# Search input
# ---------------------------------------------------------------------------


class SearchParams(BaseModel):
    """Parameters that drive a job search across one or more sources."""

    location: str = Field(..., description="City, region, or country to search in.")
    country: str = Field("US", description="2-letter ISO country code (e.g. US, DE, GB). Used by Indeed.")
    keywords: list[str] = Field(default_factory=list, description="Search keywords (e.g. skills, tools).")
    job_title: Optional[str] = Field(None, description="Specific job title to search for.")
    work_type: list[WorkType] = Field(
        default_factory=list,
        description="Allowed work arrangements. Empty list means any.",
    )
    salary_min: Optional[float] = Field(None, description="Minimum salary (in salary_period units).")
    salary_max: Optional[float] = Field(None, description="Maximum salary (in salary_period units).")
    salary_period: SalaryPeriod = Field(
        SalaryPeriod.ANNUAL,
        description="Unit for salary_min/salary_max. Defaults to annual.",
    )
    is_show_no_salary_posts: bool = Field(
        True,
        description="Whether to include job posts that don't list a salary.",
    )
    max_post_age_days: Optional[int] = Field(
        None,
        description="Maximum age of a job posting in days. None means no limit.",
    )
    max_num_applicants: Optional[int] = Field(
        None,
        description="Only include posts with fewer than this many applicants. None means no limit.",
    )
    experience_level_years_min: Optional[int] = Field(
        None,
        description="Minimum years of experience required by the job.",
    )
    experience_level_years_max: Optional[int] = Field(
        None,
        description="Maximum years of experience required by the job.",
    )

    @property
    def salary_min_annual(self) -> Optional[float]:
        """salary_min normalised to an annual figure."""
        from jobhunter.search.filters import salary_to_annual
        return salary_to_annual(self.salary_min, self.salary_period) if self.salary_min is not None else None

    @property
    def salary_max_annual(self) -> Optional[float]:
        """salary_max normalised to an annual figure."""
        from jobhunter.search.filters import salary_to_annual
        return salary_to_annual(self.salary_max, self.salary_period) if self.salary_max is not None else None


# ---------------------------------------------------------------------------
# Job post
# ---------------------------------------------------------------------------


class JobPost(BaseModel):
    """A single job listing, normalised from any source."""

    id: str = Field(..., description="Unique identifier (source-specific).")
    title: str
    company: str
    location: str
    work_type: Optional[WorkType] = None
    salary_min: Optional[float] = Field(None, description="Raw minimum salary as reported by the source.")
    salary_max: Optional[float] = Field(None, description="Raw maximum salary as reported by the source.")
    salary_period: Optional[SalaryPeriod] = None
    salary_annual_min: Optional[float] = Field(None, description="salary_min converted to annual.")
    salary_annual_max: Optional[float] = Field(None, description="salary_max converted to annual.")
    description: str = ""
    requirements: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    posted_date: Optional[datetime] = None
    num_applicants: Optional[int] = None
    url: str = ""
    source: JobSource
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None

    @property
    def has_salary(self) -> bool:
        return self.salary_annual_min is not None or self.salary_annual_max is not None

    @property
    def salary_display(self) -> str:
        if not self.has_salary:
            return "Not listed"
        lo = f"${self.salary_annual_min:,.0f}" if self.salary_annual_min else "?"
        hi = f"${self.salary_annual_max:,.0f}" if self.salary_annual_max else "?"
        return f"{lo} – {hi} / year"


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------


class MatchCategory(BaseModel):
    """Score breakdown for one matching dimension."""

    name: str
    score: float = Field(..., ge=0.0, le=1.0, description="Raw score for this category (0–1).")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight applied to this category.")
    weighted_score: float = Field(..., ge=0.0, le=1.0)
    matches: list[str] = Field(default_factory=list, description="Positive alignment points.")
    mismatches: list[str] = Field(default_factory=list, description="Gaps or mismatches.")
    notes: Optional[str] = None


class MatchResult(BaseModel):
    """Full matching result for one CV ↔ job pair."""

    job: JobPost
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Weighted overall score (0–100).")
    categories: list[MatchCategory]
    top_matches: list[str] = Field(default_factory=list, description="Key strengths for this role.")
    top_gaps: list[str] = Field(default_factory=list, description="Main areas where the CV falls short.")
    recommendation: str = ""
    apply_recommended: bool = False

    @property
    def category_map(self) -> dict[str, MatchCategory]:
        return {c.name: c for c in self.categories}
