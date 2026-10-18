import time
import uuid
import json
import logging
from collections import deque

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

START_TIME = time.time()

# 1. Live Prometheus counter
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)

# 2. In-memory structured logs
LOG_LIMIT = 1000
logs = deque(maxlen=LOG_LIMIT)

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

# 3. Middleware runs for every request
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - started

    # Increment counter for every endpoint, including /metrics and /healthz
    http_requests_total.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code
    ).inc()

    log_entry = {
        "level": "info",
        "ts": time.time(),
        "path": request.url.path,
        "request_id": request_id,
        "method": request.method,
        "status": response.status_code,
        "duration_s": round(duration, 6)
    }

    logs.append(log_entry)
    logger.info(json.dumps(log_entry))

    response.headers["X-Request-ID"] = request_id
    return response


# 4. Work endpoint
@app.get("/work")
async def work(n: int = Query(default=1, ge=1)):
    # Simulate K units of work
    total = 0
    for i in range(n):
        total += i * i

    return {"email": "23f1001344@ds.study.iitm.ac.in", "done": n}


# 5. Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# 6. Health endpoint
@app.get("/healthz")
async def healthz():
    uptime = time.time() - START_TIME
    return {"status": "ok", "uptime_s": uptime}


# 7. Tail logs endpoint
@app.get("/logs/tail")
async def logs_tail(limit: int = Query(default=50, ge=1, le=LOG_LIMIT)):
    return list(logs)[-limit:]
