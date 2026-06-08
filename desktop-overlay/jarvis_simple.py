#!/usr/bin/env python3
"""
JARVIS Integrated Overlay - Visual orb + voice input/output.
"""
import asyncio
import json
import os
import platform
import subprocess
import sys
import threading

if platform.system() == 'Linux' and 'PYWEBVIEW_GUI' not in os.environ:
    os.environ['PYWEBVIEW_GUI'] = 'qt'

import webview
from vosk import Model, KaldiRecognizer
import sounddevice as sd
import numpy as np

SERVER_PORT = 8340
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'vosk-model-small-es-0.42')

def speak_text(text: str):
    try:
        subprocess.run(['festival', '--tts'], input=text.encode(), check=True)
    except:
        subprocess.run(['espeak-ng', '-v', 'en-us', '-s', '150', text], check=True)


async def run_jarvis():
    if not os.path.exists(MODEL_PATH):
        return
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(True)
    
    import websockets
    uri = f"ws://localhost:{SERVER_PORT}/ws/voice"
    print("JARVIS listening...")
    
    async with websockets.connect(uri) as ws:
        audio_queue = asyncio.Queue()
        def callback(indata, frames, time, status):
            if not status:
                audio_queue.put_nowait(indata.copy())
        
        last_text = ""
        with sd.InputStream(samplerate=16000, channels=1, callback=callback):
            while True:
                # Handle audio
                data = await audio_queue.get()
                audio_data = (data[:, 0] * 32767).astype('int16').tobytes()
                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    text = result.get('text', '').strip()
                    if text and text != last_text:
                        last_text = text
                        await ws.send(json.dumps({"type": "transcript", "text": text, "isFinal": True}))
                        print(f"You: {text}")
                
                # Handle responses
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0)
                except asyncio.TimeoutError:
                    msg = None
                    
                if msg:
                    data = json.loads(msg)
                    if (data.get('type') in ('audio', 'text')) and data.get('text'):
                        speak_text(data['text'])


HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><title>JARVIS</title>
<style>html,body{width:100%;height:100%;margin:0;padding:0;overflow:hidden;background:transparent}
canvas{display:block;width:100%;height:100%}#label{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);color:rgba(224,240,255,.88);font-family:sans-serif;font-size:.95rem;opacity:.9;pointer-events:none}</style></head>
<body><canvas id="orb"></canvas><div id="label">JARVIS</div>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
let state='listening',canvas=document.getElementById('orb'),renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
renderer.setPixelRatio(devicePixelRatio);renderer.setSize(innerWidth,innerHeight);renderer.setClearColor(0x000000,0);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,1,1200);camera.position.z=80;
const N=1500,positions=new Float32Array(N*3),phases=new Float32Array(N);
for(let i=0;i<N;i++){const t=Math.random()*Math.PI*2,p=Math.acos(2*Math.random()-1),r=Math.pow(Math.random(),.5)*18;positions[i*3]=r*Math.sin(p)*Math.cos(t);positions[i*3+1]=r*Math.sin(p)*Math.sin(t);positions[i*3+2]=r*Math.cos(p);phases[i]=Math.random()*1000}
const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(positions,3));
const mat=new THREE.PointsMaterial({color:0x4ca8e8,size:.4,transparent:true,opacity:.8,blending:THREE.AdditiveBlending});
const points=new THREE.Points(geo,mat);scene.add(points);
let targetRadius=22,currentRadius=22,targetSpeed=.2,currentSpeed=.2,targetOpacity=.8,currentOpacity=.8,targetLineCount=.1,currentLineCount=.1,lastState='idle',transitionEnergy=0,spinX=0,spinY=0,spinZ=0;
function updateState(){switch(state){case'thinking':targetRadius=14;targetSpeed=.5;targetOpacity=1;targetLineCount=1;break;case'speaking':targetRadius=18;targetSpeed=.25;targetOpacity=.85;targetLineCount=.6;break;default:targetRadius=22;targetSpeed=.2;targetOpacity=.75;targetLineCount=.12;break}}
function animate(){requestAnimationFrame(animate);const time=performance.now()*.001;if(state!==lastState){transitionEnergy=1;lastState=state;updateState()}transitionEnergy*=.97;currentRadius+=(targetRadius-currentRadius)*.03;currentSpeed+=(targetSpeed-currentSpeed)*.03;currentOpacity+=(targetOpacity-currentOpacity)*.03;currentLineCount+=(targetLineCount-currentLineCount)*.03;mat.opacity=currentOpacity;if(transitionEnergy>.02){spinX+=transitionEnergy*.015*Math.sin(time*1.7);spinY+=transitionEnergy*.014*Math.cos(time*1.5);spinZ+=transitionEnergy*.01*Math.cos(time*1.2)}points.rotation.set(spinX,spinY,spinZ);const pos=geo.getAttribute('position'),arr=pos.array;for(let i=0;i<N;i++){const idx=i*3;arr[idx]+=Math.sin(time*.12+phases[i])*.0007*currentSpeed;arr[idx+1]+=Math.cos(time*.14+phases[i]*1.1)*.0007*currentSpeed;arr[idx+2]+=Math.sin(time*.1+phases[i]*.9)*.0007*currentSpeed}pos.needsUpdate=true;renderer.render(scene,camera)}
window.addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight)});
window.addEventListener('click',()=>{window.close()}); connectSocket(); animate();
function connectSocket(){const socket=new WebSocket('ws://localhost:8340/ws/voice');socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='status'&&m.state)state=m.state};socket.onclose=()=>setTimeout(connectSocket,2000)}
</script></body></html>"""


def main():
    threading.Thread(target=lambda: asyncio.run(run_jarvis()), daemon=True).start()
    webview.create_window('JARVIS', html=HTML, width=520, height=520, frameless=True, transparent=True, on_top=True)
    webview.start()

if __name__ == '__main__':
    main()