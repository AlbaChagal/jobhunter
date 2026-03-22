"""MatchConfig — configurable weights and thresholds for CV matching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MatchWeights(BaseModel):
    """Weights for each CV-matching category. Must sum to 1.0."""

    tech_stack: float = Field(0.35, ge=0.0, le=1.0)
    experience: float = Field(0.25, ge=0.0, le=1.0)
    location: float = Field(0.10, ge=0.0, le=1.0)
    education: float = Field(0.10, ge=0.0, le=1.0)
    soft_skills: float = Field(0.10, ge=0.0, le=1.0)
    work_type: float = Field(0.05, ge=0.0, le=1.0)
    salary: float = Field(0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "MatchWeights":
        total = (
            self.tech_stack
            + self.experience
            + self.location
            + self.education
            + self.soft_skills
            + self.work_type
            + self.salary
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"MatchWeights must sum to 1.0, but they sum to {total:.4f}. "
                "Adjust your weights so they add up to exactly 1.0."
            )
        return self

    @property
    def category_names(self) -> list[str]:
        return ["tech_stack", "experience", "location", "education", "soft_skills", "work_type", "salary"]

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in self.category_names}


class MatchConfig(BaseModel):
    """Full configuration for the CV matching algorithm."""

    weights: MatchWeights = Field(default_factory=MatchWeights)
    minimum_score_to_apply: float = Field(
        60.0,
        ge=0.0,
        le=100.0,
        description="Overall score threshold (0–100) above which apply_recommended=True.",
    )
    strict_experience_match: bool = Field(
        False,
        description=(
            "If True, a job requiring more experience than the candidate has scores 0.0 "
            "for the experience category rather than a partial credit."
        ),
    )
    experience_adjacent_years: int = Field(
        1,
        ge=0,
        description=(
            "Number of years outside the required range that still receive partial credit. "
            "E.g. a 5-year requirement with adjacent_years=1 gives partial credit to 4 or 6 years."
        ),
    )
    include_no_salary_in_scoring: bool = Field(
        False,
        description=(
            "If True, jobs without a listed salary still contribute to the salary category score "
            "(treated as neutral). If False, the salary category is skipped and its weight "
            "redistributed proportionally."
        ),
    )

    @classmethod
    def from_json(cls, path: str | Path) -> "MatchConfig":
        """Load a MatchConfig from a JSON file."""
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchConfig":
        """Build a MatchConfig from a plain dictionary."""
        if "weights" in data and isinstance(data["weights"], dict):
            data = {**data, "weights": MatchWeights(**data["weights"])}
        return cls(**data)

    def effective_weights(self, has_salary: bool) -> dict[str, float]:
        """
        Return per-category weights as a dict, redistributing the salary weight if the job
        has no salary and include_no_salary_in_scoring is False.
        """
        w = self.weights.as_dict()
        if not has_salary and not self.include_no_salary_in_scoring:
            salary_weight = w.pop("salary")
            other_total = sum(w.values())
            if other_total > 0:
                w = {k: v + salary_weight * (v / other_total) for k, v in w.items()}
            w["salary"] = 0.0
        return w
