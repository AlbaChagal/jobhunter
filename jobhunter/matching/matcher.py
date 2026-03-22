"""CVMatcher — LLM-powered CV-to-job scoring engine."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rich.progress import Progress, SpinnerColumn, BarColumn, MofNCompleteColumn, TextColumn, TimeElapsedColumn

from jobhunter.config import MatchConfig
from jobhunter.llm import LLMClient, create_llm_client
from jobhunter.matching.cv_parser import load_cv
from jobhunter.matching.prompts import SYSTEM_PROMPT, build_user_prompt
from jobhunter.models import JobPost, MatchCategory, MatchResult

# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a string (handles markdown fences)."""
    # Strip code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_match_result(
    raw: dict[str, Any],
    job: JobPost,
    config: MatchConfig,
) -> MatchResult:
    """Convert the parsed LLM JSON response into a MatchResult."""
    weights = config.effective_weights(has_salary=job.has_salary)

    categories_raw = raw.get("categories", {})
    categories: list[MatchCategory] = []

    for name, weight in weights.items():
        cat_data = categories_raw.get(name, {})
        raw_score = float(cat_data.get("score", 0.5))
        raw_score = max(0.0, min(1.0, raw_score))

        # Apply strict experience matching override
        if name == "experience" and config.strict_experience_match:
            mismatches = cat_data.get("mismatches", [])
            if any("more" in m.lower() or "exceeds" in m.lower() for m in mismatches):
                raw_score = 0.0

        weighted = raw_score * weight
        categories.append(
            MatchCategory(
                name=name,
                score=raw_score,
                weight=weight,
                weighted_score=weighted,
                matches=cat_data.get("matches", []),
                mismatches=cat_data.get("mismatches", []),
                notes=cat_data.get("notes"),
            )
        )

    overall = sum(c.weighted_score for c in categories) * 100.0
    overall = max(0.0, min(100.0, overall))
    apply_recommended = overall >= config.minimum_score_to_apply

    return MatchResult(
        job=job,
        overall_score=round(overall, 2),
        categories=categories,
        top_matches=raw.get("top_matches", []),
        top_gaps=raw.get("top_gaps", []),
        recommendation=raw.get("recommendation", ""),
        apply_recommended=apply_recommended,
    )


# ---------------------------------------------------------------------------
# CVMatcher
# ---------------------------------------------------------------------------


class CVMatcher:
    """
    Match a CV against one or more job postings using an LLM.

    Args:
        llm_api_key: API key for the chosen LLM provider.
        llm_provider: One of ``"claude"``, ``"openai"``, ``"gemini"``.
                      Defaults to ``"claude"``.
        model: Optional model override. Uses each provider's default if omitted.
        llm_client: Alternatively, pass a pre-built :class:`LLMClient` directly.
    """

    def __init__(
        self,
        llm_api_key: str | None = None,
        llm_provider: str = "claude",
        model: str | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        if llm_client is not None:
            self._llm = llm_client
        elif llm_api_key is not None:
            self._llm = create_llm_client(llm_provider, llm_api_key, model)
        else:
            raise ValueError("Either llm_api_key or llm_client must be provided.")

    def match(
        self,
        cv: str | Path,
        job: JobPost,
        config: MatchConfig | None = None,
    ) -> MatchResult:
        """
        Score a single CV against a single job post.

        Args:
            cv: CV text string, or path to a .pdf / text file.
            job: The job post to evaluate against.
            config: Matching configuration (weights, thresholds). Uses defaults if None.

        Returns:
            A :class:`MatchResult` with overall score, category breakdown, and advice.
        """
        cfg = config or MatchConfig()
        cv_text = load_cv(cv)
        user_prompt = build_user_prompt(cv_text, job)

        raw_response = self._llm.complete(system=SYSTEM_PROMPT, user=user_prompt)

        try:
            parsed = _extract_json(raw_response)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"LLM returned an unparseable response for job '{job.title}' "
                f"at '{job.company}': {exc}\n\nRaw response:\n{raw_response}"
            ) from exc

        return _build_match_result(parsed, job, cfg)

    def match_many(
        self,
        cv: str | Path,
        jobs: list[JobPost],
        config: MatchConfig | None = None,
        max_workers: int = 30,
    ) -> list[MatchResult]:
        """
        Score a CV against multiple job posts in parallel.

        Args:
            cv: CV text string, or path to a .pdf / text file.
            jobs: List of job posts to evaluate.
            config: Matching configuration. Uses defaults if None.
            max_workers: Max number of concurrent LLM requests. Defaults to 30.

        Returns:
            List of :class:`MatchResult` objects (one per job that succeeded).
        """
        cfg = config or MatchConfig()
        cv_text = load_cv(cv)

        def _score_one(job: JobPost) -> MatchResult:
            user_prompt = build_user_prompt(cv_text, job)
            raw_response = self._llm.complete(system=SYSTEM_PROMPT, user=user_prompt)
            parsed = _extract_json(raw_response)
            return _build_match_result(parsed, job, cfg)

        results: list[MatchResult] = []
        workers = min(max_workers, len(jobs))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Matching {len(jobs)} jobs…", total=len(jobs))

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_score_one, job): job for job in jobs}
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        print(f"[jobhunter] Warning: matching failed for '{job.title}' @ '{job.company}' — {exc}")
                    finally:
                        progress.advance(task)

        return results

    def rank(
        self,
        cv: str | Path,
        jobs: list[JobPost],
        config: MatchConfig | None = None,
        max_workers: int = 30,
    ) -> list[MatchResult]:
        """
        Score and rank jobs by match quality, best first.

        Args:
            cv: CV text string, or path to a .pdf / text file.
            jobs: List of job posts to evaluate.
            config: Matching configuration. Uses defaults if None.
            max_workers: Max number of concurrent LLM requests. Defaults to 30.

        Returns:
            List of :class:`MatchResult` sorted by ``overall_score`` descending.
        """
        results = self.match_many(cv, jobs, config, max_workers=max_workers)
        return sorted(results, key=lambda r: r.overall_score, reverse=True)
