import asyncio

from backend.demonstrations.player import DemonstrationPlayer
from backend.demonstrations.recorder import DemonstrationRecorder

SAMPLE_XML = (
    '<hierarchy rotation="0">'
    '<node index="0" text="Search" resource-id="com.linkedin:id/search_btn" '
    'class="android.widget.ImageButton" content-desc="Search jobs" '
    'bounds="[20,100][200,200]" clickable="true" focusable="true" scrollable="false"/>'
    "</hierarchy>"
)

PRE_STATE = [
    {"resource_id": "com.linkedin:id/search_btn", "class_name": "android.widget.ImageButton"}
]


class FakeDevice:
    def __init__(self, xml=""):
        self._xml = xml
        self.calls = []

    async def pull_xml(self):
        return self._xml

    async def tap(self, x, y):
        self.calls.append(("tap", x, y))

    async def text(self, content):
        self.calls.append(("text", content))

    async def clear_text(self):
        self.calls.append(("clear_text",))

    async def swipe(self, direction, from_x=None, from_y=None):
        self.calls.append(("swipe", direction, from_x, from_y))

    async def long_press(self, x, y):
        self.calls.append(("long_press", x, y))

    async def key_event(self, code):
        self.calls.append(("key_event", code))


class FakeCredentials:
    def __init__(self, secrets):
        self._secrets = secrets

    def has(self, secret_id):
        return secret_id in self._secrets

    def resolve(self, secret_id):
        return self._secrets[secret_id]


# ── Recorder ───────────────────────────────────────────────────────────────────


def test_capture_step_appends_step_shape():
    device = FakeDevice(xml=SAMPLE_XML)
    recorder = DemonstrationRecorder(device, "linkedin", "search for jobs")

    async def run():
        await recorder.capture_step("tap", x=10, y=20, description="tap the search button")
        await recorder.capture_step("swipe", direction="up")

    asyncio.run(run())
    assert len(recorder.steps) == 2
    step = recorder.steps[0]
    assert set(step) == {"action_type", "pre_state", "params", "description"}
    assert step["action_type"] == "tap"
    assert step["pre_state"] == PRE_STATE
    assert step["params"] == {"x": 10, "y": 20}
    assert step["description"] == "tap the search button"
    assert recorder.steps[1]["params"] == {"direction": "up"}
    assert recorder.steps[1]["description"] == ""


def test_save_and_load_round_trip(tmp_path):
    device = FakeDevice(xml=SAMPLE_XML)
    recorder = DemonstrationRecorder(device, "linkedin", "search for jobs")

    async def run():
        await recorder.capture_step("tap", x=10, y=20, description="tap the search button")
        await recorder.capture_step("text", content="SDE Bangalore", description="type the query")

    asyncio.run(run())
    path = tmp_path / "nested" / "demo.json"
    recorder.save(str(path))
    assert path.exists()

    data = DemonstrationPlayer(device).load(str(path))
    assert data["app_name"] == "linkedin"
    assert data["task_description"] == "search for jobs"
    assert data["schema_version"] == 1
    assert data["steps"] == recorder.steps


# ── Similarity ─────────────────────────────────────────────────────────────────


def test_similarity_identical_states():
    player = DemonstrationPlayer(FakeDevice())
    assert player._similarity(PRE_STATE, list(PRE_STATE)) == 1.0


def test_similarity_disjoint_states():
    player = DemonstrationPlayer(FakeDevice())
    other = [{"resource_id": "com.x:id/other", "class_name": "android.widget.TextView"}]
    assert player._similarity(PRE_STATE, other) == 0.0


def test_similarity_partial_overlap():
    player = DemonstrationPlayer(FakeDevice())
    a = [{"resource_id": "a", "class_name": "X"}, {"resource_id": "b", "class_name": "Y"}]
    b = [{"resource_id": "b", "class_name": "Y"}, {"resource_id": "c", "class_name": "Z"}]
    assert player._similarity(a, b) == 1 / 3


