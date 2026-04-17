import os
import requests
import json
from datetime import datetime, timezone
from collections import defaultdict

USERNAME = os.environ.get("GITHUB_USERNAME", "Amitabh-Phule")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json",
}

# ── GraphQL query: contributions, repos, lang breakdown, PRs, issues, stars ──
GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    createdAt
    followers { totalCount }
    following { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 25) {
        repository { nameWithOwner }
        contributions {
          totalCount
        }
      }
    }
    pullRequests(states: MERGED) { totalCount }
    issues { totalCount }
  }
}
"""

def run_graphql(query, variables):
    resp = requests.post(
        "https://api.github.com/graphql",
        headers=HEADERS,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]

def fetch_commit_hours():
    """Fetch recent commit timestamps via REST to build hourly chart."""
    repos_resp = requests.get(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=30&sort=pushed",
        headers=HEADERS, timeout=20
    )
    repos = repos_resp.json() if repos_resp.ok else []
    hour_counts = defaultdict(int)
    for repo in repos[:10]:
        commits_resp = requests.get(
            f"https://api.github.com/repos/{USERNAME}/{repo['name']}/commits?per_page=50&author={USERNAME}",
            headers=HEADERS, timeout=20
        )
        if not commits_resp.ok:
            continue
        for commit in commits_resp.json():
            try:
                date_str = commit["commit"]["author"]["date"]
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                ist_hour = (dt.hour + 5) % 24
                hour_counts[ist_hour] += 1
            except Exception:
                pass
    return hour_counts

def build_contrib_chart_data(weeks):
    """Last 12 months contribution totals grouped by month."""
    monthly = defaultdict(int)
    for week in weeks:
        for day in week["contributionDays"]:
            try:
                dt = datetime.fromisoformat(day["date"])
                key = dt.strftime("%b %Y")
                monthly[key] += day["contributionCount"]
            except Exception:
                pass
    sorted_months = sorted(monthly.keys(), key=lambda k: datetime.strptime(k, "%b %Y"))
    last12 = sorted_months[-12:]
    return last12, [monthly[m] for m in last12]

def top_languages_by_repo(repos):
    lang_count = defaultdict(int)
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            lang_count[edge["node"]["name"]] += 1
    total = sum(lang_count.values()) or 1
    sorted_langs = sorted(lang_count.items(), key=lambda x: -x[1])[:6]
    return [(name, round(count * 100 / total)) for name, count in sorted_langs]

def top_languages_by_commit(commit_by_repo):
    """Approximate lang by commit using repo primary language heuristic."""
    lang_commits = defaultdict(int)
    for entry in commit_by_repo:
        repo_name = entry["repository"]["nameWithOwner"].split("/")[1]
        count = entry["contributions"]["totalCount"]
        resp = requests.get(
            f"https://api.github.com/repos/{USERNAME}/{repo_name}/languages",
            headers=HEADERS, timeout=10
        )
        if resp.ok:
            langs = resp.json()
            total_bytes = sum(langs.values()) or 1
            for lang, size in langs.items():
                lang_commits[lang] += count * size / total_bytes
    total = sum(lang_commits.values()) or 1
    sorted_langs = sorted(lang_commits.items(), key=lambda x: -x[1])[:6]
    return [(name, round(val * 100 / total)) for name, val in sorted_langs]

LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "Java": "#b07219",
    "TypeScript": "#2b7489", "C++": "#f34b7d", "C": "#555555",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B", "Go": "#00ADD8", "Rust": "#dea584",
    "Ruby": "#701516", "Kotlin": "#A97BFF", "Swift": "#F05138",
    "Dart": "#00B4AB", "PHP": "#4F5D95", "C#": "#178600",
}

LANG_ICONS = {
    "Python": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg",
    "JavaScript": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/javascript/javascript-original.svg",
    "Java": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/java/java-original.svg",
    "TypeScript": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/typescript/typescript-original.svg",
    "C++": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg",
    "HTML": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/html5/html5-original.svg",
    "CSS": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/css3/css3-original.svg",
    "Go": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original.svg",
    "Rust": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/rust/rust-plain.svg",
    "Kotlin": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/kotlin/kotlin-original.svg",
    "C#": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/csharp/csharp-original.svg",
    "Dart": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/dart/dart-original.svg",
    "PHP": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/php/php-original.svg",
    "Swift": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/swift/swift-original.svg",
    "Ruby": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ruby/ruby-original.svg",
    "Shell": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/bash/bash-original.svg",
    "C": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/c/c-original.svg",
}

def lang_icon_img(name, size=16):
    url = LANG_ICONS.get(name)
    if url:
        return f'<img src="{url}" width="{size}" height="{size}" style="border-radius:3px;vertical-align:middle;"/>'
    color = LANG_COLORS.get(name, "#888")
    return f'<span style="display:inline-block;width:{size}px;height:{size}px;background:{color};border-radius:3px;"></span>'

def joined_ago(created_at_str):
    created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    diff = now - created
    years = diff.days // 365
    months = (diff.days % 365) // 30
    if years >= 1:
        return f"{years} year{'s' if years > 1 else ''} ago"
    return f"{months} month{'s' if months > 1 else ''} ago"

def generate_readme(data, hour_counts):
    user = data["user"]
    cc = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    total_contribs = cc["contributionCalendar"]["totalContributions"]
    total_commits = cc["totalCommitContributions"]
    total_prs = user["pullRequests"]["totalCount"]
    total_issues = user["issues"]["totalCount"]
    total_repos = user["repositories"]["totalCount"]
    contributed_to = cc["totalRepositoriesWithContributedCommits"]
    joined = joined_ago(user["createdAt"])
    updated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    weeks = cc["contributionCalendar"]["weeks"]
    month_labels, month_data = build_contrib_chart_data(weeks)

    repo_langs = top_languages_by_repo(repos)
    commit_langs = top_languages_by_commit(cc["commitContributionsByRepository"])

    hours_labels = list(range(24))
    hours_data = [hour_counts.get(h, 0) for h in hours_labels]

    def lang_rows(langs):
        rows = ""
        for name, pct in langs:
            icon = lang_icon_img(name)
            color = LANG_COLORS.get(name, "#888")
            rows += f"""
    <tr>
      <td style="padding:4px 8px;">{icon}&nbsp;<span style="color:#c9d1d9;font-size:12px;">{name}</span></td>
      <td style="padding:4px 8px;">
        <div style="background:#21262d;border-radius:4px;height:8px;width:100px;overflow:hidden;">
          <div style="background:{color};height:100%;width:{pct}%;border-radius:4px;"></div>
        </div>
      </td>
      <td style="padding:4px 8px;color:#8b949e;font-size:12px;text-align:right;">{pct}%</td>
    </tr>"""
        return rows

    repo_lang_colors = json.dumps([LANG_COLORS.get(n, "#888") for n, _ in repo_langs])
    repo_lang_data = json.dumps([p for _, p in repo_langs])
    repo_lang_labels = json.dumps([n for n, _ in repo_langs])

    commit_lang_colors = json.dumps([LANG_COLORS.get(n, "#888") for n, _ in commit_langs])
    commit_lang_data = json.dumps([p for _, p in commit_langs])
    commit_lang_labels = json.dumps([n for n, _ in commit_langs])

    readme = f"""<div align="center">

