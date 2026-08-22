"""Central structlog configuration."""

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib logging + structlog once, at application startup."""
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    """Project-wide logger factory."""
    return structlog.get_logger(name)
