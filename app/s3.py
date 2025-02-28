import json
import os
import subprocess
from pathlib import Path

import boto3
from botocore.client import Config

from app.audio import AUDIO_SAMPLE_RATE
from app.utils import log_error, logger

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_HOST = os.environ["AWS_HOST"]


s3_client = boto3.client(
    "s3",
    endpoint_url=f"https://{AWS_HOST}",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="eu-central-2",
)


def validate_video_has_audio_stream(
    bucket_name: str, file_name: str
) -> tuple[bool, str]:
    """Validate whether a video has an audio stream"""

    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": file_name},
        ExpiresIn=3600,
    )

    # Use ffprobe to get video duration and stream info
    command = [
        "ffprobe",
        "-v",
        "error",
        "-i",
        presigned_url,
        "-show_entries",
        "format=duration : stream=codec_type,codec_name,sample_rate,channels",  # Only audio-related stream info
        "-of",
        "json",
    ]

    try:
        result = subprocess.run(command, capture_output=True, check=True)
    except Exception as e:
        log_error(e, "Validation of input file")
        message = (
            f"Failed to probe {file_name}. The file may not exist or be corrupted."
        )
        logger.error(message)
        return False, message

    info = json.loads(result.stdout)

    if not info.get("streams"):
        message = f"No streams found in {file_name}"
        logger.error(message)
        return False, message

    audio_stream = next(
        (s for s in info["streams"] if s.get("codec_type") == "audio"), None
    )
    has_audio = audio_stream is not None

    if not has_audio:
        message = f"No audio stream found in {file_name}"
        logger.error(message)
        return False, message

    duration = (
        float(info["format"]["duration"])
        if "duration" in info.get("format", {})
        else 0.0
    )

    message = (
        f"Video file {file_name} with duration of {duration:.1f}s "
        f"{'has' if has_audio else 'does not have'} an audio stream"
    )
    logger.info(message)
    return True, message


def extract_audio_from_s3_video(bucket: str, key: str, destination: Path) -> None:
    """Stream video from bucket and extract its audio as WAV"""
    input_url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
    )
    logger.info(f"Extracting audio from {bucket}/{key}...")

    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        input_url,
        "-vn",
        "-acodec",
        "pcm_s16le",  # Use 16-bit PCM codec for WAV
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-ac",
        "1",
        str(destination),
        "-y",
    ]

    try:
        subprocess.run(args=command, check=True, text=True)
        logger.info(f"Extracted audio to {destination.name}!")
    except Exception as e:
        log_error(e, "Extraction of audio")
        raise


def upload_to_s3(file_location: Path, bucket: str, folder: str, key: str) -> str:
    """Upload file to S3. I've added the folder to the key as a prefix to avoid overwriting existing files in the bucket."""
    try:
        s3_key = f"{folder}/{key}"
        s3_url = f"{s3_client.meta.endpoint_url}/{bucket}/{s3_key}"
        s3_client.upload_file(Filename=str(file_location), Bucket=bucket, Key=s3_key)
        logger.info(f"Uploaded file to {s3_url}")
        return s3_url
    except Exception as e:
        log_error(e, "Uploading to S3")
        raise
