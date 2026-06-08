#!/usr/bin/env python3
"""
JARVIS Integrated Overlay - Visual orb + voice input/output.
Uses subprocess for TTS (espeak/festival) and vosk for STT.
"""
import argparse
import os
import platform
import sys
import json
import subprocess
import threading
import asyncio

if platform.system() == 'Linux' and 'PYWEBVIEW_GUI' not in os.environ:
    os.environ['PYWEBVIEW_GUI'] = 'qt'

try:
    import webview
except ImportError:
    print("pywebview required: pip install pywebview")
    sys.exit(1)

try:
    from vosk import Model, KaldiRecognizer
    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

SERVER_PORT = 8340
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'vosk-model-small-es-0.42')
RATE = 16000


def speak_text(text: str):
    """Speak using espeak/festival (offline)."""
    try:
        subprocess.run(['festival', '--tts'], input=text.encode(), check=True, capture_output=True)
        return
    except:
        pass
    try:
        subprocess.run(['espeak-ng', '-v', 'en-us', '-s', '150', text], check=True, capture_output=True)
    except:
        print(f"JARVIS: {text}")


async def voice_loop():
    """Main voice loop - listen and respond."""
    if not HAS_VOSK or not HAS_AUDIO:
        return
    if not os.path.exists(MODEL_PATH):
        return
        
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, RATE)
    recognizer.SetWords(True)
    
    import websockets
    uri = f"ws://localhost:{SERVER_PORT}/ws/voice"
    print("Listening...")
    
    async with websockets.connect(uri) as ws:
        audio_queue = asyncio.Queue()
        def callback(indata, frames, time, status):
            if not status:
                audio_queue.put_nowait(indata.copy())
        
        last_text = ""
        with sd.InputStream(samplerate=RATE, channels=1, callback=callback):
            while True:
                data = await audio_queue.get()
                audio_data = (data[:, 0] * 32767).astype('int16').tobytes()
                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    text = result.get('text', '').strip()
                    if text and text != last_text:
                        last_text = text
                        await ws.send(json.dumps({"type": "transcript", "text": text, "isFinal": True}))
                        print(f"You: {text}")
                # Listen for responses and speak them
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.01)
                    data = json.loads(msg)
                    if (data.get('type') in ('audio', 'text')) and data.get('text'):
                        speak_text(data['text'])
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(0.01)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" /><title>JARVIS</title>
<style>html,body{width:100%;height:100%;margin:0;padding:0;overflow:hidden;background:transparent}canvas{display:block;width:100%;height:100%}#label{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);color:rgba(224,240,255,.88);font-family:sans-serif;font-size:.95rem;opacity:.9;pointer-events:none}</style>
</head>
<body><canvas id="orb"></canvas><div id="label">JARVIS</div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
const wsUrl = '__WS_URL__';
let state = 'listening';
const canvas = document.getElementById('orb');
const renderer = new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
renderer.setPixelRatio(window.devicePixelRatio);renderer.setSize(innerWidth,innerHeight);renderer.setClearColor(0x000000,0);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45,innerWidth/innerHeight,1,1200);camera.position.z=80;
const N=1500,positions=new Float32Array(N*3),phases=new Float32Array(N);
for(let i=0;i<N;i++){const theta=Math.random()*Math.PI*2,phi=Math.acos(2*Math.random()-1),r=Math.pow(Math.random(),.5)*18;positions[i*3]=r*Math.sin(phi)*Math.cos(theta);positions[i*3+1]=r*Math.sin(phi)*Math.sin(theta);positions[i*3+2]=r*Math.cos(phi);phases[i]=Math.random()*1000}
const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(positions,3));
const mat=new THREE.PointsMaterial({color:0x4ca8e8,size:.4,transparent:true,opacity:.8,blending:THREE.AdditiveBlending,depthWrite:false});
const points=new THREE.Points(geo,mat);scene.add(points);
let targetRadius=22,currentRadius=22,targetSpeed=.2,currentSpeed=.2;
let targetOpacity=.8,currentOpacity=.8,targetLineCount=.1,currentLineCount=.1;
let lastState='idle',transitionEnergy=0,spinX=0,spinY=0,spinZ=0;
function updateState(){switch(state){case'thinking':targetRadius=14;targetSpeed=.5;targetOpacity=1;targetLineCount=1;break;case'speaking':targetRadius=18;targetSpeed=.25;targetOpacity=.85;targetLineCount=.6;break;default:targetRadius=22;targetSpeed=.2;targetOpacity=.75;targetLineCount=.12;break}}
function animate(){requestAnimationFrame(animate);const time=performance.now()*.001;if(state!==lastState){transitionEnergy=1;lastState=state;updateState()}transitionEnergy*=.97;currentRadius+=(targetRadius-currentRadius)*.03;currentSpeed+=(targetSpeed-currentSpeed)*.03;currentOpacity+=(targetOpacity-currentOpacity)*.03;currentLineCount+=(targetLineCount-currentLineCount)*.03;mat.opacity=currentOpacity;if(transitionEnergy>.02){spinX+=transitionEnergy*.015*Math.sin(time*1.7);spinY+=transitionEnergy*.014*Math.cos(time*1.5);spinZ+=transitionEnergy*.01*Math.cos(time*1.2)}points.rotation.set(spinX,spinY,spinZ);const pos=geo.getAttribute('position'),arr=pos.array;for(let i=0;i<N;i+=10){const idx=i*3,arr2=arr;arr2[idx]+=Math.sin(time*.12+phases[i])*.0007*currentSpeed;arr2[idx+1]+=Math.cos(time*.14+phases[i]*1.1)*.0007*currentSpeed;arr2[idx+2]+=Math.sin(time*.1+phases[i]*.9)*.0007*currentSpeed}pos.needsUpdate=true;renderer.render(scene,camera)}
window.addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight)});
window.addEventListener('click',()=>{window.close()});
function connectSocket(){if(!wsUrl)return;try{const socket=new WebSocket(wsUrl);socket.onmessage=e=>{const msg=JSON.parse(e.data);if(msg.type==='status'&&msg.state)state=msg.state;if((msg.type==='audio'||msg.type==='text')&&msg.text){if(window.speechSynthesis){window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(msg.text);u.lang='en-US';u.rate=.95;window.speechSynthesis.speak(u)}}};socket.onclose=()=>setTimeout(connectSocket,2000);socket.onerror=()=>{};console.log('WebSocket connected to '+wsUrl)}catch(err){setTimeout(connectSocket,3000)} }
connectSocket();animate();
</script></body></html>
"""


def create_js_api():
    """Create JS API methods for webview."""
    class VoiceAPI:
        def speak(self, text):
            speak_text(text)
    return VoiceAPI()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8340)
    args = parser.parse_args()
    
    ws_url = f'ws://{args.host}:{args.port}/ws/voice'
    html = HTML_TEMPLATE.replace('__WS_URL__', ws_url)
    
    def start_voice_thread():
        if not HAS_VOSK or not HAS_AUDIO:
            print("Missing vosk/sounddevice")
            return
        if not os.path.exists(MODEL_PATH):
            print(f"Model missing: {MODEL_PATH}")
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(voice_loop())
    
    # Start voice in background thread
    threading.Thread(target=start_voice_thread, daemon=True).start()
    
    window = webview.create_window('JARVIS', html=html, width=520, height=520,
                                   frameless=True, transparent=True, on_top=True)
    window.expose(speak_text)  # Expose speak_text as JS callable
    webview.start()


if __name__ == '__main__':
    main()