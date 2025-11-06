"""FastAPI application with metrics endpoint"""

import logging
import threading
import signal
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import StreamingResponse
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from .config import FASTAPI_PORT, MITMPROXY_PORT, LOG_LEVEL
from .database import (
    init_database,
    get_metrics,
    get_logs,
    get_log_by_id,
    delete_logs,
    iterate_logs,
    get_detailed_metrics,
    reset_metrics,
)
from .rules_manager import RulesManager
from .firewall_addon import FirewallAddon

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global variables for mitmproxy
mitmproxy_thread = None
mitmproxy_master = None
rules_manager = None

# App state
app_state: dict[str, Any] = {
    "start_time": datetime.now(),
    "observe_mode": False,
    "last_rules_reload_at": None,
}


def run_mitmproxy():
    """Run mitmproxy in a separate thread with its own event loop"""
    global mitmproxy_master, rules_manager

    try:
        if not rules_manager:
            logger.error("Rules manager not initialized, cannot start mitmproxy")
            return

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        opts = Options(listen_port=MITMPROXY_PORT)
        mitmproxy_master = DumpMaster(opts, loop=loop)

        # Add the firewall addon
        firewall_addon = FirewallAddon(
            rules_manager, get_observe_mode=lambda: app_state["observe_mode"]
        )
        mitmproxy_master.addons.add(firewall_addon)

        logger.info(f"Starting mitmproxy on port {MITMPROXY_PORT}")
        # Run the async run() method in the event loop
        loop.run_until_complete(mitmproxy_master.run())
    except Exception as e:
        # Use print to avoid logging issues when event loop isn't set up
        print(f"Error in mitmproxy: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global mitmproxy_thread, mitmproxy_master, rules_manager

    # Startup
    logger.info("Initializing firewall...")

    # Initialize database
    init_database()

    # Initialize rules manager
    rules_manager = RulesManager("rules.json")
    app_state["last_rules_reload_at"] = rules_manager.last_loaded_at

    # Start mitmproxy in background thread
    mitmproxy_thread = threading.Thread(target=run_mitmproxy, daemon=True)
    mitmproxy_thread.start()

    logger.info(
        f"Firewall started. FastAPI on port {FASTAPI_PORT}, mitmproxy on port {MITMPROXY_PORT}"
    )

    yield

    # Shutdown
    logger.info("Shutting down firewall...")

    # Stop rules manager watcher
    if rules_manager:
        rules_manager.stop_watching()

    # Stop mitmproxy
    if mitmproxy_master:
        try:
            mitmproxy_master.shutdown()
        except Exception as e:
            logger.warning(f"Error shutting down mitmproxy: {e}")

    # Wait for thread to finish
    if mitmproxy_thread and mitmproxy_thread.is_alive():
        mitmproxy_thread.join(timeout=2.0)

    logger.info("Firewall shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="DPI Firewall",
    description="Deep Packet Inspection Firewall with metrics",
    lifespan=lifespan,
)


@app.get("/metrics")
async def metrics():
    """Get firewall metrics"""
    total_requests, blocked_requests = get_metrics()
    return {"total_requests": total_requests, "blocked_requests": blocked_requests}


@app.get("/logs")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    blocked: bool | None = Query(None),
    url_contains: str | None = Query(None),
):
    items, total = get_logs(
        page=page, page_size=page_size, blocked=blocked, url_contains=url_contains
    )

    def to_dict(r):
        return {
            "id": r.id,
            "url": r.url,
            "blocked": r.blocked,
            "timestamp": r.timestamp.isoformat() + "Z",
            "headers": r.headers,
            "body": r.body,
            "matched_rule": r.matched_rule,
        }

    return {"items": [to_dict(r) for r in items], "total": total}


@app.get("/logs/{log_id}")
async def get_log(log_id: int):
    r = get_log_by_id(log_id)
    if not r:
        raise HTTPException(status_code=404, detail="Log not found")
    return {
        "id": r.id,
        "url": r.url,
        "blocked": r.blocked,
        "timestamp": r.timestamp.isoformat() + "Z",
        "headers": r.headers,
        "body": r.body,
        "matched_rule": r.matched_rule,
    }


@app.delete("/logs")
async def purge_logs(blocked: bool | None = Query(None)):
    deleted = delete_logs(blocked)
    return {"deleted": deleted}


