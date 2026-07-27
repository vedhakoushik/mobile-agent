import asyncio
import json
from typing import Optional

from ..device.controller import DeviceController
from ..perception.xml_parser import parse_interactive_elements
from ..security.credentials import CredentialManager, CredentialNotFoundError


class DemonstrationPlayer:
    def __init__(
        self,
        device: DeviceController,
        credentials: Optional[CredentialManager] = None,
        state_similarity_threshold: float = 0.7,
    ):
        self.device = device
        self.credentials = credentials
        self.state_similarity_threshold = state_similarity_threshold

    def load(self, path: str) -> dict:
        with open(path) as f:
            data = json.load(f)
        if data.get("schema_version") != 1:
            raise ValueError(
                f"Unsupported demonstration schema_version: {data.get('schema_version')!r}, expected 1"
            )
        return data

    async def _capture_state(self) -> list[dict]:
        xml = await self.device.pull_xml()
        elements = parse_interactive_elements(xml)
        return [
            {"resource_id": e.resource_id, "class_name": e.class_name}
            for e in elements
        ]

    def _similarity(self, recorded: list[dict], live: list[dict]) -> float:
        recorded_set = {(d["resource_id"], d["class_name"]) for d in recorded}
        live_set = {(d["resource_id"], d["class_name"]) for d in live}
        if not recorded_set and not live_set:
            return 1.0
        intersection = recorded_set & live_set
        union = recorded_set | live_set
        return len(intersection) / len(union)

    async def replay(self, macro_data: dict, on_drift: str = "stop") -> dict:
        steps = macro_data.get("steps", [])
        failures = []
        steps_executed = 0

        for i, step in enumerate(steps):
            live_state = await self._capture_state()
            similarity = self._similarity(step["pre_state"], live_state)

            if similarity < self.state_similarity_threshold:
                if on_drift == "stop":
                    return {
                        "completed": False,
                        "stopped_at_step": i,
                        "reason": "state drift",
                        "similarity": similarity,
                        "steps_executed": steps_executed,
                        "steps_total": len(steps),
                        "failures": failures,
                    }
                elif on_drift == "skip":
                    failures.append({"step": i, "reason": "state drift", "similarity": similarity})
                    continue

            params = step.get("params", {})
            action_type = step["action_type"]

            try:
                if action_type == "tap":
                    await self.device.tap(params["x"], params["y"])
                elif action_type == "text":
                    await self.device.text(params["content"])
                elif action_type == "swipe":
                    await self.device.swipe(
                        params.get("direction", "up"),
                        from_x=params.get("from_x"),
                        from_y=params.get("from_y"),
                    )
                elif action_type == "long_press":
                    await self.device.long_press(params["x"], params["y"])
                elif action_type == "key_event":
                    await self.device.key_event(params["code"])
                elif action_type == "wait":
                    await asyncio.sleep(params.get("duration", 1))
                elif action_type == "type_secret":
                    secret_id = params.get("secret_id")
                    if (
                        self.credentials is None
                        or secret_id is None
                        or not self.credentials.has(secret_id)
                    ):
                        failures.append({
                            "step": i,
                            "reason": "credential unavailable",
                            "secret_id": secret_id,
                        })
                        continue
                    try:
                        secret_value = self.credentials.resolve(secret_id)
                        await self.device.text(secret_value)
                    except CredentialNotFoundError:
                        failures.append({
                            "step": i,
                            "reason": "credential unavailable",
                            "secret_id": secret_id,
                        })
                        continue
                else:
                    failures.append({"step": i, "reason": f"unknown action_type: {action_type}"})
                    continue
            except Exception as e:
                failures.append({"step": i, "reason": str(e)})
                continue

            steps_executed += 1
            await asyncio.sleep(0.5)

        return {
            "completed": True,
            "steps_executed": steps_executed,
            "steps_total": len(steps),
            "failures": failures,
        }
