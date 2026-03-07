#!/usr/bin/env python3
"""
Unit tests for html-updater.py

Run with: python tests/test-html-updater.py
Or with pytest: pytest tests/test-html-updater.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from importlib import import_module

# Import the module
html_updater = import_module("html-updater")
HTMLUpdater = html_updater.HTMLUpdater
HTMLUpdaterError = html_updater.HTMLUpdaterError
HTMLParseError = html_updater.HTMLParseError
ProjectNotFoundError = html_updater.ProjectNotFoundError
ValidationError = html_updater.ValidationError
format_diff = html_updater.format_diff


# Sample HTML content for testing
SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Test Page</title>
</head>
<body>
  <main>
    <section class="projects">
      <h2>Projects</h2>
      <div class="project-list">
        <article class="project">
          <h3>ProjectA</h3>
          <p>Description of Project A.</p>
        </article>
        <article class="project">
          <h3>ProjectB</h3>
          <p>Description of Project B with more details.</p>
        </article>
        <article class="project">
          <h3>ProjectC</h3>
          <p>Project C description here.</p>
        </article>
      </div>
    </section>

    <section class="work">
      <h2>Work</h2>
      <div class="work-list">
        <article class="work-item current">
          <div class="work-header">
            <h3>CompanyA</h3>
            <span class="period">Current</span>
          </div>
          <p>Working at Company A on interesting projects.</p>
        </article>
        <article class="work-item">
          <div class="work-header">
            <h3>CompanyB</h3>
            <span class="period">2020 - 2024</span>
          </div>
          <p>Worked at Company B building software.</p>
        </article>
      </div>
    </section>
  </main>
</body>
</html>
"""

INVALID_HTML = """
<html>
<body>
<p>Missing DOCTYPE and head
</body>
"""


