#!/usr/bin/env bash
# Start script for Hermes Voice Satellite Receiver (Linux / macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================="
echo "  Starting Hermes Voice Satellite Receiver"
echo "======================================================="

# Check for virtual environment in common locations
if [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "$HOME/.hermes/venv" ]; then
    source "$HOME/.hermes/venv/bin/activate"
fi

# Load local .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

python3 hermes_voice_receiver.py
