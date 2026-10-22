"""Turn the Path.AI GPU (a RunPod pod serving Qwen with vLLM) on and off from the terminal.

    python -m scripts.gpu create      first time: creates the pod and writes its address and keys into .env
    python -m scripts.gpu start       start it again; the model answers ≈3–5 min later (see `wait`)
    python -m scripts.gpu stop        stop it: GPU billing stops (the disk with the weights stays, ≈$0.27/day)
    python -m scripts.gpu status      running or not, for how long, what this session costs, balance left
    python -m scripts.gpu wait        wait until the model answers
    python -m scripts.gpu recreate    when RunPod has no free GPU for the stopped pod: a new pod (downloads the model again)

Needs RUNPOD_API_KEY in .env (RunPod → Settings → API Keys). Inside the pod a watchdog (deploy/runpod/watchdog.py)
stops it after IDLE_MINUTES without requests, so a forgotten GPU stops on its own.
"""
import argparse
import datetime as dt
import re
import secrets
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
DEPLOY = ROOT / "deploy/runpod"
API = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
DEFAULTS = {"VLLM_IMAGE": "vllm/vllm-openai:v0.31.0", "GPU_TYPE": "NVIDIA RTX A6000", "LLM_MODEL": "Qwen/Qwen3.8-27B-FP8",
            "GPU_CLOUD": "SECURE", "IDLE_MINUTES": "20", "MAX_HOURS": "10", "MAX_MODEL_LEN": "16384"}
PRICE_HINT = {"SECURE": 0.59, "COMMUNITY": 0.33}    # RTX A6000 $/h on runpod.io/pricing, checked 2026-10-20
VOLUME_GB = 40                                      # Qwen3.8-27B-FP8 is 30.9 GB


class GpuError(RuntimeError):
    pass