def test_similarity_both_empty():
    player = DemonstrationPlayer(FakeDevice())
    assert player._similarity([], []) == 1.0


# ── Replay ─────────────────────────────────────────────────────────────────────


def _macro(*steps):
    return {"steps": list(steps)}


def test_replay_happy_path():
    device = FakeDevice()
    player = DemonstrationPlayer(device, state_similarity_threshold=0.0)
    player.credentials = FakeCredentials({"pw": "hunter2"})
    macro = _macro(
        {"action_type": "tap", "pre_state": [], "params": {"x": 10, "y": 20}},
        {"action_type": "text", "pre_state": [], "params": {"content": "cats"}},
        {"action_type": "type_secret", "pre_state": [], "params": {"secret_id": "pw"}},
    )

    result = asyncio.run(player.replay(macro, on_drift="stop"))
    assert result["completed"] is True
    assert result["steps_executed"] == 3
    assert result["steps_total"] == 3
    assert result["failures"] == []
    assert ("tap", 10, 20) in device.calls
    assert ("text", "cats") in device.calls
    assert ("text", "hunter2") in device.calls


def test_replay_unknown_action_type_goes_to_failures():
    device = FakeDevice()
    player = DemonstrationPlayer(device, state_similarity_threshold=0.0)
    macro = _macro(
        {"action_type": "tap", "pre_state": [], "params": {"x": 1, "y": 2}},
        {"action_type": "banana", "pre_state": [], "params": {}},
    )

    result = asyncio.run(player.replay(macro, on_drift="stop"))
    assert result["completed"] is True
    assert result["steps_executed"] == 1
    assert result["failures"] == [{"step": 1, "reason": "unknown action_type: banana"}]


def test_replay_missing_credential_goes_to_failures():
    device = FakeDevice()
    player = DemonstrationPlayer(device, state_similarity_threshold=0.0)
    player.credentials = None
    macro = _macro({"action_type": "type_secret", "pre_state": [], "params": {"secret_id": "pw"}})

    result = asyncio.run(player.replay(macro))
    assert result["completed"] is True
    assert result["steps_executed"] == 0
    assert result["failures"] == [
        {"step": 0, "reason": "credential unavailable", "secret_id": "pw"}
    ]


def test_replay_drift_stop_stops_and_runs_nothing():
    device = FakeDevice()
    player = DemonstrationPlayer(device, state_similarity_threshold=0.7)
    macro = _macro(
        {"action_type": "tap", "pre_state": PRE_STATE, "params": {"x": 1, "y": 2}},
    )

    async def fake_capture():
        return [{"resource_id": "com.x:id/zzz", "class_name": "android.widget.TextView"}]

    player._capture_state = fake_capture
    result = asyncio.run(player.replay(macro, on_drift="stop"))
    assert result["completed"] is False
    assert result["stopped_at_step"] == 0
    assert result["reason"] == "state drift"
    assert result["similarity"] == 0.0
    assert result["steps_executed"] == 0
    assert result["steps_total"] == 1
    assert device.calls == []


def test_replay_drift_skip_records_failure_and_continues():
    device = FakeDevice()
    player = DemonstrationPlayer(device, state_similarity_threshold=0.7)
    macro = _macro(
        {"action_type": "tap", "pre_state": PRE_STATE, "params": {"x": 1, "y": 2}},
        {"action_type": "tap", "pre_state": PRE_STATE, "params": {"x": 3, "y": 4}},
    )

    live_states = [
        [{"resource_id": "com.x:id/zzz", "class_name": "android.widget.TextView"}],
        PRE_STATE,
    ]

    async def fake_capture():
        return live_states.pop(0)

    player._capture_state = fake_capture
    result = asyncio.run(player.replay(macro, on_drift="skip"))
    assert result["completed"] is True
    assert result["steps_executed"] == 1
    assert result["steps_total"] == 2
    assert result["failures"] == [{"step": 0, "reason": "state drift", "similarity": 0.0}]
    assert device.calls == [("tap", 3, 4)]
