import sys
import subprocess
import threading
import datetime as dt
from fastapi import APIRouter
from loguru import logger
from api.core_config import PROJECT_DIR, CUR_DIR

router = APIRouter()

_refresh_lock = threading.Lock()
_refresh_status = {"running": False, "last_result": None, "last_time": None}

_reports_refresh_status = {"running": False, "last_time": None, "last_result": None}
_reports_refresh_lock = threading.Lock()

_topics_refresh_status = {"running": False, "last_time": None, "last_result": None}
_topics_refresh_lock = threading.Lock()

@router.post("/api/refresh/reports")
def refresh_reports_only():
    """
    Triggers only the AI Reports update, avoiding the full global data refresh.
    """
    if _reports_refresh_status["running"]:
        return {"status": "busy", "message": "A reports refresh is already running. Please wait."}

    def _do_refresh():
        _reports_refresh_status["running"] = True
        _reports_refresh_status["last_result"] = None
        try:
            script = str(PROJECT_DIR / "zizizaizai/reports.py")
            logger.info(f"[Refresh Reports] Running: {script}")
            result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120, cwd=str(CUR_DIR))

            if result.returncode == 0:
                _reports_refresh_status["last_result"] = "success"
                logger.info("[Refresh Reports] Completed successfully.")
            else:
                _reports_refresh_status["last_result"] = "error"
                logger.error(f"[Refresh Reports] Failed: {result.stderr if result.stderr else result.stdout}")
        except Exception as e:
            _reports_refresh_status["last_result"] = f"exception: {str(e)}"
            logger.error(f"[Refresh Reports] Exception: {e}")
        finally:
            _reports_refresh_status["running"] = False
            _reports_refresh_status["last_time"] = dt.datetime.now().isoformat()

    with _reports_refresh_lock:
        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    return {"status": "started", "message": "Reports refresh started in background."}

@router.get("/api/refresh/reports/status")
def get_reports_refresh_status():
    return _reports_refresh_status

@router.post("/api/refresh/topics")
def refresh_topics_only():
    """
    Triggers only the Topics & K-lines update.
    """
    if _topics_refresh_status["running"]:
        return {"status": "busy", "message": "A topics refresh is already running. Please wait."}

    def _do_refresh():
        _topics_refresh_status["running"] = True
        _topics_refresh_status["last_result"] = None
        try:
            update_script = str(PROJECT_DIR / "tasks/update_daily.py")
            cmd = [sys.executable, update_script, "--mode", "topics"]
            logger.info(f"[Refresh Topics] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(PROJECT_DIR))

            if result.returncode == 0:
                _topics_refresh_status["last_result"] = "success"
                logger.info("[Refresh Topics] Completed successfully.")
            else:
                _topics_refresh_status["last_result"] = "error"
                logger.error(f"[Refresh Topics] Failed: {result.stderr if result.stderr else result.stdout}")
        except Exception as e:
            _topics_refresh_status["last_result"] = f"exception: {str(e)}"
            logger.error(f"[Refresh Topics] Exception: {e}")
        finally:
            _topics_refresh_status["running"] = False
            _topics_refresh_status["last_time"] = dt.datetime.now().isoformat()

    with _topics_refresh_lock:
        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    return {"status": "started", "message": "Topics refresh started in background."}

@router.get("/api/refresh/topics/status")
def get_topics_refresh_status():
    return _topics_refresh_status

@router.post("/api/refresh")
def refresh_data():
    """
    Triggers a full refresh of market_sentiment.csv by running the collector's
    signals layer.
    """
    if _refresh_status["running"]:
        return {"status": "busy", "message": "A refresh is already running. Please wait."}

    def _do_refresh():
        _refresh_status["running"] = True
        _refresh_status["last_result"] = None
        try:
            update_script = str(PROJECT_DIR / "tasks/update_daily.py")
            cmd = [sys.executable, update_script, "--force"]
            logger.info(f"[Refresh] Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(PROJECT_DIR))

            if result.returncode == 0:
                _refresh_status["last_result"] = "success"
                logger.info("[Refresh] Full data update completed successfully.")
            else:
                _refresh_status["last_result"] = f"error: {result.stderr[-500:] if result.stderr else result.stdout[-500:]}"
                logger.error(f"[Refresh] Full data update failed: {result.stderr if result.stderr else result.stdout}")
        except Exception as e:
            _refresh_status["last_result"] = f"exception: {str(e)}"
            logger.error(f"[Refresh] Exception during refresh: {e}")
        finally:
            _refresh_status["running"] = False
            _refresh_status["last_time"] = dt.datetime.now().isoformat()

    with _refresh_lock:
        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    return {"status": "started", "message": "Data refresh started in background. Check /api/refresh/status for progress."}

@router.get("/api/refresh/status")
def refresh_status():
    """Returns the current status of the last data refresh."""
    return {
        "running": _refresh_status["running"],
        "last_result": _refresh_status["last_result"],
        "last_time": _refresh_status["last_time"],
    }
