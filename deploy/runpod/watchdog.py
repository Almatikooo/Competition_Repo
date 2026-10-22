"""Runs inside the RunPod pod next to vLLM and stops the pod so that a forgotten GPU never eats the budget.

It stops the pod when the model has had no requests for IDLE_MINUTES, when it never comes up within STARTUP_MINUTES
(a broken start), or after MAX_HOURS in total. RunPod sets RUNPOD_POD_ID and a pod-scoped RUNPOD_API_KEY in every pod,
so no account key is needed here. Standard library only: the vLLM image has nothing else we can rely on.
"""
import os
import time
import urllib.request

METRICS = "http://127.0.0.1:8000/metrics"   # vLLM's Prometheus endpoint (open, unlike /v1)
CHECK_EVERY = 30


def read_metrics(text: str) -> tuple[float, float]:
    """(requests finished so far, requests running or waiting now) from vLLM's Prometheus text."""
    done = busy = 0.0
    for line in text.splitlines():
        if line.startswith("vllm:request_success_total"):
            done += float(line.rsplit(" ", 1)[1])
        elif line.startswith(("vllm:num_requests_running", "vllm:num_requests_waiting")):
            busy += float(line.rsplit(" ", 1)[1])
    return done, busy


class Watchdog:
    def __init__(self, idle_minutes: float, startup_minutes: float, max_hours: float, now: float) -> None:
        self.idle, self.startup, self.max = idle_minutes * 60, startup_minutes * 60, max_hours * 3600
        self.started = now
        self.last_use: float | None = None      # None until the model has answered /metrics once
        self.done: float | None = None

    def tick(self, now: float, metrics: str | None) -> str | None:
        """Feeds one look at the server; returns why the pod should stop, or None."""
        if now - self.started > self.max:
            return f"it has run for {self.max / 3600:g} h (MAX_HOURS)"
        if metrics is None:
            if self.last_use is None:
                return "the model did not come up" if now - self.started > self.startup else None
        else:
            done, busy = read_metrics(metrics)
            if self.last_use is None or busy > 0 or done != self.done:
                self.last_use, self.done = now, done
        if self.last_use is not None and now - self.last_use > self.idle:
            return f"no requests for {self.idle / 60:g} min"
        return None


def stop_pod() -> None:
    pod, key = os.environ["RUNPOD_POD_ID"], os.environ["RUNPOD_API_KEY"]
    req = urllib.request.Request(f"https://rest.runpod.io/v1/pods/{pod}/stop", method="POST",
                                 headers={"Authorization": f"Bearer {key}"})
    urllib.request.urlopen(req, timeout=30).read()


def main() -> None:
    env = os.environ.get
    dog = Watchdog(float(env("IDLE_MINUTES", "20")), float(env("STARTUP_MINUTES", "40")), float(env("MAX_HOURS", "10")), time.time())
    print(f"[watchdog] on: stops the pod after {env('IDLE_MINUTES', '20')} idle minutes or {env('MAX_HOURS', '10')} h", flush=True)
    while True:
        time.sleep(CHECK_EVERY)
        try:
            metrics = urllib.request.urlopen(METRICS, timeout=5).read().decode()
        except Exception:
            metrics = None
        reason = dog.tick(time.time(), metrics)
        if reason:
            print(f"[watchdog] stopping the pod: {reason}", flush=True)
            try:
                stop_pod()
                time.sleep(300)
            except Exception as exc:              # try again on the next check
                print(f"[watchdog] stop failed: {exc}", flush=True)


if __name__ == "__main__":
    main()
