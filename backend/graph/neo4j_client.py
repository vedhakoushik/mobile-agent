import hashlib
import logging
import os
from typing import Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


def screen_signature(elements: list[dict]) -> str:
    """Derive a stable fingerprint for a screen from its interactive elements.

    Uses (resource_id, class_name) pairs for elements that have a resource_id
    (sorted for stability). Falls back to sorted class_names if no element has
    a resource_id, so we still get some signature rather than a constant one.
    """
    with_rid = sorted(
        (e.get("resource_id", ""), e.get("class_name", ""))
        for e in elements
        if e.get("resource_id")
    )
    if with_rid:
        raw = "|".join(f"{rid}::{cls}" for rid, cls in with_rid)
    else:
        raw = "|".join(sorted(e.get("class_name", "") for e in elements))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class NavigationGraph:
    """Thin wrapper around a Neo4j driver for recording/querying screen-to-screen
    navigation discovered during Explore mode. Must never raise or block Explore —
    every public method catches its own exceptions and logs a warning instead.
    """

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = user or os.environ.get("NEO4J_USER", "neo4j")
        password = password or os.environ.get("NEO4J_PASSWORD", "learnGraph123")
        # NOTE: do NOT call verify_connectivity() here -- construction must never
        # block or raise even if Neo4j is down. Connectivity is only checked
        # lazily on first real use (inside record_transition/find_path).
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def record_transition(self, app_name: str, from_screen_sig: str, element_sig: str, element_text: str, to_screen_sig: str) -> None:
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (a:Screen {app_name: $app_name, sig: $from_sig})
                    MERGE (b:Screen {app_name: $app_name, sig: $to_sig})
                    MERGE (a)-[r:LEADS_TO {element_sig: $element_sig, element_text: $element_text}]->(b)
                    """,
                    app_name=app_name,
                    from_sig=from_screen_sig,
                    to_sig=to_screen_sig,
                    element_sig=element_sig,
                    element_text=element_text,
                )
        except Exception as e:
            logger.warning("NavigationGraph.record_transition failed: %s", e)

    def find_path(self, app_name: str, from_screen_sig: str, to_screen_sig: str, max_hops: int = 6) -> Optional[list[dict]]:
        try:
            with self._driver.session() as session:
                result = session.run(
                    f"""
                    MATCH p = shortestPath(
                        (a:Screen {{app_name: $app_name, sig: $from_sig}})-[:LEADS_TO*..{int(max_hops)}]->(b:Screen {{app_name: $app_name, sig: $to_sig}})
                    )
                    RETURN relationships(p) AS rels
                    """,
                    app_name=app_name,
                    from_sig=from_screen_sig,
                    to_sig=to_screen_sig,
                )
                record = result.single()
                if record is None:
                    return None
                rels = record["rels"]
                return [
                    {"element_sig": rel.get("element_sig"), "element_text": rel.get("element_text")}
                    for rel in rels
                ]
        except Exception as e:
            logger.warning("NavigationGraph.find_path failed: %s", e)
            return None

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception as e:
            logger.warning("NavigationGraph.close failed: %s", e)
