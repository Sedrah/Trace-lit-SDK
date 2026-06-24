"""
Eval quality gate endpoints.

POST /datasets/{dataset_id}/eval          — run eval, returns result immediately
GET  /datasets/{dataset_id}/eval/runs     — list past runs for a dataset
"""

from __future__ import annotations

import sys
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import require_org
from ..db import clickhouse as ch
from ..db import timescale as ts
from ..models import EvalRunListResponse, EvalRunRequest, EvalRunResponse

router = APIRouter(tags=["Evals"])


@router.post("/datasets/{dataset_id}/eval", response_model=EvalRunResponse, status_code=201)
async def run_eval(
    dataset_id: str,
    body: EvalRunRequest,
    request: Request,
    org_id: str = Depends(require_org),
) -> EvalRunResponse:
    # Verify dataset exists and belongs to org
    dataset = await ts.get_dataset(request, org_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    if not 0.0 < body.threshold <= 1.0:
        raise HTTPException(status_code=422, detail="threshold must be between 0.0 and 1.0.")

    # Resolve baseline spans
    if body.baseline_version is not None:
        # Use spans from an explicit previous prompt version
        baseline_spans = await ch.get_spans_for_prompt_version(
            request, org_id, body.prompt_name, body.baseline_version
        )
    else:
        # Use dataset "good" items — look up their span_ids in ClickHouse
        items = await ts.list_dataset_items(request, org_id, dataset_id)
        good_span_ids = [i["span_id"] for i in items if i["label"] == "good"]
        baseline_spans = await ch.get_spans_by_ids(request, org_id, good_span_ids)

    # Fetch new version spans
    new_spans = await ch.get_spans_for_prompt_version(
        request, org_id, body.prompt_name, body.prompt_version
    )

    # Run the eval engine (add eval/ to path so it's importable from API)
    _ensure_eval_on_path()
    from eval.engine import run_eval as _run_eval  # type: ignore[import]

    result = _run_eval(
        baseline_spans=baseline_spans,
        new_spans=new_spans,
        threshold=body.threshold,
    )

    # Persist
    row = await ts.create_eval_run(request, org_id, {
        "dataset_id": dataset_id,
        "prompt_name": body.prompt_name,
        "prompt_version": body.prompt_version,
        "baseline_version": body.baseline_version,
        "status": "passed" if result.passed else "failed",
        "score": result.score,
        "threshold": result.threshold,
        "new_spans": result.new_spans,
        "baseline_spans": result.baseline_spans,
        "message": result.message,
        "detail": result.detail,
    })

    return EvalRunResponse(**row)


@router.get("/datasets/{dataset_id}/eval/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    dataset_id: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> EvalRunListResponse:
    dataset = await ts.get_dataset(request, org_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    rows = await ts.list_eval_runs(request, org_id, dataset_id)
    return EvalRunListResponse(items=[EvalRunResponse(**r) for r in rows])


def _ensure_eval_on_path() -> None:
    """Add the directory containing eval/ to sys.path.

    In Docker: eval/ is at /app/eval/ — two levels up from routes/ gives /app/.
    Locally:   eval/ is at AMO/eval/  — three levels up from routes/ gives AMO/.
    We probe both and add the first one that actually contains eval/engine/.
    """
    routes_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(routes_dir, "..", "..")),    # Docker: /app
        os.path.abspath(os.path.join(routes_dir, "..", "..", "..")),  # local: AMO/
    ]
    for path in candidates:
        if os.path.isdir(os.path.join(path, "eval", "engine")):
            if path not in sys.path:
                sys.path.insert(0, path)
            return
