#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Setting up GitHub for patrickbrownai@gmail.com..."

# Git identity
git config --global user.name "Patrick Brown"
git config --global user.email "patrickbrownai@gmail.com"

# SSH setup
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# GitHub SSH config
cat > ~/.ssh/config << 'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config

# Test connection
echo "Testing GitHub SSH..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo "Success: GitHub SSH works."
else
  echo "SSH test failed. Add ~/.ssh/id_ed25519.pub to GitHub SSH keys."
fi

echo "Installing dependencies from requirements-gpu.txt..."
cd "$PROJECT_ROOT"
pip install -r requirements-gpu.txt

# Verify CUDA
echo "Verifying CUDA..."
if python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  echo "Success: CUDA is available."
else
  echo "CUDA check failed or not available on this machine."
fi

echo "Setup complete."
