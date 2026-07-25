"""Web layer — FastAPI wrapper exposing the resume pipeline over HTTP + SSE.

Pure/data modules (config, schemas, job, events) carry no threading or HTTP
concerns; runner/job_manager/sse own concurrency; routers/app own the surface.
"""
