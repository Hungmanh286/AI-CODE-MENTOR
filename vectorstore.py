import structlog

logger = structlog.get_logger(__name__)

import langchain
import langchain_core
import langchain_community

logger.info(" ".join(str(_log_value) for _log_value in ("langchain:", langchain.__version__)))
logger.info(" ".join(str(_log_value) for _log_value in ("core:", langchain_core.__version__)))
logger.info(" ".join(str(_log_value) for _log_value in ("community:", langchain_community.__version__)))
logger.info(" ".join(str(_log_value) for _log_value in ("path:", langchain.__file__)))
