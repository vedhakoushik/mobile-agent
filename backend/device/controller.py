import asyncio
import os
import re
from typing import Optional

import adbutils


KEYCODE_BACK  = 4
KEYCODE_HOME  = 3
KEYCODE_ENTER = 66
KEYCODE_DEL   = 67


class ADBError(Exception):
    pass


class DeviceController:
    def __init__(self, serial: Optional[str] = None):
        self._serial = serial or os.getenv("ANDROID_SERIAL")
        self._client = adbutils.AdbClient(host="127.0.0.1", port=5037)
        self._device = None
        self._width = 1080
        self._height = 1920

    def connect(self) -> None:
        try:
            if self._serial:
                self._device = self._client.device(serial=self._serial)
            else:
                devices = self._client.device_list()
                if not devices:
                    raise ADBError("No Android devices found. Start an emulator or connect a device.")
                self._device = devices[0]
                self._serial = self._device.serial
            self._width, self._height = self._get_resolution()
        except Exception as e:
            raise ADBError(f"ADB connection failed: {e}") from e

    def is_connected(self) -> bool:
        try:
            if self._device is None:
                return False
            state = self._device.get_state()
            return state == "device"
        except Exception:
            return False

    def _get_resolution(self) -> tuple[int, int]:
        try:
            output = self._device.shell("wm size")
            match = re.search(r"(\d+)x(\d+)", output)
            if match:
                return int(match.group(1)), int(match.group(2))
        except Exception:
            pass
        return 1080, 1920

    @property
    def serial(self) -> Optional[str]:
        return self._serial

    @property
    def resolution(self) -> tuple[int, int]:
        return self._width, self._height

    async def screenshot(self) -> bytes:
        return await asyncio.to_thread(
            self._device.shell, "screencap -p", encoding=None
        )

    async def pull_xml(self) -> str:
        raw = await asyncio.to_thread(
            self._device.shell, "uiautomator dump /dev/fd/1"
        )
        # strip trailing status message from uiautomator
        if "UI hierchary" in raw:
            raw = raw[:raw.rfind("UI hierchary")]
        return raw.strip()

    async def tap(self, x: int, y: int) -> None:
        await asyncio.to_thread(self._device.shell, f"input tap {x} {y}")
        await asyncio.sleep(0.8)

    async def text(self, content: str) -> None:
        escaped = (
            content
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(" ", "%s")
            .replace("&", "\\&")
            .replace("|", "\\|")
            .replace(";", "\\;")
            .replace("\"", "\\\"")
        )
        await asyncio.to_thread(self._device.shell, f"input text '{escaped}'")
        await asyncio.sleep(0.3)

    async def swipe(self, direction: str, from_x: Optional[int] = None, from_y: Optional[int] = None) -> None:
        deltas = {
            "up":    (0, -500),
            "down":  (0,  500),
            "left":  (-400, 0),
            "right": ( 400, 0),
        }
        dx, dy = deltas.get(direction, (0, 0))
        x1 = from_x if from_x is not None else self._width // 2
        y1 = from_y if from_y is not None else self._height // 2
        x2 = max(0, min(x1 + dx, self._width))
        y2 = max(0, min(y1 + dy, self._height))
        await asyncio.to_thread(
            self._device.shell, f"input swipe {x1} {y1} {x2} {y2} 300"
        )
        await asyncio.sleep(0.4)

    async def long_press(self, x: int, y: int) -> None:
        await asyncio.to_thread(
            self._device.shell, f"input swipe {x} {y} {x} {y} 1000"
        )
        await asyncio.sleep(1.2)

    async def key_event(self, code: int) -> None:
        await asyncio.to_thread(self._device.shell, f"input keyevent {code}")
        await asyncio.sleep(0.3)

    async def wait_idle(self) -> None:
        await asyncio.to_thread(self._device.shell, "uiautomator dump /dev/null")

    async def launch_app(self, package: str) -> None:
        await asyncio.to_thread(
            self._device.shell,
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )
        await asyncio.sleep(2.0)
