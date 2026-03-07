#!/bin/bash
# =============================================================================
# Daily Website Update Script
# =============================================================================
# This script is designed to be run by cron for automated daily updates of
# project descriptions on the portfolio website.
#
# SETUP INSTRUCTIONS:
# -------------------
# 1. Make this script executable:
#    chmod +x cron/daily-update.sh
#
# 2. Set required environment variables in your shell profile (~/.bashrc, ~/.zshrc):
#    export ANTHROPIC_API_KEY="your-api-key-here"
#    # Or for OpenAI:
#    export OPENAI_API_KEY="your-api-key-here"
#
# 3. Add to crontab (run `crontab -e`):
#    # Run daily at 6:00 AM local time
#    0 6 * * * /path/to/me/cron/daily-update.sh >> /path/to/me/logs/daily-update.log 2>&1
#
#    # Alternative: Run with specific environment
#    0 6 * * * /bin/bash -c 'source ~/.bashrc && /path/to/me/cron/daily-update.sh' >> /path/to/me/logs/daily-update.log 2>&1
#
# MANUAL EXECUTION:
# -----------------
# Run directly:
#   ./cron/daily-update.sh
#
# Dry run (preview changes):
#   DRY_RUN=1 ./cron/daily-update.sh
#
# Skip LLM calls:
#   NO_LLM=1 ./cron/daily-update.sh
#
# Use OpenAI instead of Anthropic:
#   PROVIDER=openai ./cron/daily-update.sh
#
# Update specific projects:
#   PROJECTS="tact prepend" ./cron/daily-update.sh
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Determine script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Log file location
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/daily-update-$(date +%Y-%m-%d).log"

# Python interpreter (use virtual env if available)
if [[ -d "${PROJECT_ROOT}/venv" ]]; then
    PYTHON="${PROJECT_ROOT}/venv/bin/python"
elif [[ -d "${PROJECT_ROOT}/.venv" ]]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
else
    PYTHON="python3"
fi

# Options from environment
DRY_RUN="${DRY_RUN:-0}"
NO_LLM="${NO_LLM:-0}"
PROVIDER="${PROVIDER:-anthropic}"
PROJECTS="${PROJECTS:-}"
COMMIT="${COMMIT:-1}"  # Auto-commit by default

# =============================================================================
# Functions
# =============================================================================

log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }

check_dependencies() {
    log_info "Checking dependencies..."

    # Check Python
    if ! command -v "${PYTHON}" &> /dev/null; then
        log_error "Python not found: ${PYTHON}"
        exit 1
    fi

    # Check required Python packages
    "${PYTHON}" -c "import yaml" 2>/dev/null || {
        log_error "PyYAML not installed. Run: pip install pyyaml"
        exit 1
    }

    "${PYTHON}" -c "from bs4 import BeautifulSoup" 2>/dev/null || {
        log_error "BeautifulSoup4 not installed. Run: pip install beautifulsoup4"
        exit 1
    }

    # Check for API key (unless no-llm mode)
    if [[ "${NO_LLM}" != "1" ]]; then
        if [[ "${PROVIDER}" == "anthropic" ]] && [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
            log_error "ANTHROPIC_API_KEY not set. Set the environment variable or use NO_LLM=1"
            exit 1
        fi
        if [[ "${PROVIDER}" == "openai" ]] && [[ -z "${OPENAI_API_KEY:-}" ]]; then
            log_error "OPENAI_API_KEY not set. Set the environment variable or use NO_LLM=1"
            exit 1
        fi
    fi

    log_info "All dependencies satisfied"
}

run_update() {
    log_info "Starting website update..."

    # Build command
    CMD="${PYTHON} ${PROJECT_ROOT}/scripts/update-website.py"
    CMD="${CMD} --verbose"
    CMD="${CMD} --provider ${PROVIDER}"

    if [[ "${DRY_RUN}" == "1" ]]; then
        CMD="${CMD} --dry-run"
        log_info "Mode: DRY RUN"
    fi

    if [[ "${NO_LLM}" == "1" ]]; then
        CMD="${CMD} --no-llm"
        log_info "LLM: DISABLED"
    fi

    if [[ -n "${PROJECTS}" ]]; then
        CMD="${CMD} --projects ${PROJECTS}"
        log_info "Projects: ${PROJECTS}"
    fi

    if [[ "${COMMIT}" == "1" ]] && [[ "${DRY_RUN}" != "1" ]]; then
        CMD="${CMD} --commit"
        log_info "Auto-commit: ENABLED"
    fi

    # Add JSON output for logging
    CMD="${CMD} --output-json ${LOG_DIR}/last-update-result.json"

    log_info "Running: ${CMD}"
    echo ""

    # Execute
    if ${CMD}; then
        log_info "Update completed successfully"
        return 0
    else
        log_error "Update failed"
        return 1
    fi
}

cleanup_old_logs() {
    # Keep logs for 30 days
    if [[ -d "${LOG_DIR}" ]]; then
        find "${LOG_DIR}" -name "daily-update-*.log" -mtime +30 -delete 2>/dev/null || true
        log_info "Cleaned up old log files"
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Create log directory
    mkdir -p "${LOG_DIR}"

    # Banner
    echo "============================================================"
    echo "Daily Website Update"
    echo "============================================================"
    echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Project Root: ${PROJECT_ROOT}"
    echo "Python: ${PYTHON}"
    echo "Provider: ${PROVIDER}"
    echo ""

    # Pre-flight checks
    check_dependencies

    # Change to project directory
    cd "${PROJECT_ROOT}"

    # Run update
    run_update
    EXIT_CODE=$?

    # Cleanup
    cleanup_old_logs

    echo ""
    echo "============================================================"
    echo "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Exit code: ${EXIT_CODE}"
    echo "============================================================"

    exit ${EXIT_CODE}
}

# Run main function
main "$@"
