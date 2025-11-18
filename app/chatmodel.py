from langchain.chat_models import init_chat_model
from langchain.chat_models.base import BaseChatModel


def init_llm(model: str, **kwargs) -> BaseChatModel:
    """
    Initialize the chat model with the given model name and configuration.
    Args:
        model (str): The name of the chat model to initialize.
        **kwargs: Additional keyword arguments for the chat model initialization.

    Returns:
        BaseChatModel: An instance of the initialized chat model.
    """

    model = "google_genai:" + model if model.startswith("gemini") else model
    llm_config = dict(
        max_tokens=6000,
        temperature=0,
        timeout=None,
        max_retries=2,
        stream_usage=True,
    )
    llm_config.update(kwargs)

    return init_chat_model(model=model, **llm_config)
