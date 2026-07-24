#!/usr/bin/env python3
"""Generate weekly/index.html linking to all weekly report HTML files."""

from __future__ import annotations

import html as html_mod
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_ROOT = REPO_ROOT / "weekly"

REPORT_TYPES = {
    "AI-trends.html": {"title": "AI 行业动态", "icon": "🤖", "order": 1},
    "Git-news.html": {"title": "Git 技术动态", "icon": "🔀", "order": 2},
}


def scan_weeks() -> list[dict]:
    """Scan all week directories and collect available reports."""
    weeks = []
    for week_dir in sorted(WEEKLY_ROOT.iterdir(), reverse=True):
        if not week_dir.is_dir() or week_dir.name.startswith("."):
            continue
        
        week_name = week_dir.name
        try:
            datetime.strptime(week_name, "%Y-%m-%d")
        except ValueError:
            continue
        
        reports = []
        for filename, meta in sorted(REPORT_TYPES.items(), key=lambda x: x[1]["order"]):
            html_path = week_dir / filename
            if html_path.exists():
                reports.append({
                    "filename": filename,
                    "title": meta["title"],
                    "icon": meta["icon"],
                    "url": f"{week_name}/{filename}",
                    "size_kb": html_path.stat().st_size / 1024,
                })
        
        if reports:
            weeks.append({
                "date": week_name,
                "reports": reports,
            })
    
    return weeks


def render_index(weeks: list[dict]) -> str:
    """Render the index HTML page."""
    weeks_html_parts = []
    
    for week in weeks:
        report_cards = []
        for report in week["reports"]:
            report_cards.append(
                f'<a href="{html_mod.escape(report["url"])}" class="report-card">\n'
                f'  <span class="report-icon">{report["icon"]}</span>\n'
                f'  <span class="report-title">{html_mod.escape(report["title"])}</span>\n'
                f'  <span class="report-size">{report["size_kb"]:.0f} KB</span>\n'
                f'</a>'
            )
        
        reports_html = "\n".join(report_cards)
        weeks_html_parts.append(
            f'<div class="week-card">\n'
            f'  <div class="week-date">{html_mod.escape(week["date"])}</div>\n'
            f'  <div class="week-reports">\n'
            f'{reports_html}\n'
            f'  </div>\n'
            f'</div>'
        )
    
    weeks_html = "\n".join(weeks_html_parts)
    total_weeks = len(weeks)
    total_reports = sum(len(w["reports"]) for w in weeks)
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>技术周报索引</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 20px;
  color: #333;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}}

.container {{
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}}

h1 {{
  margin: 0 0 8px 0;
  font-size: 32px;
  color: #1a1a1a;
}}

.subtitle {{
  color: #666;
  font-size: 16px;
  margin-bottom: 32px;
}}

.stats {{
  display: flex;
  gap: 24px;
  margin-bottom: 32px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
}}

.stat-item {{
  display: flex;
  flex-direction: column;
}}

.stat-value {{
  font-size: 28px;
  font-weight: 700;
  color: #667eea;
}}

.stat-label {{
  font-size: 13px;
  color: #888;
  margin-top: 4px;
}}

.week-card {{
  margin-bottom: 24px;
  padding: 24px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  transition: all 0.2s;
}}

.week-card:hover {{
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}}

.week-date {{
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 2px solid #f0f0f0;
}}

.week-reports {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}}

.report-card {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  text-decoration: none;
  color: #333;
  transition: all 0.15s;
}}

.report-card:hover {{
  background: #667eea;
  color: white;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
}}

.report-icon {{
  font-size: 24px;
}}

.report-title {{
  flex: 1;
  font-weight: 500;
}}

.report-size {{
  font-size: 12px;
  opacity: 0.7;
}}

.empty-state {{
  text-align: center;
  padding: 60px 20px;
  color: #888;
}}

.empty-state-icon {{
  font-size: 48px;
  margin-bottom: 16px;
}}

