import os

from celery import Celery

CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", 1))
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_PORT = os.getenv("REDIS_PORT")

if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

denoiser_worker = Celery(
    "denoiser",
    broker=REDIS_URL,
    include=["app.worker"],
)

# Configure for at-least-once delivery
denoiser_worker.conf.update(
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Worker settings
    worker_concurrency=CELERY_WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    # Task acknowledgment Settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Visibility timeout
    broker_transport_options={
        # The task will become visible if not acknowledged again after 2 hours
        "visibility_timeout": 7200,
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
        "socket_keepalive": True,
        "health_check_interval": 60,
    },
    # Task Publishing retry settings
    task_publish_retry=True,
    retry_backoff=True,
    retry_jitter=True,
    task_publish_retry_policy={
        "max_retries": 3,
    },
    worker_max_tasks_per_child=1,  # Restart worker after each task, may be safer for memory, but slower!
    redis_socket_keepalive=True,
)
