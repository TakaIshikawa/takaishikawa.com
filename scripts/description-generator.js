#!/usr/bin/env node
/**
 * AI-Powered Description Generator for Project Portfolio
 *
 * Takes git activity summaries and generates natural, concise project descriptions
 * that match the website's professional, technical tone.
 *
 * Usage:
 *   node description-generator.js --input activity.json --output descriptions.json
 *   node description-generator.js --input activity.json --provider openai
 *   cat activity.json | node description-generator.js --stdin
 */

const fs = require("fs");
const path = require("path");

/**
 * @typedef {Object} ProjectActivity
 * @property {string} project_name
 * @property {string} [description]
 * @property {Array} [recent_commits]
 * @property {Array} [top_contributors]
 * @property {Array<string>} [languages]
 * @property {string} [last_active]
 * @property {number} [commit_count]
 * @property {Array<string>} [recent_features]
 * @property {Array<string>} [recent_fixes]
 * @property {Array<string>} [recent_refactors]
 * @property {string} [manual_override]
 */

/**
 * @typedef {Object} GeneratedDescription
 * @property {string} project_name
 * @property {string} description
 * @property {string} source - 'llm', 'fallback', or 'manual_override'
 * @property {number} confidence - 0.0 to 1.0
 */

class DescriptionGenerator {
  /**
   * @param {Object} options
   * @param {string} [options.provider='anthropic']
   * @param {string} [options.promptPath]
   */
  constructor(options = {}) {
    this.provider = (options.provider || "anthropic").toLowerCase();
    this.promptTemplate = this._loadPrompt(options.promptPath);
    this._client = null;
  }

  /**
   * Load the prompt template from file or use default
   * @param {string} [promptPath]
   * @returns {string}
   */
  _loadPrompt(promptPath) {
    const defaultPath = path.join(
      __dirname,
      "..",
      "prompts",
      "project-description.txt"
    );
    const targetPath = promptPath || defaultPath;

    try {
      if (fs.existsSync(targetPath)) {
        return fs.readFileSync(targetPath, "utf-8");
      }
    } catch (e) {
      // Fall through to default
    }

    return this._getDefaultPrompt();
  }

  /**
   * Default prompt template for description generation
   * @returns {string}
   */
  _getDefaultPrompt() {
    return `You are a technical writer creating concise project descriptions for a software engineer's portfolio website.

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

Generate a description that captures the project's essence based on its recent activity and technical focus. Output ONLY the description text, no quotes or formatting.`;
  }

  /**
   * Format project activity data for the prompt
   * @param {ProjectActivity} activity
   * @returns {string}
   */
  _formatProjectData(activity) {
    const lines = [`Project: ${activity.project_name}`];

    if (activity.description) {
      lines.push(`Current Description: ${activity.description}`);
    }

    if (activity.languages && activity.languages.length > 0) {
      lines.push(`Languages: ${activity.languages.join(", ")}`);
    }

    if (activity.recent_features && activity.recent_features.length > 0) {
      lines.push(`Recent Features: ${activity.recent_features.slice(0, 5).join("; ")}`);
    }

    if (activity.recent_fixes && activity.recent_fixes.length > 0) {
      lines.push(`Recent Fixes: ${activity.recent_fixes.slice(0, 3).join("; ")}`);
    }

    if (activity.recent_refactors && activity.recent_refactors.length > 0) {
      lines.push(`Recent Refactoring: ${activity.recent_refactors.slice(0, 3).join("; ")}`);
    }

    if (activity.recent_commits && activity.recent_commits.length > 0) {
      const commitMsgs = activity.recent_commits.slice(0, 10).map((c) => {
        return typeof c === "object" ? c.message || c : String(c);
      });
      lines.push(`Recent Commits: ${commitMsgs.join("; ")}`);
    }

    if (activity.commit_count) {
      lines.push(`Total Commits: ${activity.commit_count}`);
    }

    if (activity.last_active) {
      lines.push(`Last Active: ${activity.last_active}`);
    }

    return lines.join("\n");
  }

  /**
   * Initialize the Anthropic client
   * @returns {Object}
   */
  _getAnthropicClient() {
    if (this._client) return this._client;

    try {
      const Anthropic = require("@anthropic-ai/sdk");
      this._client = new Anthropic();
      return this._client;
    } catch (e) {
      throw new Error(
        "Anthropic SDK not installed. Run: npm install @anthropic-ai/sdk"
      );
    }
  }

