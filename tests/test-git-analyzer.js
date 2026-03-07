/**
 * Unit tests for git-analyzer.js
 *
 * Run with: node tests/test-git-analyzer.js
 */

const path = require("path");
const fs = require("fs");
const os = require("os");
const { execSync } = require("child_process");

// Import the module under test
const {
  analyzeGitActivity,
  classifyCommit,
  parseCommit,
  validateRepository,
  generateInsights,
  GitAnalyzerError,
  RepositoryNotFoundError,
  NotAGitRepositoryError,
  PermissionError,
  COMMIT_TYPE_PATTERNS,
} = require("../scripts/git-analyzer.js");

// Simple test framework
let testsPassed = 0;
let testsFailed = 0;
const testResults = [];

function describe(suiteName, fn) {
  console.log(`\n${suiteName}`);
  fn();
}

function it(testName, fn) {
  try {
    fn();
    testsPassed++;
    console.log(`  ✓ ${testName}`);
    testResults.push({ name: testName, passed: true });
  } catch (err) {
    testsFailed++;
    console.log(`  ✗ ${testName}`);
    console.log(`    Error: ${err.message}`);
    testResults.push({ name: testName, passed: false, error: err.message });
  }
}

function assertEqual(actual, expected, message = "") {
  if (actual !== expected) {
    throw new Error(
      `${message ? message + ": " : ""}Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
    );
  }
}

function assertDeepEqual(actual, expected, message = "") {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${message ? message + ": " : ""}Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
    );
  }
}

function assertTrue(value, message = "") {
  if (!value) {
    throw new Error(`${message ? message + ": " : ""}Expected truthy value, got ${value}`);
  }
}

function assertFalse(value, message = "") {
  if (value) {
    throw new Error(`${message ? message + ": " : ""}Expected falsy value, got ${value}`);
  }
}

function assertThrows(fn, errorType, message = "") {
  try {
    fn();
    throw new Error(`${message ? message + ": " : ""}Expected function to throw ${errorType.name}`);
  } catch (err) {
    if (!(err instanceof errorType)) {
      throw new Error(
        `${message ? message + ": " : ""}Expected ${errorType.name}, got ${err.constructor.name}: ${err.message}`
      );
    }
  }
}

function assertContains(array, value, message = "") {
  if (!array.includes(value)) {
    throw new Error(
      `${message ? message + ": " : ""}Expected array to contain ${JSON.stringify(value)}`
    );
  }
}

// Helper to create a temporary git repository for testing
function createTempRepo(options = {}) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "git-analyzer-test-"));

  execSync("git init", { cwd: tmpDir, stdio: "pipe" });
  execSync('git config user.email "test@example.com"', { cwd: tmpDir, stdio: "pipe" });
  execSync('git config user.name "Test User"', { cwd: tmpDir, stdio: "pipe" });

  if (!options.empty) {
    // Create initial commit
    fs.writeFileSync(path.join(tmpDir, "README.md"), "# Test Project\n");
    execSync("git add README.md", { cwd: tmpDir, stdio: "pipe" });
    execSync('git commit -m "docs: initial commit"', { cwd: tmpDir, stdio: "pipe" });
  }

  return tmpDir;
}

function cleanupTempRepo(tmpDir) {
  try {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  } catch (err) {
    // Ignore cleanup errors
  }
}

// ============================================================================
// Tests
// ============================================================================

describe("classifyCommit", () => {
  it("should classify conventional commit prefixes correctly", () => {
    assertEqual(classifyCommit("feat: add new feature"), "feature");
    assertEqual(classifyCommit("feat(auth): add login"), "feature");
    assertEqual(classifyCommit("fix: resolve bug"), "fix");
    assertEqual(classifyCommit("fix(api): handle edge case"), "fix");
    assertEqual(classifyCommit("docs: update readme"), "docs");
    assertEqual(classifyCommit("refactor: restructure code"), "refactor");
    assertEqual(classifyCommit("test: add unit tests"), "test");
    assertEqual(classifyCommit("style: format code"), "style");
    assertEqual(classifyCommit("chore: update deps"), "chore");
    assertEqual(classifyCommit("perf: optimize query"), "perf");
  });

  it("should classify feature commits by keywords", () => {
    assertEqual(classifyCommit("Add new authentication system"), "feature");
    assertEqual(classifyCommit("Implement user dashboard"), "feature");
    assertEqual(classifyCommit("New payment integration"), "feature");
    assertEqual(classifyCommit("Adding support for OAuth"), "feature");
  });

  it("should classify fix commits by keywords", () => {
    assertEqual(classifyCommit("Fix login bug"), "fix");
    assertEqual(classifyCommit("Resolved issue with API"), "fix");
    assertEqual(classifyCommit("Patched security vulnerability"), "fix");
    assertEqual(classifyCommit("Bug in user registration"), "fix");
  });

  it("should classify docs commits by keywords", () => {
    assertEqual(classifyCommit("Update documentation"), "docs");
    assertEqual(classifyCommit("README updates"), "docs");
    assertEqual(classifyCommit("Add inline comments"), "docs");
  });

  it("should classify refactor commits by keywords", () => {
    assertEqual(classifyCommit("Refactored auth module"), "refactor");
    assertEqual(classifyCommit("Restructure project layout"), "refactor");
    assertEqual(classifyCommit("Clean up dead code"), "refactor");
  });

  it("should classify chore commits by keywords", () => {
    assertEqual(classifyCommit("Update dependencies"), "chore");
    assertEqual(classifyCommit("Bump version to 2.0"), "chore");
    assertEqual(classifyCommit("Upgrade Node.js"), "chore");
  });

  it("should classify perf commits by keywords", () => {
    assertEqual(classifyCommit("Optimize database queries"), "perf");
    assertEqual(classifyCommit("Performance improvements"), "perf");
    assertEqual(classifyCommit("Speed up rendering"), "perf");
  });

  it("should return other for unclassifiable commits", () => {
    assertEqual(classifyCommit("WIP"), "other");
    assertEqual(classifyCommit("misc changes"), "other");
    assertEqual(classifyCommit("stuff"), "other");
  });

  it("should be case insensitive", () => {
    assertEqual(classifyCommit("FEAT: ADD FEATURE"), "feature");
    assertEqual(classifyCommit("FIX: RESOLVE BUG"), "fix");
    assertEqual(classifyCommit("DOCS: UPDATE README"), "docs");
  });
});

describe("parseCommit", () => {
  it("should parse a valid commit entry", () => {
    const entry = `abc123def
John Doe
2024-01-15T10:30:00Z
feat: add new feature

This is the commit body`;

    const commit = parseCommit(entry);

    assertEqual(commit.hash, "abc123def");
    assertEqual(commit.author, "John Doe");
    assertEqual(commit.timestamp, "2024-01-15T10:30:00Z");
    assertTrue(commit.message.includes("feat: add new feature"));
    assertEqual(commit.shortMessage, "feat: add new feature");
  });

  it("should handle single-line commit messages", () => {
    const entry = `abc123def
John Doe
2024-01-15T10:30:00Z
Simple commit message`;

    const commit = parseCommit(entry);

    assertEqual(commit.shortMessage, "Simple commit message");
    assertEqual(commit.message, "Simple commit message");
  });

  it("should return null for invalid entries", () => {
    assertEqual(parseCommit(""), null);
    assertEqual(parseCommit("only\ntwo\nlines"), null);
    assertEqual(parseCommit("   "), null);
  });

  it("should generate valid ISO date", () => {
    const entry = `abc123def
John Doe
2024-01-15T10:30:00Z
Test commit`;

    const commit = parseCommit(entry);
    const date = new Date(commit.date);

    assertTrue(!isNaN(date.getTime()), "Date should be valid");
  });
});

describe("validateRepository", () => {
  it("should throw RepositoryNotFoundError for non-existent path", () => {
    assertThrows(
      () => validateRepository("/non/existent/path/12345"),
      RepositoryNotFoundError
    );
  });

  it("should throw NotAGitRepositoryError for non-git directory", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "not-git-"));
    try {
      assertThrows(() => validateRepository(tmpDir), NotAGitRepositoryError);
    } finally {
      cleanupTempRepo(tmpDir);
    }
  });

  it("should not throw for valid git repository", () => {
    const tmpRepo = createTempRepo();
    try {
      validateRepository(tmpRepo); // Should not throw
      assertTrue(true);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });
});

describe("analyzeGitActivity", () => {
  it("should analyze a repository with commits", () => {
    const tmpRepo = createTempRepo();
    try {
      // Add more commits
      fs.writeFileSync(path.join(tmpRepo, "feature.js"), "// feature code");
      execSync("git add feature.js", { cwd: tmpRepo, stdio: "pipe" });
      execSync('git commit -m "feat: add new feature"', { cwd: tmpRepo, stdio: "pipe" });

      fs.writeFileSync(path.join(tmpRepo, "fix.js"), "// fix code");
      execSync("git add fix.js", { cwd: tmpRepo, stdio: "pipe" });
      execSync('git commit -m "fix: resolve critical bug"', { cwd: tmpRepo, stdio: "pipe" });

      const result = analyzeGitActivity(tmpRepo);

      assertEqual(result.summary.totalCommits, 3);
      assertTrue(result.summary.commitsByType.docs >= 1);
      assertTrue(result.summary.commitsByType.feature >= 1);
      assertTrue(result.summary.commitsByType.fix >= 1);
      assertTrue(result.commits.length === 3);
      assertTrue(result.repository.includes(tmpRepo.split(path.sep).pop()));
      assertTrue(result.analyzedAt !== undefined);
      assertTrue(Array.isArray(result.insights));
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should handle repository with no commits", () => {
    const tmpRepo = createTempRepo({ empty: true });
    try {
      const result = analyzeGitActivity(tmpRepo);

      assertEqual(result.summary.totalCommits, 0);
      assertEqual(result.commits.length, 0);
      assertContains(result.insights, "No commits found in the specified range");
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should respect limit option", () => {
    const tmpRepo = createTempRepo();
    try {
      // Add multiple commits
      for (let i = 0; i < 5; i++) {
        fs.writeFileSync(path.join(tmpRepo, `file${i}.js`), `// file ${i}`);
        execSync(`git add file${i}.js`, { cwd: tmpRepo, stdio: "pipe" });
        execSync(`git commit -m "feat: add file ${i}"`, { cwd: tmpRepo, stdio: "pipe" });
      }

      const result = analyzeGitActivity(tmpRepo, { limit: 3 });

      assertEqual(result.summary.totalCommits, 3);
      assertEqual(result.commits.length, 3);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should include file change statistics", () => {
    const tmpRepo = createTempRepo();
    try {
      fs.writeFileSync(path.join(tmpRepo, "stats.js"), "line1\nline2\nline3\n");
      execSync("git add stats.js", { cwd: tmpRepo, stdio: "pipe" });
      execSync('git commit -m "feat: add file with lines"', { cwd: tmpRepo, stdio: "pipe" });

      const result = analyzeGitActivity(tmpRepo);
      const lastCommit = result.commits[0];

      assertTrue(lastCommit.stats.additions >= 3);
      assertTrue(lastCommit.stats.filesChanged >= 1);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should include branch information", () => {
    const tmpRepo = createTempRepo();
    try {
      const result = analyzeGitActivity(tmpRepo);

      assertTrue(result.branches !== undefined);
      assertTrue(result.branches.current !== undefined);
      assertTrue(Array.isArray(result.branches.local));
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should track top contributors", () => {
    const tmpRepo = createTempRepo();
    try {
      const result = analyzeGitActivity(tmpRepo);

      assertTrue(result.summary.topContributors.length > 0);
      assertEqual(result.summary.topContributors[0].name, "Test User");
      assertTrue(result.summary.topContributors[0].commits >= 1);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });

  it("should throw RepositoryNotFoundError for invalid path", () => {
    assertThrows(
      () => analyzeGitActivity("/invalid/path/12345"),
      RepositoryNotFoundError
    );
  });

  it("should calculate date range correctly", () => {
    const tmpRepo = createTempRepo();
    try {
      const result = analyzeGitActivity(tmpRepo);

      assertTrue(result.summary.dateRange !== null);
      assertTrue(result.summary.dateRange.oldest !== undefined);
      assertTrue(result.summary.dateRange.newest !== undefined);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });
});

describe("generateInsights", () => {
  it("should generate insights for empty commits", () => {
    const insights = generateInsights([], {}, []);
    assertContains(insights, "No recent activity detected");
  });

  it("should generate activity level insight", () => {
    const commits = [
      { timestamp: new Date().toISOString() },
      { timestamp: new Date(Date.now() - 86400000).toISOString() },
    ];
    const insights = generateInsights(commits, { feature: 2 }, []);

    assertTrue(insights.some((i) => i.includes("commits per day")));
  });

  it("should generate type-specific insights", () => {
    const commits = [{ timestamp: new Date().toISOString() }];
    const commitsByType = { feature: 3, fix: 2, docs: 1, refactor: 1 };
    const insights = generateInsights(commits, commitsByType, []);

    assertTrue(insights.some((i) => i.includes("feature")));
    assertTrue(insights.some((i) => i.includes("bug fix")));
    assertTrue(insights.some((i) => i.includes("documentation")));
    assertTrue(insights.some((i) => i.includes("refactoring")));
  });

  it("should include top contributor insight", () => {
    const commits = [{ timestamp: new Date().toISOString() }];
    const topContributors = [{ name: "Alice", commits: 10 }];
    const insights = generateInsights(commits, {}, topContributors);

    assertTrue(insights.some((i) => i.includes("Alice")));
    assertTrue(insights.some((i) => i.includes("Top contributor")));
  });
});

describe("COMMIT_TYPE_PATTERNS", () => {
  it("should have all required commit types", () => {
    const requiredTypes = ["feature", "fix", "docs", "refactor", "test", "style", "chore", "perf"];

    for (const type of requiredTypes) {
      assertTrue(COMMIT_TYPE_PATTERNS[type] !== undefined, `Missing type: ${type}`);
      assertTrue(Array.isArray(COMMIT_TYPE_PATTERNS[type]), `${type} should be an array`);
      assertTrue(COMMIT_TYPE_PATTERNS[type].length > 0, `${type} should have patterns`);
    }
  });

  it("should have valid regex patterns", () => {
    for (const [type, patterns] of Object.entries(COMMIT_TYPE_PATTERNS)) {
      for (const pattern of patterns) {
        assertTrue(pattern instanceof RegExp, `Pattern in ${type} should be RegExp`);
      }
    }
  });
});

describe("Error classes", () => {
  it("should have correct error codes", () => {
    const repoNotFound = new RepositoryNotFoundError("/path");
    assertEqual(repoNotFound.code, "REPO_NOT_FOUND");

    const notGitRepo = new NotAGitRepositoryError("/path");
    assertEqual(notGitRepo.code, "NOT_GIT_REPO");

    const permissionError = new PermissionError("/path");
    assertEqual(permissionError.code, "PERMISSION_DENIED");
  });

  it("should be instances of GitAnalyzerError", () => {
    assertTrue(new RepositoryNotFoundError("/path") instanceof GitAnalyzerError);
    assertTrue(new NotAGitRepositoryError("/path") instanceof GitAnalyzerError);
    assertTrue(new PermissionError("/path") instanceof GitAnalyzerError);
  });
});

describe("Integration: Full workflow", () => {
  it("should produce valid JSON output structure", () => {
    const tmpRepo = createTempRepo();
    try {
      // Add various commit types
      const commits = [
        { file: "feat.js", msg: "feat: implement auth" },
        { file: "fix.js", msg: "fix: resolve login bug" },
        { file: "DOCS.md", msg: "docs: add API docs" },
        { file: "refactor.js", msg: "refactor: clean up code" },
      ];

      for (const { file, msg } of commits) {
        fs.writeFileSync(path.join(tmpRepo, file), `// ${file}`);
        execSync(`git add ${file}`, { cwd: tmpRepo, stdio: "pipe" });
        execSync(`git commit -m "${msg}"`, { cwd: tmpRepo, stdio: "pipe" });
      }

      const result = analyzeGitActivity(tmpRepo);

      // Verify JSON structure
      assertTrue(typeof result === "object");
      assertTrue(typeof result.repository === "string");
      assertTrue(typeof result.analyzedAt === "string");
      assertTrue(typeof result.summary === "object");
      assertTrue(typeof result.summary.totalCommits === "number");
      assertTrue(typeof result.summary.commitsByType === "object");
      assertTrue(Array.isArray(result.summary.topContributors));
      assertTrue(typeof result.branches === "object");
      assertTrue(Array.isArray(result.commits));
      assertTrue(Array.isArray(result.insights));

      // Verify commit structure
      for (const commit of result.commits) {
        assertTrue(typeof commit.hash === "string");
        assertTrue(typeof commit.shortHash === "string");
        assertTrue(typeof commit.author === "string");
        assertTrue(typeof commit.date === "string");
        assertTrue(typeof commit.type === "string");
        assertTrue(typeof commit.shortMessage === "string");
        assertTrue(typeof commit.stats === "object");
      }

      // Verify it's valid JSON
      const jsonString = JSON.stringify(result);
      const parsed = JSON.parse(jsonString);
      assertTrue(parsed !== null);
    } finally {
      cleanupTempRepo(tmpRepo);
    }
  });
});

// ============================================================================
// Run tests and report
// ============================================================================

console.log("\n" + "=".repeat(60));
console.log("Test Summary");
console.log("=".repeat(60));
console.log(`Passed: ${testsPassed}`);
console.log(`Failed: ${testsFailed}`);
console.log(`Total:  ${testsPassed + testsFailed}`);
console.log("=".repeat(60));

if (testsFailed > 0) {
  console.log("\nFailed tests:");
  for (const result of testResults) {
    if (!result.passed) {
      console.log(`  - ${result.name}: ${result.error}`);
    }
  }
  process.exit(1);
} else {
  console.log("\nAll tests passed!");
  process.exit(0);
}
