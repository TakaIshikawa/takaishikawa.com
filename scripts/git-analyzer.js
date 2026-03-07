#!/usr/bin/env node
/**
 * Git Activity Analyzer
 *
 * Reads git commit history from local project repositories, analyzes recent activity,
 * and generates structured summaries suitable for project descriptions.
 *
 * Usage:
 *   node git-analyzer.js <repository-path> [options]
 *
 * Options:
 *   --since <date>     Only include commits after this date (e.g., "2024-01-01", "1 month ago")
 *   --limit <number>   Maximum number of commits to analyze (default: 100)
 *   --output <file>    Write JSON output to file instead of stdout
 *   --pretty           Pretty-print JSON output
 */

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

/**
 * Conventional commit prefix patterns (highest priority)
 * These match the start of commit messages
 */
const CONVENTIONAL_COMMIT_PREFIXES = [
  { type: "feature", pattern: /^feat(\(.+\))?:/i },
  { type: "feature", pattern: /^feature(\(.+\))?:/i },
  { type: "fix", pattern: /^fix(\(.+\))?:/i },
  { type: "fix", pattern: /^bugfix(\(.+\))?:/i },
  { type: "fix", pattern: /^hotfix(\(.+\))?:/i },
  { type: "docs", pattern: /^docs?(\(.+\))?:/i },
  { type: "refactor", pattern: /^refactor(\(.+\))?:/i },
  { type: "test", pattern: /^test(\(.+\))?:/i },
  { type: "style", pattern: /^style(\(.+\))?:/i },
  { type: "chore", pattern: /^chore(\(.+\))?:/i },
  { type: "chore", pattern: /^build(\(.+\))?:/i },
  { type: "chore", pattern: /^ci(\(.+\))?:/i },
  { type: "perf", pattern: /^perf(\(.+\))?:/i },
];

/**
 * Keyword patterns for classification (lower priority, checked in order)
 * Order matters: more specific patterns should come first
 */
const KEYWORD_PATTERNS = [
  // Docs - check before feature since "add comments" should be docs
  { type: "docs", pattern: /\bdoc(s|umentation)\b/i },
  { type: "docs", pattern: /\breadme\b/i },
  { type: "docs", pattern: /\bcomment(s|ed|ing)?\b/i },
  // Test - check before feature since "add tests" should be test
  { type: "test", pattern: /\btest(s|ed|ing)?\b/i },
  { type: "test", pattern: /\bspec(s)?\b/i },
  // Fix
  { type: "fix", pattern: /\bfix(ed|ing|es)?\b/i },
  { type: "fix", pattern: /\bbug\b/i },
  { type: "fix", pattern: /\bresolve[ds]?\b/i },
  { type: "fix", pattern: /\bpatch(ed|ing)?\b/i },
  // Refactor
  { type: "refactor", pattern: /\brefactor(ed|ing|s)?\b/i },
  { type: "refactor", pattern: /\brestructur(e|ed|ing)\b/i },
  { type: "refactor", pattern: /\breorganiz(e|ed|ing)\b/i },
  { type: "refactor", pattern: /\bclean(ed|ing|s)?\s*(up)?\b/i },
  // Perf
  { type: "perf", pattern: /\bperformance\b/i },
  { type: "perf", pattern: /\boptimiz(e|ed|ing|ation)\b/i },
  { type: "perf", pattern: /\bspeed\b/i },
  // Style
  { type: "style", pattern: /\bformat(ted|ting)?\b/i },
  { type: "style", pattern: /\blint(ed|ing)?\b/i },
  // Chore
  { type: "chore", pattern: /\bdependenc(y|ies)\b/i },
  { type: "chore", pattern: /\bupgrade[ds]?\b/i },
  { type: "chore", pattern: /\bupdate[ds]?\b/i },
  { type: "chore", pattern: /\bbump(ed|ing)?\b/i },
  // Feature - last because it has the most generic patterns
  { type: "feature", pattern: /\badd(ed|ing|s)?\b/i },
  { type: "feature", pattern: /\bnew\b/i },
  { type: "feature", pattern: /\bimplement(ed|ing|s)?\b/i },
];

