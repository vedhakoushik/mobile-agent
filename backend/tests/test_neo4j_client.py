from backend.graph.neo4j_client import NavigationGraph, screen_signature


def _element(rid="", cls="android.widget.Button"):
    return {"resource_id": rid, "class_name": cls}


def test_signature_is_order_independent():
    a = [
        _element("com.x:id/a", "android.widget.Button"),
        _element("com.x:id/b", "android.widget.TextView"),
    ]
    b = [
        _element("com.x:id/b", "android.widget.TextView"),
        _element("com.x:id/a", "android.widget.Button"),
    ]
    assert screen_signature(a) == screen_signature(b)


def test_signature_empty_list_does_not_raise():
    sig = screen_signature([])
    assert isinstance(sig, str)
    assert len(sig) == 16


def test_signature_different_element_sets_differ():
    a = [_element("com.x:id/a", "android.widget.Button")]
    b = [_element("com.x:id/b", "android.widget.Button")]
    c = [_element("com.x:id/a", "android.widget.TextView")]
    assert screen_signature(a) != screen_signature(b)
    assert screen_signature(a) != screen_signature(c)


def test_signature_falls_back_to_class_names_without_resource_id():
    elements = [_element("", "android.widget.Button"), _element("", "android.widget.TextView")]
    sig = screen_signature(elements)
    assert len(sig) == 16
    assert sig == screen_signature(list(reversed(elements)))
    assert sig != screen_signature([])


def test_signature_missing_resource_id_key_uses_class_name_fallback():
    no_rid = [{"class_name": "android.widget.Button"}]
    with_rid = [{"class_name": "android.widget.Button", "resource_id": "com.x:id/a"}]
    assert screen_signature(no_rid) != screen_signature(with_rid)


def _down_graph() -> NavigationGraph:
    return NavigationGraph(uri="bolt://localhost:1", user="test-user", password="test-pass")


def test_get_outgoing_transitions_fails_soft():
    graph = _down_graph()
    try:
        assert graph.get_outgoing_transitions("youtube", "sig-1") == []
    finally:
        graph.close()


def test_record_transition_fails_soft():
    graph = _down_graph()
    try:
        assert graph.record_transition("youtube", "sig-1", "elem", "text", "sig-2") is None
    finally:
        graph.close()


def test_find_path_fails_soft():
    graph = _down_graph()
    try:
        assert graph.find_path("youtube", "sig-1", "sig-2") is None
    finally:
        graph.close()


def test_close_fails_soft_even_after_failed_calls():
    graph = _down_graph()
    graph.get_outgoing_transitions("youtube", "sig-1")
    graph.record_transition("youtube", "sig-1", "elem", "text", "sig-2")
    graph.find_path("youtube", "sig-1", "sig-2")
    assert graph.close() is None
