import os
import tempfile
from pathlib import Path

import requests
from pydantic import UUID4

from app.audio import denoise_audio, normalize_audio
from app.celery_app import denoiser_worker
from app.models import AudioProcessingResult, S3FileLocation, TaskStatus
from app.s3 import extract_audio_from_s3_video, upload_to_s3
from app.utils import logger, timer

AWS_INPUT_BUCKET = os.environ["AWS_INPUT_BUCKET"]
AWS_OUTPUT_BUCKET = os.getenv("AWS_OUTPUT_BUCKET", AWS_INPUT_BUCKET)
AWS_OUTPUT_FOLDER = os.environ["AWS_OUTPUT_FOLDER"]

COMPLETION_WEBHOOK_URL = os.environ["COMPLETION_WEBHOOK_URL"]
COMPLETION_WEBHOOK_AUTH_KEY = os.environ["COMPLETION_WEBHOOK_AUTH_KEY"]

NORMALIZE_AUDIO = os.getenv("NORMALIZE_AUDIO", "true").lower() == "true"


@denoiser_worker.task(ignore_result=True)
@timer
def process_audio_task(
    task_id: UUID4,
    source_video_location: dict,
    destination_bucket: str = AWS_OUTPUT_BUCKET,
    destination_folder: str = AWS_OUTPUT_FOLDER,
) -> S3FileLocation:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            source_video_filename = source_video_location["key"]
            input_path = (Path(temp_dir) / source_video_filename).with_suffix(".wav")
            input_path.parent.mkdir(parents=True, exist_ok=True)

            extract_audio_from_s3_video(
                bucket=source_video_location["bucket"],
                key=source_video_location["key"],
                destination=input_path,
            )

            # Process audio
            denoised_file_location = denoise_audio(input_path, output_dir=temp_dir)

            # Conditionally normalize audio
            if NORMALIZE_AUDIO:
                processed_file_location = normalize_audio(
                    denoised_file_location, output_dir=temp_dir
                )
            else:
                processed_file_location = denoised_file_location

            # Upload result
            result_key = f"{task_id}/{processed_file_location.name}"

            upload_to_s3(
                file_location=processed_file_location,
                bucket=destination_bucket,
                folder=destination_folder,
                key=result_key,
            )

            target_audio_location = S3FileLocation(
                bucket=destination_bucket,
                key=f"{destination_folder}/{result_key}",
            )

            # Send notification with result of the task
            send_completion_notification(
                task_id=task_id,
                status=TaskStatus.COMPLETE,
                source_video_location=S3FileLocation(**source_video_location),
                target_audio_location=target_audio_location,
            )

            return target_audio_location

    except Exception as e:
        error_message = f"Exception: {type(e).__name__}\nException message: {e}"

        logger.error(error_message)

        send_completion_notification(
            task_id=task_id,
            status=TaskStatus.ERROR,
            source_video_location=S3FileLocation(**source_video_location),
            error_message=error_message,
        )
        raise


def send_completion_notification(
    task_id: UUID4,
    status: TaskStatus,
    source_video_location: S3FileLocation,
    target_audio_location: S3FileLocation | None = None,
    error_message: str | None = None,
):
    result = AudioProcessingResult(
        task_id=task_id,
        status=status,
        source_video=source_video_location,
        target_audio=target_audio_location if status == TaskStatus.COMPLETE else None,
        error_message=error_message if status == TaskStatus.ERROR else None,
    )

    response = requests.post(
        COMPLETION_WEBHOOK_URL,
        json=result.model_dump_json(),
        headers={"auth-key": COMPLETION_WEBHOOK_AUTH_KEY},
    )

    log_message = "Sent completion notification"
    if error_message:
        log_message += f" with error: {error_message}"
    logger.info(log_message)
    response.raise_for_status()
