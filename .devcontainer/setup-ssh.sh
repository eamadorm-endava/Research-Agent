#!/bin/bash
set -euo pipefail

echo "🔐 Setting up SSH for Git inside Dev Container..."

SSH_DIR="$HOME/.ssh"
SSH_CONFIG_SRC="$SSH_DIR/config"
SSH_CONFIG_SAFE="$SSH_DIR/config-devcontainer"

# Only run this if we're inside a Dev Container
if grep -q "vscode" <<< "$USER"; then
  # Copy SSH config to a safe file if it exists
  if [[ -f "$SSH_CONFIG_SRC" ]]; then
    cp "$SSH_CONFIG_SRC" "$SSH_CONFIG_SAFE"
    chmod 600 "$SSH_CONFIG_SAFE" || echo "⚠️ Could not chmod $SSH_CONFIG_SAFE — likely due to Windows bind mount"
    echo "✅ Copied SSH config to $SSH_CONFIG_SAFE"

    # Configure Git to use the safe SSH config (local to this repo)
    git config core.sshCommand "ssh -F $SSH_CONFIG_SAFE"
    echo "✅ Git configured to use safe SSH config"
  else
    echo "⚠️ No SSH config found at $SSH_CONFIG_SRC — skipping"
  fi
else
  echo "ℹ️ Not in Dev Container — skipping SSH override"
fi