"""
WSGI config for smartq project.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import logging
import os
import threading

from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smartq.settings")

application = get_wsgi_application()

_logger = logging.getLogger(__name__)
_live_study_started = False
_live_study_lock = threading.Lock()


def _env_bool(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _start_scheduled_live_study():
    """
    Presentation-only scheduler.

    Render's free web service has no separate worker process. When explicitly
    enabled by environment variable, the single Gunicorn worker starts one
    daemon thread that arms the Pretoria Central live-study management command.
    The command itself is idempotent so a Render restart can safely resume it.
    """
    global _live_study_started

    if not _env_bool("SMARTQ_LIVE_STUDY_ENABLED"):
        return

    with _live_study_lock:
        if _live_study_started:
            return
        _live_study_started = True

    target_date = os.getenv("SMARTQ_LIVE_STUDY_DATE", "").strip()
    start_time = os.getenv("SMARTQ_LIVE_STUDY_START", "02:00").strip()
    customers = int(os.getenv("SMARTQ_LIVE_STUDY_CUSTOMERS", "15"))
    priority = int(os.getenv("SMARTQ_LIVE_STUDY_PRIORITY", "5"))
    window_minutes = int(os.getenv("SMARTQ_LIVE_STUDY_WINDOW_MINUTES", "90"))

    if not target_date:
        _logger.error(
            "SMARTQ_LIVE_STUDY_ENABLED is true but SMARTQ_LIVE_STUDY_DATE is missing."
        )
        return

    def runner():
        try:
            call_command(
                "run_pretoria_live_study",
                target_date=target_date,
                start_time=start_time,
                customers=customers,
                priority=priority,
                window_minutes=window_minutes,
                poll_seconds=2.0,
                branch_code="PTA01",
            )
        except Exception:
            _logger.exception("Pretoria Central live study stopped unexpectedly.")

    threading.Thread(
        target=runner,
        name="smartq-pretoria-live-study",
        daemon=True,
    ).start()


_start_scheduled_live_study()
