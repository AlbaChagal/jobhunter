"""jobhunter CLI — search, match, and find jobs from the terminal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from jobhunter.config import MatchConfig
from jobhunter.models import JobPost, SearchParams, SalaryPeriod, WorkType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_multi(valid_choices: list[str]):
    """Click callback: accept a comma-separated string and validate each token."""
    valid = {c.lower() for c in valid_choices}

    def callback(ctx, param, value):
        if not value:
            return ()
        items = tuple(v.strip().lower() for v in value.split(",") if v.strip())
        for item in items:
            if item not in valid:
                raise click.BadParameter(
                    f"'{item}' is not one of {sorted(valid_choices)}.",
                    ctx=ctx, param=param,
                )
        return items

    return callback


def _load_jobs(path: str) -> list[JobPost]:
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return [JobPost.model_validate(item) for item in data]
    raise ValueError(f"Expected a JSON array of job posts in {path}")


def _save_json(data: object, path: str | None) -> None:
    if hasattr(data, "model_dump"):
        serialised = data.model_dump(mode="json")
    elif isinstance(data, list):
        serialised = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    else:
        serialised = data

    text = json.dumps(serialised, indent=2, ensure_ascii=False)
    if path:
        Path(path).write_text(text, encoding="utf-8")
        click.echo(f"Saved to {path}")
    else:
        click.echo(text)


def _build_search_params(
    location: str,
    country: str,
    work_type: tuple[str, ...],
    salary_min: float | None,
    salary_max: float | None,
    salary_period: str,
    no_salary: bool,
    max_age: int | None,
    max_applicants: int | None,
    exp_min: int | None,
    exp_max: int | None,
    keywords: tuple[str, ...],
    job_title: str | None,
) -> SearchParams:
    return SearchParams(
        location=location,
        country=country.upper(),
        work_type=[WorkType(w) for w in work_type],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=SalaryPeriod(salary_period),
        is_show_no_salary_posts=no_salary,
        max_post_age_days=max_age,
        max_num_applicants=max_applicants,
        experience_level_years_min=exp_min,
        experience_level_years_max=exp_max,
        keywords=list(keywords),
        job_title=job_title,
    )


# ---------------------------------------------------------------------------
# Shared options (reusable click decorators)
# ---------------------------------------------------------------------------

_search_options = [
    click.option("--location", "-l", required=True, help="City or region to search in."),
    click.option("--country", "-c", default="US", show_default=True, help="2-letter country code (e.g. DE, GB, US)."),
    click.option(
        "--work-type", "-w",
        default="",
        help="Work arrangement(s), comma-separated: on-site,hybrid,remote. Omit for any.",
        callback=_validate_multi(["on-site", "hybrid", "remote"]),
        is_eager=False,
    ),
    click.option("--salary-min", type=float, default=None, help="Minimum salary."),
    click.option("--salary-max", type=float, default=None, help="Maximum salary."),
    click.option(
        "--salary-period",
        type=click.Choice(["hourly", "monthly", "annual"], case_sensitive=False),
        default="annual",
        show_default=True,
        help="Unit for salary-min / salary-max.",
    ),
    click.option(
        "--no-salary-posts/--hide-no-salary-posts",
        "no_salary",
        default=True,
        show_default=True,
        help="Include posts that don't list a salary.",
    ),
    click.option("--max-age", type=int, default=None, help="Max post age in days."),
    click.option("--max-applicants", type=int, default=None, help="Max number of applicants."),
    click.option("--exp-min", type=int, default=None, help="Min years of experience required."),
    click.option("--exp-max", type=int, default=None, help="Max years of experience required."),
    click.option("--keywords", "-k", multiple=True, help="Search keywords (repeatable)."),
    click.option("--job-title", "-t", default=None, help="Specific job title to search for."),
    click.option(
        "--source", "-s",
        default="linkedin,indeed,glassdoor",
        show_default=True,
        help="Job sources, comma-separated: linkedin,indeed,glassdoor.",
        callback=_validate_multi(["linkedin", "indeed", "glassdoor"]),
        is_eager=False,
    ),
    click.option("--apify-key", envvar="APIFY_API_KEY", required=True, help="Apify API key."),
    click.option("--max-results", type=int, default=50, show_default=True, help="Max results per source."),
]

_match_options = [
    click.option("--cv", required=True, help="Path to CV file (.pdf or .txt) or raw text."),
    click.option(
        "--provider", "-p",
        default="claude",
        show_default=True,
        type=click.Choice(["claude", "openai", "gemini"], case_sensitive=False),
        help="LLM provider.",
    ),
    click.option("--llm-key", envvar="LLM_API_KEY", required=True, help="API key for the LLM provider."),
    click.option("--model", default=None, help="Override the default model for the chosen provider."),
    click.option("--config", "config_path", default=None, help="Path to match config JSON file."),
    click.option("--min-score", type=float, default=None, help="Override minimum score to recommend applying."),
]

_output_option = [
    click.option("--output", "-o", default=None, help="Output file path (JSON). Prints to stdout if omitted."),
]


def _add_options(options):
    def decorator(f):
        for opt in reversed(options):
            f = opt(f)
        return f
    return decorator


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="jobhunter")
def cli() -> None:
    """jobhunter — search jobs and match them against your CV."""


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------

@cli.command("search")
@_add_options(_search_options)
@_add_options(_output_option)
def search_cmd(
    location, country, work_type, salary_min, salary_max, salary_period, no_salary,
    max_age, max_applicants, exp_min, exp_max, keywords, job_title,
    source, apify_key, max_results, output,
):
    """Search for jobs and save results to JSON."""
    from jobhunter.search import JobSearcher

    params = _build_search_params(
        location, country, work_type, salary_min, salary_max, salary_period, no_salary,
        max_age, max_applicants, exp_min, exp_max, keywords, job_title,
    )

    click.echo(f"Searching {', '.join(source)} for jobs in {location}…")
    searcher = JobSearcher(apify_api_key=apify_key)
    jobs = searcher.search(params, sources=list(source), max_results_per_source=max_results)
    click.echo(f"Found {len(jobs)} jobs after filtering.")

    _save_json(jobs, output)


# ---------------------------------------------------------------------------
# match command
# ---------------------------------------------------------------------------

@cli.command("match")
@click.option("--jobs", "jobs_path", required=True, help="Path to jobs JSON file (from `search`).")
@_add_options(_match_options)
@_add_options(_output_option)
def match_cmd(jobs_path, cv, provider, llm_key, model, config_path, min_score, output):
    """Match a CV against pre-fetched job postings and rank results."""
    from jobhunter.matching import CVMatcher

    jobs = _load_jobs(jobs_path)
    click.echo(f"Loaded {len(jobs)} jobs. Matching with {provider}…")

    cfg = _build_match_config(config_path, min_score)
    matcher = CVMatcher(llm_api_key=llm_key, llm_provider=provider, model=model)
    ranked = matcher.rank(cv=cv, jobs=jobs, config=cfg)

    click.echo(f"\nTop matches ({len(ranked)} total):\n")
    for i, result in enumerate(ranked[:10], 1):
        marker = "✓" if result.apply_recommended else "✗"
        click.echo(
            f"  {i:2}. [{marker}] {result.overall_score:5.1f}%  "
            f"{result.job.title} @ {result.job.company}  ({result.job.location})"
        )

    _save_json(ranked, output)


# ---------------------------------------------------------------------------
# find command (search + match in one shot)
# ---------------------------------------------------------------------------

@cli.command("find")
@_add_options(_search_options)
@_add_options(_match_options)
@_add_options(_output_option)
def find_cmd(
    # search options
    location, country, work_type, salary_min, salary_max, salary_period, no_salary,
    max_age, max_applicants, exp_min, exp_max, keywords, job_title,
    source, apify_key, max_results,
    # match options
    cv, provider, llm_key, model, config_path, min_score,
    # shared
    output,
):
    """Search for jobs and immediately rank them against your CV."""
    from jobhunter.matching import CVMatcher
    from jobhunter.search import JobSearcher

    params = _build_search_params(
        location, country, work_type, salary_min, salary_max, salary_period, no_salary,
        max_age, max_applicants, exp_min, exp_max, keywords, job_title,
    )

    click.echo(f"Searching {', '.join(source)} for jobs in {location}…")
    searcher = JobSearcher(apify_api_key=apify_key)
    jobs = searcher.search(params, sources=list(source), max_results_per_source=max_results)
    click.echo(f"Found {len(jobs)} jobs. Matching with {provider}…")

    if not jobs:
        click.echo("No jobs found — try broadening your search parameters.")
        sys.exit(0)

    cfg = _build_match_config(config_path, min_score)
    matcher = CVMatcher(llm_api_key=llm_key, llm_provider=provider, model=model)
    ranked = matcher.rank(cv=cv, jobs=jobs, config=cfg)

    click.echo(f"\nTop matches ({len(ranked)} total):\n")
    for i, result in enumerate(ranked[:10], 1):
        marker = "✓" if result.apply_recommended else "✗"
        click.echo(
            f"  {i:2}. [{marker}] {result.overall_score:5.1f}%  "
            f"{result.job.title} @ {result.job.company}  ({result.job.location})"
        )
        if result.top_matches:
            click.echo(f"       + {result.top_matches[0]}")
        if result.top_gaps:
            click.echo(f"       - {result.top_gaps[0]}")

    _save_json(ranked, output)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_match_config(config_path: str | None, min_score: float | None) -> MatchConfig:
    if config_path:
        cfg = MatchConfig.from_json(config_path)
    else:
        cfg = MatchConfig()

    if min_score is not None:
        cfg = cfg.model_copy(update={"minimum_score_to_apply": min_score})

    return cfg
