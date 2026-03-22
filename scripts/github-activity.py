#!/usr/bin/env python3
"""
GitHub Activity Analyzer

Fetches git activity data via the GitHub REST API, providing the same
GitActivity dataclass that the local git analyzer produces. This allows
the update pipeline to work in CI environments (GitHub Actions) where
sibling project repositories are not checked out.

Usage (standalone):
    python scripts/github-activity.py --url https://github.com/Owner/Repo

As a module:
    from github_activity import analyze_git_activity_github, GitHubClient
"""

import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None


def resolve_github_token() -> Optional[str]:
    """Resolve GitHub API token from environment or gh CLI.

    Resolution order:
    1. GITHUB_TOKEN environment variable (GitHub Actions default)
    2. GH_TOKEN environment variable (gh CLI convention)
    3. `gh auth token` CLI command (local dev with gh authenticated)
    4. None (unauthenticated, 60 req/hr rate limit)
    """
    for env_var in ('GITHUB_TOKEN', 'GH_TOKEN'):
        token = os.environ.get(env_var)
        if token:
            return token

    try:
        result = subprocess.run(
            ['gh', 'auth', 'token'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Handles:
        https://github.com/Owner/Repo
        https://github.com/Owner/Repo.git
        https://github.com/Owner/Repo/
    """
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]

    parts = path.split('/')
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from URL: {url}")

    return parts[0], parts[1]


class GitHubClient:
    """Lightweight GitHub REST API client."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        if requests is None:
            raise ImportError("requests is required. Install with: pip install requests")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "website-updater",
        })
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

        self.logger = logging.getLogger('update-website.github')

    def _request(self, path: str, params: Optional[dict] = None) -> requests.Response:
        """Make a GET request with rate limit checking."""
        url = f"{self.BASE_URL}{path}"
        resp = self.session.get(url, params=params, timeout=15)

        remaining = resp.headers.get('X-RateLimit-Remaining')
        if remaining is not None and int(remaining) < 10:
            reset_ts = resp.headers.get('X-RateLimit-Reset', '0')
            reset_time = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
            self.logger.warning(
                f"GitHub API rate limit low: {remaining} remaining, resets at {reset_time.isoformat()}"
            )

        if resp.status_code == 403 and 'rate limit' in resp.text.lower():
            reset_ts = resp.headers.get('X-RateLimit-Reset', '0')
            reset_time = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
            raise RuntimeError(
                f"GitHub API rate limit exceeded. Resets at {reset_time.isoformat()}"
            )

        resp.raise_for_status()
        return resp

    def get_recent_commits(
        self, owner: str, repo: str, since_days: int = 30, limit: int = 20,
    ) -> list[str]:
        """Fetch recent commit messages (first line only)."""
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        resp = self._request(
            f"/repos/{owner}/{repo}/commits",
            params={"since": since, "per_page": limit},
        )
        commits = resp.json()
        return [c["commit"]["message"].split('\n')[0] for c in commits]

    def get_commit_count(self, owner: str, repo: str) -> int:
        """Get approximate total commit count via Link header pagination."""
        resp = self._request(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": 1},
        )
        link = resp.headers.get("Link", "")
        match = re.search(r'page=(\d+)>; rel="last"', link)
        if match:
            return int(match.group(1))
        # No Link header means single page — count items directly
        return len(resp.json())

    def get_languages(self, owner: str, repo: str) -> list[str]:
        """Fetch top 3 languages by bytes (via GitHub Linguist)."""
        resp = self._request(f"/repos/{owner}/{repo}/languages")
        languages = resp.json()  # {"TypeScript": 245000, "Python": 12000, ...}
        sorted_langs = sorted(languages.keys(), key=lambda k: languages[k], reverse=True)
        return sorted_langs[:3]

    def get_repo_info(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata (pushed_at, etc.)."""
        resp = self._request(f"/repos/{owner}/{repo}")
        return resp.json()


def analyze_git_activity_github(project, logger, client=None):
    """Analyze git activity via GitHub API.

    Drop-in replacement for analyze_git_activity() — returns the same
    GitActivity dataclass (imported dynamically to avoid circular imports).

    Args:
        project: ProjectConfig with url field set to a GitHub URL
        logger: Logger instance
        client: Optional pre-configured GitHubClient (creates one if None)

    Returns:
        GitActivity instance or None on failure
    """
    # Import GitActivity from the orchestrator to match the expected return type
    import sys
    from pathlib import Path
    script_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(script_dir))

    # GitActivity is defined in update-website.py — import it if available
    if 'update_website' in sys.modules:
        GitActivity = sys.modules['update_website'].GitActivity
    else:
        # Standalone usage: import from update-website.py
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'update_website', script_dir / 'update-website.py',
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GitActivity = mod.GitActivity

    if not project.url:
        logger.warning(f"No GitHub URL configured for {project.name}, skipping GitHub API")
        return None

    try:
        owner, repo = parse_github_url(project.url)
    except ValueError as e:
        logger.warning(f"Invalid GitHub URL for {project.name}: {e}")
        return None

    if client is None:
        token = resolve_github_token()
        client = GitHubClient(token=token)

    logger.debug(f"  Fetching activity from GitHub API: {owner}/{repo}")

    activity_data = {
        'project_name': project.name,
        'repo_path': project.url,
        'description': project.description,
    }

    # Fetch recent commits
    try:
        commits = client.get_recent_commits(owner, repo)
        activity_data['recent_commits'] = commits

        # Categorize commits (same keywords as local analyzer)
        features, fixes, refactors = [], [], []
        for msg in commits:
            msg_lower = msg.lower()
            if any(kw in msg_lower for kw in ['feat:', 'add:', 'feature', 'implement']):
                features.append(msg)
            elif any(kw in msg_lower for kw in ['fix:', 'bug', 'patch', 'resolve']):
                fixes.append(msg)
            elif any(kw in msg_lower for kw in ['refactor:', 'refactor', 'cleanup', 'reorganize']):
                refactors.append(msg)

        activity_data['recent_features'] = features
        activity_data['recent_fixes'] = fixes
        activity_data['recent_refactors'] = refactors
    except Exception as e:
        logger.warning(f"  Failed to fetch commits for {project.name}: {e}")
        activity_data['recent_commits'] = []

    # Fetch commit count
    try:
        activity_data['commit_count'] = client.get_commit_count(owner, repo)
    except Exception as e:
        logger.warning(f"  Failed to fetch commit count for {project.name}: {e}")
        activity_data['commit_count'] = 0

    # Fetch last active timestamp
    try:
        repo_info = client.get_repo_info(owner, repo)
        activity_data['last_active'] = repo_info.get('pushed_at')
    except Exception as e:
        logger.warning(f"  Failed to fetch repo info for {project.name}: {e}")

    # Fetch languages
    try:
        activity_data['languages'] = client.get_languages(owner, repo)
    except Exception as e:
        logger.warning(f"  Failed to fetch languages for {project.name}: {e}")
        activity_data['languages'] = []

    return GitActivity(**activity_data)
