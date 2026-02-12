import logging
from contextvars import ContextVar
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / 'logs'

_current_host: ContextVar[str] = ContextVar('current_host', default='unknown')


def set_host(host: str):
    _current_host.set(host)


def current_host() -> str:
    return _current_host.get()


class _HostnameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.hostname = _current_host.get()
        return True


def setup_logging():
    today = date.today().isoformat()
    log_dir = LOGS_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)

    app_logger = logging.getLogger('smart_apply')
    app_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on repeated calls
    if app_logger.handlers:
        return

    fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(hostname)s] %(message)s', datefmt='%H:%M:%S')
    hostname_filter = _HostnameFilter()

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    console.addFilter(hostname_filter)
    app_logger.addHandler(console)

    # app.log file handler
    app_file = logging.FileHandler(log_dir / 'app.log', mode='a', encoding='utf-8')
    app_file.setLevel(logging.INFO)
    app_file.setFormatter(fmt)
    app_file.addFilter(hostname_filter)
    app_logger.addHandler(app_file)

    # Specialized loggers (message-only format, no propagation to parent)
    msg_fmt = logging.Formatter('%(message)s')

    for name in ('sent_emails', 'failed_forms', 'failed_urls'):
        logger = logging.getLogger(f'smart_apply.{name}')
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            handler = logging.FileHandler(log_dir / f'{name}.log', mode='a', encoding='utf-8')
            handler.setFormatter(msg_fmt)
            logger.addHandler(handler)


# ── Convenience functions ──

def log_info(msg: str):
    logging.getLogger('smart_apply').info(msg)


def log_warning(msg: str):
    logging.getLogger('smart_apply').warning(msg)


def log_error(msg: str):
    logging.getLogger('smart_apply').error(msg)


def log_debug(msg: str):
    logging.getLogger('smart_apply').debug(msg)


def log_sent_email(email: str):
    logging.getLogger('smart_apply.sent_emails').info(email)
    log_info(f"Sent email to {email}")


def log_failed_form(url: str):
    logging.getLogger('smart_apply.failed_forms').info(url)
    log_warning(f"Failed to submit form at {url}")


def log_failed_url(url: str):
    logging.getLogger('smart_apply.failed_urls').info(url)
    log_warning(f"Failed URL: {url}")