@app.get("/rules")
async def get_rules():
    return {
        "rules": rules_manager.serialize_rules() if rules_manager else [],
        "last_loaded_at": rules_manager.last_loaded_at if rules_manager else None,
        "source_path": str(rules_manager.rules_file) if rules_manager else None,
    }


@app.post("/rules/reload")
async def reload_rules():
    if not rules_manager:
        raise HTTPException(status_code=500, detail="Rules manager not initialized")
    rules_manager.load_rules()
    app_state["last_rules_reload_at"] = rules_manager.last_loaded_at
    return {"reloaded_count": len(rules_manager.serialize_rules())}


@app.post("/rules/validate")
async def validate_rules(payload: dict[str, str] = Body(...)):
    valid, errors = RulesManager.validate_rules_payload(payload)
    return {"valid": valid, "errors": errors}


@app.post("/rules/test")
async def test_rules(payload: dict[str, str | dict[str, str]] = Body(...)):
    if not rules_manager:
        raise HTTPException(status_code=500, detail="Rules manager not initialized")
    url = payload.get("url", "")
    headers = payload.get("headers", None) or {}
    body = payload.get("body") or ""
    matched = rules_manager.check_request(url, headers, body)
    if matched:
        return {
            "matched": True,
            "rule": {
                "pattern": matched.pattern,
                "type": matched.type,
                "action": matched.action,
                "description": matched.description,
            },
        }
    return {"matched": False, "rule": None}


@app.get("/metrics/detailed")
async def metrics_detailed():
    return get_detailed_metrics()


@app.post("/metrics/reset")
async def metrics_reset():
    reset_metrics()
    return {"ok": True}


@app.get("/status")
async def status():
    proxy_running = bool(
        mitmproxy_master and getattr(mitmproxy_master, "running", False)
    )
    rules_count = len(rules_manager.serialize_rules()) if rules_manager else 0
    from .config import DB_PATH

    uptime_sec = int((datetime.now() - app_state["start_time"]).total_seconds())
    return {
        "fastapi_port": FASTAPI_PORT,
        "mitmproxy_port": MITMPROXY_PORT,
        "proxy_running": proxy_running,
        "rules_count": rules_count,
        "db_path": DB_PATH,
        "log_level": LOG_LEVEL,
        "uptime_sec": uptime_sec,
    }


@app.post("/admin/log-level")
async def admin_log_level(payload: dict = Body(...)):
    level = str(payload.get("level", "INFO")).upper()
    if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
        raise HTTPException(status_code=400, detail="Invalid level")
    logging.getLogger().setLevel(level)
    return {"ok": True, "level": level}


@app.post("/admin/firewall")
async def admin_firewall(payload: dict = Body(...)):
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="'enabled' must be boolean")
    app_state["observe_mode"] = not enabled
    return {"ok": True, "mode": "enforce" if enabled else "observe"}


@app.get("/export/logs")
async def export_logs(blocked: bool | None = Query(None), format: str = Query("csv")):
    fmt = format.lower()
    if fmt not in {"csv", "ndjson"}:
        raise HTTPException(status_code=400, detail="format must be csv or ndjson")

    def row_to_dict(r):
        return {
            "id": r.id,
            "url": r.url,
            "blocked": r.blocked,
            "timestamp": r.timestamp.isoformat() + "Z",
            "headers": r.headers,
            "body": r.body,
            "matched_rule": r.matched_rule,
        }

    if fmt == "csv":
        import csv
        import io

        def generate():
            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=[
                    "id",
                    "url",
                    "blocked",
                    "timestamp",
                    "headers",
                    "body",
                    "matched_rule",
                ],
            )
            writer.writeheader()
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            for r in iterate_logs(blocked):
                writer.writerow(row_to_dict(r))
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate(0)

        return StreamingResponse(generate(), media_type="text/csv")
    else:
        import json as _json

        def generate():
            for r in iterate_logs(blocked):
                yield _json.dumps(row_to_dict(r)) + "\n"

        return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/health/live")
async def health_live():
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready():
    try:
        # simple DB check
        _ = get_metrics()
        ready = True
    except Exception:
        ready = False
    rules_ok = rules_manager is not None and len(rules_manager.serialize_rules()) >= 0
    return {"status": "ready" if (ready and rules_ok) else "not_ready"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run FastAPI with uvicorn
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=FASTAPI_PORT)
