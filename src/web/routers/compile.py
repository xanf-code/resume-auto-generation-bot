"""Compile router — POST /compile for raw tectonic compile.

Uses a small dedicated ThreadPoolExecutor so editor compile requests never
starve real pipeline jobs running in the main executor.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.compiler.tectonic import compile_tex
from src.web.schemas import CompileErrorResponse, CompileRequest

router = APIRouter(prefix="/compile", tags=["compile"])

# Dedicated pool — small so compile never starves the main pipeline executor.
_compile_pool = ThreadPoolExecutor(max_workers=2)


@router.post("")
async def compile_resume(req: CompileRequest) -> FileResponse:
    """Compile LaTeX source via tectonic and return the PDF.

    On success: 200 application/pdf.
    On failure: 422 with CompileErrorResponse detail.
    """
    workdir = tempfile.mkdtemp(prefix="resumebot_compile_")
    loop = asyncio.get_event_loop()

    try:
        ok, pdf_path, errors = await loop.run_in_executor(
            _compile_pool,
            lambda: compile_tex(
                tex_source=req.resume_tex,
                workdir=workdir,
            ),
        )
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail=CompileErrorResponse(ok=False, errors=[str(exc)]).model_dump(),
        ) from exc

    if ok and pdf_path:
        # FileResponse streams the file; workdir will persist until GC.
        # For a production service you'd register a background cleanup task.
        return FileResponse(pdf_path, media_type="application/pdf")

    # Compile failed — clean up and return structured error.
    shutil.rmtree(workdir, ignore_errors=True)
    raise HTTPException(
        status_code=422,
        detail=CompileErrorResponse(ok=False, errors=errors).model_dump(),
    )
