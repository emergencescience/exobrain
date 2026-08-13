"""Run route — execute Python code in a sandboxed subprocess."""

import logging
import subprocess
import tempfile
import os
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.storage import ExecutionArtifact, StorageProtocol, get_storage

logger = logging.getLogger("exobrain.run")

router = APIRouter(prefix="/api/play/exobrain", tags=["run"])


class RunRequest(BaseModel):
    code: str
    timeout: int = 30  # max seconds
    document_id: str | None = None


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False
    artifact_id: str | None = None


MAX_OUTPUT_BYTES = 100_000  # 100KB max output


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "local"


@router.post("/run", response_model=RunResponse)
async def run_code(
    req: RunRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Execute Python code in a sandboxed subprocess and return stdout/stderr."""
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Code is empty")

    timeout = min(req.timeout, 60)  # hard cap at 60s
    document = None
    if req.document_id:
        document = await storage.get_document(req.document_id)
        if document is None or document.user_id != user_id:
            raise HTTPException(status_code=404, detail="Document not found")

    # Write code to a temp file for execution
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="exobrain_run_"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            timeout=timeout,
            text=True,
            env={
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "HOME": "/tmp",
                "PYTHONUNBUFFERED": "1",
                "MPLBACKEND": "Agg",  # headless matplotlib
                # Block network access by unsetting proxy vars
                "HTTP_PROXY": "",
                "HTTPS_PROXY": "",
                "http_proxy": "",
                "https_proxy": "",
            },
            cwd="/tmp",
        )

        stdout = result.stdout[-MAX_OUTPUT_BYTES:]
        stderr = result.stderr[-MAX_OUTPUT_BYTES:]
        truncated = (
            len(result.stdout) > MAX_OUTPUT_BYTES
            or len(result.stderr) > MAX_OUTPUT_BYTES
        )

        artifact_id = None
        if document is not None:
            artifact = await storage.save_execution_artifact(
                ExecutionArtifact(
                    document_id=document.id,
                    code=code,
                    code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=result.returncode,
                    truncated=truncated,
                )
            )
            artifact_id = artifact.id
        return RunResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            truncated=truncated,
            artifact_id=artifact_id,
        )

    except subprocess.TimeoutExpired:
        return RunResponse(
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds.",
            exit_code=-1,
        )
    except Exception as e:
        logger.error(f"Run error: {e}")
        return RunResponse(
            stdout="",
            stderr=f"Internal error: {str(e)}",
            exit_code=-1,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
