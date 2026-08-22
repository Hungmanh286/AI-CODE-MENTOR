from typing import Optional

from redis import Redis

from app.core.config import settings


class UserUsage:
    def __init__(
        self,
        redis: Redis,
        window_minutes: int = settings.RATELIMIT_WINDOW_MINUTES,
    ):
        self.redis = redis
        self.window_minutes = window_minutes

    async def close(self) -> None:
        await self.redis.close()

    async def isratelimit(self, user_id: str, rate_limit: int) -> bool:
        """Check user usage is reach limited

        Args:
            user_id (str): user id as key store
            rate_limit (int): ratelimit (tokens)

        Returns:
            bool: is user usage reach limit
        """
        current_tokens = await self.redis.get(name=user_id)
        return int(current_tokens or 0) >= rate_limit

    async def update_usage(
        self,
        user_id: str,
        tokens_usage: int,
        window_minutes: Optional[int] = None,
    ) -> None:
        """Update user usage

        Args:
            user_id (str): user id as ratelimit key
            tokens_usage (int): user token usage
            window_hours (int, optional): window minutes for ratelimit. Defaults to None.

        Returns:
            None
        """
        ttl = (window_minutes or self.window_minutes) * 60
        if not await self.redis.exists(user_id):
            await self.redis.set(user_id, tokens_usage, ex=ttl)
            return

        await self.redis.incrby(user_id, tokens_usage)