/**
 * Export for testing - combined view of all patterns
 */
const COMMIT_TYPE_PATTERNS = {
  feature: [/^feat(\(.+\))?:/i, /^feature(\(.+\))?:/i, /\badd(ed|ing|s)?\b/i, /\bnew\b/i, /\bimplement(ed|ing|s)?\b/i],
  fix: [/^fix(\(.+\))?:/i, /^bugfix(\(.+\))?:/i, /^hotfix(\(.+\))?:/i, /\bfix(ed|ing|es)?\b/i, /\bbug\b/i, /\bresolve[ds]?\b/i, /\bpatch(ed|ing)?\b/i],
  docs: [/^docs?(\(.+\))?:/i, /\bdoc(s|umentation)?\b/i, /\breadme\b/i, /\bcomment(s|ed|ing)?\b/i],
  refactor: [/^refactor(\(.+\))?:/i, /\brefactor(ed|ing|s)?\b/i, /\brestructur(e|ed|ing)\b/i, /\breorganiz(e|ed|ing)\b/i, /\bclean(ed|ing|up)?\b/i],
  test: [/^test(\(.+\))?:/i, /\btest(s|ed|ing)?\b/i, /\bspec(s)?\b/i],
  style: [/^style(\(.+\))?:/i, /\bformat(ted|ting)?\b/i, /\blint(ed|ing)?\b/i, /\bstyle[ds]?\b/i],
  chore: [/^chore(\(.+\))?:/i, /^build(\(.+\))?:/i, /^ci(\(.+\))?:/i, /\bdependenc(y|ies)\b/i, /\bupgrade[ds]?\b/i, /\bupdate[ds]?\b/i, /\bbump(ed|ing)?\b/i],
  perf: [/^perf(\(.+\))?:/i, /\bperformance\b/i, /\boptimiz(e|ed|ing|ation)\b/i, /\bspeed\b/i],
};

/**
 * Custom error classes for specific error handling
 */
class GitAnalyzerError extends Error {
  constructor(message, code) {
    super(message);
    this.name = "GitAnalyzerError";
    this.code = code;
  }
}

class RepositoryNotFoundError extends GitAnalyzerError {
  constructor(repoPath) {
    super(`Repository not found: ${repoPath}`, "REPO_NOT_FOUND");
  }
}

class NotAGitRepositoryError extends GitAnalyzerError {
  constructor(repoPath) {
    super(`Not a git repository: ${repoPath}`, "NOT_GIT_REPO");
  }
}

class PermissionError extends GitAnalyzerError {
  constructor(repoPath) {
    super(`Permission denied accessing repository: ${repoPath}`, "PERMISSION_DENIED");
  }
}

/**
 * Validates that a path exists and is a git repository
 * @param {string} repoPath - Path to the repository
 * @throws {RepositoryNotFoundError|NotAGitRepositoryError|PermissionError}
 */
function validateRepository(repoPath) {
  // Check if path exists
  try {
    const stats = fs.statSync(repoPath);
    if (!stats.isDirectory()) {
      throw new RepositoryNotFoundError(repoPath);
    }
  } catch (err) {
    if (err.code === "ENOENT") {
      throw new RepositoryNotFoundError(repoPath);
    }
    if (err.code === "EACCES") {
      throw new PermissionError(repoPath);
    }
    if (err instanceof GitAnalyzerError) {
      throw err;
    }
    throw new GitAnalyzerError(`Error accessing repository: ${err.message}`, "UNKNOWN");
  }

  // Check if it's a git repository
  // .git can be a directory (normal repo) or a file (worktree)
  const gitDir = path.join(repoPath, ".git");
  try {
    const gitStats = fs.statSync(gitDir);
    // Accept both directory (normal repo) and file (worktree)
    if (!gitStats.isDirectory() && !gitStats.isFile()) {
      throw new NotAGitRepositoryError(repoPath);
    }
  } catch (err) {
    if (err.code === "ENOENT") {
      throw new NotAGitRepositoryError(repoPath);
    }
    if (err.code === "EACCES") {
      throw new PermissionError(repoPath);
    }
    if (err instanceof GitAnalyzerError) {
      throw err;
    }
    throw new NotAGitRepositoryError(repoPath);
  }
}