![Banner](WhatsApp%20Image%202026-04-17%20at%2010.39.43%20PM%20(1).jpeg)

</div>

---

<div align="center">

# Amitabh Phule

### 🤖 AI/ML Engineer · Full-Stack Developer · Systems Thinker

*Building intelligent systems at the intersection of machine learning, scalable architecture, and human-centred design.*

<br/>

<img src="game.gif" alt="Interactive Banner" width="480"/>

</div>

---

## 🛠️ Tech Stack

### 💻 Languages

<table border="0" cellspacing="0" cellpadding="8"><tr>
<td align="center"><img src="https://skillicons.dev/icons?i=python" width="55" height="55"/><br/>Python</td>
<td align="center"><img src="https://skillicons.dev/icons?i=cpp" width="55" height="55"/><br/>C++</td>
<td align="center"><img src="https://skillicons.dev/icons?i=java" width="55" height="55"/><br/>Java</td>
<td align="center"><img src="https://skillicons.dev/icons?i=js" width="55" height="55"/><br/>JavaScript</td>
<td align="center"><img src="https://skillicons.dev/icons?i=html" width="55" height="55"/><br/>HTML5</td>
<td align="center"><img src="https://skillicons.dev/icons?i=css" width="55" height="55"/><br/>CSS3</td>
</tr></table>

### 🤖 AI / ML

<table border="0" cellspacing="0" cellpadding="8"><tr>
<td align="center"><img src="https://skillicons.dev/icons?i=tensorflow" width="55" height="55"/><br/>TensorFlow</td>
<td align="center"><img src="https://skillicons.dev/icons?i=opencv" width="55" height="55"/><br/>OpenCV</td>
<td align="center"><img src="https://skillicons.dev/icons?i=sklearn" width="55" height="55"/><br/>Scikit-Learn</td>
<td align="center"><img src="https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=Jupyter&logoColor=white" height="40"/><br/>Jupyter</td>
<td align="center"><img src="https://img.shields.io/badge/RAG-6A0DAD?style=for-the-badge&logo=openai&logoColor=white" height="40"/><br/>RAG</td>
</tr></table>

### 🌐 Web & DevOps Tools