  /**
   * Initialize the OpenAI client
   * @returns {Object}
   */
  _getOpenAIClient() {
    if (this._client) return this._client;

    try {
      const OpenAI = require("openai");
      this._client = new OpenAI();
      return this._client;
    } catch (e) {
      throw new Error("OpenAI SDK not installed. Run: npm install openai");
    }
  }

  /**
   * Call the Anthropic Claude API
   * @param {string} prompt
   * @returns {Promise<string>}
   */
  async _callAnthropic(prompt) {
    const client = this._getAnthropicClient();

    const message = await client.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 300,
      messages: [{ role: "user", content: prompt }],
    });

    return message.content[0].text.trim();
  }

  /**
   * Call the OpenAI API
   * @param {string} prompt
   * @returns {Promise<string>}
   */
  async _callOpenAI(prompt) {
    const client = this._getOpenAIClient();

    const response = await client.chat.completions.create({
      model: "gpt-4o",
      max_tokens: 300,
      messages: [{ role: "user", content: prompt }],
    });

    return response.choices[0].message.content.trim();
  }

  /**
   * Generate a template-based fallback description
   * @param {ProjectActivity} activity
   * @returns {string}
   */
  _generateFallback(activity) {
    const name = activity.project_name;

    // Determine project type from languages/features
    let langHint = "";
    if (activity.languages && activity.languages.length > 0) {
      langHint = `built with ${activity.languages[0]}`;
    }

    // Extract key capabilities from features
    let capabilities = [];
    if (activity.recent_features && activity.recent_features.length > 0) {
      capabilities = activity.recent_features.slice(0, 3);
    } else if (activity.recent_commits && activity.recent_commits.length > 0) {
      // Extract from commit messages
      for (const commit of activity.recent_commits.slice(0, 5)) {
        const msg = typeof commit === "object" ? commit.message || commit : String(commit);
        if (msg) {
          const extracted = msg.includes(":") ? msg.split(":").pop().trim() : msg;
          capabilities.push(extracted);
          if (capabilities.length >= 3) break;
        }
      }
    }

    // Build the description
    if (capabilities.length > 0) {
      const capText = capabilities.slice(0, 2).join(", ");
      if (langHint) {
        return `${name} is a software project ${langHint}, featuring ${capText}.`;
      }
      return `${name} is a software project featuring ${capText}.`;
    }

    if (activity.description) {
      return activity.description;
    }

    if (langHint) {
      return `${name} is a software project ${langHint}.`;
    }

    return `${name} is a software project under active development.`;
  }

  /**
   * Generate a description for a project
   * @param {ProjectActivity} activity
   * @returns {Promise<GeneratedDescription>}
   */
  async generate(activity) {
    // Check for manual override first
    if (activity.manual_override) {
      return {
        project_name: activity.project_name,
        description: activity.manual_override,
        source: "manual_override",
        confidence: 1.0,
      };
    }

    // Try LLM generation
    try {
      const projectData = this._formatProjectData(activity);
      const prompt = this.promptTemplate.replace("{project_data}", projectData);

      let description;
      if (this.provider === "anthropic") {
        description = await this._callAnthropic(prompt);
      } else if (this.provider === "openai") {
        description = await this._callOpenAI(prompt);
      } else {
        throw new Error(`Unsupported provider: ${this.provider}`);
      }

      // Clean up the response
      description = description.replace(/^["']|["']$/g, "");

      return {
        project_name: activity.project_name,
        description: description,
        source: "llm",
        confidence: 0.9,
      };
    } catch (e) {
      // Log the error and fall back
      console.error(
        `Warning: LLM generation failed for ${activity.project_name}: ${e.message}`
      );

      const fallback = this._generateFallback(activity);
      return {
        project_name: activity.project_name,
        description: fallback,
        source: "fallback",
        confidence: 0.5,
      };
    }
  }

  /**
   * Generate descriptions for multiple projects
   * @param {Array<ProjectActivity>} activities
   * @returns {Promise<Array<GeneratedDescription>>}
   */
  async generateBatch(activities) {
    const results = [];
    for (const activity of activities) {
      results.push(await this.generate(activity));
    }
    return results;
  }
}

/**
 * Parse JSON activity data into ProjectActivity objects
 * @param {Object} data
 * @returns {Array<ProjectActivity>}
 */
function parseActivityData(data) {
  let items;

  if (Array.isArray(data)) {
    items = data;
  } else if (data.projects) {
    items = data.projects;
  } else {
    items = [data];
  }

  return items.map((item) => ({
    project_name: item.project_name || item.name || "Unknown",
    description: item.description,
    recent_commits: item.recent_commits || [],
    top_contributors: item.top_contributors || [],
    languages: item.languages || [],
    last_active: item.last_active,
    commit_count: item.commit_count || 0,
    recent_features: item.recent_features || [],
    recent_fixes: item.recent_fixes || [],
    recent_refactors: item.recent_refactors || [],
    manual_override: item.manual_override,
  }));
}

/**
 * Read input from stdin
 * @returns {Promise<string>}
 */
function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf-8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

/**
 * Parse command line arguments
 * @returns {Object}
 */
function parseArgs() {
  const args = {
    input: null,
    stdin: false,
    output: null,
    provider: "anthropic",
    prompt: null,
    dryRun: false,
    help: false,
  };

  const argv = process.argv.slice(2);

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    switch (arg) {
      case "--input":
      case "-i":
        args.input = argv[++i];
        break;
      case "--stdin":
        args.stdin = true;
        break;
      case "--output":
      case "-o":
        args.output = argv[++i];
        break;
      case "--provider":
      case "-p":
        args.provider = argv[++i];
        break;
      case "--prompt":
        args.prompt = argv[++i];
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--help":
      case "-h":
        args.help = true;
        break;
    }
  }

  return args;
}