/**
 * Executes a git command in the specified repository
 * @param {string} repoPath - Path to the repository
 * @param {string[]} args - Git command arguments
 * @returns {string} Command output
 */
function execGit(repoPath, args) {
  const result = spawnSync("git", args, {
    cwd: repoPath,
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024, // 50MB buffer for large repos
  });

  if (result.error) {
    if (result.error.code === "EACCES") {
      throw new PermissionError(repoPath);
    }
    throw new GitAnalyzerError(`Git command failed: ${result.error.message}`, "GIT_ERROR");
  }

  if (result.status !== 0) {
    const errorMsg = result.stderr || "Unknown git error";
    throw new GitAnalyzerError(`Git command failed: ${errorMsg}`, "GIT_ERROR");
  }

  return result.stdout;
}

/**
 * Parses a git log entry into a structured commit object
 * @param {string} logEntry - Raw git log entry
 * @returns {Object} Parsed commit object
 */
function parseCommit(logEntry) {
  const lines = logEntry.trim().split("\n");
  if (lines.length < 4) {
    return null;
  }

  const hash = lines[0];
  const author = lines[1];
  const timestamp = lines[2];
  const message = lines.slice(3).join("\n").trim();

  return {
    hash,
    author,
    timestamp,
    date: new Date(timestamp).toISOString(),
    message,
    shortMessage: message.split("\n")[0],
  };
}

/**
 * Classifies a commit message into a type category
 * Uses a two-pass approach: first check conventional commit prefixes (highest priority),
 * then check keywords in a specific order (more specific patterns first)
 * @param {string} message - Commit message
 * @returns {string} Commit type (feature, fix, docs, refactor, test, style, chore, perf, other)
 */
function classifyCommit(message) {
  // First pass: check conventional commit prefixes (highest priority)
  for (const { type, pattern } of CONVENTIONAL_COMMIT_PREFIXES) {
    if (pattern.test(message)) {
      return type;
    }
  }

  // Second pass: check keywords in priority order
  for (const { type, pattern } of KEYWORD_PATTERNS) {
    if (pattern.test(message)) {
      return type;
    }
  }

  return "other";
}

/**
 * Gets file change statistics for a commit
 * @param {string} repoPath - Path to the repository
 * @param {string} hash - Commit hash
 * @returns {Object} File change statistics
 */
function getCommitStats(repoPath, hash) {
  try {
    const output = execGit(repoPath, [
      "diff-tree",
      "--no-commit-id",
      "--numstat",
      "-r",
      hash,
    ]);

    const lines = output.trim().split("\n").filter(Boolean);
    let additions = 0;
    let deletions = 0;
    const files = [];

    for (const line of lines) {
      const [added, deleted, filename] = line.split("\t");
      // Binary files show "-" for additions/deletions
      const addedNum = added === "-" ? 0 : parseInt(added, 10);
      const deletedNum = deleted === "-" ? 0 : parseInt(deleted, 10);

      additions += addedNum;
      deletions += deletedNum;
      files.push({
        filename,
        additions: addedNum,
        deletions: deletedNum,
      });
    }

    return {
      additions,
      deletions,
      filesChanged: files.length,
      files,
    };
  } catch (err) {
    // Return empty stats if we can't get them
    return {
      additions: 0,
      deletions: 0,
      filesChanged: 0,
      files: [],
    };
  }
}

/**
 * Gets branch information for the repository
 * @param {string} repoPath - Path to the repository
 * @returns {Object} Branch information
 */
function getBranchInfo(repoPath) {
  try {
    const currentBranch = execGit(repoPath, ["rev-parse", "--abbrev-ref", "HEAD"]).trim();
    const branchesOutput = execGit(repoPath, ["branch", "-a", "--format=%(refname:short)"]);
    const branches = branchesOutput
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((b) => b.trim());

    // Get recent branch activity
    const localBranches = branches.filter((b) => !b.startsWith("origin/"));
    const remoteBranches = branches.filter((b) => b.startsWith("origin/"));

    return {
      current: currentBranch,
      local: localBranches,
      remote: remoteBranches,
      totalBranches: localBranches.length,
    };
  } catch (err) {
    return {
      current: "unknown",
      local: [],
      remote: [],
      totalBranches: 0,
    };
  }
}

