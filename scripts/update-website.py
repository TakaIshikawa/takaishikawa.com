#!/usr/bin/env python3
"""
Website Update Orchestrator

Main orchestration script that coordinates the full workflow for updating
project descriptions on the portfolio website:

1. Reads project configuration from config/projects.yaml
2. Analyzes git activity for each enabled project
3. Generates descriptions using LLM (or fallback)
4. Updates index.html with new descriptions
5. Optionally commits changes to git

Usage:
    # Full update (all projects)
    python scripts/update-website.py

    # Update specific projects only
    python scripts/update-website.py --projects tact prepend

    # Dry-run mode (no changes)
    python scripts/update-website.py --dry-run

    # Skip LLM, use fallback descriptions
    python scripts/update-website.py --no-llm

    # Commit changes after update
    python scripts/update-website.py --commit

    # Verbose logging
    python scripts/update-website.py --verbose
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add scripts directory to path for imports
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import sibling modules (handle hyphenated filenames)
import importlib.util

def import_module_from_file(module_name: str, file_path: Path):
    """Import a module from a file path (handles hyphenated names)."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import description-generator.py
_desc_gen = import_module_from_file('description_generator', SCRIPT_DIR / 'description-generator.py')
DescriptionGenerator = _desc_gen.DescriptionGenerator
ProjectActivity = _desc_gen.ProjectActivity
parse_activity_data = _desc_gen.parse_activity_data

# Import html-updater.py
_html_upd = import_module_from_file('html_updater', SCRIPT_DIR / 'html-updater.py')
HTMLUpdater = _html_upd.HTMLUpdater
HTMLUpdaterError = _html_upd.HTMLUpdaterError

# Try to import yaml
try:
    import yaml
except ImportError:
    yaml = None