<table border="0" cellspacing="0" cellpadding="8"><tr>
<td align="center"><img src="https://skillicons.dev/icons?i=vscode" width="55" height="55"/><br/>VS Code</td>
<td align="center"><img src="https://skillicons.dev/icons?i=git" width="55" height="55"/><br/>Git</td>
<td align="center"><img src="https://skillicons.dev/icons?i=github" width="55" height="55"/><br/>GitHub</td>
<td align="center"><img src="https://skillicons.dev/icons?i=docker" width="55" height="55"/><br/>Docker</td>
<td align="center"><img src="https://skillicons.dev/icons?i=kubernetes" width="55" height="55"/><br/>Kubernetes</td>
</tr></table>

### 🎨 Design

<table border="0" cellspacing="0" cellpadding="8"><tr>
<td align="center"><img src="https://skillicons.dev/icons?i=figma" width="55" height="55"/><br/>Figma</td>
<td align="center"><img src="https://img.shields.io/badge/Canva-00C4CC?style=for-the-badge&logo=Canva&logoColor=white" height="40"/><br/>Canva</td>
</tr></table>

> *Aesthetic interest in tribal geometric design systems — structured symmetry meets cultural depth.*

### ⚙️ Core Concepts

<table border="0" cellspacing="0" cellpadding="8"><tr>
<td align="center"><img src="https://img.shields.io/badge/SaaS%20Architecture-0A66C2?style=for-the-badge&logo=amazonaws&logoColor=white" height="40"/><br/>SaaS Architecture</td>
<td align="center"><img src="https://img.shields.io/badge/CI%2FCD%20Pipelines-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" height="40"/><br/>CI/CD Pipelines</td>
<td align="center"><img src="https://img.shields.io/badge/System%20Design-6DB33F?style=for-the-badge&logo=apachekafka&logoColor=white" height="40"/><br/>System Design</td>
</tr></table>

---

## 📊 GitHub Dashboard

> 🔄 **Auto-updated daily** via GitHub Actions &nbsp;|&nbsp; Last updated: `{updated}`

<!--DASHBOARD_START-->
<table width="100%" border="0" cellspacing="0" cellpadding="0">
<tr>
<td width="30%" valign="middle" style="padding:16px;">

<b>Amitabh-Phule (Amitabh)</b><br/><br/>

🔵 &nbsp;<b>{total_contribs}</b> Contributions in {datetime.now().year}<br/><br/>
📋 &nbsp;<b>{total_repos}</b> Public Repos<br/><br/>
🕐 &nbsp;Joined GitHub <b>{joined}</b><br/><br/>
⭐ &nbsp;<b>{total_stars}</b> Total Stars<br/><br/>
🎴 &nbsp;@Amitabh-Phule

</td>
<td width="70%" valign="top" style="padding:16px;">

[![Activity Graph](https://github-readme-activity-graph.vercel.app/graph?username=Amitabh-Phule&theme=react-dark&hide_border=true&area=true&custom_title=Contributions+in+the+last+year&color=58a6ff&line=58a6ff&point=58a6ff)](https://github.com/Amitabh-Phule)

</td>
</tr>
</table>

<table width="100%" border="0" cellspacing="0" cellpadding="0">
<tr>
<td width="50%" valign="top" style="padding:8px;">

| Metric | Count |
|--------|-------|
| ⭐ Total Stars | **{total_stars}** |
| 💻 Total Commits | **{total_commits}** |
| 🔀 Total PRs | **{total_prs}** |
| 🐛 Total Issues | **{total_issues}** |
| 📦 Contributed to | **{contributed_to} repos** |

</td>
<td width="50%" valign="top" style="padding:8px;">

[![Commits UTC](https://github-profile-summary-cards.vercel.app/api/cards/productive-time?username=Amitabh-Phule&theme=react_dark&utcOffset=5.5)](https://github.com/Amitabh-Phule)

</td>
</tr>
</table>

<table width="100%" border="0" cellspacing="0" cellpadding="0">
<tr>
<td width="50%" valign="top" style="padding:8px;">

**Top Languages by Repo**

<table border="0" cellspacing="0" cellpadding="0" width="100%">
{lang_rows(repo_langs)}
</table>

</td>
<td width="50%" valign="top" style="padding:8px;">

**Top Languages by Commit**

<table border="0" cellspacing="0" cellpadding="0" width="100%">
{lang_rows(commit_langs)}
</table>

</td>
</tr>
</table>
<!--DASHBOARD_END-->

---

<div align="center">

*Crafted with purpose · Powered by curiosity · Driven by impact*

![Profile Views](https://komarev.com/ghpvc/?username=Amitabh-Phule&color=6A0DAD&style=for-the-badge&label=PROFILE+VIEWS)

</div>
"""
    return readme

def main():
    print(f"Fetching data for {USERNAME}...")
    data = run_graphql(GRAPHQL_QUERY, {"login": USERNAME})
    print(f"Fetching commit hour data...")
    hour_counts = fetch_commit_hours()
    print(f"Generating README...")
    readme = generate_readme(data, hour_counts)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)
    print("README.md written successfully.")

if __name__ == "__main__":
    main()
