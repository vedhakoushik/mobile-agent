import asyncio

from fastapi import APIRouter

from ..schemas import KBListResponse, KBDocOut, KBDeleteResponse
from ...knowledge_base.store import KnowledgeBase

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


# ChromaDB's client is synchronous, so every call here goes through
# asyncio.to_thread. Called directly, they block the whole event loop —
# which on this server means stalling every in-flight agent run and the
# WebSocket feed, not just the request being served. The hot agent path
# (store.upsert / store.retrieve_context) already does this internally;
# these router-side reads were the ones still blocking.


async def _load_kb(app_name: str) -> KnowledgeBase:
    # Constructing a KnowledgeBase opens a PersistentClient (disk I/O), so
    # that gets offloaded too.
    return await asyncio.to_thread(KnowledgeBase, app_name)


@router.get("/{app_name}", response_model=KBListResponse)
async def get_kb(app_name: str):
    kb = await _load_kb(app_name)
    docs = await asyncio.to_thread(kb.get_all)
    return KBListResponse(
        app_name=app_name,
        count=len(docs),
        docs=[KBDocOut(**d.__dict__) for d in docs],
    )


@router.delete("/{app_name}", response_model=KBDeleteResponse)
async def clear_kb(app_name: str):
    kb = await _load_kb(app_name)
    deleted = await asyncio.to_thread(kb.clear)
    return KBDeleteResponse(deleted=deleted)


@router.get("/{app_name}/search", response_model=KBListResponse)
async def search_kb(app_name: str, q: str = ""):
    kb = await _load_kb(app_name)
    all_docs = await asyncio.to_thread(kb.get_all)
    if not q:
        docs = all_docs
    else:
        # Substring match over documentation/element_sig. ChromaDB's `where`
        # filter can't express this, so it stays a client-side scan; fine at
        # per-app KB sizes, revisit if a single app's KB grows large.
        needle = q.lower()
        docs = [
            d for d in all_docs
            if needle in d.documentation.lower() or needle in d.element_sig.lower()
        ]
    return KBListResponse(
        app_name=app_name,
        count=len(docs),
        docs=[KBDocOut(**d.__dict__) for d in docs],
    )
