import structlog

logger = structlog.get_logger(__name__)

import secrets

password = secrets.token_urlsafe(16)

logger.info(password)
