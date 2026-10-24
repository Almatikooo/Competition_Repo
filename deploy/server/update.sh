#!/usr/bin/env bash
# Deploys the latest main. From the laptop:  ssh -i ~/.ssh/pathai_deploy root@SERVER /srv/pathai/app/deploy/server/update.sh
# The body is one function: bash reads it whole before running, so the reset below can safely replace this file.
# Every file and git operation runs as the app user: root never writes into directories the app can change.
set -euo pipefail

main() {
  cd /srv/pathai/app
  local keep old newer
  app() { sudo -u pathai "$@"; }
  # A trend refresh on the server rewrites data/signals: keep that data across the reset when it is newer than git's.
  keep=$(app mktemp -d)
  app cp -a data/signals/. "$keep"/
  app git fetch -q origin main
  old=$(app git rev-parse HEAD)
  app git reset -q --hard origin/main
  newer=$(app python3 -c 'import json, sys
latest = lambda p: max(v.get("refreshed_at") or "" for v in json.load(open(p)).values())
print(int(latest(sys.argv[1]) > latest(sys.argv[2])))' "$keep/meta.json" data/signals/meta.json)
  if [ "$newer" = 1 ]; then app cp -a --remove-destination "$keep"/. data/signals/; fi
  app rm -rf "$keep"
  if ! app git diff --quiet "$old" HEAD -- requirements.txt; then
    app .venv/bin/pip install -q -r requirements.txt
  fi
  systemctl restart pathai
  echo "deployed: $(app git log --oneline -1)$([ "$newer" = 1 ] && echo ' (kept the newer trend data)')"
}

main "$@"
exit
