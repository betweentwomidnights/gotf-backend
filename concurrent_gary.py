import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp as youtube_dl
import torch
import torchaudio
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write
import torchaudio.transforms as T
from concurrent.futures import ThreadPoolExecutor
from flask_socketio import SocketIO

app = Flask(__name__)
CORS(app)
executor = ThreadPoolExecutor(max_workers=2)

def cleanup_files(*file_paths):
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)

def download_audio(youtube_url):
    downloaded_mp3 = 'downloaded_audio.mp3'
    downloaded_webm = 'downloaded_audio.webm'
    cleanup_files(downloaded_mp3, downloaded_webm)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'downloaded_audio.%(ext)s',
        'keepvideo': True,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return downloaded_mp3, downloaded_webm

def load_and_preprocess_audio(file_path):
    song, sr = torchaudio.load(file_path)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    song = song.to(device)
    expected_sr = 32000
    if sr != expected_sr:
        resampler = T.Resample(sr, expected_sr).to(device)
        song = resampler(song)
        sr = expected_sr
    prompt_length = sr * 5
    prompt_waveform = song[:, :prompt_length] if song.shape[1] > prompt_length else song
    return prompt_waveform, sr

def generate_audio_continuation(prompt_waveform, sr):
    model_continue = MusicGen.get_pretrained('facebook/musicgen-small')
    model_continue.set_generation_params(use_sampling=True, top_k=250, top_p=0.0, temperature=1.0, duration=12, cfg_coef=3)
    output = model_continue.generate_continuation(prompt_waveform, prompt_sample_rate=sr, progress=True)
    return output.cpu().squeeze(0)

def save_generated_audio(output, sr):
    output_filename = 'generated_continuation'
    audio_write(output_filename, output, sr, strategy="loudness", loudness_compressor=True)
    return output_filename + '.wav'

def process_youtube_url(youtube_url):
    try:
        downloaded_mp3, downloaded_webm = download_audio(youtube_url)
        prompt_waveform, sr = load_and_preprocess_audio(downloaded_mp3)
        output = generate_audio_continuation(prompt_waveform, sr)
        output_filename = save_generated_audio(output, sr)
        cleanup_files(downloaded_mp3, downloaded_webm)
        return output_filename
    except Exception as e:
        print(f"Error processing YouTube URL: {e}")
        return None

@app.route('/generate', methods=['POST'])
def generate_audio():
    data = request.json
    youtube_url = data['url']
    audio_path = process_youtube_url(youtube_url)  # Assuming this is a synchronous call.
    if audio_path:
        with open(audio_path, 'rb') as audio_file:
            encoded_audio = base64.b64encode(audio_file.read()).decode('utf-8')
        cleanup_files(audio_path)
        return jsonify({"audio": encoded_audio})  # Send the audio data back in the response
    else:
        return jsonify({"error": "Failed to process audio"}), 500

if __name__ == '__main__':
    app.run(debug=True)  # Use app.run instead of socketio.run
