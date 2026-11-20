import os
import json
import math
import urllib.request
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "CharmanderTheGreat")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = "assets/stats"

ACCENT = "#F78166"
BG = "#0D1117"
BORDER = "#30363D"
TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED = "#8B949E"

LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#F1E05A",
    "TypeScript": "#3178C6",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "C++": "#F34B7D",
    "C": "#555555",
    "Java": "#B07219",
    "PHP": "#4F5D95",
    "Dart": "#00B4AB",
    "Shell": "#89E051",
}


def graphql_query(query: str, variables: dict) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-stats-generator",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_github_data() -> dict:
    now = datetime.now(timezone.utc)
    one_year_ago = (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        name
        location
        createdAt
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes {
            stargazerCount
            primaryLanguage {
              name
              color
            }
          }
        }
        pullRequests(first: 1) {
          totalCount
        }
        issues(first: 1) {
          totalCount
        }
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    res = graphql_query(query, {"login": USERNAME, "from": one_year_ago, "to": now_iso})
    return res["data"]["user"]


def compute_streaks(weeks: list) -> dict:
    days = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort(key=lambda x: x[0])

    longest = 0
    longest_start = ""
    longest_end = ""
    cur = 0
    cur_start = ""

    for date_str, count in days:
        if count > 0:
            if cur == 0:
                cur_start = date_str
            cur += 1
            if cur >= longest:
                longest = cur
                longest_start = cur_start
                longest_end = date_str
        else:
            cur = 0

    # Current streak (allowing today to be 0 if yesterday > 0)
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    active_streak = 0
    active_start = ""
    active_end = ""

    for date_str, count in reversed(days):
        if date_str > today_str:
            continue
        if count > 0:
            if active_streak == 0:
                active_end = date_str
            active_streak += 1
            active_start = date_str
        else:
            if date_str == today_str:
                continue
            break

    def fmt_date(d: str) -> str:
        if not d:
            return "-"
        dt = datetime.strptime(d, "%Y-%m-%d")
        return dt.strftime("%b %d").replace(" 0", " ")

    return {
        "current": active_streak,
        "current_range": f"{fmt_date(active_start)} - {fmt_date(active_end)}" if active_streak else "No active streak",
        "longest": longest,
        "longest_range": f"{fmt_date(longest_start)} - {fmt_date(longest_end)}" if longest else "-",
    }