# =============================================================================
# Logging Setup
# =============================================================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and timestamps."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add color if terminal supports it
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname}{self.RESET}"

        return super().format(record)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging with timestamps and optional file output."""
    logger = logging.getLogger('update-website')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(ColoredFormatter(
        '%(timestamp)s [%(levelname)s] %(message)s'
    ))
    logger.addHandler(console)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        logger.addHandler(file_handler)

    return logger


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ProjectConfig:
    """Configuration for a single project."""
    id: str
    name: str
    repo_path: str
    description: str = ""
    enabled: bool = True
    frequency: str = "weekly"
    triggers: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    last_updated: Optional[str] = None
    url: Optional[str] = None
    tags: list = field(default_factory=list)


@dataclass
class Config:
    """Overall configuration."""
    version: str = "1.0"
    default_frequency: str = "weekly"
    default_prompt: str = "prompts/project-description.txt"
    projects: list = field(default_factory=list)


def load_config(config_path: Path) -> Config:
    """Load project configuration from YAML file."""
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    config = Config(
        version=data.get('version', '1.0'),
        default_frequency=data.get('defaults', {}).get('updateFrequency', 'weekly'),
        default_prompt=data.get('defaults', {}).get('descriptionPrompt', 'prompts/project-description.txt'),
    )

    for proj in data.get('projects', []):
        update_rules = proj.get('updateRules', {})
        metadata = proj.get('metadata', {})

        config.projects.append(ProjectConfig(
            id=proj.get('id', ''),
            name=proj.get('name', ''),
            repo_path=proj.get('repoPath', ''),
            description=proj.get('description', ''),
            enabled=proj.get('enabled', True),
            frequency=update_rules.get('frequency', config.default_frequency),
            triggers=update_rules.get('triggers', []),
            sources=update_rules.get('sources', []),
            last_updated=update_rules.get('lastUpdated'),
            url=metadata.get('url'),
            tags=metadata.get('tags', []),
        ))

    return config


# =============================================================================
# Git Activity Analysis
# =============================================================================

@dataclass
class GitActivity:
    """Git activity data for a project."""
    project_name: str
    repo_path: str
    description: str = ""
    recent_commits: list = field(default_factory=list)
    languages: list = field(default_factory=list)
    last_active: Optional[str] = None
    commit_count: int = 0
    recent_features: list = field(default_factory=list)
    recent_fixes: list = field(default_factory=list)
    recent_refactors: list = field(default_factory=list)


def run_git_command(repo_path: Path, args: list, logger: logging.Logger) -> Optional[str]:
    """Run a git command in the specified repository."""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.debug(f"Git command failed: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out in {repo_path}")
        return None
    except Exception as e:
        logger.debug(f"Git command error: {e}")
        return None


def analyze_git_activity(project: ProjectConfig, logger: logging.Logger) -> Optional[GitActivity]:
    """Analyze git activity for a project repository."""
    repo_path = Path(project.repo_path).expanduser()

    if not repo_path.exists():
        logger.warning(f"Repository not found: {repo_path}")
        return None

    if not (repo_path / '.git').exists():
        logger.warning(f"Not a git repository: {repo_path}")
        return None

    activity = GitActivity(
        project_name=project.name,
        repo_path=str(repo_path),
        description=project.description,
    )

    # Get recent commits (last 30 days, up to 20 commits)
    commits_output = run_git_command(
        repo_path,
        ['log', '--oneline', '--since=30.days.ago', '-n', '20', '--format=%s'],
        logger
    )
    if commits_output:
        activity.recent_commits = commits_output.split('\n')

        # Categorize commits
        for msg in activity.recent_commits:
            msg_lower = msg.lower()
            if any(kw in msg_lower for kw in ['feat:', 'add:', 'feature', 'implement']):
                activity.recent_features.append(msg)
            elif any(kw in msg_lower for kw in ['fix:', 'bug', 'patch', 'resolve']):
                activity.recent_fixes.append(msg)
            elif any(kw in msg_lower for kw in ['refactor:', 'refactor', 'cleanup', 'reorganize']):
                activity.recent_refactors.append(msg)

    # Get total commit count
    count_output = run_git_command(repo_path, ['rev-list', '--count', 'HEAD'], logger)
    if count_output:
        try:
            activity.commit_count = int(count_output)
        except ValueError:
            pass

    # Get last commit date
    date_output = run_git_command(
        repo_path,
        ['log', '-1', '--format=%ci'],
        logger
    )
    if date_output:
        activity.last_active = date_output

    # Detect languages from file extensions
    files_output = run_git_command(
        repo_path,
        ['ls-files'],
        logger
    )
    if files_output:
        extensions = {}
        for file in files_output.split('\n'):
            ext = Path(file).suffix.lower()
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1

        # Map extensions to languages
        ext_to_lang = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.tsx': 'TypeScript', '.jsx': 'JavaScript', '.go': 'Go',
            '.rs': 'Rust', '.java': 'Java', '.rb': 'Ruby',
            '.cpp': 'C++', '.c': 'C', '.swift': 'Swift',
            '.kt': 'Kotlin', '.scala': 'Scala', '.sh': 'Shell',
        }

        # Get top 3 languages by file count
        lang_counts = {}
        for ext, count in extensions.items():
            lang = ext_to_lang.get(ext)
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + count

        activity.languages = sorted(
            lang_counts.keys(),
            key=lambda x: lang_counts[x],
            reverse=True
        )[:3]

    return activity


# =============================================================================
# Orchestration
# =============================================================================

@dataclass
class UpdateResult:
    """Result of updating a single project."""
    project_name: str
    success: bool
    description: Optional[str] = None
    source: Optional[str] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


def update_project(
    project: ProjectConfig,
    generator: DescriptionGenerator,
    logger: logging.Logger,
    dry_run: bool = False,
    no_llm: bool = False
) -> UpdateResult:
    """Update a single project's description."""
    logger.info(f"Processing project: {project.name}")

    # Analyze git activity
    logger.debug(f"  Analyzing git activity for {project.name}...")
    activity = analyze_git_activity(project, logger)

    if activity is None:
        return UpdateResult(
            project_name=project.name,
            success=False,
            error="Failed to analyze git activity",
        )

    # Convert to ProjectActivity for description generator
    proj_activity = ProjectActivity(
        project_name=activity.project_name,
        description=activity.description,
        recent_commits=activity.recent_commits,
        languages=activity.languages,
        last_active=activity.last_active,
        commit_count=activity.commit_count,
        recent_features=activity.recent_features,
        recent_fixes=activity.recent_fixes,
        recent_refactors=activity.recent_refactors,
    )

    # Generate description
    logger.debug(f"  Generating description for {project.name}...")
    try:
        if no_llm:
            # Use fallback only
            description = generator._generate_fallback(proj_activity)
            source = "fallback"
        else:
            result = generator.generate(proj_activity)
            description = result.description
            source = result.source
    except Exception as e:
        return UpdateResult(
            project_name=project.name,
            success=False,
            error=f"Description generation failed: {e}",
        )

    logger.info(f"  Generated ({source}): {description[:80]}...")

    return UpdateResult(
        project_name=project.name,
        success=True,
        description=description,
        source=source,
    )


