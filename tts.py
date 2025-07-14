import threading
import tempfile
import os
import wave
import soundfile as sf
import sounddevice as sd
from piper import PiperVoice

# Load voice once
voice = PiperVoice.load("/home/gamer/Jarvis-Assistant-Project/voices/jarvis-medium.onnx")

def speak(text):
    def run():
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            path = f.name

        # 🛠 Properly open as wave file for Piper
        with wave.open(path, 'wb') as wf:
            voice.synthesize(text, wav_file=wf)

        # ✅ Read back and play
        data, samplerate = sf.read(path)
        sd.play(data, samplerate=samplerate)
        sd.wait()
        os.remove(path)

    threading.Thread(target=run).start()

