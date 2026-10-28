#!/usr/bin/env bash
# Run on the laptop: copies the model settings (LLM_*, incl. the backup model's) and the Google, GitHub and Apple sign-in keys (plus Apple's .p8 file) from the local .env and the certificate key to the server's .env,
# then restarts the app. Run it again after `python -m scripts.gpu recreate` (the pod's URL changes).
#
#   SERVER=root@157.230.248.132 bash deploy/server/push_env.sh
#
# The RunPod API key stays on the laptop: the server only talks to the model; it never starts or stops the GPU.
set -euo pipefail
SERVER=${SERVER:?set SERVER, e.g. root@157.230.248.132}
KEY=${SSH_KEY:-$HOME/.ssh/pathai_deploy}
cd "$(dirname "$0")/../.."
secret=$(grep -E '^CERT_SECRET=' .env | cut -d= -f2- || true)
[ -n "$secret" ] || secret=$(cat data/cache/cert_secret)      # same key as the laptop, so certificates already issued stay valid
{ grep -E '^(LLM_(BASE_URL|API_KEY|MODEL|BACKUP_BASE_URL|BACKUP_API_KEY|BACKUP_MODEL)|GOOGLE_CLIENT_(ID|SECRET)|GITHUB_CLIENT_(ID|SECRET)|APPLE_(CLIENT_ID|TEAM_ID|KEY_ID))=' .env || true; echo "CERT_SECRET=$secret"; } |
  ssh -i "$KEY" "$SERVER" 'umask 077; cat > /srv/pathai/app/.env && chown pathai: /srv/pathai/app/.env && systemctl restart pathai'
if [ -f data/cache/apple_signin_key.p8 ]; then      # the Sign in with Apple key: a file, readable by the app only
  ssh -i "$KEY" "$SERVER" 'umask 077; cat > /srv/pathai/app/data/cache/apple_signin_key.p8 && chown pathai: /srv/pathai/app/data/cache/apple_signin_key.p8 && systemctl restart pathai' < data/cache/apple_signin_key.p8
fi
echo "server .env updated and the app restarted"
