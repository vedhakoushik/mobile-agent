from ..device.controller import DeviceController, KEYCODE_BACK
from ..perception.grid import overlay_grid
from ..llm import call_vision_llm
from ..llm.prompts import build_grid_prompt


async def execute_action(device: DeviceController, action: dict, elements: list[dict]) -> None:
    """
    Execute the LLM-decided action on the Android device.
    action: parsed action dict with keys: action, element_id, text_input, direction, grid_cell
    """
    action_type = action.get("action", "").lower()
    elem_id = action.get("element_id")
    text_input = action.get("text_input")
    direction = action.get("direction", "up")
    grid_cell = action.get("grid_cell")

    if action_type == "tap" and elem_id is not None:
        elem = _find_element(elements, elem_id)
        if elem:
            cx, cy = _center(elem)
            await device.tap(cx, cy)

    elif action_type == "text" and text_input:
        # tap the focused element first if specified
        if elem_id is not None:
            elem = _find_element(elements, elem_id)
            if elem:
                cx, cy = _center(elem)
                await device.tap(cx, cy)
        await device.text(text_input)

    elif action_type == "swipe":
        from_x = from_y = None
        if elem_id is not None:
            elem = _find_element(elements, elem_id)
            if elem:
                from_x, from_y = _center(elem)
        await device.swipe(direction or "up", from_x=from_x, from_y=from_y)

    elif action_type == "long_press" and elem_id is not None:
        elem = _find_element(elements, elem_id)
        if elem:
            cx, cy = _center(elem)
            await device.long_press(cx, cy)

    elif action_type == "back":
        await device.key_event(KEYCODE_BACK)

    elif action_type == "grid":
        # grid mode: take raw screenshot, overlay grid, ask LLM which cell, tap center
        raw = await device.screenshot()
        grid_b64, coords = overlay_grid(raw)
        thought = action.get("thought", "")
        prompt = build_grid_prompt(thought)
        # use the same provider that called us — caller passes provider via closure
        # grid_cell may already be set if LLM returned it; otherwise ask again
        if not grid_cell:
            grid_resp = await call_vision_llm(
                action.get("_provider", "gemini"), grid_b64, prompt
            )
            grid_cell = grid_resp.get("grid_cell", "E5")

        coord = coords.get(grid_cell.upper())
        if coord:
            await device.tap(coord[0], coord[1])


def _find_element(elements: list[dict], elem_id: int) -> dict | None:
    for e in elements:
        if e["id"] == elem_id:
            return e
    return None


def _center(elem: dict) -> tuple[int, int]:
    b = elem["bounds"]
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
