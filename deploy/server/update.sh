#!/usr/bin/env bash
# Deploys the latest main. From the laptop:  ssh -i ~/.ssh/pathai_deploy root@SERVER /srv/pathai/app/deploy/server/update.sh
# A trend refresh on the server rewrites data/signals; the reset puts the committed files back (press refresh again).
set -euo pipefail
cd /srv/pathai/app
sudo -u pathai git fetch -q origin main
old=$(sudo -u pathai git rev-parse HEAD)
sudo -u pathai git reset -q --hard origin/main
if ! sudo -u pathai git diff --quiet "$old" HEAD -- requirements.txt; then
  sudo -u pathai .venv/bin/pip install -q -r requirements.txt
fi
systemctl restart pathai
echo "deployed: $(sudo -u pathai git log --oneline -1)"
