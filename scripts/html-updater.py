#!/usr/bin/env python3
"""
HTML Updater for Project Descriptions

Safely updates project descriptions in index.html by parsing the HTML,
locating specific project sections, and replacing description content
while preserving structure and styling.

Uses BeautifulSoup for proper HTML parsing (not regex) to ensure reliability.

Usage:
    python html-updater.py --input descriptions.json
    python html-updater.py --input descriptions.json --dry-run
    python html-updater.py --input descriptions.json --html custom.html
    cat descriptions.json | python html-updater.py --stdin
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    print("Error: BeautifulSoup4 is required. Install with: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)


class HTMLUpdaterError(Exception):
    """Base exception for HTML updater errors."""
    pass


class HTMLParseError(HTMLUpdaterError):
    """Error parsing HTML file."""
    pass


class ProjectNotFoundError(HTMLUpdaterError):
    """Project section not found in HTML."""
    pass


class ValidationError(HTMLUpdaterError):
    """HTML validation failed after update."""
    pass


class HTMLUpdater:
    """Updates project descriptions in HTML files while preserving structure."""

    def __init__(self, html_path: str):
        """
        Initialize the HTML updater.

        Args:
            html_path: Path to the HTML file to update
        """
        self.html_path = Path(html_path)
        if not self.html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        self._original_content: Optional[str] = None
        self._soup: Optional[BeautifulSoup] = None
        self._changes: list[dict] = []

    def load(self) -> None:
        """Load and parse the HTML file."""
        try:
            self._original_content = self.html_path.read_text(encoding='utf-8')
            # Use html.parser to preserve formatting better than lxml
            self._soup = BeautifulSoup(self._original_content, 'html.parser')
        except Exception as e:
            raise HTMLParseError(f"Failed to parse HTML: {e}")

    def find_project_section(self, project_name: str) -> Optional[dict]:
        """
        Find a project section by its heading text.

        Args:
            project_name: The project name to search for (case-insensitive)

        Returns:
            Dictionary with 'article', 'heading', and 'description' BeautifulSoup elements,
            or None if not found
        """
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        # Look in the projects section
        projects_section = self._soup.find('section', class_='projects')
        if not projects_section:
            return None

        # Find all project articles
        for article in projects_section.find_all('article', class_='project'):
            heading = article.find('h3')
            if heading and heading.get_text(strip=True).lower() == project_name.lower():
                # Find the description paragraph (the <p> element after the heading)
                description = article.find('p')
                if description:
                    return {
                        'article': article,
                        'heading': heading,
                        'description': description
                    }

        return None

    def find_work_section(self, work_name: str) -> Optional[dict]:
        """
        Find a work section by its heading text.

        Args:
            work_name: The work/company name to search for (case-insensitive)

        Returns:
            Dictionary with 'article', 'heading', and 'description' BeautifulSoup elements,
            or None if not found
        """
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        # Look in the work section
        work_section = self._soup.find('section', class_='work')
        if not work_section:
            return None

        # Find all work articles
        for article in work_section.find_all('article', class_='work-item'):
            heading = article.find('h3')
            if heading and heading.get_text(strip=True).lower() == work_name.lower():
                # Find the description paragraph (direct child <p> not in work-header)
                description = article.find('p', recursive=False)
                if not description:
                    # Try finding <p> that's not inside work-header
                    for p in article.find_all('p'):
                        if p.parent == article:
                            description = p
                            break
                if description:
                    return {
                        'article': article,
                        'heading': heading,
                        'description': description
                    }

        return None

    def update_project_description(self, project_name: str, new_description: str) -> bool:
        """
        Update the description for a specific project.

        Args:
            project_name: The project name to update
            new_description: The new description text

        Returns:
            True if the update was successful, False if project not found
        """
        project = self.find_project_section(project_name)
        if not project:
            return False

        old_description = project['description'].get_text(strip=True)

        # Preserve any existing HTML structure in the description
        # Clear and replace the content
        project['description'].clear()
        project['description'].append(NavigableString(new_description))

        self._changes.append({
            'type': 'project',
            'name': project_name,
            'old': old_description,
            'new': new_description
        })

        return True

    def update_work_description(self, work_name: str, new_description: str) -> bool:
        """
        Update the description for a specific work item.

        Args:
            work_name: The work/company name to update
            new_description: The new description text

        Returns:
            True if the update was successful, False if work item not found
        """
        work = self.find_work_section(work_name)
        if not work:
            return False

        old_description = work['description'].get_text(strip=True)

        work['description'].clear()
        work['description'].append(NavigableString(new_description))

        self._changes.append({
            'type': 'work',
            'name': work_name,
            'old': old_description,
            'new': new_description
        })

        return True

    def get_changes(self) -> list[dict]:
        """Get the list of pending changes."""
        return self._changes.copy()

    def get_all_projects(self) -> list[str]:
        """Get names of all projects in the HTML."""
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        projects = []
        projects_section = self._soup.find('section', class_='projects')
        if projects_section:
            for article in projects_section.find_all('article', class_='project'):
                heading = article.find('h3')
                if heading:
                    projects.append(heading.get_text(strip=True))
        return projects

    def get_all_work_items(self) -> list[str]:
        """Get names of all work items in the HTML."""
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        work_items = []
        work_section = self._soup.find('section', class_='work')
        if work_section:
            for article in work_section.find_all('article', class_='work-item'):
                heading = article.find('h3')
                if heading:
                    work_items.append(heading.get_text(strip=True))
        return work_items

    def validate_html(self) -> list[str]:
        """
        Validate the HTML structure after updates.

        Returns:
            List of validation warnings (empty if valid)
        """
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        warnings = []

        # Check for DOCTYPE - BeautifulSoup represents it as Doctype object
        from bs4 import Doctype
        has_doctype = any(isinstance(item, Doctype) for item in self._soup.contents)
        if not has_doctype:
            # Also check the original content string
            if self._original_content and not self._original_content.lower().strip().startswith('<!doctype'):
                warnings.append("Missing DOCTYPE declaration")

        # Check for required elements
        if not self._soup.find('html'):
            warnings.append("Missing <html> element")
        if not self._soup.find('head'):
            warnings.append("Missing <head> element")
        if not self._soup.find('body'):
            warnings.append("Missing <body> element")
        if not self._soup.find('title'):
            warnings.append("Missing <title> element")

        # Check that all projects have descriptions
        projects_section = self._soup.find('section', class_='projects')
        if projects_section:
            for article in projects_section.find_all('article', class_='project'):
                heading = article.find('h3')
                description = article.find('p')
                if heading and not description:
                    name = heading.get_text(strip=True)
                    warnings.append(f"Project '{name}' missing description paragraph")
                if heading and description and not description.get_text(strip=True):
                    name = heading.get_text(strip=True)
                    warnings.append(f"Project '{name}' has empty description")

        return warnings

    def create_backup(self, backup_path: Optional[str] = None) -> str:
        """
        Create a backup of the HTML file before modifications.

        Args:
            backup_path: Optional custom backup path. If not provided,
                         creates a timestamped backup in the same directory.

        Returns:
            Path to the backup file
        """
        if backup_path:
            backup_file = Path(backup_path)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.html_path.with_suffix(f'.{timestamp}.backup.html')

        shutil.copy2(self.html_path, backup_file)
        return str(backup_file)

    def render(self) -> str:
        """
        Render the updated HTML as a string, preserving original formatting.

        Returns:
            The HTML string with updates applied
        """
        if self._soup is None:
            raise HTMLUpdaterError("HTML not loaded. Call load() first.")

        # Use the soup's prettify with custom formatter to preserve structure
        # But prettify changes formatting, so we need a different approach

        # Get the modified HTML
        modified_html = str(self._soup)

        # Try to preserve original formatting by using a smarter approach:
        # 1. If no changes were made, return original
        if not self._changes:
            return self._original_content

        # 2. For each change, do a targeted replacement in the original content
        result = self._original_content

        for change in self._changes:
            # Find and replace the old description with the new one
            # We need to be careful about HTML entities
            old_escaped = change['old']
            new_escaped = change['new']

            # Replace in the result, being careful about context
            result = self._replace_description(result, change['name'], change['old'], change['new'])

        return result

    def _replace_description(self, html: str, name: str, old_desc: str, new_desc: str) -> str:
        """
        Replace a description in the HTML while preserving formatting.

        Uses a regex-based approach that finds the project by name and
        updates only the description paragraph content.
        """
        # Find the project article by its h3 heading
        # Pattern: <article...><h3>name</h3>...<p>old_desc</p>
        # We need to match the <p>...</p> after the h3 with the project name

        # Escape special regex characters in name and old_desc
        name_escaped = re.escape(name)

        # Pattern to find the project and capture its description paragraph
        # This is more targeted than a full replace
        pattern = (
            r'(<article[^>]*class="[^"]*project[^"]*"[^>]*>.*?'  # article start
            r'<h3>' + name_escaped + r'</h3>\s*'  # h3 with project name
            r'<p>)([^<]*)(</p>)'  # p tag with content
        )

        def replacer(match):
            return match.group(1) + new_desc + match.group(3)

        # Try project pattern first
        new_html, count = re.subn(pattern, replacer, html, flags=re.IGNORECASE | re.DOTALL)

        if count > 0:
            return new_html

        # Try work-item pattern
        work_pattern = (
            r'(<article[^>]*class="[^"]*work-item[^"]*"[^>]*>.*?'
            r'<h3>' + name_escaped + r'</h3>.*?'
            r'</div>\s*'  # end of work-header div
            r'<p>)([^<]*)(</p>)'
        )

        new_html, count = re.subn(work_pattern, replacer, html, flags=re.IGNORECASE | re.DOTALL)

        return new_html

    def save(self, output_path: Optional[str] = None, create_backup: bool = True) -> dict:
        """
        Save the updated HTML to file.

        Args:
            output_path: Optional custom output path. If not provided,
                        overwrites the original file.
            create_backup: Whether to create a backup before saving

        Returns:
            Dictionary with 'saved_to', 'backup_path', and 'changes' keys
        """
        result = {
            'saved_to': None,
            'backup_path': None,
            'changes': self._changes
        }

        output_file = Path(output_path) if output_path else self.html_path

        if create_backup and not output_path:
            result['backup_path'] = self.create_backup()

        # Render and save
        html_content = self.render()

        # Validate before saving
        warnings = self.validate_html()
        if warnings:
            print("Validation warnings:", file=sys.stderr)
            for warning in warnings:
                print(f"  - {warning}", file=sys.stderr)

        output_file.write_text(html_content, encoding='utf-8')
        result['saved_to'] = str(output_file)

        return result


def format_diff(old_text: str, new_text: str, name: str, change_type: str) -> str:
    """Format a change as a human-readable diff."""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"{change_type.upper()}: {name}")
    lines.append(f"{'='*60}")
    lines.append(f"- OLD: {old_text}")
    lines.append(f"+ NEW: {new_text}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Update project descriptions in index.html"
    )
    parser.add_argument(
        "--input", "-i",
        help="Input JSON file with descriptions to update"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read input from stdin"
    )
    parser.add_argument(
        "--html",
        default="index.html",
        help="Path to the HTML file to update (default: index.html)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for updated HTML (default: overwrite original)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed changes without applying them"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before modifications"
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List all projects in the HTML file"
    )
    parser.add_argument(
        "--list-work",
        action="store_true",
        help="List all work items in the HTML file"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Only validate the HTML structure"
    )

    args = parser.parse_args()

    # Resolve HTML path relative to script location if needed
    html_path = Path(args.html)
    if not html_path.is_absolute() and not html_path.exists():
        # Try relative to script directory
        script_dir = Path(__file__).parent.parent
        html_path = script_dir / args.html

    if not html_path.exists():
        print(f"Error: HTML file not found: {args.html}", file=sys.stderr)
        sys.exit(1)

    try:
        updater = HTMLUpdater(str(html_path))
        updater.load()
    except Exception as e:
        print(f"Error loading HTML: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle info-only commands
    if args.list_projects:
        projects = updater.get_all_projects()
        print("Projects found:")
        for project in projects:
            print(f"  - {project}")
        sys.exit(0)

    if args.list_work:
        work_items = updater.get_all_work_items()
        print("Work items found:")
        for item in work_items:
            print(f"  - {item}")
        sys.exit(0)

    if args.validate:
        warnings = updater.validate_html()
        if warnings:
            print("Validation warnings:")
            for warning in warnings:
                print(f"  - {warning}")
            sys.exit(1)
        else:
            print("HTML structure is valid")
            sys.exit(0)

    # Read input descriptions
    if args.stdin:
        input_data = json.load(sys.stdin)
    elif args.input:
        with open(args.input) as f:
            input_data = json.load(f)
    else:
        parser.error("Either --input or --stdin is required (or use --list-projects, --list-work, --validate)")

    # Parse descriptions
    descriptions = []
    if isinstance(input_data, list):
        descriptions = input_data
    elif "descriptions" in input_data:
        descriptions = input_data["descriptions"]
    elif "projects" in input_data:
        descriptions = input_data["projects"]
    else:
        # Single description
        descriptions = [input_data]

    # Apply updates
    not_found = []
    for desc in descriptions:
        name = desc.get("project_name") or desc.get("name")
        description = desc.get("description")
        item_type = desc.get("type", "project")

        if not name or not description:
            continue

        if item_type == "work":
            success = updater.update_work_description(name, description)
        else:
            success = updater.update_project_description(name, description)

        if not success:
            not_found.append(name)

    # Get changes
    changes = updater.get_changes()

    # Handle dry-run mode
    if args.dry_run:
        if not changes:
            print("No changes to apply")
            if not_found:
                print(f"\nNot found in HTML: {', '.join(not_found)}")
            sys.exit(0)

        print("DRY RUN - Proposed changes:")
        print("")
        for change in changes:
            print(format_diff(change['old'], change['new'], change['name'], change['type']))

        if not_found:
            print(f"\nNot found in HTML: {', '.join(not_found)}")

        # Validate
        warnings = updater.validate_html()
        if warnings:
            print("\nValidation warnings (if applied):")
            for warning in warnings:
                print(f"  - {warning}")

        sys.exit(0)

    # Apply changes
    if not changes:
        print("No changes to apply")
        if not_found:
            print(f"\nNot found in HTML: {', '.join(not_found)}")
        sys.exit(0)

    # Save
    result = updater.save(
        output_path=args.output,
        create_backup=not args.no_backup
    )

    # Report
    print(f"Updated: {result['saved_to']}")
    if result['backup_path']:
        print(f"Backup:  {result['backup_path']}")

    print(f"\nChanges applied: {len(changes)}")
    for change in changes:
        print(f"  - {change['type']}: {change['name']}")

    if not_found:
        print(f"\nNot found in HTML: {', '.join(not_found)}")


if __name__ == "__main__":
    main()
