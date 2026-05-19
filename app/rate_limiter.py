import asyncio
import random
from .config import settings


async def anti_429_delay() -> float:
    delay = random.uniform(settings.rate_limit_min, settings.rate_limit_max)
    await asyncio.sleep(delay)
    return delay
