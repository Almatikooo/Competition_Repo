"""The GPU on/off tooling and the in-pod watchdog, against a fake RunPod API: no account, no GPU, no cost."""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from scripts import gpu

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("watchdog", ROOT / "deploy/runpod/watchdog.py")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)

METRICS = """# HELP vllm:num_requests_running Number of requests in model execution batches.
vllm:num_requests_running{model_name="Qwen/Qwen3.8-27B-FP8"} %s
vllm:num_requests_waiting{model_name="Qwen/Qwen3.8-27B-FP8"} 0.0
vllm:request_success_total{finished_reason="stop",model_name="Qwen/Qwen3.8-27B-FP8"} %s
vllm:request_success_total{finished_reason="length",model_name="Qwen/Qwen3.8-27B-FP8"} 1.0
"""


# ---------------------------------------------------------------- watchdog
def test_watchdog_reads_vllm_metrics():
    assert watchdog.read_metrics(METRICS % ("2.0", "5.0")) == (6.0, 2.0)


def test_watchdog_stops_an_idle_pod_but_never_a_busy_one():
    dog = watchdog.Watchdog(idle_minutes=20, startup_minutes=40, max_hours=10, now=0)
    assert dog.tick(60, None) is None                         # still loading the model
    assert dog.tick(120, METRICS % ("0.0", "0.0")) is None    # up: the idle clock starts now
    assert dog.tick(120 + 19 * 60, METRICS % ("0.0", "0.0")) is None
    assert dog.tick(120 + 19 * 60 + 30, METRICS % ("1.0", "0.0")) is None   # still answering
    assert dog.tick(120 + 39 * 60, METRICS % ("0.0", "3.0")) is None        # a request finished: clock restarts
    t = 120 + 39 * 60 + 20 * 60 + 1
    assert "no requests for 20 min" in dog.tick(t, METRICS % ("0.0", "3.0"))


def test_watchdog_stops_a_pod_that_never_comes_up_or_runs_too_long():
    dog = watchdog.Watchdog(idle_minutes=20, startup_minutes=40, max_hours=10, now=0)
    assert dog.tick(39 * 60, None) is None
    assert dog.tick(41 * 60, None) == "the model did not come up"
    busy = watchdog.Watchdog(idle_minutes=20, startup_minutes=40, max_hours=10, now=0)
    assert busy.tick(60, METRICS % ("4.0", "0.0")) is None
    assert "10 h" in busy.tick(10 * 3600 + 1, METRICS % ("4.0", "9.0"))


# ---------------------------------------------------------------- .env and the pod
def test_env_updates_keep_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# keys\nRUNPOD_API_KEY=rp_secret\nLLM_BASE_URL=\nCERT_SECRET=abc\n")
    gpu.write_env({"LLM_BASE_URL": "https://p1-8000.proxy.runpod.net/v1", "RUNPOD_POD_ID": "p1"}, env)
    assert env.read_text() == "# keys\nRUNPOD_API_KEY=rp_secret\nLLM_BASE_URL=https://p1-8000.proxy.runpod.net/v1\nCERT_SECRET=abc\nRUNPOD_POD_ID=p1\n"
    assert gpu.read_env(env)["RUNPOD_POD_ID"] == "p1"


def test_start_command_writes_the_watchdog_and_serves_qwen():
    cmd = gpu.start_command()
    assert cmd.startswith("cat > /workspace/watchdog.py <<'PATHAI_WATCHDOG'\n")
    assert "def tick(" in cmd and "\nPATHAI_WATCHDOG\n" in cmd
    assert 'vllm serve "$MODEL"' in cmd and cmd.rstrip().endswith("exec python3 /workspace/watchdog.py")


