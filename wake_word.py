#!/usr/bin/env python3
"""
Porcupine wake word detection for JARVIS.
Listens for "JARVIS" or "Hey JARVIS" and triggers on detection.
"""

import os
import sys
import struct
import pyaudio
import pvporcupine
from pathlib import Path

WAKE_KEYWORDS = ["jarvis", "hey jarvis"]
DEFAULT_SENSITIVITY = 0.6

def _get_picovoice_key() -> str | None:
    key = os.environ.get("PICOVOICE_KEY")
    if not key:
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("PICOVOICE_KEY="):
                    key = line.partition("=")[2].strip()
                    break
    return key

async def listen_for_wake_word(callback, keyword: str = "jarvis", sensitivity: float = DEFAULT_SENSITIVITY):
    """
    Listen for wake word and call the callback when detected.
    
    Args:
        callback: Async function to call when wake word is detected
        keyword: Wake word to listen for (jarvis or hey jarvis)
        sensitivity: Detection sensitivity (0.0 to 1.0)
    """
    api_key = _get_picovoice_key()
    if not api_key:
        print("PICOVOICE_KEY not set, wake word disabled", file=sys.stderr)
        return
    
    porcupine = None
    pa = None
    
    try:
        porcupine = pvporcupine.create(keywords=[keyword], sensitivities=[sensitivity], access_key=api_key)
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )
        
        print(f"Listening for '{keyword}'...", file=sys.stderr)
        
        while True:
            pcm = audio_stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            if porcupine.process(pcm) >= 0:
                print("Wake word detected!", file=sys.stderr)
                await callback()
                
    except KeyboardInterrupt:
        pass
    finally:
        if porcupine:
            porcupine.delete()
        if pa:
            pa.terminate()

if __name__ == "__main__":
    import asyncio
    
    async def test_callback():
        print("Wake word triggered!")
    
    asyncio.run(listen_for_wake_word(test_callback))