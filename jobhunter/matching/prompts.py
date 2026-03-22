"""LLM prompt templates for CV-to-job matching."""

from __future__ import annotations

from jobhunter.models import JobPost

SYSTEM_PROMPT = """\
You are an expert career advisor and talent matching specialist. Your job is to objectively \
evaluate how well a candidate's CV aligns with a specific job posting.

You will be given a candidate's CV and a job posting. Evaluate the match across EXACTLY these \
seven categories:

1. tech_stack    — Technical skills, tools, frameworks, and programming languages alignment.
2. experience    — Years of experience, seniority level, and type of work experience match.
3. location      — Geographic or remote-work compatibility between candidate and role.
4. education     — Educational background, degrees, certifications, and formal training relevance.
5. soft_skills   — Communication, leadership, teamwork, problem-solving indicators.
6. work_type     — Remote / hybrid / on-site preference alignment.
7. salary        — Salary expectation vs. listed compensation (score 0.5 if no data available).

For each category provide:
- score: float between 0.0 and 1.0 (0 = no match, 1 = perfect match)
- matches: list of 1–5 specific, concrete points where the CV aligns with the job
- mismatches: list of 1–5 specific gaps or concerns
- notes: one sentence summarising the category assessment

Also provide:
- top_matches: list of 3 strongest overall alignment points (across all categories)
- top_gaps: list of 3 most significant gaps the candidate should address
- recommendation: 2–3 sentences of career advice for this specific application
- apply_recommended: true if the candidate should apply, false if not

IMPORTANT: Respond with ONLY valid JSON. No markdown fences, no commentary outside the JSON.\
"""


def build_user_prompt(cv_text: str, job: JobPost) -> str:
    """Build the user-turn prompt for a CV ↔ job match evaluation."""
    salary_display = job.salary_display if job.has_salary else "Not listed"

    exp_display = "Not specified"
    if job.experience_years_min is not None or job.experience_years_max is not None:
        lo = job.experience_years_min
        hi = job.experience_years_max
        if lo and hi:
            exp_display = f"{lo}–{hi} years"
        elif lo:
            exp_display = f"{lo}+ years"
        elif hi:
            exp_display = f"Up to {hi} years"

    lines = [
        "## Candidate CV",
        "",
        cv_text.strip(),
        "",
        "## Job Posting",
        "",
        f"Title:               {job.title}",
        f"Company:             {job.company}",
        f"Location:            {job.location}",
        f"Work Type:           {job.work_type.value if job.work_type else 'Not specified'}",
        f"Experience Required: {exp_display}",
        f"Salary:              {salary_display}",
        f"Source:              {job.source.value}",
        "",
        "### Description",
        "",
        job.description.strip(),
    ]

    if job.requirements:
        lines += ["", "### Requirements", ""]
        lines += [f"- {r}" for r in job.requirements]

    if job.tech_stack:
        lines += ["", "### Tech Stack", ""]
        lines += [f"- {t}" for t in job.tech_stack]

    lines += [
        "",
        "## Your Task",
        "",
        "Return a JSON object with this exact structure:",
        "",
        '{',
        '  "categories": {',
        '    "tech_stack":  {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "experience":  {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "location":    {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "education":   {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "soft_skills": {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "work_type":   {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "salary":      {"score": 0.0, "matches": [], "mismatches": [], "notes": ""}',
        '  },',
        '  "top_matches": ["...", "...", "..."],',
        '  "top_gaps": ["...", "...", "..."],',
        '  "recommendation": "...",',
        '  "apply_recommended": true',
        '}',
    ]

    return "\n".join(lines)
