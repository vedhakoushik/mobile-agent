"""Manages multiple simultaneously-connected Android devices — replaces the old
single-global-device pattern (one DeviceController on app.state)."""

import asyncio
import logging
from typing import Optional

import adbutils

from .controller import DeviceController

logger = logging.getLogger(__name__)


class DeviceRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, DeviceController] = {}
        self._busy: dict[str, bool] = {}

    async def discover_and_connect(self) -> list[str]:
        connected: list[str] = []
        try:
            client = adbutils.AdbClient()
            adb_devices = await asyncio.to_thread(client.device_list)
        except Exception as e:
            logger.warning(f"ADB discovery failed: {e}")
            return connected

        for d in adb_devices:
            serial = d.serial
            ctrl = DeviceController(serial=serial)
            try:
                await asyncio.to_thread(ctrl.connect)
            except Exception as e:
                logger.warning(f"Failed to connect to device {serial}: {e}")
                continue
            self._devices[serial] = ctrl
            self._busy[serial] = False
            connected.append(serial)

        return connected

    def list_status(self) -> list[dict]:
        return [
            {"serial": s, "resolution": ctrl.resolution, "busy": self._busy.get(s, False)}
            for s, ctrl in self._devices.items()
        ]

    def get(self, serial: str) -> Optional[DeviceController]:
        return self._devices.get(serial)

    def acquire(self, serial: Optional[str] = None) -> Optional[tuple[str, DeviceController]]:
        if serial is not None:
            if serial in self._devices and not self._busy.get(serial, False):
                self._busy[serial] = True
                return serial, self._devices[serial]
            return None

        for s, ctrl in self._devices.items():
            if not self._busy.get(s, False):
                self._busy[s] = True
                return s, ctrl
        return None

    def release(self, serial: str) -> None:
        self._busy[serial] = False
