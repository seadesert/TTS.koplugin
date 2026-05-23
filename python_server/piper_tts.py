"""
Python Piper-TTS server based on Flask, based on piper script [https://github.com/OHF-Voice/piper1-gpl/blob/main/src/piper/http_server.py]

Install necessary dependencies using:
python3 -m pip install piper-tts[http] gunicorn

set following environment variables:
export PIPER_MODEL="~/model.onnx"
export PIPER_USE_CUDA="false"
export API_PASSWORD="p4$$w0rd"

Run server using:
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 piper_tts:app
"""

import os
import io
import json
import logging
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlopen

from flask import Flask, request, Response

# Assuming these are available in your environment/package
try:
    from . import PiperVoice, SynthesisConfig
    from .download_voices import VOICES_JSON, download_voice
except ImportError:
    # Fallback for local execution if not running as a package
    from piper import PiperVoice, SynthesisConfig
    from piper.download_voices import VOICES_JSON, download_voice

# --- CONFIGURATION (Environment Variables) ---
MODEL_PATH = Path(os.environ.get("PIPER_MODEL", "model.onnx"))
USE_CUDA = os.environ.get("PIPER_USE_CUDA", "false").lower() == "true"
DATA_DIRS = os.environ.get("PIPER_DATA_DIRS", str(Path.cwd())).split(",")
DOWNLOAD_DIR = Path(os.environ.get("PIPER_DOWNLOAD_DIR", DATA_DIRS[0]))
SENTENCE_SILENCE = float(os.environ.get("PIPER_SENTENCE_SILENCE", 0.0))
DEFAULT_SPEAKER = int(os.environ.get("PIPER_SPEAKER", 0))
DEBUG_MODE = os.environ.get("PIPER_DEBUG", "false").lower() == "true"
PASSWORD = os.environ.get("API_PASSWORD", "p4$$w0rd")

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
_LOGGER = logging.getLogger(__name__)

# --- INITIALIZATION ---
def load_initial_voice():
    """Loads the default voice once at startup."""
    if not MODEL_PATH.exists():
        _LOGGER.warning(f"Model path {MODEL_PATH} not found. Checking data dirs...")
        # Search for model in data directories if full path wasn't provided
        for data_dir in DATA_DIRS:
            maybe_path = Path(data_dir) / f"{MODEL_PATH.name}"
            if maybe_path.exists():
                return PiperVoice.load(maybe_path, use_cuda=USE_CUDA)
        raise FileNotFoundError(f"Could not find model: {MODEL_PATH}")

    return PiperVoice.load(MODEL_PATH, use_cuda=USE_CUDA)

# Pre-load the default voice
default_voice = load_initial_voice()
default_model_id = MODEL_PATH.name.rstrip(".onnx")
loaded_voices: Dict[str, PiperVoice] = {default_model_id: default_voice}

# --- FLASK APP ---
app = Flask(__name__)

@app.route("/voices", methods=["GET"])
def app_voices() -> Dict[str, Any]:
    voices_dict: Dict[str, Any] = {}
    config_paths: List[Path] = [Path(f"{MODEL_PATH}.json")]

    for data_dir in DATA_DIRS:
        for onnx_path in Path(data_dir).glob("*.onnx"):
            config_path = Path(f"{onnx_path}.json")
            if config_path.exists():
                config_paths.append(config_path)

    for config_path in config_paths:
        model_id = config_path.name.rstrip(".onnx.json")
        if model_id in voices_dict:
            continue

        with open(config_path, "r", encoding="utf-8") as config_file:
            voices_dict[model_id] = json.load(config_file)

    return voices_dict

@app.route("/all-voices", methods=["GET"])
def app_all_voices() -> Dict[str, Any]:
    with urlopen(VOICES_JSON) as response:
        return json.load(response)

# @app.route("/download", methods=["POST"])
# def app_download() -> str:
#     data = request.get_json()
#     model_id = data.get("voice")
#     if not model_id:
#         return "voice is required", 400

#     force_redownload = data.get("force_redownload", False)
#     download_voice(model_id, DOWNLOAD_DIR, force_redownload=force_redownload)
#     return model_id

@app.route("/", methods=["POST"])
def app_synthesize():
    data = request.get_json()
    if not data:
        return "Invalid JSON", 400

    text = data.get("text", "").strip()
    if not text:
        return "No text provided", 400

    password = data.get("password", "").strip()
    if not password and password != PASSWORD:
        return "Invalid password", 400

    model_id = data.get("voice", default_model_id)
    voice = loaded_voices.get(model_id)

    if voice is None:
        for data_dir in DATA_DIRS:
            maybe_model_path = Path(data_dir) / f"{model_id}.onnx"
            if maybe_model_path.exists():
                _LOGGER.debug("Loading voice %s", model_id)
                voice = PiperVoice.load(maybe_model_path, use_cuda=USE_CUDA)
                loaded_voices[model_id] = voice
                break

    if voice is None:
        _LOGGER.warning("Voice not found: %s. Using default.", model_id)
        voice = default_voice

    speaker_id: Optional[int] = data.get("speaker_id")
    if (voice.config.num_speakers > 1) and (speaker_id is None):
        speaker = data.get("speaker")
        if speaker:
            speaker_id = voice.config.speaker_id_map.get(speaker)
        if speaker_id is None:
            speaker_id = DEFAULT_SPEAKER

    syn_config = SynthesisConfig(
        speaker_id=speaker_id,
        length_scale=float(data.get("length_scale", voice.config.length_scale)),
        noise_scale=float(data.get("noise_scale", voice.config.noise_scale)),
        noise_w_scale=float(data.get("noise_w_scale", voice.config.noise_w_scale)),
    )

    _LOGGER.debug("Synthesizing: '%s'", text)
    try:
        with io.BytesIO() as wav_io:
            wav_file: wave.Wave_write = wave.open(wav_io, "wb")
            with wav_file:
                wav_params_set = False
                for i, audio_chunk in enumerate(voice.synthesize(text, syn_config)):
                    if not wav_params_set:
                        wav_file.setframerate(audio_chunk.sample_rate)
                        wav_file.setsampwidth(audio_chunk.sample_width)
                        wav_file.setnchannels(audio_chunk.sample_channels)
                        wav_params_set = True

                    if i > 0:
                        wav_file.writeframes(
                            bytes(
                                int(
                                    voice.config.sample_rate * SENTENCE_SILENCE * 2
                                )
                            )
                        )

                    wav_file.writeframes(audio_chunk.audio_int16_bytes)

            return wav_io.getvalue()
    except wave.Error as e:
        _LOGGER.warning("Error writing WAV file: %s. Returning empty audio.", e)
        # Return a valid empty WAV file
        with io.BytesIO() as wav_io:
            wav_file: wave.Wave_write = wave.open(wav_io, "wb")
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.close()
            return wav_io.getvalue()


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=DEBUG_MODE)