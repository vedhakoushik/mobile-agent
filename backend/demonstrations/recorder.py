import json
import os

from ..device.controller import DeviceController
from ..perception.xml_parser import parse_interactive_elements


class DemonstrationRecorder:
    def __init__(self, device: DeviceController, app_name: str, task_description: str):
        self.device = device
        self.app_name = app_name
        self.task_description = task_description
        self.steps: list[dict] = []

    async def capture_step(self, action_type: str, **kwargs) -> None:
        xml = await self.device.pull_xml()
        elements = parse_interactive_elements(xml)
        pre_state = [
            {"resource_id": e.resource_id, "class_name": e.class_name}
            for e in elements
        ]

        description = kwargs.pop("description", "")

        self.steps.append({
            "action_type": action_type,
            "pre_state": pre_state,
            "params": kwargs,
            "description": description,
        })

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "app_name": self.app_name,
            "task_description": self.task_description,
            "schema_version": 1,
            "steps": self.steps,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