/**
 * Main function to analyze git activity
 * @param {string} repoPath - Path to the repository
 * @param {Object} options - Analysis options
 * @returns {Object} Structured activity summary
 */
function analyzeGitActivity(repoPath, options = {}) {
  const { since = null, limit = 100 } = options;

  // Resolve and validate repository path
  const absolutePath = path.resolve(repoPath);
  validateRepository(absolutePath);

  // Build git log command
  const logArgs = [
    "log",
    "--format=%H%n%an%n%aI%n%B%x00", // Hash, author, ISO date, body, null separator
    `-n${limit}`,
  ];

  if (since) {
    logArgs.push(`--since=${since}`);
  }

  // Get commits - handle empty repository case
  let logOutput = "";
  let commitEntries = [];
  try {
    logOutput = execGit(absolutePath, logArgs);
    commitEntries = logOutput.split("\x00").filter((entry) => entry.trim());
  } catch (err) {
    // Check if this is an empty repository (no commits yet)
    if (err.message && err.message.includes("does not have any commits")) {
      commitEntries = [];
    } else {
      throw err;
    }
  }

  // Handle no commits case
  if (commitEntries.length === 0) {
    return {
      repository: absolutePath,
      analyzedAt: new Date().toISOString(),
      summary: {
        totalCommits: 0,
        dateRange: null,
        commitsByType: {},
        topContributors: [],
        totalAdditions: 0,
        totalDeletions: 0,
        totalFilesChanged: 0,
      },
      branches: getBranchInfo(absolutePath),
      commits: [],
      insights: ["No commits found in the specified range"],
    };
  }

  // Parse all commits
  const commits = [];
  const commitsByType = {};
  const authorStats = {};
  let totalAdditions = 0;
  let totalDeletions = 0;
  let totalFilesChanged = 0;

  for (const entry of commitEntries) {
    const commit = parseCommit(entry);
    if (!commit) continue;

    // Classify commit
    const type = classifyCommit(commit.message);
    commit.type = type;

    // Get stats
    const stats = getCommitStats(absolutePath, commit.hash);
    commit.stats = stats;

    // Aggregate statistics
    totalAdditions += stats.additions;
    totalDeletions += stats.deletions;
    totalFilesChanged += stats.filesChanged;

    // Count by type
    commitsByType[type] = (commitsByType[type] || 0) + 1;

    // Track author contributions
    if (!authorStats[commit.author]) {
      authorStats[commit.author] = {
        name: commit.author,
        commits: 0,
        additions: 0,
        deletions: 0,
      };
    }
    authorStats[commit.author].commits++;
    authorStats[commit.author].additions += stats.additions;
    authorStats[commit.author].deletions += stats.deletions;

    commits.push(commit);
  }

  // Sort contributors by commit count
  const topContributors = Object.values(authorStats)
    .sort((a, b) => b.commits - a.commits)
    .slice(0, 10);

  // Determine date range
  const dates = commits.map((c) => new Date(c.timestamp));
  const dateRange = dates.length > 0
    ? {
        oldest: new Date(Math.min(...dates)).toISOString(),
        newest: new Date(Math.max(...dates)).toISOString(),
      }
    : null;

  // Generate insights
  const insights = generateInsights(commits, commitsByType, topContributors);

  return {
    repository: absolutePath,
    analyzedAt: new Date().toISOString(),
    summary: {
      totalCommits: commits.length,
      dateRange,
      commitsByType,
      topContributors,
      totalAdditions,
      totalDeletions,
      totalFilesChanged,
    },
    branches: getBranchInfo(absolutePath),
    commits: commits.map((c) => ({
      hash: c.hash,
      shortHash: c.hash.substring(0, 7),
      author: c.author,
      date: c.date,
      type: c.type,
      shortMessage: c.shortMessage,
      stats: {
        additions: c.stats.additions,
        deletions: c.stats.deletions,
        filesChanged: c.stats.filesChanged,
      },
    })),
    insights,
  };
}

