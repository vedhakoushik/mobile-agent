from backend.device.app_registry import resolve_package


def test_resolves_known_apps():
    assert resolve_package("youtube") == "com.google.android.youtube"
    assert resolve_package("gmail") == "com.google.android.gm"


def test_resolution_is_case_and_whitespace_insensitive():
    assert resolve_package("  YouTube  ") == "com.google.android.youtube"
    assert resolve_package("GMAIL") == "com.google.android.gm"


def test_unknown_app_returns_none():
    assert resolve_package("some_unheard_of_app") is None
