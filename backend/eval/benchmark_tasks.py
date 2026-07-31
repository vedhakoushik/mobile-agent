"""Fixed task list for the end-to-end benchmark harness.

These tasks run against a real physical phone, so they are deliberately
safe/read-only/idempotent: search and navigation only — no purchases, no
messages sent, no account changes, nothing destructive.
"""

BENCHMARK_TASKS = [
    {
        "name": "youtube_search",
        "app_name": "youtube",
        "task": "Search for lofi music",
        "max_rounds": 5,
        "max_llm_calls": 4,
        "provider": "ollama",
    },
    {
        "name": "youtube_check_home",
        "app_name": "youtube",
        "task": "Check what videos are currently shown on the home screen",
        "max_rounds": 3,
        "max_llm_calls": 2,
        "provider": "ollama",
    },
]