class TestHTMLUpdater(unittest.TestCase):
    """Test the HTMLUpdater class."""

    def setUp(self):
        """Create a temporary HTML file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.html_path = Path(self.temp_dir) / "test.html"
        self.html_path.write_text(SAMPLE_HTML, encoding='utf-8')

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_html(self):
        """Test loading and parsing HTML file."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()
        # Should not raise any errors
        self.assertIsNotNone(updater._soup)

    def test_load_nonexistent_file(self):
        """Test loading a non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            HTMLUpdater("/nonexistent/path/file.html")

    def test_find_project_section(self):
        """Test finding a project section by name."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        project = updater.find_project_section("ProjectA")
        self.assertIsNotNone(project)
        self.assertEqual(project['heading'].get_text(strip=True), "ProjectA")
        self.assertIn("Description of Project A", project['description'].get_text())

    def test_find_project_case_insensitive(self):
        """Test finding projects is case-insensitive."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        project = updater.find_project_section("projecta")
        self.assertIsNotNone(project)
        self.assertEqual(project['heading'].get_text(strip=True), "ProjectA")

    def test_find_nonexistent_project(self):
        """Test finding a non-existent project returns None."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        project = updater.find_project_section("NonExistentProject")
        self.assertIsNone(project)

    def test_find_work_section(self):
        """Test finding a work section by name."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        work = updater.find_work_section("CompanyA")
        self.assertIsNotNone(work)
        self.assertEqual(work['heading'].get_text(strip=True), "CompanyA")
        self.assertIn("Working at Company A", work['description'].get_text())

    def test_get_all_projects(self):
        """Test getting list of all projects."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        projects = updater.get_all_projects()
        self.assertEqual(len(projects), 3)
        self.assertIn("ProjectA", projects)
        self.assertIn("ProjectB", projects)
        self.assertIn("ProjectC", projects)

    def test_get_all_work_items(self):
        """Test getting list of all work items."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        work_items = updater.get_all_work_items()
        self.assertEqual(len(work_items), 2)
        self.assertIn("CompanyA", work_items)
        self.assertIn("CompanyB", work_items)

    def test_update_project_description(self):
        """Test updating a project description."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        new_desc = "This is the new description for Project A."
        success = updater.update_project_description("ProjectA", new_desc)

        self.assertTrue(success)
        self.assertEqual(len(updater.get_changes()), 1)

        change = updater.get_changes()[0]
        self.assertEqual(change['type'], 'project')
        self.assertEqual(change['name'], 'ProjectA')
        self.assertEqual(change['new'], new_desc)

    def test_update_nonexistent_project(self):
        """Test updating a non-existent project returns False."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        success = updater.update_project_description("NonExistent", "New desc")
        self.assertFalse(success)
        self.assertEqual(len(updater.get_changes()), 0)

    def test_update_work_description(self):
        """Test updating a work description."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        new_desc = "Updated work description for Company A."
        success = updater.update_work_description("CompanyA", new_desc)

        self.assertTrue(success)
        self.assertEqual(len(updater.get_changes()), 1)

        change = updater.get_changes()[0]
        self.assertEqual(change['type'], 'work')
        self.assertEqual(change['name'], 'CompanyA')

    def test_multiple_updates(self):
        """Test applying multiple updates."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        updater.update_project_description("ProjectA", "New A desc")
        updater.update_project_description("ProjectB", "New B desc")
        updater.update_work_description("CompanyA", "New Company A desc")

        changes = updater.get_changes()
        self.assertEqual(len(changes), 3)

    def test_validate_html_valid(self):
        """Test validation of valid HTML."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        warnings = updater.validate_html()
        self.assertEqual(len(warnings), 0)

    def test_validate_html_invalid(self):
        """Test validation catches missing elements."""
        invalid_path = Path(self.temp_dir) / "invalid.html"
        invalid_path.write_text(INVALID_HTML, encoding='utf-8')

        updater = HTMLUpdater(str(invalid_path))
        updater.load()

        warnings = updater.validate_html()
        self.assertGreater(len(warnings), 0)
        # Should warn about missing DOCTYPE, head, title
        warning_text = " ".join(warnings)
        self.assertIn("DOCTYPE", warning_text)

    def test_create_backup(self):
        """Test backup file creation."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        backup_path = updater.create_backup()

        self.assertTrue(Path(backup_path).exists())
        self.assertIn("backup", backup_path)

        # Content should match
        original = self.html_path.read_text()
        backup_content = Path(backup_path).read_text()
        self.assertEqual(original, backup_content)

    def test_create_backup_custom_path(self):
        """Test backup to custom path."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        custom_backup = Path(self.temp_dir) / "my_backup.html"
        backup_path = updater.create_backup(str(custom_backup))

        self.assertEqual(backup_path, str(custom_backup))
        self.assertTrue(custom_backup.exists())

    def test_render_preserves_content(self):
        """Test rendering preserves content when no changes."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        rendered = updater.render()
        # Should be the same as original since no changes
        original = self.html_path.read_text()
        self.assertEqual(rendered, original)

    def test_render_applies_changes(self):
        """Test rendering includes changes."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        new_desc = "Completely new description text."
        updater.update_project_description("ProjectA", new_desc)

        rendered = updater.render()
        self.assertIn(new_desc, rendered)
        self.assertNotIn("Description of Project A", rendered)

    def test_save_creates_backup(self):
        """Test save creates backup by default."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()
        updater.update_project_description("ProjectA", "New description")

        result = updater.save()

        self.assertIsNotNone(result['backup_path'])
        self.assertTrue(Path(result['backup_path']).exists())

    def test_save_no_backup(self):
        """Test save without backup."""
        output_path = Path(self.temp_dir) / "output.html"

        updater = HTMLUpdater(str(self.html_path))
        updater.load()
        updater.update_project_description("ProjectA", "New description")

        result = updater.save(output_path=str(output_path), create_backup=False)

        self.assertIsNone(result['backup_path'])
        self.assertTrue(output_path.exists())

    def test_save_to_different_file(self):
        """Test saving to a different file."""
        output_path = Path(self.temp_dir) / "output.html"

        updater = HTMLUpdater(str(self.html_path))
        updater.load()
        updater.update_project_description("ProjectA", "New description")

        result = updater.save(output_path=str(output_path))

        self.assertEqual(result['saved_to'], str(output_path))
        self.assertTrue(output_path.exists())

        # Original should be unchanged
        original = self.html_path.read_text()
        self.assertIn("Description of Project A", original)

    def test_error_before_load(self):
        """Test operations before load raise errors."""
        updater = HTMLUpdater(str(self.html_path))

        with self.assertRaises(HTMLUpdaterError):
            updater.find_project_section("ProjectA")

        with self.assertRaises(HTMLUpdaterError):
            updater.get_all_projects()

        with self.assertRaises(HTMLUpdaterError):
            updater.validate_html()


class TestFormatDiff(unittest.TestCase):
    """Test the format_diff helper function."""

    def test_format_diff_output(self):
        """Test diff formatting."""
        diff = format_diff("old text", "new text", "TestProject", "project")

        self.assertIn("PROJECT: TestProject", diff)
        self.assertIn("- OLD: old text", diff)
        self.assertIn("+ NEW: new text", diff)


class TestPreserveFormatting(unittest.TestCase):
    """Test that formatting is preserved after updates."""

    def setUp(self):
        """Create a temporary HTML file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.html_path = Path(self.temp_dir) / "test.html"
        self.html_path.write_text(SAMPLE_HTML, encoding='utf-8')

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_preserves_indentation(self):
        """Test that indentation is preserved."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        updater.update_project_description("ProjectA", "New description text.")
        rendered = updater.render()

        # Check that basic structure is preserved
        self.assertIn("  <main>", rendered)
        self.assertIn("    <section class=\"projects\">", rendered)

    def test_preserves_other_projects(self):
        """Test that other projects are not affected."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        updater.update_project_description("ProjectA", "New A description")
        rendered = updater.render()

        # ProjectB and ProjectC should be unchanged
        self.assertIn("Description of Project B with more details.", rendered)
        self.assertIn("Project C description here.", rendered)

    def test_preserves_html_structure(self):
        """Test that HTML structure elements are preserved."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        updater.update_project_description("ProjectA", "New description")
        rendered = updater.render()

        # All structural elements should be present
        self.assertIn('<!DOCTYPE html>', rendered)
        self.assertIn('<html lang="en">', rendered)
        self.assertIn('<head>', rendered)
        self.assertIn('</head>', rendered)
        self.assertIn('<body>', rendered)
        self.assertIn('</body>', rendered)
        self.assertIn('<article class="project">', rendered)


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflows."""

    def setUp(self):
        """Create a temporary HTML file for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.html_path = Path(self.temp_dir) / "test.html"
        self.html_path.write_text(SAMPLE_HTML, encoding='utf-8')

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_update_workflow(self):
        """Test complete update workflow."""
        # 1. Load HTML
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        # 2. List projects
        projects = updater.get_all_projects()
        self.assertEqual(len(projects), 3)

        # 3. Update descriptions
        updater.update_project_description("ProjectA", "Updated A")
        updater.update_project_description("ProjectB", "Updated B")

        # 4. Validate
        warnings = updater.validate_html()
        self.assertEqual(len(warnings), 0)

        # 5. Save
        result = updater.save()

        # 6. Verify
        saved_content = self.html_path.read_text()
        self.assertIn("Updated A", saved_content)
        self.assertIn("Updated B", saved_content)
        self.assertIn("Project C description here.", saved_content)

    def test_json_input_workflow(self):
        """Test workflow with JSON input."""
        # Create JSON input
        json_input = {
            "descriptions": [
                {"project_name": "ProjectA", "description": "JSON Updated A"},
                {"project_name": "ProjectB", "description": "JSON Updated B"},
                {"project_name": "NonExistent", "description": "Should be skipped"},
            ]
        }

        # Load HTML
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        # Apply updates from JSON
        not_found = []
        for desc in json_input["descriptions"]:
            success = updater.update_project_description(
                desc["project_name"],
                desc["description"]
            )
            if not success:
                not_found.append(desc["project_name"])

        # Verify
        self.assertEqual(len(updater.get_changes()), 2)
        self.assertIn("NonExistent", not_found)

    def test_work_and_project_updates(self):
        """Test updating both work and project items."""
        updater = HTMLUpdater(str(self.html_path))
        updater.load()

        updater.update_project_description("ProjectA", "New project desc")
        updater.update_work_description("CompanyA", "New work desc")

        changes = updater.get_changes()
        self.assertEqual(len(changes), 2)

        types = [c['type'] for c in changes]
        self.assertIn('project', types)
        self.assertIn('work', types)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
