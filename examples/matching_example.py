"""
Example: match a CV against job posts and rank results.

Prerequisites:
    1. Run search_example.py first to generate jobs.json
    2. Place your CV at cv.pdf (or update the path below)

Set environment variables before running:
    export ANTHROPIC_API_KEY=your_key_here
    python examples/matching_example.py

Alternatively, use OpenAI or Gemini:
    export OPENAI_API_KEY=your_key_here
    # then set provider="openai" below

    export GOOGLE_API_KEY=your_key_here
    # then set provider="gemini" below
"""

import json
import os
from pathlib import Path

from jobhunter import CVMatcher, JobPost, MatchConfig

# --- Configuration ---
LLM_PROVIDER = "claude"   # or "openai" or "gemini"
LLM_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ["LLM_API_KEY"]
CV_PATH = "cv.pdf"        # supports .pdf or plain text string
JOBS_FILE = "jobs.json"

# Optional: custom weights (comment out to use defaults)
config = MatchConfig.from_dict({
    "weights": {
        "tech_stack": 0.35,
        "experience": 0.25,
        "location": 0.10,
        "education": 0.10,
        "soft_skills": 0.10,
        "work_type": 0.05,
        "salary": 0.05,
    },
    "minimum_score_to_apply": 65.0,
    "strict_experience_match": False,
})

# --- Load jobs ---
jobs_data = json.loads(Path(JOBS_FILE).read_text())
jobs = [JobPost.model_validate(item) for item in jobs_data]
print(f"Loaded {len(jobs)} jobs from {JOBS_FILE}\n")

# --- Run matching ---
matcher = CVMatcher(llm_api_key=LLM_API_KEY, llm_provider=LLM_PROVIDER)
ranked = matcher.rank(cv=CV_PATH, jobs=jobs, config=config)

# --- Display results ---
print(f"{'Rank':<5} {'Score':>6}  {'Apply':<6}  {'Title':<40}  {'Company':<25}  Location")
print("-" * 120)
for i, result in enumerate(ranked, 1):
    marker = "YES" if result.apply_recommended else "no"
    print(
        f"{i:<5} {result.overall_score:>5.1f}%  {marker:<6}  "
        f"{result.job.title[:39]:<40}  {result.job.company[:24]:<25}  {result.job.location}"
    )

print("\n--- Top pick details ---\n")
best = ranked[0]
print(f"Title:       {best.job.title}")
print(f"Company:     {best.job.company}")
print(f"Score:       {best.overall_score:.1f}%")
print(f"Salary:      {best.job.salary_display}")
print(f"URL:         {best.job.url}\n")

print("Category breakdown:")
for cat in sorted(best.categories, key=lambda c: c.weighted_score, reverse=True):
    bar = "█" * int(cat.score * 10) + "░" * (10 - int(cat.score * 10))
    print(f"  {cat.name:<12} {bar}  {cat.score * 100:4.0f}%  (weight {cat.weight:.0%})")

print(f"\nTop strengths:")
for m in best.top_matches:
    print(f"  + {m}")

print(f"\nTop gaps:")
for g in best.top_gaps:
    print(f"  - {g}")

print(f"\nRecommendation:\n  {best.recommendation}")

# --- Save ranked results ---
output = [r.model_dump(mode="json") for r in ranked]
Path("ranked.json").write_text(json.dumps(output, indent=2))
print("\nFull results saved to ranked.json")
