"""End-to-end task-completion benchmark harness.

Drives the REAL running backend over HTTP (the same routes the Deploy pipeline
exposes in the live FastAPI app) against a real connected Android device, and
scores task_complete rate / rounds / tokens / cost / duration.

Unlike run_llm_quality.py, this does not call agent internals directly — it
needs the real device registry/session machinery that is only wired up inside
the live app.

Usage (from the project root, backend/venv activated):
    python -m backend.eval.run_benchmark
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .benchmark_tasks import BENCHMARK_TASKS

load_dotenv()

BASE_URL = os.environ.get("BENCHMARK_BASE_URL", "http://localhost:8000")

POLL_INTERVAL_SECONDS = 3
TASK_TIMEOUT_SECONDS = 180

REPORT_PATH = Path(__file__).resolve().parent / "reports" / "benchmark_latest.json"

_TERMINAL_STATUSES = {"done", "error"}


def _auth_headers() -> dict:
    key = os.environ.get("API_KEY")
    if key:
        return {"X-API-Key": key}
    return {}


def _fetch_device_status(client: httpx.Client) -> dict:
    """Return the /device/status payload, or exit(1) if the backend is unreachable."""
    try:
        resp = client.get("/api/v1/device/status")
    except httpx.HTTPError as exc:
        print(f"Could not reach backend at {BASE_URL}: {exc}")
        sys.exit(1)
    if resp.status_code != 200:
        print(f"Backend returned {resp.status_code} for /device/status: {resp.text}")
        sys.exit(1)
    return resp.json()


def _empty_result(task: dict, failure_reason: str, duration: float) -> dict:
    return {
        "name": task["name"],
        "task_complete": False,
        "status": "error",
        "round_num": 0,
        "tokens_used": 0,
        "estimated_cost_usd": 0.0,
        "llm_call_count": 0,
        "escalation_count": 0,
        "failure_reason": failure_reason,
        "duration_seconds": round(duration, 2),
    }


def _run_task(client: httpx.Client, task: dict) -> dict:
    body = {
        k: task[k]
        for k in ("task", "app_name", "max_rounds", "provider", "max_llm_calls")
    }
    started = time.monotonic()

    try:
        deploy = client.post("/api/v1/agent/deploy", json=body)
    except httpx.HTTPError as exc:
        return _empty_result(task, f"deploy request failed: {exc}", time.monotonic() - started)
    if deploy.status_code != 200:
        detail = deploy.text
        try:
            detail = deploy.json().get("detail", detail)
        except ValueError:
            pass
        return _empty_result(
            task, f"deploy failed ({deploy.status_code}): {detail}", time.monotonic() - started
        )
    session_id = deploy.json()["session_id"]
    print(f"  session {session_id}", flush=True)

    status = None
    while True:
        elapsed = time.monotonic() - started
        if elapsed >= TASK_TIMEOUT_SECONDS:
            break
        try:
            resp = client.get(f"/api/v1/agent/{session_id}")
        except httpx.HTTPError as exc:
            print(f"  poll error: {exc}", flush=True)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if resp.status_code == 404:
            status = {"status": "error", "failure_reason": "session not found"}
            break
        if resp.status_code != 200:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        status = resp.json()
        print(
            f"  [{elapsed:5.1f}s] status={status.get('status')} "
            f"round={status.get('round_num')}",
            flush=True,
        )
        if status.get("status") in _TERMINAL_STATUSES:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    duration = time.monotonic() - started
    if status is None:
        return _empty_result(task, "session ended without a terminal status", duration)
    if status.get("status") not in _TERMINAL_STATUSES:
        status["status"] = "timed_out"

    return {
        "name": task["name"],
        "task_complete": bool(status.get("task_complete")),
        "status": status.get("status"),
        "round_num": status.get("round_num", 0),
        "tokens_used": status.get("tokens_used", 0),
        "estimated_cost_usd": status.get("estimated_cost_usd", 0.0),
        "llm_call_count": status.get("llm_call_count", 0),
        "escalation_count": status.get("escalation_count", 0),
        "failure_reason": status.get("failure_reason"),
        "duration_seconds": round(duration, 2),
    }


def _print_summary(results: list[dict]) -> None:
    print("\nBenchmark summary:")
    header = (
        f"{'task':<20} {'complete':<9} {'status':<10} {'rounds':<7} {'tokens':<8} "
        f"{'cost_usd':<10} {'llm_calls':<10} {'escal':<7} {'duration_s':<11}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        cost = f"{r['estimated_cost_usd']:.4f}"
        print(
            f"{r['name']:<20} {str(r['task_complete']):<9} {r['status']:<10} "
            f"{r['round_num']:<7} {r['tokens_used']:<8} {cost:<10} "
            f"{r['llm_call_count']:<10} {r['escalation_count']:<7} "
            f"{r['duration_seconds']:<11.1f}"
        )


def _build_report(results: list[dict], device_serial) -> dict:
    n = len(results)
    completed = sum(1 for r in results if r["task_complete"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "device_serial": device_serial,
        "results": results,
        "summary": {
            "tasks_total": n,
            "tasks_complete": completed,
            "tasks_failed": n - completed,
            "avg_rounds": round(sum(r["round_num"] for r in results) / n, 2) if n else 0.0,
            "total_tokens_used": sum(r["tokens_used"] for r in results),
            "total_cost_usd": round(sum(r["estimated_cost_usd"] for r in results), 4),
            "total_llm_calls": sum(r["llm_call_count"] for r in results),
            "total_escalations": sum(r["escalation_count"] for r in results),
            "total_duration_seconds": round(sum(r["duration_seconds"] for r in results), 2),
        },
    }


def main() -> None:
    headers = _auth_headers()
    if not headers:
        print("WARNING: API_KEY not set in .env — backend may reject requests", flush=True)

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0) as client:
        status = _fetch_device_status(client)
        if not status.get("connected"):
            print(
                f"No Android device connected — {status.get('message')}. "
                "Benchmark aborted; connect a device and retry.",
                flush=True,
            )
            sys.exit(1)
        device_serial = status.get("serial")
        print(f"Device connected: {device_serial}", flush=True)

        results = []
        for task in BENCHMARK_TASKS:
            label = f"{task['name']} (app={task['app_name']}, provider={task['provider']})"
            print(f"Running task: {label}", flush=True)
            result = _run_task(client, task)
            results.append(result)
            print(
                f"  -> status={result['status']}, task_complete={result['task_complete']}",
                flush=True,
            )

    _print_summary(results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = json.dumps(_build_report(results, device_serial), indent=2)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
