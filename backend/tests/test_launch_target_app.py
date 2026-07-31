import asyncio

from backend.agent.loop import _launch_target_app
from backend.agent.state import AgentState, RunConfig


class _FakeDevice:
    def __init__(self, raise_on_launch=False):
        self.launched_packages = []
        self._raise = raise_on_launch

    async def launch_app(self, package):
        if self._raise:
            raise RuntimeError("adb shell failed")
        self.launched_packages.append(package)


def _state(app_name, device):
    config = RunConfig(app_name=app_name, task="do something", mode="deploy")
    return AgentState(session_id="sess-1", config=config, device=device)


def test_launches_resolved_package_for_known_app():
    device = _FakeDevice()
    state = _state("youtube", device)
    asyncio.run(_launch_target_app(state))
    assert device.launched_packages == ["com.google.android.youtube"]


def test_unknown_app_does_not_call_launch_app():
    device = _FakeDevice()
    state = _state("some_never_heard_of_app", device)
    asyncio.run(_launch_target_app(state))
    assert device.launched_packages == []


def test_launch_failure_does_not_raise():
    device = _FakeDevice(raise_on_launch=True)
    state = _state("gmail", device)
    # must not propagate — a launch failure should not crash the whole run
    asyncio.run(_launch_target_app(state))
