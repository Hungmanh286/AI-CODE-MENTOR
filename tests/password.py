import structlog

import secrets

logger = structlog.get_logger(__name__)

password = secrets.token_urlsafe(16)

logger.info(password)