@media (max-width: 600px) {{
  .container {{
    padding: 24px;
  }}
  
  h1 {{
    font-size: 24px;
  }}
  
  .stats {{
    flex-direction: column;
    gap: 16px;
  }}
  
  .week-reports {{
    grid-template-columns: 1fr;
  }}
}}
</style>
</head>
<body>
<div class="container">
  <h1>技术周报索引</h1>
  <div class="subtitle">Weekly Tech Trends Report</div>
  
  <div class="stats">
    <div class="stat-item">
      <div class="stat-value">{total_weeks}</div>
      <div class="stat-label">周报期数</div>
    </div>
    <div class="stat-item">
      <div class="stat-value">{total_reports}</div>
      <div class="stat-label">报告总数</div>
    </div>
  </div>
  
  {weeks_html if weeks_html else '<div class="empty-state"><div class="empty-state-icon">📭</div><div>暂无周报</div></div>'}
</div>
</body>
</html>
"""


def render_week_index(week: dict) -> str:
    """Render a per-week index HTML page."""
    report_cards = []
    for report in week["reports"]:
        report_cards.append(
            f'<a href="{html_mod.escape(report["filename"])}" class="report-card">\n'
            f'  <span class="report-icon">{report["icon"]}</span>\n'
            f'  <div class="report-info">\n'
            f'    <div class="report-title">{html_mod.escape(report["title"])}</div>\n'
            f'    <div class="report-size">{report["size_kb"]:.0f} KB</div>\n'
            f'  </div>\n'
            f'</a>'
        )
    
    reports_html = "\n".join(report_cards)
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_mod.escape(week["date"])} 技术周报</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  max-width: 700px;
  margin: 0 auto;
  padding: 40px 20px;
  color: #333;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}}

.container {{
  background: white;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}}

.back-link {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
  margin-bottom: 24px;
  transition: all 0.15s;
}}

.back-link:hover {{
  color: #764ba2;
  gap: 10px;
}}

h1 {{
  margin: 0 0 8px 0;
  font-size: 36px;
  color: #1a1a1a;
}}

.subtitle {{
  color: #666;
  font-size: 16px;
  margin-bottom: 32px;
}}

.report-list {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

.report-card {{
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px;
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  text-decoration: none;
  color: #333;
  transition: all 0.2s;
}}

.report-card:hover {{
  background: #667eea;
  color: white;
  border-color: #667eea;
  transform: translateX(4px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
}}

.report-icon {{
  font-size: 36px;
  flex-shrink: 0;
}}

.report-info {{
  flex: 1;
}}

.report-title {{
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}}

.report-size {{
  font-size: 13px;
  opacity: 0.6;
}}

@media (max-width: 600px) {{
  .container {{
    padding: 24px;
  }}
  
  h1 {{
    font-size: 28px;
  }}
  
  .report-card {{
    padding: 18px;
    gap: 14px;
  }}
  
  .report-icon {{
    font-size: 28px;
  }}
  
  .report-title {{
    font-size: 16px;
  }}
}}
</style>
</head>
<body>
<div class="container">
  <a href="../index.html" class="back-link">← 所有周报</a>
  <h1>{html_mod.escape(week["date"])}</h1>
  <div class="subtitle">技术周报 · {len(week["reports"])} 篇报告</div>
  
  <div class="report-list">
{reports_html}
  </div>
</div>
</body>
</html>
"""


def main() -> int:
    weeks = scan_weeks()
    index_html = render_index(weeks)
    
    index_path = WEEKLY_ROOT / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    print(f"WROTE: {index_path}")
    
    total_reports = sum(len(w["reports"]) for w in weeks)
    print(f"  {len(weeks)} weeks, {total_reports} reports")
    
    for week in weeks:
        week_html = render_week_index(week)
        week_path = WEEKLY_ROOT / week["date"] / "index.html"
        week_path.write_text(week_html, encoding="utf-8")
        print(f"WROTE: {week_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
