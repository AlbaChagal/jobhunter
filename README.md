# jobhunter

An open-source Python library and CLI for searching jobs across LinkedIn, Indeed, and Glassdoor — and matching them against your CV using LLMs (Claude, GPT-4o, Gemini).

## Features

- **Multi-source job search** via [Apify](https://apify.com): LinkedIn, Indeed, Glassdoor
- **Smart filtering**: work type, salary range, post age, applicant count, experience level
- **CV matching**: LLM-powered scoring across tech stack, experience, location, education, soft skills, and more
- **Configurable weights**: tune the matching formula via a JSON config file
- **Multiple LLM providers**: Claude (Anthropic), GPT-4o (OpenAI), Gemini (Google)
- **CV formats**: plain text string or PDF
- **Python API + CLI**: use as a library or from the terminal

## Installation

```bash
pip install jobhunter
```

## Quick Start

### As a Python library

```python
from jobhunter import JobSearcher, CVMatcher, SearchParams, MatchConfig

# 1. Search for jobs
searcher = JobSearcher(apify_api_key="YOUR_APIFY_KEY")

params = SearchParams(
    location="New York",
    work_type=["remote", "hybrid"],
    salary_min=100_000,
    salary_period="annual",
    is_show_no_salary_posts=False,
    max_post_age_days=7,
    max_num_applicants=200,
    experience_level_years_min=3,
    experience_level_years_max=8,
    keywords=["Python", "backend"],
)

jobs = searcher.search(params, sources=["linkedin", "indeed"])
print(f"Found {len(jobs)} jobs")

# 2. Match your CV
matcher = CVMatcher(llm_api_key="YOUR_ANTHROPIC_KEY", llm_provider="claude")

ranked = matcher.rank(cv="path/to/cv.pdf", jobs=jobs)

for result in ranked[:5]:
    print(f"{result.job.title} @ {result.job.company}  →  {result.overall_score:.1f}%")
    if result.apply_recommended:
        print(f"  ✓ APPLY  |  {result.top_matches[0]}")
    else:
        print(f"  ✗ Skip   |  Gap: {result.top_gaps[0]}")
```

### Custom matching weights

```python
from jobhunter import MatchConfig

# Load from JSON file
config = MatchConfig.from_json("my_config.json")

# Or build in code
config = MatchConfig.from_dict({
    "weights": {
        "tech_stack": 0.40,
        "experience": 0.30,
        "location": 0.10,
        "education": 0.05,
        "soft_skills": 0.10,
        "work_type": 0.03,
        "salary": 0.02,
    },
    "minimum_score_to_apply": 70.0,
    "strict_experience_match": False,
})

ranked = matcher.rank(cv="cv.pdf", jobs=jobs, config=config)
```

### Match config JSON format

```json
{
  "weights": {
    "tech_stack": 0.35,
    "experience": 0.25,
    "location": 0.10,
    "education": 0.10,
    "soft_skills": 0.10,
    "work_type": 0.05,
    "salary": 0.05
  },
  "minimum_score_to_apply": 60.0,
  "strict_experience_match": false,
  "experience_adjacent_years": 1,
  "include_no_salary_in_scoring": false
}
```

## CLI Usage

```bash
# Search and save to JSON
jobhunter search \
  --location "New York" \
  --work-type remote,hybrid \
  --salary-min 100000 \
  --max-age 7 \
  --max-applicants 200 \
  --exp-min 3 --exp-max 8 \
  --source linkedin,indeed \
  --apify-key $APIFY_API_KEY \
  --output jobs.json

# Match CV against saved jobs
jobhunter match \
  --cv cv.pdf \
  --jobs jobs.json \
  --provider claude \
  --llm-key $ANTHROPIC_API_KEY \
  --config match_config.json \
  --min-score 65 \
  --output ranked.json

# Search + match in one command
jobhunter find \
  --cv cv.pdf \
  --location "New York" \
  --work-type remote,hybrid \
  --salary-min 100000 \
  --max-age 7 \
  --apify-key $APIFY_API_KEY \
  --provider claude \
  --llm-key $ANTHROPIC_API_KEY \
  --output ranked.json
```

## API Keys

Copy `.env.example` to `.env` and fill in your keys:

| Key | Where to get it |
|-----|----------------|
| `APIFY_API_KEY` | [console.apify.com](https://console.apify.com/account/integrations) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) |
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |

## Supported Sources

| Source | Apify Actor |
|--------|-------------|
| LinkedIn | `bebity/linkedin-jobs-scraper` |
| Indeed | `misceres/indeed-scraper` |
| Glassdoor | `bebity/glassdoor-jobs-scraper` |

## License

Apache
