import logging
import os
import subprocess
from functools import wraps
from time import perf_counter

from fastapi import HTTPException
from pydantic import UUID4

logger = logging.getLogger("denoiser")

AUTH_KEY = UUID4(os.environ["AUTH_KEY"])

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.info(f"{func.__name__} took {end - start:.2f} seconds")
        return result

    return wrapper


def validate_key(auth_key: UUID4):
    if auth_key != AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid authentication key")


def log_error(e: Exception, context: str):
    """Log errors with context and additional details for subprocess errors

    Args:
        e: The Exception that occurred
        context: Description of what failed
    """
    logger.error(f"{context} failed with error of type {type(e).__name__}: {e}")

    if isinstance(e, subprocess.CalledProcessError):
        logger.error(f"Error output: {e.stderr}")
