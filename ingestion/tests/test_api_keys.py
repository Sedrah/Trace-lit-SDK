from __future__ import annotations

from pipeline.api_keys import ApiKeyResolver


def test_resolve_known_key() -> None:
    r = ApiKeyResolver({"sk-abc": "org-acme"})
    assert r.resolve("sk-abc") == "org-acme"


def test_resolve_unknown_key_returns_none() -> None:
    r = ApiKeyResolver({"sk-abc": "org-acme"})
    assert r.resolve("sk-unknown") is None


def test_resolve_empty_key_returns_default() -> None:
    r = ApiKeyResolver({"": "default"})
    assert r.resolve("") == "default"


def test_from_json_valid() -> None:
    r = ApiKeyResolver.from_json('{"sk-key1": "org-one", "sk-key2": "org-two"}')
    assert r.resolve("sk-key1") == "org-one"
    assert r.resolve("sk-key2") == "org-two"
    assert r.resolve("") == "default"  # empty key always maps to default


def test_from_json_empty_string() -> None:
    r = ApiKeyResolver.from_json("")
    assert r.resolve("") == "default"


def test_from_json_invalid_json_falls_back_to_default_only() -> None:
    r = ApiKeyResolver.from_json("{bad json")
    assert r.resolve("") == "default"
    assert r.resolve("sk-anything") is None


def test_add_runtime() -> None:
    r = ApiKeyResolver({})
    r.add("sk-new", "org-new")
    assert r.resolve("sk-new") == "org-new"


def test_len() -> None:
    r = ApiKeyResolver({"a": "1", "b": "2"})
    assert len(r) == 2
