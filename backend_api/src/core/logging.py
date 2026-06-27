import logging
import json
import traceback
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

correlation_id_ctx: ContextVar[str] = ContextVar(
    "correlation_id", default="NO_CORRELATION_ID"
)
request_path_ctx: ContextVar[str] = ContextVar(
    "request_path", default="SYSTEM_BACKGROUND"
)
client_ip_ctx: ContextVar[str] = ContextVar("client_ip", default="LOCAL")


class EnterpriseJSONFormatter(logging.Formatter):
    def __init__(self, service_name: str, environment: str):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

        self.pii_keys = {
            "password",
            "token",
            "secret",
            "ssn",
            "credit_card",
            "cvv",
            "key",
        }

    def _scrub_record_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        scrubbed = {}
        for key, value in data.items():
            if any(pii in key.lower() for pii in self.pii_keys):
                scrubbed[key] = "[REDACTED_LOGGER]"
            elif isinstance(value, dict):
                scrubbed[key] = self._scrub_record_dict(value)
            else:
                scrubbed[key] = value
        return scrubbed

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "environment": self.environment,
            "logger_name": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get(),
            "request_path": request_path_ctx.get(),
            "client_ip": client_ip_ctx.get(),
            "process": record.process,
            "thread": record.threadName,
            "source": f"{record.pathname}:{record.lineno}",
        }

        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_obj["metadata"] = self._scrub_record_dict(record.extra_data)

        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__
                if record.exc_info[0]
                else "Unknown",
                "message": str(record.exc_info[1]),
                "stacktrace": "".join(traceback.format_exception(*record.exc_info)),
            }

        return json.dumps(log_obj)


def setup_enterprise_logging(
    level: int = logging.INFO, environment: str = "development"
) -> None:
    root_logger = logging.getLogger()

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)

    if environment == "local_dev":
        console_format = logging.Formatter(
            "%(asctime)s - [%(levelname)s] - [%(correlation_id)s] - %(name)s - %(message)s"
        )
        console_handler.setFormatter(console_format)
    else:
        json_formatter = EnterpriseJSONFormatter(
            service_name="agentic-governance-os", environment=environment
        )
        console_handler.setFormatter(json_formatter)

    class ContextFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.correlation_id = correlation_id_ctx.get()
            record.client_ip = client_ip_ctx.get()
            return True

    console_handler.addFilter(ContextFilter())
    root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class AuditLogShipper:
    def __init__(self, target_url: str, api_key: str):
        self.target_url = target_url
        self.api_key = api_key
        self.batch_size = 100
        self._buffer: List[Dict[str, Any]] = []

    def queue_log(self, log_entry: Dict[str, Any]) -> None:
        self._buffer.append(log_entry)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return

        payload = list(self._buffer)
        self._buffer.clear()

        try:
            pass
        except Exception as e:
            fallback_logger = logging.getLogger("shipper_fallback")
            fallback_logger.error(f"Failed to ship logs to {self.target_url}: {str(e)}")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_security_event(
    logger: logging.Logger, event_name: str, user_id: str, details: Dict[str, Any]
) -> None:
    logger.warning(
        f"SECURITY EVENT: {event_name}",
        extra={
            "extra_data": {
                "user_id": user_id,
                "event_details": details,
                "is_security_event": True,
            }
        },
    )


def set_logging_context(correlation_id: str, request_path: str, client_ip: str) -> None:
    correlation_id_ctx.set(correlation_id)
    request_path_ctx.set(request_path)
    client_ip_ctx.set(client_ip)
