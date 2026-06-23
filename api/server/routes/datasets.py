"""
Dataset builder endpoints.

GET    /datasets                           — list datasets for org
POST   /datasets                           — create dataset
DELETE /datasets/{dataset_id}             — delete dataset
GET    /datasets/{dataset_id}/items       — list items + dataset info
POST   /datasets/{dataset_id}/items       — add span to dataset
DELETE /datasets/{dataset_id}/items/{id}  — remove item
GET    /datasets/{dataset_id}/export      — download as JSONL
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import require_org
from ..db import timescale as ts
from ..models import (
    DatasetCreate,
    DatasetItemCreate,
    DatasetItemListResponse,
    DatasetItemResponse,
    DatasetListResponse,
    DatasetResponse,
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    request: Request,
    org_id: str = Depends(require_org),
) -> DatasetListResponse:
    rows = await ts.list_datasets(request, org_id)
    return DatasetListResponse(items=[DatasetResponse(**r) for r in rows])


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    body: DatasetCreate,
    request: Request,
    org_id: str = Depends(require_org),
) -> DatasetResponse:
    try:
        row = await ts.create_dataset(request, org_id, body.name, body.description)
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A dataset with that name already exists.")
        raise
    return DatasetResponse(**row)


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> None:
    deleted = await ts.delete_dataset(request, org_id, dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found.")


@router.get("/{dataset_id}/items", response_model=DatasetItemListResponse)
async def list_dataset_items(
    dataset_id: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> DatasetItemListResponse:
    dataset = await ts.get_dataset(request, org_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    items = await ts.list_dataset_items(request, org_id, dataset_id)
    return DatasetItemListResponse(
        dataset=DatasetResponse(**dataset),
        items=[DatasetItemResponse(**i) for i in items],
    )


@router.post("/{dataset_id}/items", response_model=DatasetItemResponse, status_code=201)
async def add_dataset_item(
    dataset_id: str,
    body: DatasetItemCreate,
    request: Request,
    org_id: str = Depends(require_org),
) -> DatasetItemResponse:
    dataset = await ts.get_dataset(request, org_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if body.label not in ("good", "bad", "neutral"):
        raise HTTPException(status_code=422, detail="label must be 'good', 'bad', or 'neutral'.")
    row = await ts.add_dataset_item(request, org_id, dataset_id, body.model_dump())
    return DatasetItemResponse(**row)


@router.delete("/{dataset_id}/items/{item_id}", status_code=204)
async def delete_dataset_item(
    dataset_id: str,
    item_id: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> None:
    deleted = await ts.delete_dataset_item(request, org_id, dataset_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found.")


@router.get("/{dataset_id}/export")
async def export_dataset(
    dataset_id: str,
    request: Request,
    org_id: str = Depends(require_org),
) -> Response:
    dataset = await ts.get_dataset(request, org_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    items = await ts.list_dataset_items(request, org_id, dataset_id)

    lines = []
    for item in items:
        lines.append(json.dumps({
            "id": str(item["id"]),
            "dataset": dataset["name"],
            "label": item["label"],
            "notes": item["notes"],
            "trace_id": item["trace_id"],
            "span_id": item["span_id"],
            "agent_name": item["agent_name"],
            "action": item["action"],
            "model": item["model"],
            "input": item["input_text"],
            "output": item["output_text"],
            "created_at": item["created_at"].isoformat() if item["created_at"] else None,
        }))

    filename = f"{dataset['name'].replace(' ', '_')}.jsonl"
    return Response(
        content="\n".join(lines),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