@pytest.fixture
def fake_runpod(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("RUNPOD_API_KEY=rp_secret\n")
    monkeypatch.setattr(gpu, "ENV_FILE", env_file)
    calls = []
    pods = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
        assert request.headers["Authorization"] == "Bearer rp_secret"
        path = request.url.path.removeprefix("/v1")
        if request.method == "POST" and path == "/pods":
            pods["p1"] = {"id": "p1", "desiredStatus": "RUNNING", "costPerHr": 0.59, "gpu": {"count": 1}}
            return httpx.Response(201, json=pods["p1"])
        pod_id = path.split("/")[2]
        if pod_id not in pods:
            return httpx.Response(404, json={"error": "pod not found"})
        if path.endswith("/stop"):
            pods[pod_id]["desiredStatus"] = "EXITED"
        elif path.endswith("/start"):
            pods[pod_id]["desiredStatus"] = "RUNNING"
        elif request.method == "DELETE":
            pods.pop(pod_id)
            return httpx.Response(204)
        return httpx.Response(200, json=pods.get(pod_id, {}))

    rp = gpu.RunPod("rp_secret", transport=httpx.MockTransport(handler))
    return rp, env_file, calls, pods


def test_create_sends_a_qwen_pod_and_writes_its_address(fake_runpod):
    rp, env_file, calls, pods = fake_runpod
    gpu.create(rp, gpu.read_env(env_file), "SECURE", 20, yes=True)
    method, path, body = calls[-1]
    assert (method, path) == ("POST", "/v1/pods")
    assert body["gpuTypeIds"] == ["NVIDIA RTX A6000"] and body["cloudType"] == "SECURE" and body["ports"] == ["8000/http"]
    assert body["imageName"].startswith("vllm/vllm-openai:v") and body["volumeMountPath"] == "/workspace"
    assert body["dockerEntrypoint"] == ["bash", "-c"] and "watchdog" in body["dockerStartCmd"][0]
    assert body["env"]["MODEL"] == "Qwen/Qwen3.8-27B-FP8" and body["env"]["IDLE_MINUTES"] == "20" and len(body["env"]["VLLM_API_KEY"]) > 20
    env = gpu.read_env(env_file)
    assert env["RUNPOD_POD_ID"] == "p1" and env["LLM_BASE_URL"] == "https://p1-8000.proxy.runpod.net/v1"
    assert env["LLM_API_KEY"] == body["env"]["VLLM_API_KEY"] and env["RUNPOD_API_KEY"] == "rp_secret"
    with pytest.raises(gpu.GpuError, match="already exists"):       # a second create does not make a second pod
        gpu.create(rp, env, "SECURE", 20, yes=True)


def test_start_stop_and_status(fake_runpod, capsys):
    rp, env_file, calls, pods = fake_runpod
    gpu.create(rp, gpu.read_env(env_file), "SECURE", 20, yes=True)
    env = gpu.read_env(env_file)
    gpu.stop(rp, env)
    assert pods["p1"]["desiredStatus"] == "EXITED" and gpu.status(rp, env)["state"] == "EXITED"
    gpu.start(rp, env, yes=True)
    assert pods["p1"]["desiredStatus"] == "RUNNING"
    pods["p1"]["gpu"] = {"count": 0}                                 # RunPod restarted it on a machine with no free GPU
    with pytest.raises(gpu.GpuError, match="without a GPU"):
        gpu.start(rp, env, yes=True)
    assert pods["p1"]["desiredStatus"] == "EXITED"                   # ...so it is stopped again, not billed for nothing


def test_recreate_replaces_the_pod_and_keeps_the_model_key(fake_runpod):
    rp, env_file, calls, pods = fake_runpod
    gpu.create(rp, gpu.read_env(env_file), "SECURE", 20, yes=True)
    key = gpu.read_env(env_file)["LLM_API_KEY"]
    gpu.create(rp, gpu.read_env(env_file), "COMMUNITY", 30, yes=True, replace=True)
    assert ("DELETE", "/v1/pods/p1", None) in calls
    assert calls[-1][2]["cloudType"] == "COMMUNITY" and calls[-1][2]["env"]["VLLM_API_KEY"] == key


def test_nothing_costly_happens_without_a_confirmation(fake_runpod, monkeypatch):
    rp, env_file, calls, pods = fake_runpod
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(gpu.GpuError, match="--yes"):
        gpu.create(rp, gpu.read_env(env_file), "SECURE", 20, yes=False)
    assert not pods


def test_uptime_from_runpod_timestamps():
    assert gpu.uptime_hours({"desiredStatus": "EXITED", "lastStartedAt": "2026-10-22T01:00:00Z"}) is None
    assert gpu.uptime_hours({"desiredStatus": "RUNNING", "lastStartedAt": "2020-01-01T00:00:00Z"}) > 1000
    assert gpu.uptime_hours({"desiredStatus": "RUNNING", "lastStartedAt": "2020-01-01 00:00:00"}) > 1000
    assert gpu.uptime_hours({"desiredStatus": "RUNNING", "lastStartedAt": "soon"}) is None
    assert gpu.uptime_hours({"desiredStatus": "RUNNING", "lastStartedAt": "2020-01-01 03:11:54.149 +0000 UTC"}) > 1000   # RunPod's format
