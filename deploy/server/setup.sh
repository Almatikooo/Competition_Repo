#!/usr/bin/env bash
# Sets up (or re-applies) Path.AI on an Ubuntu 24.04 server. Run as root from the checkout:
#
#   HOST=pathai.lol ALIASES="www.pathai.lol 157-230-248-132.sslip.io" bash /srv/pathai/app/deploy/server/setup.sh
#
# The app runs as the 'pathai' user under systemd (uvicorn on 127.0.0.1:8000) and Caddy serves it over HTTPS on $HOST;
# ALIASES (optional) are other names that lead to it. Without a domain, sslip.io turns the server's IP into a name
# (157-230-248-132.sslip.io), so a certificate works anyway. Secrets live only in /srv/pathai/app/.env, written by
# push_env.sh from the laptop.
set -euo pipefail
HOST=${HOST:?set HOST, e.g. pathai.lol}
ALIASES=${ALIASES:-}
APP=/srv/pathai/app
HERE=$(cd "$(dirname "$0")" && pwd)

if ! swapon --show | grep -q /swapfile; then       # 1 GB of RAM: swap keeps pip and trend refreshes clear of the OOM killer
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q >/dev/null
apt-get install -yq python3-venv caddy ufw >/dev/null
ufw allow OpenSSH >/dev/null && ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null && ufw --force enable >/dev/null

sudo -u pathai python3 -m venv "$APP/.venv"
sudo -u pathai "$APP/.venv/bin/pip" install -q --upgrade pip
sudo -u pathai "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

install -m 644 "$HERE/pathai.service" /etc/systemd/system/pathai.service
{                                                   # Caddy gets and renews the HTTPS certificates on its own
  printf '%s {\n\tencode zstd gzip\n\treverse_proxy 127.0.0.1:8000\n}\n' "$HOST"
  [ -z "$ALIASES" ] || printf '\n%s {\n\tredir https://%s{uri} permanent\n}\n' "${ALIASES// /, }" "$HOST"
  printf '\n# The bare IP address leads to the HTTPS name.\nhttp:// {\n\tredir https://%s{uri}\n}\n' "$HOST"
} > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable -q pathai
systemctl restart pathai
systemctl reload caddy 2>/dev/null || systemctl restart caddy
echo "Path.AI is served at https://$HOST"
