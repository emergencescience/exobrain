"""Run route — execute Python code in a sandboxed subprocess."""

import logging
import subprocess
import tempfile
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("exobrain.run")

router = APIRouter(prefix="/api/play/exobrain", tags=["run"])


class RunRequest(BaseModel):
    code: str
    timeout: int = 30  # max seconds


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False


MAX_OUTPUT_BYTES = 100_000  # 100KB max output


@router.post("/run", response_model=RunResponse)
async def run_code(req: RunRequest):
    """Execute Python code in a sandboxed subprocess and return stdout/stderr."""
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Code is empty")

    timeout = min(req.timeout, 60)  # hard cap at 60s

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

        return RunResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            truncated=truncated,
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