/**
 * Print usage information
 */
function printHelp() {
  console.log(`
AI-Powered Description Generator

Usage:
  node description-generator.js --input <file> [options]
  cat activity.json | node description-generator.js --stdin [options]

Options:
  -i, --input <file>     Input JSON file with git activity data
  --stdin                Read input from stdin
  -o, --output <file>    Output JSON file (defaults to stdout)
  -p, --provider <name>  LLM provider: anthropic (default) or openai
  --prompt <file>        Path to custom prompt template file
  --dry-run              Generate fallback descriptions without calling LLM
  -h, --help             Show this help message

Environment Variables:
  ANTHROPIC_API_KEY      Required for Anthropic provider
  OPENAI_API_KEY         Required for OpenAI provider

Examples:
  node description-generator.js -i activity.json -o descriptions.json
  node description-generator.js -i activity.json --provider openai
  node description-generator.js -i activity.json --dry-run
`);
}

async function main() {
  const args = parseArgs();

  if (args.help) {
    printHelp();
    process.exit(0);
  }

  // Read input
  let inputData;
  try {
    if (args.stdin) {
      const stdinData = await readStdin();
      inputData = JSON.parse(stdinData);
    } else if (args.input) {
      const fileData = fs.readFileSync(args.input, "utf-8");
      inputData = JSON.parse(fileData);
    } else {
      console.error("Error: Either --input or --stdin is required");
      printHelp();
      process.exit(1);
    }
  } catch (e) {
    console.error(`Error reading input: ${e.message}`);
    process.exit(1);
  }

  // Parse activity data
  const activities = parseActivityData(inputData);

  // Generate descriptions
  let results;
  if (args.dryRun) {
    // Use fallback generation only (but respect manual overrides)
    const generator = new DescriptionGenerator({
      provider: args.provider,
      promptPath: args.prompt,
    });
    results = activities.map((activity) => {
      if (activity.manual_override) {
        return {
          project_name: activity.project_name,
          description: activity.manual_override,
          source: "manual_override",
          confidence: 1.0,
        };
      }
      return {
        project_name: activity.project_name,
        description: generator._generateFallback(activity),
        source: "fallback",
        confidence: 0.5,
      };
    });
  } else {
    const generator = new DescriptionGenerator({
      provider: args.provider,
      promptPath: args.prompt,
    });
    results = await generator.generateBatch(activities);
  }

  // Format output
  const output = {
    descriptions: results.map((r) => ({
      project_name: r.project_name,
      description: r.description,
      source: r.source,
      confidence: r.confidence,
    })),
  };

  // Write output
  const outputJson = JSON.stringify(output, null, 2);
  if (args.output) {
    fs.writeFileSync(args.output, outputJson);
  } else {
    console.log(outputJson);
  }
}

// Export for use as a module
module.exports = { DescriptionGenerator, parseActivityData };

// Run if executed directly
if (require.main === module) {
  main().catch((e) => {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  });
}
