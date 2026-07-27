"""Wireless ADB helper functions for pairing and connecting.

adbutils has no native pairing support, so this module shells out to the
``adb`` CLI directly for pairing.  The resulting connection is picked up
normally by ``DeviceRegistry.discover_and_connect()`` via ``adb devices``,
which lists the ``ip:port`` as a serial once connected.
"""

import asyncio


async def pair_device(ip: str, port: int, code: str, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "pair", f"{ip}:{port}", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "adb executable not found on PATH"

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return False, "timed out"

    output = (stdout or b"").decode("utf-8", errors="replace") + (stderr or b"").decode("utf-8", errors="replace")
    if "successfully paired" in output.lower():
        return True, output
    return False, output


async def connect_device(ip: str, port: int, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "connect", f"{ip}:{port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "adb executable not found on PATH"

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return False, "timed out"

    output = (stdout or b"").decode("utf-8", errors="replace") + (stderr or b"").decode("utf-8", errors="replace")
    if "connected to" in output.lower():
        return True, output
    return False, output
