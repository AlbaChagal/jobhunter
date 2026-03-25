"""
Example: search for jobs across LinkedIn and Indeed.

Set environment variables before running:
    export APIFY_API_KEY=your_key_here
    python examples/search_example.py
"""

import json
import os

from jobhunter import JobSearcher, SearchParams

apify_key = os.environ["APIFY_API_KEY"]

params = SearchParams(
    location="New York",
    job_title="Software Engineer",
    work_type=["remote", "hybrid"],
    salary_min=100_000,
    salary_period="annual",
    is_show_no_salary_posts=False,
    max_post_age_days=14,
    max_num_applicants=300,
    experience_level_years_min=2,
    experience_level_years_max=7,
    keywords=["Python", "backend"],
)

searcher = JobSearcher(apify_api_key=apify_key)
jobs = searcher.search(params, sources=["linkedin", "indeed"], max_results_per_source=25)

print(f"Found {len(jobs)} jobs after filtering.\n")
for job in jobs[:5]:
    print(f"  {job.title} @ {job.company}")
    print(f"    Location:    {job.location} ({job.work_type})")
    print(f"    Salary:      {job.salary_display}")
    print(f"    Applicants:  {job.num_applicants or 'unknown'}")
    print(f"    URL:         {job.url}")
    print()

# Save all results
with open("jobs.json", "w") as f:
    json.dump([j.model_dump(mode="json") for j in jobs], f, indent=2)
print("Saved to jobs.json")
