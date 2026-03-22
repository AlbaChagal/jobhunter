"""HTML report generator for match results."""

from __future__ import annotations

import html
from pathlib import Path

from jobhunter.models import MatchResult


_SCORE_COLOR = {
    "green":  ("#d1fae5", "#065f46"),  # bg, text
    "yellow": ("#fef9c3", "#854d0e"),
    "red":    ("#fee2e2", "#991b1b"),
}


def _score_colors(score: float, recommended: bool) -> tuple[str, str]:
    if recommended:
        return _SCORE_COLOR["green"]
    if score >= 50:
        return _SCORE_COLOR["yellow"]
    return _SCORE_COLOR["red"]


def write_html_report(ranked: list[MatchResult], path: str) -> None:
    rows = []
    for r in ranked:
        job = r.job
        bg, fg = _score_colors(r.overall_score, r.apply_recommended)
        badge = "✓ Apply" if r.apply_recommended else "✗ Skip"

        desc = (job.description or "").replace("\n", " ").strip()
        desc_short = html.escape(desc[:300] + "…" if len(desc) > 300 else desc)
        desc_full  = html.escape(desc)

        apply_btn = (
            f'<a href="{html.escape(job.url)}" target="_blank" class="apply-btn">Apply →</a>'
            if job.url else "—"
        )

        breakdown_rows = "".join(
            f"<tr><td>{html.escape(c.name)}</td>"
            f"<td>{c.score * 100:.0f}%</td>"
            f"<td>{c.weight * 100:.0f}%</td>"
            f"<td>{'<br>'.join(html.escape(m) for m in c.matches) or '—'}</td>"
            f"<td>{'<br>'.join(html.escape(m) for m in c.mismatches) or '—'}</td></tr>"
            for c in r.categories
        )

        top_matches = "".join(f"<li>{html.escape(m)}</li>" for m in r.top_matches)
        top_gaps    = "".join(f"<li>{html.escape(g)}</li>" for g in r.top_gaps)

        rows.append(f"""
        <tr class="job-row" data-score="{r.overall_score:.0f}">
          <td>
            <span class="score-badge" style="background:{bg};color:{fg}">
              {r.overall_score:.0f}%<br><small>{badge}</small>
            </span>
          </td>
          <td>
            <strong>{html.escape(job.title or '—')}</strong><br>
            <span class="company">{html.escape(job.company or '—')}</span>
          </td>
          <td>{html.escape(job.location or '—')}</td>
          <td>{html.escape(job.salary_display)}</td>
          <td>{html.escape(job.work_type.value if job.work_type else '—')}</td>
          <td>
            <span class="desc-short">{desc_short}</span>
            {'<details><summary>More</summary><p class="desc-full">' + desc_full + '</p></details>' if len(desc) > 300 else ''}
          </td>
          <td>{apply_btn}</td>
          <td>
            <details>
              <summary>Breakdown</summary>
              <table class="breakdown-table">
                <thead><tr><th>Category</th><th>Score</th><th>Weight</th><th>Matches</th><th>Gaps</th></tr></thead>
                <tbody>{breakdown_rows}</tbody>
              </table>
              {'<div class="strengths"><strong>Strengths:</strong><ul>' + top_matches + '</ul></div>' if top_matches else ''}
              {'<div class="gaps"><strong>Gaps:</strong><ul>' + top_gaps + '</ul></div>' if top_gaps else ''}
              {'<p class="rec"><strong>Recommendation:</strong> ' + html.escape(r.recommendation) + '</p>' if r.recommendation else ''}
            </details>
          </td>
        </tr>""")

    recommended_count = sum(1 for r in ranked if r.apply_recommended)
    all_rows = "\n".join(rows)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Match Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #f8fafc; color: #1e293b; padding: 24px; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; margin-bottom: 20px; font-size: .9rem; }}

    .filters {{ display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }}
    .filters button {{ padding: 6px 14px; border: 1px solid #cbd5e1; border-radius: 6px;
                       background: #fff; cursor: pointer; font-size: .85rem; }}
    .filters button.active {{ background: #0f172a; color: #fff; border-color: #0f172a; }}

    table {{ width: 100%; border-collapse: collapse; background: #fff;
             border-radius: 10px; overflow: hidden;
             box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    thead th {{ background: #0f172a; color: #f1f5f9; padding: 10px 12px;
                text-align: left; font-size: .8rem; text-transform: uppercase;
                letter-spacing: .05em; white-space: nowrap; }}
    tbody tr {{ border-bottom: 1px solid #e2e8f0; transition: background .15s; }}
    tbody tr:hover {{ background: #f1f5f9; }}
    tbody tr.hidden {{ display: none; }}
    td {{ padding: 10px 12px; vertical-align: top; font-size: .88rem; }}

    .score-badge {{ display: inline-block; padding: 6px 10px; border-radius: 8px;
                    font-weight: 700; text-align: center; font-size: .95rem;
                    min-width: 64px; line-height: 1.3; }}
    .score-badge small {{ font-weight: 500; font-size: .7rem; display: block; }}
    .company {{ color: #64748b; font-size: .83rem; }}

    .apply-btn {{ display: inline-block; padding: 5px 12px; background: #2563eb;
                  color: #fff; border-radius: 6px; text-decoration: none;
                  font-size: .82rem; font-weight: 600; white-space: nowrap; }}
    .apply-btn:hover {{ background: #1d4ed8; }}

    details summary {{ cursor: pointer; color: #2563eb; font-size: .82rem;
                       user-select: none; list-style: none; }}
    details summary::-webkit-details-marker {{ display: none; }}
    details[open] summary {{ margin-bottom: 8px; }}

    .breakdown-table {{ width: 100%; font-size: .8rem; border-collapse: collapse;
                        margin-top: 6px; }}
    .breakdown-table th {{ background: #f1f5f9; padding: 4px 8px; text-align: left;
                           font-weight: 600; border-bottom: 1px solid #e2e8f0; }}
    .breakdown-table td {{ padding: 4px 8px; border-bottom: 1px solid #f1f5f9;
                           vertical-align: top; }}
    .strengths, .gaps {{ margin-top: 8px; font-size: .82rem; }}
    .strengths ul, .gaps ul {{ padding-left: 16px; }}
    .rec {{ margin-top: 8px; font-size: .82rem; color: #475569; }}
    .desc-full {{ margin-top: 6px; font-size: .82rem; color: #475569; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Job Match Report</h1>
  <p class="subtitle">
    {len(ranked)} jobs matched &nbsp;·&nbsp;
    <strong style="color:#065f46">{recommended_count} recommended to apply</strong>
  </p>

  <div class="filters">
    <button class="active" onclick="filterRows('all', this)">All ({len(ranked)})</button>
    <button onclick="filterRows('apply', this)">Recommended ({recommended_count})</button>
    <button onclick="filterRows('skip', this)">Skip ({len(ranked) - recommended_count})</button>
  </div>

  <table id="results-table">
    <thead>
      <tr>
        <th>Score</th>
        <th>Job</th>
        <th>Location</th>
        <th>Salary</th>
        <th>Type</th>
        <th>Description</th>
        <th>Apply</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      {all_rows}
    </tbody>
  </table>

  <script>
    function filterRows(filter, btn) {{
      document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#results-table tbody tr').forEach(row => {{
        const score = parseInt(row.dataset.score);
        const badge = row.querySelector('.score-badge small').textContent.trim();
        if (filter === 'all') row.classList.remove('hidden');
        else if (filter === 'apply') row.classList.toggle('hidden', !badge.startsWith('✓'));
        else if (filter === 'skip')  row.classList.toggle('hidden',  badge.startsWith('✓'));
      }});
    }}
  </script>
</body>
</html>"""

    Path(path).write_text(html_content, encoding="utf-8")
