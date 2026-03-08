# Automated Project Description Update System

This document provides comprehensive documentation for the automated system that keeps portfolio project descriptions current by analyzing git activity and generating AI-powered descriptions.

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [First-Time Setup](#first-time-setup)
- [Running Updates](#running-updates)
- [Adding New Projects](#adding-new-projects)
- [Customizing Description Generation](#customizing-description-generation)
- [Command-Line Reference](#command-line-reference)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

---

## Overview

The automated update system monitors your project repositories, analyzes recent git activity, and uses AI to generate professional project descriptions that reflect current development progress. These descriptions are automatically updated on your portfolio website.

### Key Features

- **Git Activity Analysis**: Extracts commits, categorizes changes (features, fixes, refactors), detects languages
- **AI-Powered Descriptions**: Uses Claude (Anthropic) or GPT-4 (OpenAI) to generate concise, technical descriptions
- **Safe Updates**: Creates backups, validates HTML structure, supports dry-run mode
- **Flexible Scheduling**: Daily automated updates via GitHub Actions, plus manual trigger options
- **Fallback Mechanism**: Template-based generation when LLM is unavailable

### Data Flow

```
┌─────────────────────┐
│  config/projects.yaml │  ← Project definitions
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Git Repository    │  ← Analyze commits (30 days, 20 commits)
│   Analysis          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LLM Description    │  ← Claude/GPT-4 generates description
│  Generation         │     (or fallback template)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   HTML Update       │  ← Update index.html with new descriptions
│   (with backup)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Git Commit        │  ← Optional: commit changes
│   (optional)        │
└─────────────────────┘
```

---

## System Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `scripts/update-website.py` | Main entry point, coordinates all components |
| **Git Analyzer** | `scripts/git-analyzer.js` | Analyzes repository commit history |
| **Description Generator** | `scripts/description-generator.py` | LLM-based description generation |
| **HTML Updater** | `scripts/html-updater.py` | Safe HTML file manipulation |
| **Project Config** | `config/projects.yaml` | Project definitions and settings |
| **Prompt Template** | `prompts/project-description.txt` | LLM prompt for description style |
| **GitHub Workflow** | `.github/workflows/update-projects.yml` | Automated daily updates |

### File Structure

```
.
├── config/
│   ├── projects.yaml          # Project configuration (edit this!)
│   └── projects.schema.json   # JSON Schema for validation
├── scripts/
│   ├── update-website.py      # Main orchestration script
│   ├── description-generator.py
│   ├── html-updater.py
│   └── git-analyzer.js
├── prompts/
│   └── project-description.txt  # Customize generation prompt
├── .github/
│   └── workflows/
│       └── update-projects.yml  # Automated workflow
└── index.html                   # Website (updated automatically)
```

---

## First-Time Setup

### Prerequisites

- Python 3.11+
- Git
- API key for Anthropic (Claude) or OpenAI (GPT-4)

### Step 1: Install Dependencies

```bash
pip install pyyaml beautifulsoup4 anthropic
# Or for OpenAI:
pip install pyyaml beautifulsoup4 openai
```

### Step 2: Set API Key

For local development:

```bash
# For Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Or for OpenAI
export OPENAI_API_KEY="sk-..."
```

For GitHub Actions, add the secret in your repository settings:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`)
4. Value: Your API key

### Step 3: Configure Projects

Edit `config/projects.yaml` to define your projects (see [Adding New Projects](#adding-new-projects)).

### Step 4: Test the Setup

```bash
# Run a dry-run to verify everything works
python scripts/update-website.py --dry-run --verbose
```

### Step 5: Enable GitHub Actions

The workflow runs automatically once configured. To enable:
1. Ensure the workflow file exists at `.github/workflows/update-projects.yml`
2. Add your API key as a repository secret
3. Optionally trigger manually from **Actions** → **Update Project Descriptions** → **Run workflow**

---

## Running Updates

### Automatic Updates (GitHub Actions)

Updates run automatically:
- **Schedule**: Daily at 6:00 AM UTC
- **Manual**: Via "Run workflow" button in GitHub Actions

### Manual Updates (Local)

```bash
# Update all projects
python scripts/update-website.py

# Preview changes without applying
python scripts/update-website.py --dry-run

# Update specific projects only
python scripts/update-website.py --projects tact prepend

# Skip LLM (use fallback descriptions)
python scripts/update-website.py --no-llm

# Update and commit changes
python scripts/update-website.py --commit

# Verbose output with log file
python scripts/update-website.py --verbose --log-file update.log
```

### Output

The script produces:
- Updated `index.html` with new descriptions
- Timestamped backup file (e.g., `index.20260308_143022.backup.html`)
- Optional JSON results file (`--output-json results.json`)
- Console/log output with colored status messages

---

## Adding New Projects

### Step 1: Add to Configuration

Edit `config/projects.yaml`:

```yaml
projects:
  # ... existing projects ...

  - id: my-new-project                    # Unique ID (lowercase, hyphenated)
    name: My New Project                   # Display name on website
    repoPath: ~/Projects/my-new-project   # Path to git repository
    description: >-
      Initial description for the website.
      This will be updated automatically.
    enabled: true                          # Set false to skip
    updateRules:
      frequency: weekly                    # daily, weekly, monthly, manual
      triggers:
        - commit                           # Update on new commits
        - manual                           # Allow manual triggers
      sources:
        - readme                           # Read README for context
        - commits                          # Analyze commit messages
    metadata:
      url: https://github.com/user/repo   # Project URL (displayed on site)
      tags:
        - python
        - automation
```

### Step 2: Add to HTML

Ensure your `index.html` has a matching project section:

```html
<section class="projects">
  <h2>Projects</h2>
  <div class="project-list">
    <!-- Existing projects -->

    <article class="project">
      <h3>My New Project</h3>  <!-- Must match 'name' in config -->
      <p>Initial description here.</p>
    </article>
  </div>
</section>
```

### Step 3: Verify

```bash
# Test that the project is recognized
python scripts/update-website.py --projects my-new-project --dry-run --verbose
```

### Required vs Optional Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `name` | Yes | Display name (must match HTML) |
| `repoPath` | Yes | Path to local git repository |
| `description` | Yes | Initial/current description |
| `enabled` | No | Default: `true` |
| `updateRules` | No | Defaults from `defaults` section |
| `metadata` | No | Additional info (url, tags) |

---

## Customizing Description Generation

### Prompt Template

The LLM uses the prompt template at `prompts/project-description.txt`. Customize this to change the style, tone, and format of generated descriptions.

#### Current Prompt Structure

```text
You are a technical writer creating concise project descriptions...

STYLE GUIDELINES:
- Professional and technical, not marketing copy
- 1-3 sentences maximum
- Start with what the system is/does
...

PROJECT DATA:
{project_data}

INSTRUCTIONS:
...
```

#### Customizing the Prompt

1. Edit `prompts/project-description.txt`
2. Keep the `{project_data}` placeholder (replaced with actual data)
3. Adjust guidelines to match your preferred style

#### Example Customizations

**For a more casual tone:**
```text
STYLE GUIDELINES:
- Conversational and approachable
- Written for a general technical audience
- Highlight the "why" before the "what"
```

**For academic/research projects:**
```text
STYLE GUIDELINES:
- Formal academic tone
- Include methodology and key findings
- Reference relevant research areas
```

### Project Data Provided to LLM

The `{project_data}` placeholder is replaced with:

```text
Project Name: TACT
Current Description: An orchestration system for AI coding agents...

Programming Languages: TypeScript, Python

Recent Features:
- feat: Add parallel agent dispatch
- feat: Implement budget constraints

Recent Fixes:
- fix: Resolve merge conflict handling

Recent Commits:
- Update documentation
- Add test coverage
- ...

Total Commits: 342
Last Active: 2026-03-07 15:30:22 -0800
```

---

## Command-Line Reference

### Main Script: `update-website.py`

```
usage: update-website.py [-h] [--projects [PROJECTS ...]] [--dry-run]
                         [--no-llm] [--commit] [--commit-message MSG]
                         [--provider {anthropic,openai}] [--config PATH]
                         [--html PATH] [--no-backup] [--verbose]
                         [--log-file PATH] [--output-json PATH]

Options:
  --projects, -p    Project IDs/names to update (default: all enabled)
  --dry-run, -n     Preview changes without applying them
  --no-llm          Skip LLM calls, use fallback descriptions
  --commit          Create a git commit with the changes
  --commit-message  Custom commit message (requires --commit)
  --provider        LLM provider: anthropic (default) or openai
  --config          Path to config file (default: config/projects.yaml)
  --html            Path to HTML file (default: index.html)
  --no-backup       Skip creating HTML backup
  --verbose, -v     Enable verbose logging
  --log-file        Write logs to file
  --output-json     Write results to JSON file
```

### Common Usage Patterns

```bash
# Daily workflow: full update with commit
python scripts/update-website.py --commit --verbose

# Development: test changes before applying
python scripts/update-website.py --dry-run --verbose

# CI/CD: output JSON for processing
python scripts/update-website.py --output-json results.json

# Debugging: single project with all logs
python scripts/update-website.py -p tact -v --log-file debug.log

# Offline mode: update without API calls
python scripts/update-website.py --no-llm
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (failed projects, config issues, etc.) |

---

## Configuration Reference

### `config/projects.yaml`

```yaml
version: "1.0"

defaults:
  updateFrequency: weekly              # Default for all projects
  descriptionPrompt: prompts/project-description.txt

projects:
  - id: project-id                     # Required: unique identifier
    name: Project Name                 # Required: display name
    repoPath: ~/path/to/repo          # Required: git repository path
    description: Current description   # Required: current text
    enabled: true                      # Optional: visibility toggle
    updateRules:
      frequency: weekly                # daily, weekly, monthly, on-change, manual
      triggers:
        - commit                       # Update triggers
        - release
        - manual
      sources:
        - readme                       # Data sources for analysis
        - commits
        - releases
        - code
      lastUpdated: "2026-03-07T00:00:00Z"
    metadata:
      url: https://github.com/...
      tags: [tag1, tag2]
```

### Update Frequencies

| Frequency | Description |
|-----------|-------------|
| `daily` | Check for updates every day |
| `weekly` | Check for updates every week |
| `monthly` | Check for updates every month |
| `on-change` | Update only when changes detected |
| `manual` | Only update when manually triggered |

### Triggers

| Trigger | Description |
|---------|-------------|
| `commit` | Update when new commits detected |
| `release` | Update on new releases |
| `manual` | Allow manual update triggers |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Anthropic | API key for Claude |
| `OPENAI_API_KEY` | For OpenAI | API key for GPT-4 |

---

## Troubleshooting

### Common Issues

#### "Config file not found"

```
Error: Config file not found: config/projects.yaml
```

**Solution**: Ensure you're running the script from the project root directory, or specify the config path:
```bash
python scripts/update-website.py --config /path/to/projects.yaml
```

#### "Repository not found"

```
WARNING: Repository not found: ~/Projects/my-project
```

**Solutions**:
1. Check that the `repoPath` in `projects.yaml` is correct
2. Expand `~` manually if needed: `/Users/username/Projects/my-project`
3. Ensure the repository exists and contains a `.git` directory

#### "Project not found in HTML"

```
WARNING: Project not found in HTML: My Project
```

**Solutions**:
1. Ensure the `<h3>` heading in HTML exactly matches the `name` in config
2. Check for case sensitivity: "TACT" vs "Tact"
3. Verify the project is inside a `<section class="projects">` element

#### "API key not set"

```
Error: ANTHROPIC_API_KEY environment variable not set
```

**Solutions**:
1. Export the key: `export ANTHROPIC_API_KEY="sk-ant-..."`
2. Or add to `.bashrc`/`.zshrc` for persistence
3. For GitHub Actions, add as repository secret

#### "Rate limit exceeded"

**Solutions**:
1. Wait and retry later
2. Use `--no-llm` flag for fallback descriptions
3. Reduce the number of projects updated at once

### Debug Mode

For detailed troubleshooting:

```bash
python scripts/update-website.py \
  --verbose \
  --log-file debug.log \
  --dry-run \
  --output-json debug-results.json
```

Check `debug.log` for:
- Config loading details
- Git command outputs
- LLM API responses
- HTML parsing information

### Validation Commands

```bash
# List all projects in HTML
python scripts/html-updater.py --list-projects

# Validate HTML structure
python scripts/html-updater.py --validate

# Test git analysis for a project
node scripts/git-analyzer.js ~/Projects/my-project --pretty
```

### Restoring from Backup

If an update goes wrong, backups are automatically created:

```bash
# Find recent backups
ls -la index.*.backup.html

# Restore from backup
cp index.20260308_143022.backup.html index.html
```

---

## Examples

### Example 1: Full Update Workflow

```bash
$ python scripts/update-website.py --verbose

2026-03-08 14:30:22 [INFO] ============================================================
2026-03-08 14:30:22 [INFO] Website Update Orchestrator
2026-03-08 14:30:22 [INFO] ============================================================
2026-03-08 14:30:22 [INFO] Config: config/projects.yaml
2026-03-08 14:30:22 [INFO] HTML: index.html
2026-03-08 14:30:22 [INFO]
2026-03-08 14:30:22 [INFO] Loaded 3 project(s) from config
2026-03-08 14:30:22 [INFO] Updating 3 project(s)
2026-03-08 14:30:22 [INFO] Processing project: TACT
2026-03-08 14:30:23 [INFO]   Generated (llm): An orchestration system for AI coding agents...
2026-03-08 14:30:23 [INFO] Processing project: Prepend
2026-03-08 14:30:24 [INFO]   Generated (llm): A health optimization platform with a 4-layer...
2026-03-08 14:30:24 [INFO] Processing project: Increment
2026-03-08 14:30:25 [INFO]   Generated (llm): An AI-augmented workspace with specialized...
2026-03-08 14:30:25 [INFO] Updating HTML: index.html
2026-03-08 14:30:25 [INFO] Updated: index.html
2026-03-08 14:30:25 [INFO] Backup: index.20260308_143025.backup.html
2026-03-08 14:30:25 [INFO]
2026-03-08 14:30:25 [INFO] ============================================================
2026-03-08 14:30:25 [INFO] Summary
2026-03-08 14:30:25 [INFO] ============================================================
2026-03-08 14:30:25 [INFO] Projects processed: 3
2026-03-08 14:30:25 [INFO]   Successful: 3
2026-03-08 14:30:25 [INFO]   Failed: 0
2026-03-08 14:30:25 [INFO] HTML changes: 3
```

### Example 2: Dry Run Output

```bash
$ python scripts/update-website.py --dry-run --projects tact

2026-03-08 14:35:00 [INFO] Mode: DRY RUN
...
2026-03-08 14:35:02 [INFO] DRY RUN: Would update 1 project(s)
2026-03-08 14:35:02 [INFO]   TACT: An orchestration system... -> An orchestration system for AI...
```

### Example 3: JSON Output

```bash
$ python scripts/update-website.py --output-json results.json
$ cat results.json
```

```json
{
  "timestamp": "2026-03-08T14:40:00.123456",
  "dry_run": false,
  "results": [
    {
      "project_name": "TACT",
      "success": true,
      "description": "An orchestration system for AI coding agents that manages parallel agent sessions: decomposing requirements into dependency-tracked tasks, dispatching within budget constraints, handling merge conflicts, and surfacing decisions for human input.",
      "source": "llm",
      "error": null
    }
  ],
  "html_update": {
    "saved_to": "index.html",
    "backup_path": "index.20260308_144000.backup.html",
    "changes": 1,
    "not_found": []
  }
}
```

### Example 4: Before/After Description

**Before (old description):**
> A multi-agent orchestration system for software development.

**After (AI-generated):**
> An orchestration system for AI coding agents that manages parallel agent sessions: decomposing requirements into dependency-tracked tasks, dispatching within budget constraints, handling merge conflicts, and surfacing decisions for human input.

### Example 5: GitHub Actions Manual Trigger

1. Navigate to **Actions** tab in your repository
2. Select **Update Project Descriptions** workflow
3. Click **Run workflow**
4. Configure options:
   - **Projects**: `all` or comma-separated list (e.g., `tact,prepend`)
   - **Dry run**: `true` for preview mode
   - **LLM provider**: `anthropic` or `openai`
   - **Skip LLM**: `true` to use fallback descriptions
5. Click **Run workflow** button

The workflow will:
- Analyze git activity for selected projects
- Generate new descriptions
- Update `index.html`
- Create a commit (unless dry run)
- Display results in the Actions summary

---

## Appendix: Schema Reference

### projects.schema.json

The configuration file is validated against `config/projects.schema.json`. Key validations:

- `id`: Must be lowercase with hyphens only (`^[a-z][a-z0-9-]*$`)
- `frequency`: Must be one of `daily`, `weekly`, `monthly`, `on-change`, `manual`
- `triggers`: Array of `commit`, `release`, `manual`
- `sources`: Array of `readme`, `commits`, `releases`, `code`

---

## Support

For issues or feature requests:
1. Check the [Troubleshooting](#troubleshooting) section
2. Run with `--verbose` and check logs
3. Open an issue with:
   - Command you ran
   - Error message
   - Relevant log output
