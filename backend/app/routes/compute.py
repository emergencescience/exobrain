"""Restricted scientific-computing API for Exobrain."""

from fastapi import APIRouter, HTTPException

from app.compute import ComputeRequest, ComputationPlan, execute_plan

router = APIRouter(prefix="/api", tags=["compute"])


@router.post("/compute")
async def compute(request: ComputeRequest):
    """Run one allowlisted computation operation.

    This endpoint accepts typed arguments only. It does not accept or execute
    arbitrary Python source.
    """

    try:
        plan = ComputationPlan(
            intent=request.intent,
            arguments=request.arguments,
            locale=request.locale,
        )
        artifact = execute_plan(plan)
        if artifact is None:
            raise HTTPException(status_code=400, detail="A computation intent is required")
        return {"artifact": artifact.model_dump()}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