def orchestrate_update(
    config: Config,
    logger: logging.Logger,
    project_filter: Optional[list] = None,
    dry_run: bool = False,
    no_llm: bool = False,
    provider: str = "anthropic",
) -> tuple[list[UpdateResult], list[dict]]:
    """
    Orchestrate the full update workflow.

    Returns:
        Tuple of (results, descriptions_for_html)
    """
    results = []
    descriptions = []

    # Filter projects
    projects_to_update = [
        p for p in config.projects
        if p.enabled and (project_filter is None or p.id in project_filter or p.name in project_filter)
    ]

    if not projects_to_update:
        logger.warning("No projects to update")
        return results, descriptions

    logger.info(f"Updating {len(projects_to_update)} project(s)")

    # Initialize description generator
    generator = DescriptionGenerator(provider=provider)

    # Process each project
    for project in projects_to_update:
        result = update_project(
            project,
            generator,
            logger,
            dry_run=dry_run,
            no_llm=no_llm,
        )
        results.append(result)

        if result.success and result.description:
            descriptions.append({
                'project_name': result.project_name,
                'description': result.description,
                'source': result.source,
                'confidence': 0.9 if result.source == 'llm' else 0.5,
            })

    return results, descriptions


def update_html(
    descriptions: list[dict],
    html_path: Path,
    logger: logging.Logger,
    dry_run: bool = False,
    no_backup: bool = False,
) -> dict:
    """Update the HTML file with new descriptions."""
    logger.info(f"Updating HTML: {html_path}")

    updater = HTMLUpdater(str(html_path))
    updater.load()

    # Apply updates
    not_found = []
    for desc in descriptions:
        name = desc.get('project_name')
        description = desc.get('description')

        if not name or not description:
            continue

        success = updater.update_project_description(name, description)
        if not success:
            not_found.append(name)
            logger.warning(f"  Project not found in HTML: {name}")
        else:
            logger.debug(f"  Updated: {name}")

    changes = updater.get_changes()

    if dry_run:
        logger.info(f"DRY RUN: Would update {len(changes)} project(s)")
        for change in changes:
            logger.info(f"  {change['name']}: {change['old'][:40]}... -> {change['new'][:40]}...")
        return {'dry_run': True, 'changes': len(changes), 'not_found': not_found}

    if not changes:
        logger.info("No changes to apply")
        return {'changes': 0, 'not_found': not_found}

    # Save changes
    result = updater.save(create_backup=not no_backup)

    logger.info(f"Updated: {result['saved_to']}")
    if result.get('backup_path'):
        logger.info(f"Backup: {result['backup_path']}")

    return {
        'saved_to': result['saved_to'],
        'backup_path': result.get('backup_path'),
        'changes': len(changes),
        'not_found': not_found,
    }


