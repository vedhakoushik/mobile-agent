from fastapi import APIRouter

from ..schemas import KBListResponse, KBDocOut, KBDeleteResponse
from ...knowledge_base.store import KnowledgeBase

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


@router.get("/{app_name}", response_model=KBListResponse)
async def get_kb(app_name: str):
    kb = KnowledgeBase(app_name=app_name)
    docs = kb.get_all()
    return KBListResponse(
        app_name=app_name,
        count=len(docs),
        docs=[KBDocOut(**d.__dict__) for d in docs],
    )


@router.delete("/{app_name}", response_model=KBDeleteResponse)
async def clear_kb(app_name: str):
    kb = KnowledgeBase(app_name=app_name)
    deleted = kb.clear()
    return KBDeleteResponse(deleted=deleted)


@router.get("/{app_name}/search", response_model=KBListResponse)
async def search_kb(app_name: str, q: str = ""):
    kb = KnowledgeBase(app_name=app_name)
    if not q:
        docs = kb.get_all()
    else:
        # simple search: filter docs where q appears in documentation
        all_docs = kb.get_all()
        docs = [d for d in all_docs if q.lower() in d.documentation.lower()
                or q.lower() in d.element_sig.lower()]
    return KBListResponse(
        app_name=app_name,
        count=len(docs),
        docs=[KBDocOut(**d.__dict__) for d in docs],
    )
