#!/usr/bin/env python3
"""
JARVIS Voice Client - Simple text input with TTS output.
"""
import asyncio
import json
import sys
import os
import ssl

SERVER_PORT = 8000


def speak_text(text: str):
    """Speak text using espeak (offline, reliable)."""
    import subprocess
    try:
        subprocess.run(['espeak-ng', '-v', 'en-us', '-s', '150', '-p', '30', '-a', '40', text],
                      check=True, capture_output=True)
    except Exception:
        print(f"JARVIS: {text}")


async def voice_loop():
    """Main loop: send text to server, speak response."""
    import websockets
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    uri = f"wss://localhost:{SERVER_PORT}/ws/voice"
    
    print("JARVIS client connected. Type your message and press Enter...")
    
    async with websockets.connect(uri, ssl=ssl_context) as ws:
        # Get greeting
        async def listen_for_responses():
            async for msg in ws:
                data = json.loads(msg)
                if data.get('type') == 'audio' and data.get('text'):
                    speak_text(data['text'])
                elif data.get('type') == 'text' and data.get('text'):
                    speak_text(data['text'])
        
        # Send text from stdin
        loop = asyncio.get_event_loop()
        response_task = asyncio.create_task(listen_for_responses())
        
        while True:
            try:
                text = await loop.run_in_executor(None, sys.stdin.readline)
                if not text:
                    continue
                text = text.strip()
                if text.lower() in ('exit', 'quit', 'salir'):
                    break
                if text:
                    await ws.send(json.dumps({"type": "transcript", "text": text, "isFinal": True}))
                    print(f"You: {text}")
            except KeyboardInterrupt:
                break
        
        response_task.cancel()


if __name__ == '__main__':
    asyncio.run(voice_loop())