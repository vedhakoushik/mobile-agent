from .device import router as device_router
from .agent import router as agent_router
from .kb import router as kb_router
from .demonstrations import router as demonstrations_router

__all__ = ["device_router", "agent_router", "kb_router", "demonstrations_router"]
