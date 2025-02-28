from enum import Enum

from pydantic import UUID4, BaseModel


class TaskStatus(str, Enum):
    COMPLETE = "complete"
    ERROR = "error"


class S3FileLocation(BaseModel):
    bucket: str
    key: str


class AudioProcessingResult(BaseModel):
    task_id: UUID4
    status: TaskStatus
    source_video: S3FileLocation
    target_audio: S3FileLocation | None = None
    error_message: str | None = None


class DenoiseResponse(BaseModel):
    task_id: UUID4
    message: str
