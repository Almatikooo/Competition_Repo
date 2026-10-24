#!/usr/bin/env bash
# Deploys the latest main. From the laptop:  ssh -i ~/.ssh/pathai_deploy root@SERVER /srv/pathai/app/deploy/server/update.sh
# The body is one function: bash reads it whole before running, so the reset below can safely replace this file.
set -euo pipefail

main() {
  cd /srv/pathai/app
  # A trend refresh on the server rewrites data/signals: keep that data across the reset when it is newer than git's.
  local keep old newer
  keep=$(mktemp -d)
  cp -a data/signals/. "$keep"/
  sudo -u pathai git fetch -q origin main
  old=$(sudo -u pathai git rev-parse HEAD)
  sudo -u pathai git reset -q --hard origin/main
  newer=$(python3 -c 'import json, sys
latest = lambda p: max(v.get("refreshed_at") or "" for v in json.load(open(p)).values())
print(int(latest(sys.argv[1]) > latest(sys.argv[2])))' "$keep/meta.json" data/signals/meta.json)
  if [ "$newer" = 1 ]; then cp -a "$keep"/. data/signals/ && chown -R pathai: data/signals; fi
  rm -rf "$keep"
  if ! sudo -u pathai git diff --quiet "$old" HEAD -- requirements.txt; then
    sudo -u pathai .venv/bin/pip install -q -r requirements.txt
  fi
  systemctl restart pathai
  echo "deployed: $(sudo -u pathai git log --oneline -1)$([ "$newer" = 1 ] && echo ' (kept the newer trend data)')"
}

main "$@"
exit
