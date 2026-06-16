from langchain_openrouter import ChatOpenRouter
from langchain.chat_models.base import BaseChatModel

from app.config import settings


def init_llm(model: str, **kwargs) -> BaseChatModel:
    """
    Initialize the chat model with the given model name and configuration.
    Uses ChatOpenRouter to route requests through OpenRouter API.
    Args:
        model (str): The name of the chat model to initialize.
        **kwargs: Additional keyword arguments for the chat model initialization.

    Returns:
        BaseChatModel: An instance of the initialized chat model.
    """

    llm_config = dict(
        api_key=settings.OPENROUTER_API_KEY,
        max_tokens=10000,
        temperature=0,
        timeout=None,
        max_retries=2,
        stream_usage=True,
    )
    llm_config.update(kwargs)

    return ChatOpenRouter(model=model, **llm_config)