# ---------------------------------------------------------------- .env
def read_env(path: Path | None = None) -> dict[str, str]:
    path = path or ENV_FILE
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(updates: dict[str, str], path: Path | None = None) -> None:
    """Sets keys in .env, keeping every other line and comment as it is."""
    path = path or ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    todo = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in todo:
            lines[i] = f"{key}={todo.pop(key)}"
    lines += [f"{k}={v}" for k, v in todo.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def setting(env: dict, key: str) -> str:
    return env.get(key) or DEFAULTS[key]


# ---------------------------------------------------------------- RunPod API
class RunPod:
    def __init__(self, key: str, transport: httpx.BaseTransport | None = None) -> None:
        if not key:
            raise GpuError("RUNPOD_API_KEY is missing in .env (RunPod → Settings → API Keys).")
        self.key = key
        self.http = httpx.Client(base_url=API, headers={"Authorization": f"Bearer {key}"}, timeout=60, transport=transport)
        self.transport = transport

    def _call(self, method: str, path: str, **kw) -> dict:
        resp = self.http.request(method, path, **kw)
        if resp.status_code >= 400:
            raise GpuError(f"RunPod said {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}

    def pod(self, pod_id: str) -> dict:
        return self._call("GET", f"/pods/{pod_id}")

    def create(self, body: dict) -> dict:
        return self._call("POST", "/pods", json=body)

    def start(self, pod_id: str) -> dict:
        return self._call("POST", f"/pods/{pod_id}/start")

    def stop(self, pod_id: str) -> dict:
        return self._call("POST", f"/pods/{pod_id}/stop")

    def terminate(self, pod_id: str) -> dict:
        return self._call("DELETE", f"/pods/{pod_id}")

    def balance(self) -> float | None:
        """Credit left, or None if RunPod does not say (best effort: shown in `status` only)."""
        query = {"query": "query { myself { clientBalance } }"}
        try:
            with httpx.Client(timeout=20, transport=self.transport) as c:
                resp = c.post(GRAPHQL, json=query, headers={"Authorization": f"Bearer {self.key}"})
                if resp.status_code >= 400:   # the documented form passes the key as a query parameter
                    resp = c.post(GRAPHQL, params={"api_key": self.key}, json=query)
                return float(resp.json()["data"]["myself"]["clientBalance"])
        except Exception:
            return None


# ---------------------------------------------------------------- the pod
def start_command() -> str:
    """The pod's start command: writes the watchdog onto the volume, then runs start.sh (vLLM + watchdog)."""
    watchdog = (DEPLOY / "watchdog.py").read_text(encoding="utf-8")
    start = (DEPLOY / "start.sh").read_text(encoding="utf-8")
    return f"cat > /workspace/watchdog.py <<'PATHAI_WATCHDOG'\n{watchdog}PATHAI_WATCHDOG\n{start}"


def pod_body(env: dict, vllm_key: str, cloud: str, idle: int) -> dict:
    model = setting(env, "LLM_MODEL")
    return {
        "name": "pathai-qwen", "imageName": setting(env, "VLLM_IMAGE"), "gpuTypeIds": [setting(env, "GPU_TYPE")], "gpuCount": 1,
        "cloudType": cloud, "containerDiskInGb": 30, "volumeInGb": VOLUME_GB, "volumeMountPath": "/workspace", "ports": ["8000/http"],
        "env": {"MODEL": model, "VLLM_API_KEY": vllm_key, "HF_HOME": "/workspace/hf", "MAX_MODEL_LEN": setting(env, "MAX_MODEL_LEN"),
                "IDLE_MINUTES": str(idle), "STARTUP_MINUTES": "40", "MAX_HOURS": setting(env, "MAX_HOURS")},
        "dockerEntrypoint": ["bash", "-c"], "dockerStartCmd": [start_command()],
    }


def base_url(pod_id: str) -> str:
    return f"https://{pod_id}-8000.proxy.runpod.net/v1"


def model_ready(env: dict, transport: httpx.BaseTransport | None = None) -> bool:
    url, key = env.get("LLM_BASE_URL"), env.get("LLM_API_KEY")
    if not url:
        return False
    try:
        with httpx.Client(timeout=8, transport=transport) as c:
            resp = c.get(f"{url}/models", headers={"Authorization": f"Bearer {key}"} if key else {})
            return resp.status_code == 200 and bool(resp.json().get("data"))
    except Exception:
        return False


def uptime_hours(pod: dict) -> float | None:
    started = pod.get("lastStartedAt")
    if pod.get("desiredStatus") != "RUNNING" or not started:
        return None
    text = str(started).replace(" UTC", "").replace("Z", "+00:00")     # RunPod: "2026-10-22 03:11:54.149 +0000 UTC"
    text = re.sub(r" ([+-]\d{2})(\d{2})$", r"\1:\2", text).replace(" ", "T", 1)
    try:
        when = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (dt.datetime.now(dt.timezone.utc) - when).total_seconds() / 3600)


# ---------------------------------------------------------------- commands
def confirm(question: str, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise GpuError(f"{question} Re-run with --yes to confirm.")
    if input(f"{question} [y/N] ").strip().lower() not in {"y", "yes"}:
        raise GpuError("Cancelled.")


def create(rp: RunPod, env: dict, cloud: str, idle: int, yes: bool, replace: bool = False) -> dict:
    old = env.get("RUNPOD_POD_ID")
    if old and not replace:
        try:
            existing = rp.pod(old)
        except GpuError:
            existing = None                       # gone from RunPod: a new one is created
        if existing and existing.get("desiredStatus") != "TERMINATED":
            raise GpuError(f"Pod {old} already exists: use `python -m scripts.gpu start` (or `recreate`).")
    confirm(f"Create a GPU pod ({setting(env, 'GPU_TYPE')}, {cloud}, ≈${PRICE_HINT.get(cloud, 0.59)}/h while running)?", yes)
    if old and replace:
        try:
            rp.terminate(old)
            print(f"Removed the old pod {old}.")
        except GpuError as exc:
            print(f"Old pod {old} not removed ({exc}); remove it in the RunPod console if it is still listed.")
    vllm_key = env.get("LLM_API_KEY") or secrets.token_urlsafe(24)
    pod = rp.create(pod_body(env, vllm_key, cloud, idle))
    pod_id = pod["id"]
    write_env({"RUNPOD_POD_ID": pod_id, "LLM_BASE_URL": base_url(pod_id), "LLM_API_KEY": vllm_key, "LLM_MODEL": setting(env, "LLM_MODEL")})
    print(f"Pod {pod_id} created, ${pod.get('costPerHr', '?')}/h while running. Its address and keys are in .env.")
    print("The first start downloads the model (≈31 GB). Wait for it: python -m scripts.gpu wait")
    return pod


def start(rp: RunPod, env: dict, yes: bool) -> None:
    pod_id = need_pod(env)
    confirm(f"Start the GPU pod {pod_id} (billing runs until it stops)?", yes)
    try:
        rp.start(pod_id)
    except GpuError as exc:
        raise GpuError(f"{exc}\nRunPod may have no free GPU for this pod now: try again later or `python -m scripts.gpu recreate`.")
    pod = rp.pod(pod_id)
    gpus = (pod.get("gpu") or {}).get("count", pod.get("gpuCount", 1))
    if gpus == 0:
        rp.stop(pod_id)
        raise GpuError("RunPod started the pod without a GPU (none free on its machine), so it was stopped again. "
                       "Try later or `python -m scripts.gpu recreate`.")
    print(f"Starting {pod_id}. The model answers in ≈3–5 min: python -m scripts.gpu wait")


def stop(rp: RunPod, env: dict) -> None:
    pod_id = need_pod(env)
    rp.stop(pod_id)
    print(f"Stopped {pod_id}. GPU billing has stopped; the disk with the model costs ≈$0.27/day.")


def status(rp: RunPod, env: dict) -> dict:
    pod_id = need_pod(env)
    pod = rp.pod(pod_id)
    hours = uptime_hours(pod)
    state = pod.get("desiredStatus", "?")
    line = f"Pod {pod_id}: {state}"
    if hours is not None:
        line += f" for {hours:.1f} h (≈${hours * float(pod.get('costPerHr') or 0):.2f} this session, ${pod.get('costPerHr')}/h)"
    print(line)
    if state == "RUNNING":
        print("Model: ready" if model_ready(env, rp.transport) else "Model: not answering yet (loading, or stopped by the watchdog)")
    left = rp.balance()
    if left is not None:
        print(f"Balance: ${left:.2f}")
    return {"state": state, "hours": hours, "balance": left}


def wait(env: dict, minutes: float = 30, transport: httpx.BaseTransport | None = None) -> None:
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        if model_ready(env, transport):
            print("\nThe model is ready.")
            return
        print(".", end="", flush=True)
        time.sleep(15)
    raise GpuError(f"The model did not answer within {minutes:g} min. Check the pod's logs in the RunPod console.")


def need_pod(env: dict) -> str:
    pod_id = env.get("RUNPOD_POD_ID")
    if not pod_id:
        raise GpuError("No pod yet: python -m scripts.gpu create")
    return pod_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.gpu", description="Turn the Path.AI GPU on and off.")
    ap.add_argument("command", choices=["create", "start", "stop", "status", "wait", "recreate"])
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    ap.add_argument("--cloud", choices=["SECURE", "COMMUNITY"], help="for create/recreate (default SECURE)")
    ap.add_argument("--idle", type=int, help="minutes without requests before the pod stops itself (default 20)")
    ap.add_argument("--minutes", type=float, default=30, help="how long `wait` waits")
    args = ap.parse_args(argv)
    env = read_env()
    try:
        if args.command == "wait":
            wait(env, args.minutes)
            return 0
        rp = RunPod(env.get("RUNPOD_API_KEY", ""))
        cloud = args.cloud or setting(env, "GPU_CLOUD")
        idle = args.idle or int(setting(env, "IDLE_MINUTES"))
        if args.command in ("create", "recreate"):
            create(rp, env, cloud, idle, args.yes, replace=args.command == "recreate")
        elif args.command == "start":
            start(rp, env, args.yes)
        elif args.command == "stop":
            stop(rp, env)
        else:
            status(rp, env)
    except GpuError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
