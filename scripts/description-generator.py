#!/usr/bin/env python3
"""
AI-Powered Description Generator for Project Portfolio

Takes git activity summaries and generates natural, concise project descriptions
that match the website's professional, technical tone.

Usage:
    python description-generator.py --input activity.json --output descriptions.json
    python description-generator.py --input activity.json --provider openai
    cat activity.json | python description-generator.py --stdin
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ProjectActivity:
    """Structured git activity data for a project."""
    project_name: str
    description: Optional[str] = None
    recent_commits: list = None
    top_contributors: list = None
    languages: list = None
    last_active: Optional[str] = None
    commit_count: int = 0
    recent_features: list = None
    recent_fixes: list = None
    recent_refactors: list = None
    manual_override: Optional[str] = None  # Preserved custom description

    def __post_init__(self):
        self.recent_commits = self.recent_commits or []
        self.top_contributors = self.top_contributors or []
        self.languages = self.languages or []
        self.recent_features = self.recent_features or []
        self.recent_fixes = self.recent_fixes or []
        self.recent_refactors = self.recent_refactors or []


@dataclass
class GeneratedDescription:
    """Output from the description generator."""
    project_name: str
    description: str
    source: str  # 'llm', 'fallback', or 'manual_override'
    confidence: float  # 0.0 to 1.0


class DescriptionGenerator:
    """Generates project descriptions using LLM APIs."""

    def __init__(self, provider: str = "anthropic", prompt_path: Optional[str] = None):
        self.provider = provider.lower()
        self.prompt_template = self._load_prompt(prompt_path)
        self._client = None

    def _load_prompt(self, prompt_path: Optional[str] = None) -> str:
        """Load the prompt template from file or use default."""
        if prompt_path:
            path = Path(prompt_path)
        else:
            # Default path relative to this script
            script_dir = Path(__file__).parent
            path = script_dir.parent / "prompts" / "project-description.txt"

        if path.exists():
            return path.read_text()

        # Fallback inline prompt if file doesn't exist
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Default prompt template for description generation."""
        return """You are a technical writer creating concise project descriptions for a software engineer's portfolio website.

STYLE GUIDELINES:
- Professional and technical, not marketing copy
- Precise terminology appropriate for engineers
- Information-dense but readable
- 1-3 sentences maximum
- Start with what the system is/does
- Include key technical details and capabilities
- Avoid jargon, buzzwords, or filler

EXAMPLES OF GOOD DESCRIPTIONS:
- "An orchestration system for AI coding agents that manages parallel agent sessions: decomposing requirements into dependency-tracked tasks, dispatching within budget constraints, handling merge conflicts, and surfacing decisions for human input."
- "A health optimization platform with a 4-layer architecture mapping conditions to biological and behavioral risk factors, featuring LE8-inspired scoring and wearable data integration."
- "An AI-augmented workspace with specialized agents for explaining, generating, reviewing, and understanding code and content."

PROJECT DATA:
{project_data}

Generate a description that captures the project's essence based on its recent activity and technical focus. Output ONLY the description text, no quotes or formatting."""

    def _get_client(self):
        """Lazily initialize the API client."""
        if self._client is not None:
            return self._client

        if self.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic()
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        elif self.provider == "openai":
            try:
                import openai
                self._client = openai.OpenAI()
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        return self._client

    def _format_project_data(self, activity: ProjectActivity) -> str:
        """Format project activity data for the prompt."""
        lines = [f"Project: {activity.project_name}"]

        if activity.description:
            lines.append(f"Current Description: {activity.description}")

        if activity.languages:
            lines.append(f"Languages: {', '.join(activity.languages)}")

        if activity.recent_features:
            lines.append(f"Recent Features: {'; '.join(activity.recent_features[:5])}")

        if activity.recent_fixes:
            lines.append(f"Recent Fixes: {'; '.join(activity.recent_fixes[:3])}")

        if activity.recent_refactors:
            lines.append(f"Recent Refactoring: {'; '.join(activity.recent_refactors[:3])}")

        if activity.recent_commits:
            commit_msgs = [c.get('message', c) if isinstance(c, dict) else str(c)
                         for c in activity.recent_commits[:10]]
            lines.append(f"Recent Commits: {'; '.join(commit_msgs)}")

        if activity.commit_count:
            lines.append(f"Total Commits: {activity.commit_count}")

        if activity.last_active:
            lines.append(f"Last Active: {activity.last_active}")

        return "\n".join(lines)

    def _call_anthropic(self, prompt: str) -> str:
        """Call the Anthropic Claude API."""
        client = self._get_client()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()

    def _call_openai(self, prompt: str) -> str:
        """Call the OpenAI API."""
        client = self._get_client()

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content.strip()

    def _generate_fallback(self, activity: ProjectActivity) -> str:
        """Generate a template-based fallback description."""
        name = activity.project_name

        # Build description from available data
        parts = []

        # Determine project type from languages/features
        if activity.languages:
            primary_lang = activity.languages[0]
            lang_hint = f"built with {primary_lang}"
        else:
            lang_hint = ""

        # Extract key capabilities from features
        capabilities = []
        if activity.recent_features:
            capabilities = activity.recent_features[:3]
        elif activity.recent_commits:
            # Extract verbs from commit messages
            for commit in activity.recent_commits[:5]:
                msg = commit.get('message', commit) if isinstance(commit, dict) else str(commit)
                if msg:
                    capabilities.append(msg.split(':')[-1].strip() if ':' in msg else msg)
                    if len(capabilities) >= 3:
                        break

        # Build the description
        if capabilities:
            cap_text = ", ".join(capabilities[:2])
            if lang_hint:
                return f"{name} is a software project {lang_hint}, featuring {cap_text}."
            return f"{name} is a software project featuring {cap_text}."

        if activity.description:
            return activity.description

        if lang_hint:
            return f"{name} is a software project {lang_hint}."

        return f"{name} is a software project under active development."

    def generate(self, activity: ProjectActivity) -> GeneratedDescription:
        """Generate a description for a project."""
        # Check for manual override first
        if activity.manual_override:
            return GeneratedDescription(
                project_name=activity.project_name,
                description=activity.manual_override,
                source="manual_override",
                confidence=1.0
            )

        # Try LLM generation
        try:
            project_data = self._format_project_data(activity)
            prompt = self.prompt_template.replace("{project_data}", project_data)

            if self.provider == "anthropic":
                description = self._call_anthropic(prompt)
            elif self.provider == "openai":
                description = self._call_openai(prompt)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            # Clean up the response
            description = description.strip('"\'')

            return GeneratedDescription(
                project_name=activity.project_name,
                description=description,
                source="llm",
                confidence=0.9
            )

        except Exception as e:
            # Log the error and fall back
            print(f"Warning: LLM generation failed for {activity.project_name}: {e}",
                  file=sys.stderr)

            fallback = self._generate_fallback(activity)
            return GeneratedDescription(
                project_name=activity.project_name,
                description=fallback,
                source="fallback",
                confidence=0.5
            )

    def generate_batch(self, activities: list[ProjectActivity]) -> list[GeneratedDescription]:
        """Generate descriptions for multiple projects."""
        return [self.generate(activity) for activity in activities]


