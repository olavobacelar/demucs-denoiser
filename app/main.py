import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import UUID4

from app.models import DenoiseResponse, S3FileLocation
from app.s3 import validate_video_has_audio_stream
from app.utils import logger, validate_key
from app.worker import process_audio_task

IS_WORKER = os.environ["IS_WORKER"].lower() == "true"

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


if not IS_WORKER:

    @app.post("/denoise", status_code=202)
    def process_audio(
        source_video_location: S3FileLocation,
        auth_key: UUID4 = Header(alias="auth-key"),
    ):
        validate_key(auth_key)
        success, message = validate_video_has_audio_stream(
            source_video_location.bucket, source_video_location.key
        )
        if not success:
            raise HTTPException(status_code=400, detail=message)

        task_id = uuid.uuid4()

        try:
            # Submit task to Celery
            process_audio_task.delay(
                task_id=task_id,
                source_video_location=source_video_location.model_dump(),
            )
            logger.info(
                f"Audio denoising task queued | Task ID: {task_id} | Source: {source_video_location.bucket}/{source_video_location.key}"
            )

            return DenoiseResponse(
                task_id=task_id, message="Audio denoising task queued successfully"
            )
        except Exception as e:
            logger.error(f"Failed to queue audio denoising task: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to queue audio denoising task"
            )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
