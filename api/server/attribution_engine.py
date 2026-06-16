"""
Pluggable attribution engine loader.

Defaults to the rule-based v1 engine (attribution.py) — fully air-gapped,
ships in this public repo, free tier. If the optional `trace_lit_enterprise`
package is installed (paid, private repo), its LLM-assisted v2 engine
(local Ollama) is used instead. The public repo never contains v2 source
or license-check logic — it only contains this import seam.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .attribution import attribute_failures as _attribute_failures_v1

logger = logging.getLogger("trace_lit.api")

AttributionEngine = Callable[[list[dict[str, Any]]], dict[str, Any]]


def _load_engine() -> AttributionEngine:
    try:
        from trace_lit_enterprise.attribution_v2 import attribute_failures_v2
    except ImportError:
        return _attribute_failures_v1

    logger.info("AMO attribution: enterprise v2 engine loaded (LLM-assisted)")
    return attribute_failures_v2


_engine: AttributionEngine = _load_engine()


def attribute_failures(spans: list[dict[str, Any]]) -> dict[str, Any]:
    return _engine(spans)
