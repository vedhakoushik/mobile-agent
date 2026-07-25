#!/usr/bin/env python3
"""
Benchmark runner for the mobile agent's deploy mode.

Usage:
    python scripts/run_benchmark.py --app linkedin --tasks tasks/linkedin.json
    python scripts/run_benchmark.py --app linkedin --tasks tasks/linkedin.json --base-url http://localhost:8000

Tasks file format:
[
  {"task": "Find a software engineering job in Bangalore", "optimal_rounds": 6},
  {"task": "Search for Python developer roles", "optimal_rounds": 4}
]

Reports:
  TSR (Task Success Rate)     — fraction of tasks where task_complete == true
  CE  (Cost Efficiency)       — mean(actual_rounds / optimal_rounds), lower is better
  KUR (KB Utilisation Rate)   — fraction of tasks where >=1 KB doc existed for the app before the run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib import request as urlreq
from urllib.error import URLError

POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 300.0


@dataclass
class TaskResult:
    task: str
    optimal_rounds: int
    actual_rounds: int = 0
    task_complete: bool = False
    failure_reason: str | None = None
    error: str | None = None


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlreq.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _get(url: str) -> dict:
    with urlreq.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def run_task(base_url: str, app_name: str, provider: str, max_rounds: int, task_def: dict) -> TaskResult:
    result = TaskResult(task=task_def["task"], optimal_rounds=task_def.get("optimal_rounds", max_rounds))

    try:
        started = _post(
            f"{base_url}/api/v1/agent/deploy",
            {"task": result.task, "app_name": app_name, "max_rounds": max_rounds, "provider": provider},
        )
    except URLError as e:
        result.error = f"failed to start: {e}"
        return result

    session_id = started["session_id"]
    deadline = time.monotonic() + POLL_TIMEOUT_S

    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        try:
            status = _get(f"{base_url}/api/v1/agent/{session_id}")
        except URLError as e:
            result.error = f"polling failed: {e}"
            return result

        result.actual_rounds = status["round_num"]
        if status["status"] in ("done", "error"):
            result.task_complete = status["task_complete"]
            result.failure_reason = status.get("failure_reason")
            return result

    result.error = "timed out waiting for completion"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the mobile agent deploy benchmark")
    parser.add_argument("--app", required=True, help="App name (must match KB namespace)")
    parser.add_argument("--tasks", required=True, type=Path, help="Path to tasks JSON file")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--provider", default="gemini", help="LLM provider")
    parser.add_argument("--max-rounds", type=int, default=20, help="Max rounds per task")
    args = parser.parse_args()

    tasks: list[dict] = json.loads(args.tasks.read_text())
    if not tasks:
        print("No tasks found in file", file=sys.stderr)
        return 1

    try:
        kb_before = _get(f"{args.base_url}/api/v1/kb/{args.app}")
        kb_had_docs = kb_before.get("count", 0) > 0
    except URLError:
        kb_had_docs = False

    results: list[TaskResult] = []
    for i, task_def in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task_def['task']}")
        r = run_task(args.base_url, args.app, args.provider, args.max_rounds, task_def)
        results.append(r)
        status = "OK" if r.task_complete else ("ERROR" if r.error else "FAILED")
        print(f"    -> {status}  rounds={r.actual_rounds}  {r.failure_reason or r.error or ''}")

    total = len(results)
    successes = sum(1 for r in results if r.task_complete)
    tsr = successes / total if total else 0.0

    ce_values = [
        r.actual_rounds / r.optimal_rounds
        for r in results
        if r.task_complete and r.optimal_rounds > 0
    ]
    ce = sum(ce_values) / len(ce_values) if ce_values else float("nan")

    kur = 1.0 if kb_had_docs else 0.0

    print("\n=== Benchmark Summary ===")
    print(f"Tasks run:            {total}")
    print(f"Task Success Rate:    {tsr * 100:.1f}%  ({successes}/{total})")
    print(f"Cost Efficiency:      {ce:.2f}  (actual/optimal rounds, lower is better)")
    print(f"KB Utilisation Rate:  {kur * 100:.0f}%  (KB pre-populated for '{args.app}': {kb_had_docs})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