def commit_changes(
    html_path: Path,
    logger: logging.Logger,
    message: Optional[str] = None,
) -> bool:
    """Commit changes to git."""
    if message is None:
        message = f"Update project descriptions ({datetime.now().strftime('%Y-%m-%d')})"

    logger.info("Committing changes to git...")

    try:
        # Stage the HTML file
        subprocess.run(
            ['git', 'add', str(html_path)],
            cwd=html_path.parent,
            check=True,
            capture_output=True,
        )

        # Check if there are staged changes
        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=html_path.parent,
            capture_output=True,
        )

        if result.returncode == 0:
            logger.info("No changes to commit")
            return False

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=html_path.parent,
            check=True,
            capture_output=True,
        )

        logger.info(f"Committed: {message}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git commit failed: {e.stderr.decode() if e.stderr else e}")
        return False


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate website project description updates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all projects
  %(prog)s

  # Update specific projects
  %(prog)s --projects tact prepend

  # Dry-run mode (preview changes)
  %(prog)s --dry-run

  # Skip LLM calls (use fallback descriptions)
  %(prog)s --no-llm

  # Commit changes after update
  %(prog)s --commit

  # Use OpenAI instead of Anthropic
  %(prog)s --provider openai

  # Verbose logging with log file
  %(prog)s --verbose --log-file update.log
"""
    )

    parser.add_argument(
        '--projects', '-p',
        nargs='+',
        help='Project IDs or names to update (default: all enabled)',
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview changes without applying them',
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Skip LLM calls, use fallback descriptions only',
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        help='Create a git commit with the changes',
    )
    parser.add_argument(
        '--commit-message', '-m',
        help='Custom commit message (requires --commit)',
    )
    parser.add_argument(
        '--provider',
        choices=['anthropic', 'openai'],
        default='anthropic',
        help='LLM provider to use (default: anthropic)',
    )
    parser.add_argument(
        '--config',
        default='config/projects.yaml',
        help='Path to project configuration file',
    )
    parser.add_argument(
        '--html',
        default='index.html',
        help='Path to HTML file to update',
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup of HTML file',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging',
    )
    parser.add_argument(
        '--log-file',
        help='Path to log file (in addition to console output)',
    )
    parser.add_argument(
        '--output-json',
        help='Write results to JSON file',
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(verbose=args.verbose, log_file=args.log_file)

    # Resolve paths
    config_path = PROJECT_ROOT / args.config
    html_path = PROJECT_ROOT / args.html

    # Log start
    logger.info("=" * 60)
    logger.info("Website Update Orchestrator")
    logger.info("=" * 60)
    logger.info(f"Config: {config_path}")
    logger.info(f"HTML: {html_path}")
    if args.dry_run:
        logger.info("Mode: DRY RUN")
    if args.no_llm:
        logger.info("LLM: Disabled (fallback only)")
    logger.info("")

    # Load configuration
    try:
        config = load_config(config_path)
        logger.info(f"Loaded {len(config.projects)} project(s) from config")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Run orchestration
    try:
        results, descriptions = orchestrate_update(
            config,
            logger,
            project_filter=args.projects,
            dry_run=args.dry_run,
            no_llm=args.no_llm,
            provider=args.provider,
        )
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        sys.exit(1)

    # Update HTML
    if descriptions:
        try:
            html_result = update_html(
                descriptions,
                html_path,
                logger,
                dry_run=args.dry_run,
                no_backup=args.no_backup,
            )
        except HTMLUpdaterError as e:
            logger.error(f"HTML update failed: {e}")
            sys.exit(1)
    else:
        html_result = {'changes': 0}
        logger.warning("No descriptions generated, skipping HTML update")

    # Commit if requested
    if args.commit and not args.dry_run and html_result.get('changes', 0) > 0:
        commit_changes(html_path, logger, message=args.commit_message)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)

    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    logger.info(f"Projects processed: {len(results)}")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"HTML changes: {html_result.get('changes', 0)}")

    # Output JSON if requested
    if args.output_json:
        output = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': args.dry_run,
            'results': [
                {
                    'project_name': r.project_name,
                    'success': r.success,
                    'description': r.description,
                    'source': r.source,
                    'error': r.error,
                }
                for r in results
            ],
            'html_update': html_result,
        }
        with open(args.output_json, 'w') as f:
            json.dump(output, f, indent=2)
        logger.info(f"Results written to: {args.output_json}")

    # Exit with error if any failures
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
