#!/bin/bash
# TradingDesk SessionStart hook — installs the tools/ quote dependencies
# (yfinance, pandas, ta, …) so ta_snapshot.py and the bot scripts run in
# Claude Code on the web sessions.
set -euo pipefail

# Only run in the remote (web) environment; local machines set up .venv manually.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

VENV_DIR=".venv"

# Idempotent: reuse the venv if it already exists.
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

# The `ta` package builds an sdist and needs a modern build toolchain
# (the system Debian setuptools trips on install_layout otherwise).
"$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt

# Make the venv's python/pip the default for the rest of the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$CLAUDE_PROJECT_DIR/$VENV_DIR/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi

echo "TradingDesk dependencies installed into $VENV_DIR"
