import os
import subprocess
from pathlib import Path

from pydub import AudioSegment

from app.utils import log_error, logger, timer

DEMUCS_MODEL_SEGMENT_SIZE = int(os.environ["DEMUCS_MODEL_SEGMENT_SIZE"])
SPLIT_AUDIO_BEFORE_DENOISING = (
    os.getenv("SPLIT_AUDIO_BEFORE_DENOISING", "true").lower() == "true"
)
AUDIO_CHUNK_DURATION_SECONDS = int(os.environ["AUDIO_CHUNK_DURATION_SECONDS"])
OUTPUT_DIR = Path("output")
AUDIO_SAMPLE_RATE = 44100


def denoise_audio(input_file_location: Path, output_dir: Path) -> Path:
    """Process audio using Demucs, optionally in chunks."""
    if not SPLIT_AUDIO_BEFORE_DENOISING:
        # Process the entire file at once
        processed_dir = output_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        return denoise_audio_chunk(input_file_location, processed_dir)

    # Create directories for intermediate files
    chunks_dir = output_dir / "chunks"
    processed_dir = output_dir / "processed_chunks"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Split audio into chunks
    logger.info("Splitting audio into chunks...")
    chunks = split_audio(input_file_location, chunks_dir)

    # Process each chunk
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        logger.info(
            f"Processing {input_file_location.with_suffix('.wav')} - chunk {i + 1}/{len(chunks)}"
        )
        processed_chunk = denoise_audio_chunk(chunk, processed_dir)
        processed_chunks.append(processed_chunk)

    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{input_file_location.stem}.wav"
    joined_file = join_audio(processed_chunks, final_output)

    return joined_file


def split_audio(
    input_file: Path,
    output_dir: Path,
    chunk_duration_seconds: int = AUDIO_CHUNK_DURATION_SECONDS,
) -> list[Path]:
    """Split audio file into chunks using ffmpeg segment filter."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pattern for output chunks
    chunk_pattern = output_dir / f"{input_file.stem}-%03d.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_file),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_duration_seconds),
        "-reset_timestamps",
        "1",
        "-c",
        "copy",
        str(chunk_pattern),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
        # Get list of created chunks
        chunks = sorted(output_dir.glob(f"{input_file.stem}-*.wav"))
        return chunks
    except Exception as e:
        log_error(e, "Splitting audio")
        raise


@timer
def join_audio(input_chunks: list[Path], output_file: Path) -> Path:
    """Join audio chunks back together using pydub."""

    logger.info(f"Joining {len(input_chunks)} chunks:")

    # Load first chunk
    combined = AudioSegment.from_wav(str(input_chunks[0]))

    # Append all other chunks
    for chunk in input_chunks[1:]:
        audio = AudioSegment.from_wav(str(chunk))
        combined += audio

    # Export the combined audio
    combined.export(str(output_file), format="wav")
    return output_file


def denoise_audio_chunk(
    input_file_location: Path,
    output_dir: Path,
    demucs_segment_size: int = DEMUCS_MODEL_SEGMENT_SIZE,
) -> Path:
    """Denoise audio file using Demucs."""

    command_denoise = [
        "demucs",
        "-d",
        "cpu",
        "-n",
        "htdemucs",
        "--two-stems=vocals",
        str(input_file_location),
        "-j",
        "1",
        "--segment",
        str(demucs_segment_size),
        "-o",
        str(output_dir),
    ]

    try:
        logger.info(f"Denoising audio file {input_file_location.name}...")
        subprocess.run(command_denoise, check=True, text=True)
    except Exception as e:
        log_error(e, "Demucs denoising")
        raise

    # We know that the output of Demucs is in the following location
    demucs_result_file_location = (
        output_dir / "htdemucs" / input_file_location.stem / "vocals.wav"
    )

    # Let's move the file to a denoised folder
    denoised_dir = output_dir / "denoised"
    denoised_dir.mkdir(parents=True, exist_ok=True)

    output_file_location = demucs_result_file_location.replace(
        denoised_dir / (input_file_location.with_suffix(".wav"))
    )
    return output_file_location


@timer
def normalize_audio(input_file_location: Path, output_dir: Path) -> Path:
    """Normalize audio file using ffmpeg-normalize."""

    normalized_dir = output_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    output_file_location = normalized_dir / input_file_location.with_suffix(".mp3").name

    command_normalize = [
        "ffmpeg-normalize",
        str(input_file_location),
        "--sample-rate",
        str(AUDIO_SAMPLE_RATE),
        "--audio-codec",
        "libmp3lame",
        "-f",
        "--quiet",
        "-o",
        str(output_file_location),
    ]

    try:
        logger.info(f"Normalizing audio file {input_file_location.name}...")
        subprocess.run(command_normalize, check=True, text=True)
    except Exception as e:
        log_error(e, "Normalization")
        raise

    return output_file_location