def parse_activity_data(data: dict) -> list[ProjectActivity]:
    """Parse JSON activity data into ProjectActivity objects."""
    projects = []

    # Handle both single project and list of projects
    if isinstance(data, list):
        items = data
    elif "projects" in data:
        items = data["projects"]
    else:
        items = [data]

    for item in items:
        projects.append(ProjectActivity(
            project_name=item.get("project_name", item.get("name", "Unknown")),
            description=item.get("description"),
            recent_commits=item.get("recent_commits", []),
            top_contributors=item.get("top_contributors", []),
            languages=item.get("languages", []),
            last_active=item.get("last_active"),
            commit_count=item.get("commit_count", 0),
            recent_features=item.get("recent_features", []),
            recent_fixes=item.get("recent_fixes", []),
            recent_refactors=item.get("recent_refactors", []),
            manual_override=item.get("manual_override")
        ))

    return projects


def main():
    parser = argparse.ArgumentParser(
        description="Generate project descriptions from git activity data"
    )
    parser.add_argument(
        "--input", "-i",
        help="Input JSON file with git activity data"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read input from stdin"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file (defaults to stdout)"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="LLM provider to use (default: anthropic)"
    )
    parser.add_argument(
        "--prompt",
        help="Path to custom prompt template file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate fallback descriptions without calling LLM"
    )

    args = parser.parse_args()

    # Read input
    if args.stdin:
        input_data = json.load(sys.stdin)
    elif args.input:
        with open(args.input) as f:
            input_data = json.load(f)
    else:
        parser.error("Either --input or --stdin is required")

    # Parse activity data
    activities = parse_activity_data(input_data)

    # Generate descriptions
    if args.dry_run:
        # Use fallback generation only (but respect manual overrides)
        results = []
        generator = DescriptionGenerator(provider=args.provider, prompt_path=args.prompt)
        for activity in activities:
            if activity.manual_override:
                results.append(GeneratedDescription(
                    project_name=activity.project_name,
                    description=activity.manual_override,
                    source="manual_override",
                    confidence=1.0
                ))
            else:
                fallback = generator._generate_fallback(activity)
                results.append(GeneratedDescription(
                    project_name=activity.project_name,
                    description=fallback,
                    source="fallback",
                    confidence=0.5
                ))
    else:
        generator = DescriptionGenerator(provider=args.provider, prompt_path=args.prompt)
        results = generator.generate_batch(activities)

    # Format output
    output = {
        "descriptions": [
            {
                "project_name": r.project_name,
                "description": r.description,
                "source": r.source,
                "confidence": r.confidence
            }
            for r in results
        ]
    }

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
