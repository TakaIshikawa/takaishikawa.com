# me

Personal portfolio website showcasing work, projects, and blog posts.

**Vision**: Represent my work, projects, and blogs as a website. Clean, Clear, and Concise.

## Quick Start

### View Locally

Open `index.html` in a browser, or serve with a local server:

```bash
python -m http.server 8000
# Visit http://localhost:8000
```

### Deploy

Push to main branch and GitHub Pages will deploy automatically.

## Project Structure

```
.
├── index.html              # Main website
├── style.css               # Styles
├── blog/                   # Blog posts (HTML)
├── config/
│   └── projects.yaml       # Project configuration
├── scripts/                # Automation scripts
├── prompts/                # LLM prompt templates
├── docs/                   # Documentation
│   └── AUTO_UPDATE_SYSTEM.md
└── .github/workflows/      # GitHub Actions
```

## Automated Project Updates

This site includes an automated system that keeps project descriptions current by analyzing git activity and generating AI-powered descriptions.

### Features

- Analyzes recent commits from tracked repositories
- Generates descriptions using Claude (Anthropic) or GPT-4 (OpenAI)
- Updates the website automatically via GitHub Actions
- Supports dry-run mode for safe previews

### Quick Usage

```bash
# Install dependencies
pip install pyyaml beautifulsoup4 anthropic

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run update (dry-run first)
python scripts/update-website.py --dry-run --verbose

# Apply changes
python scripts/update-website.py --verbose
```

### Adding a Project

1. Add to `config/projects.yaml`:

```yaml
projects:
  - id: my-project
    name: My Project
    repoPath: ~/Projects/my-project
    description: Initial description.
    enabled: true
```

2. Add matching section to `index.html`:

```html
<article class="project">
  <h3>My Project</h3>
  <p>Initial description.</p>
</article>
```

3. Test: `python scripts/update-website.py --projects my-project --dry-run`

### Full Documentation

See **[docs/AUTO_UPDATE_SYSTEM.md](docs/AUTO_UPDATE_SYSTEM.md)** for:

- Complete setup instructions
- Command-line reference
- Configuration options
- Customizing description generation prompts
- Troubleshooting guide
- Example outputs

## Manual Editing

### Update Project Descriptions

Edit `index.html` directly or use the automated system above.

### Add Blog Posts

1. Create HTML file in `blog/` directory
2. Add entry to the blog section in `index.html`:

```html
<li>
  <a href="/blog/my-post.html">My Blog Post Title</a>
  <span class="date">March 2026</span>
</li>
```

## Configuration

### projects.yaml

Defines tracked projects for automated updates:

```yaml
version: "1.0"

defaults:
  updateFrequency: weekly
  descriptionPrompt: prompts/project-description.txt

projects:
  - id: project-id
    name: Display Name
    repoPath: ~/path/to/repo
    description: Current description text
    enabled: true
    updateRules:
      frequency: weekly
      triggers: [commit, manual]
      sources: [readme, commits]
    metadata:
      url: https://github.com/user/repo
      tags: [tag1, tag2]
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API key for Claude (description generation) |
| `OPENAI_API_KEY` | API key for GPT-4 (alternative provider) |

## GitHub Actions

### Update Project Descriptions

- **Schedule**: Daily at 6:00 AM UTC
- **Manual trigger**: Actions tab → Run workflow

Options:
- Projects to update (all or specific)
- Dry run mode
- LLM provider selection
- Skip LLM (use fallback descriptions)

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/update-website.py` | Main orchestrator for updates |
| `scripts/description-generator.py` | LLM-based description generation |
| `scripts/html-updater.py` | Safe HTML file manipulation |
| `scripts/git-analyzer.js` | Git repository analysis |

## License

MIT
