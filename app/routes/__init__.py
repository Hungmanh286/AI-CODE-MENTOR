from .chat import router as chat_router


class Routers:
    chat_router = chat_router


__all__ = ["Routers"]