/**
 * Generates human-readable insights from the analysis
 * @param {Array} commits - Parsed commits
 * @param {Object} commitsByType - Commits grouped by type
 * @param {Array} topContributors - Top contributors list
 * @returns {Array} List of insight strings
 */
function generateInsights(commits, commitsByType, topContributors) {
  const insights = [];

  if (commits.length === 0) {
    return ["No recent activity detected"];
  }

  // Activity level insight
  const daysDiff = commits.length > 1
    ? Math.ceil(
        (new Date(commits[0].timestamp) - new Date(commits[commits.length - 1].timestamp)) /
          (1000 * 60 * 60 * 24)
      )
    : 1;
  const commitsPerDay = (commits.length / Math.max(daysDiff, 1)).toFixed(1);
  insights.push(`Average activity: ${commitsPerDay} commits per day over ${daysDiff} days`);

  // Type breakdown insights
  const types = Object.entries(commitsByType).sort((a, b) => b[1] - a[1]);
  if (types.length > 0) {
    const [topType, topCount] = types[0];
    const percentage = Math.round((topCount / commits.length) * 100);
    insights.push(`Primary focus: ${topType} (${percentage}% of commits)`);
  }

  // Feature additions
  if (commitsByType.feature > 0) {
    insights.push(`${commitsByType.feature} new feature${commitsByType.feature > 1 ? "s" : ""} added`);
  }

  // Bug fixes
  if (commitsByType.fix > 0) {
    insights.push(`${commitsByType.fix} bug fix${commitsByType.fix > 1 ? "es" : ""} applied`);
  }

  // Documentation updates
  if (commitsByType.docs > 0) {
    insights.push(`${commitsByType.docs} documentation update${commitsByType.docs > 1 ? "s" : ""}`);
  }

  // Refactoring work
  if (commitsByType.refactor > 0) {
    insights.push(`${commitsByType.refactor} refactoring change${commitsByType.refactor > 1 ? "s" : ""}`);
  }

  // Top contributor
  if (topContributors.length > 0) {
    const top = topContributors[0];
    insights.push(`Top contributor: ${top.name} (${top.commits} commits)`);
  }

  return insights;
}

/**
 * CLI entry point
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
    console.log(`
Git Activity Analyzer

Usage:
  node git-analyzer.js <repository-path> [options]

Options:
  --since <date>     Only include commits after this date (e.g., "2024-01-01", "1 month ago")
  --limit <number>   Maximum number of commits to analyze (default: 100)
  --output <file>    Write JSON output to file instead of stdout
  --pretty           Pretty-print JSON output
  --help, -h         Show this help message

Examples:
  node git-analyzer.js /path/to/repo
  node git-analyzer.js /path/to/repo --since "1 month ago" --pretty
  node git-analyzer.js /path/to/repo --limit 50 --output analysis.json
`);
    process.exit(0);
  }

  const repoPath = args[0];
  const options = {};
  let outputFile = null;
  let pretty = false;

  // Parse arguments
  for (let i = 1; i < args.length; i++) {
    switch (args[i]) {
      case "--since":
        options.since = args[++i];
        break;
      case "--limit":
        options.limit = parseInt(args[++i], 10);
        break;
      case "--output":
        outputFile = args[++i];
        break;
      case "--pretty":
        pretty = true;
        break;
    }
  }

  try {
    const result = analyzeGitActivity(repoPath, options);
    const json = pretty ? JSON.stringify(result, null, 2) : JSON.stringify(result);

    if (outputFile) {
      fs.writeFileSync(outputFile, json);
      console.log(`Analysis written to ${outputFile}`);
    } else {
      console.log(json);
    }

    process.exit(0);
  } catch (err) {
    if (err instanceof GitAnalyzerError) {
      console.error(`Error: ${err.message}`);
      process.exit(1);
    }
    throw err;
  }
}

// Export for testing
module.exports = {
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
};

// Run CLI if executed directly
if (require.main === module) {
  main();
}