def build_overview_svg(user: dict, total_contribs: int, monthly_points: list) -> str:
    location = user.get("location") or "Philippines"
    public_repos = user["repositories"]["totalCount"]

    # Build smooth polyline / area path
    chart_x0, chart_y0 = 420, 145
    chart_w, chart_h = 340, 85
    max_val = max(monthly_points) if monthly_points and max(monthly_points) > 0 else 1
    step_x = chart_w / max(len(monthly_points) - 1, 1)

    pts = []
    for i, val in enumerate(monthly_points):
        x = chart_x0 + i * step_x
        y = chart_y0 - (val / max_val) * chart_h
        pts.append((x, y))

    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = f"{line_d} L {pts[-1][0]:.1f},{chart_y0} L {pts[0][0]:.1f},{chart_y0} Z"

    return f"""<svg width="800" height="175" viewBox="0 0 800 175" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0.38"/>
      <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0.0"/>
    </linearGradient>
    <style>
      .title {{ font: 700 19px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
      .sub {{ font: 400 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
      .stat {{ font: 400 13.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="799" height="174" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="28" y="42" class="title">{USERNAME}</text>
  <text x="772" y="40" text-anchor="end" class="sub">Contributions (Last 12 Months)</text>

  <!-- Row 1 -->
  <circle cx="35" cy="72" r="4" fill="{ACCENT}"/>
  <text x="50" y="76" class="stat">{total_contribs:,} Total Contributions</text>

  <!-- Row 2 -->
  <rect x="31" y="96" width="8" height="8" rx="1.5" fill="{ACCENT}"/>
  <text x="50" y="104" class="stat">{public_repos} Public Repositories</text>

  <!-- Row 3 -->
  <path d="M35 123 C32.5 123 31 124.8 31 127 C31 130 35 134 35 134 C35 134 39 130 39 127 C39 124.8 37.5 123 35 123 Z" fill="{ACCENT}"/>
  <text x="50" y="132" class="stat">{location}</text>

  <!-- Area Chart -->
  <path d="{area_d}" fill="url(#areaGrad)"/>
  <path d="{line_d}" stroke="{ACCENT}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""


def build_languages_svg(repos: list) -> str:
    counts = {}
    for r in repos:
        lang = r.get("primaryLanguage")
        if lang and lang.get("name"):
            name = lang["name"]
            counts[name] = counts.get(name, 0) + 1

    sorted_langs = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:4]
    total = sum(c for _, c in sorted_langs) or 1

    cx, cy, r_outer, r_inner = 88, 118, 42, 26
    start_angle = -90.0
    paths = []
    legend_items = []

    for i, (name, count) in enumerate(sorted_langs):
        pct = round((count / total) * 100)
        sweep = (count / total) * 360.0
        if sweep >= 359.9:
            sweep = 359.9
        end_angle = start_angle + sweep
        color = LANG_COLORS.get(name, ACCENT)

        rad1 = math.radians(start_angle)
        rad2 = math.radians(end_angle)
        x1_o, y1_o = cx + r_outer * math.cos(rad1), cy + r_outer * math.sin(rad1)
        x2_o, y2_o = cx + r_outer * math.cos(rad2), cy + r_outer * math.sin(rad2)
        x1_i, y1_i = cx + r_inner * math.cos(rad2), cy + r_inner * math.sin(rad2)
        x2_i, y2_i = cx + r_inner * math.cos(rad1), cy + r_inner * math.sin(rad1)
        large_arc = 1 if sweep > 180 else 0

        d = (
            f"M {x1_o:.2f} {y1_o:.2f} "
            f"A {r_outer} {r_outer} 0 {large_arc} 1 {x2_o:.2f} {y2_o:.2f} "
            f"L {x1_i:.2f} {y1_i:.2f} "
            f"A {r_inner} {r_inner} 0 {large_arc} 0 {x2_i:.2f} {y2_i:.2f} Z"
        )
        paths.append(f'<path d="{d}" fill="{color}"/>')

        ly = 82 + i * 26
        legend_items.append(
            f'<circle cx="168" cy="{ly - 4}" r="4.5" fill="{color}"/>'
            f'<text x="182" y="{ly}" class="lang">{name}</text>'
            f'<text x="364" y="{ly}" text-anchor="end" class="pct">{pct}%</text>'
        )
        start_angle = end_angle

    return f"""<svg width="392" height="190" viewBox="0 0 392 190" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-title {{ font: 700 15.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
      .lang {{ font: 400 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
      .pct {{ font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="391" height="189" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="38" class="card-title">Top Languages (Repos)</text>
  {''.join(paths)}
  {''.join(legend_items)}
</svg>"""


def build_stats_svg(user: dict) -> str:
    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    cc = user["contributionsCollection"]
    total_commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    total_prs = user["pullRequests"]["totalCount"]
    total_issues = user["issues"]["totalCount"]

    rows = [
        ("Total Stars Earned", f"{total_stars:,}"),
        ("Total Commits (Last 12M)", f"{total_commits:,}"),
        ("Total PRs", f"{total_prs:,}"),
        ("Total Issues", f"{total_issues:,}"),
    ]

    row_svgs = []
    for i, (label, val) in enumerate(rows):
        y = 76 + i * 28
        row_svgs.append(
            f'<circle cx="29" cy="{y - 4}" r="3.5" stroke="{ACCENT}" stroke-width="1.8" fill="none"/>'
            f'<text x="44" y="{y}" class="label">{label}</text>'
            f'<text x="368" y="{y}" text-anchor="end" class="val">{val}</text>'
        )

    return f"""<svg width="392" height="190" viewBox="0 0 392 190" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-title {{ font: 700 15.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
      .label {{ font: 400 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
      .val {{ font: 700 13.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="391" height="189" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="38" class="card-title">Stats</text>
  {''.join(row_svgs)}
</svg>"""


def build_streak_svg(total_contribs: int, streaks: dict) -> str:
    return f"""<svg width="560" height="165" viewBox="0 0 560 165" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .num {{ font: 700 26px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_PRIMARY}; }}
      .lbl {{ font: 500 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
      .lbl-accent {{ font: 700 12.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {ACCENT}; }}
      .date {{ font: 400 10.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {TEXT_MUTED}; }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="559" height="164" rx="10" fill="{BG}" stroke="{BORDER}"/>

  <!-- Left: Total Contributions -->
  <text x="95" y="76" text-anchor="middle" class="num">{total_contribs:,}</text>
  <text x="95" y="102" text-anchor="middle" class="lbl">Total Contributions</text>
  <text x="95" y="120" text-anchor="middle" class="date">Last 12 Months</text>

  <line x1="190" y1="30" x2="190" y2="135" stroke="{BORDER}" stroke-width="1"/>

  <!-- Center: Current Streak -->
  <circle cx="280" cy="64" r="30" stroke="{ACCENT}" stroke-width="3.2" fill="none"/>
  <circle cx="280" cy="34" r="7" fill="{BG}"/>
  <path d="M280 27 C282.5 30 284 32 284 34.5 C284 36.8 282.2 38.5 280 38.5 C277.8 38.5 276 36.8 276 34.5 C276 33 276.8 31.5 278 30.2 C278 31.8 279 32.5 280 32.5 C279.5 30.8 279.5 29 280 27 Z" fill="{ACCENT}"/>
  <text x="280" y="72" text-anchor="middle" class="num">{streaks['current']}</text>
  <text x="280" y="114" text-anchor="middle" class="lbl-accent">Current Streak</text>
  <text x="280" y="132" text-anchor="middle" class="date">{streaks['current_range']}</text>

  <line x1="370" y1="30" x2="370" y2="135" stroke="{BORDER}" stroke-width="1"/>

  <!-- Right: Longest Streak -->
  <text x="465" y="76" text-anchor="middle" class="num">{streaks['longest']}</text>
  <text x="465" y="102" text-anchor="middle" class="lbl">Longest Streak</text>
  <text x="465" y="120" text-anchor="middle" class="date">{streaks['longest_range']}</text>
</svg>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    user = fetch_github_data()
    cal = user["contributionsCollection"]["contributionCalendar"]
    total_contribs = cal["totalContributions"]
    weeks = cal["weeks"]

    # Group into ~12 monthly buckets for the smooth area chart
    monthly = []
    chunk_size = max(len(weeks) // 12, 1)
    for i in range(0, len(weeks), chunk_size):
        chunk = weeks[i : i + chunk_size]
        monthly.append(sum(d["contributionCount"] for w in chunk for d in w["contributionDays"]))
    monthly = monthly[-12:]

    streaks = compute_streaks(weeks)

    with open(f"{OUT_DIR}/overview.svg", "w", encoding="utf-8") as f:
        f.write(build_overview_svg(user, total_contribs, monthly))

    with open(f"{OUT_DIR}/languages.svg", "w", encoding="utf-8") as f:
        f.write(build_languages_svg(user["repositories"]["nodes"]))

    with open(f"{OUT_DIR}/stats.svg", "w", encoding="utf-8") as f:
        f.write(build_stats_svg(user))

    with open(f"{OUT_DIR}/streak.svg", "w", encoding="utf-8") as f:
        f.write(build_streak_svg(total_contribs, streaks))

    print("Successfully generated all 4 custom SVG cards.")


if __name__ == "__main__":
    main()