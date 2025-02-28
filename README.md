# Demucs Denoiser API

An API to denoise using [Demucs](https://github.com/facebookresearch/demucs). While Demucs is primarily designed for audio source separation, it also excels at removing noise from voice recordings.
The API accepts video files (with audio streams) or audio files as input, extracts the audio when needed, processes it, and returns the denoised audio. Optionally, the audio can be normalized after denoising. This API uses S3 for I/O and redis as the message broker for the celery queue, which is configured for at least once delivery.

## Requirements

- A redis server for the queue.
- Docker. Note that we are using [supervisor](http://supervisord.org/) to run the celery worker together with FastAPI inside the container because the cloud I was using (Clever Cloud) does not support Docker Compose
- If not using Docker, you need to have [uv](https://docs.astral.sh/uv/getting-started/installation/) to build and run the python app and you might also want [just](https://just.systems/man/en/introduction.html) to make it easier to run the app

## How to run locally (on macOS)

1. Clone this repo
2. Set the env variables (example under `.env.example`).
   - By default, this program splits the audio into chunks for processing. If you prefer to process the entire file at once, set the `SPLIT_AUDIO_BEFORE_DENOISING` environment variable to `false`. The duration of each chunk is controlled by the `AUDIO_CHUNK_DURATION_SECONDS` variable.
   - You might want to set the `REDIS_HOST` env variable to `127.0.0.1` if you are running redis locally.
   - By default, audio is normalized after denoising. To skip normalization, set the `NORMALIZE_AUDIO` environment variable to `false`.
   - Set the AWS credentials and the API tokens as well.
   - Source the env variables with `source .env.example`.
3. Start the redis queue with `redis-server`
4. If you want to use Docker, run `just docker`
5. If you do not want to use Docker:
   - Install ffmpeg with `brew install ffmpeg`
   - Install the dependencies with `uv sync`
   - Activate the python virtual environment with `source .venv/bin/activate`
   - Run the app with `just supervisor`
