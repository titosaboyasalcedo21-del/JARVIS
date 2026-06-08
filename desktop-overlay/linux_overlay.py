#!/usr/bin/env python3
import argparse
import os
import platform
import sys
import json
import subprocess

if platform.system() == 'Linux' and 'PYWEBVIEW_GUI' not in os.environ:
    os.environ['PYWEBVIEW_GUI'] = 'qt'

try:
    import webview
except ImportError:
    print("pywebview is required to run the Linux overlay. Install it with: pip install pywebview")
    sys.exit(1)

# STT disabled in the overlay.
# Voice input is handled ONLY by desktop-overlay/voice_client.py (stdin -> /ws/voice).
HAS_VOSK = False


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>JARVIS Overlay</title>
<style>
  html, body {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: transparent;
    user-select: none;
  }
  canvas {
    display: block;
    width: 100%;
    height: 100%;
  }
  #label {
    position: absolute;
    left: 50%;
    bottom: 24px;
    transform: translateX(-50%);
    color: rgba(224, 240, 255, 0.88);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 0.95rem;
    letter-spacing: 0.05em;
    text-shadow: 0 0 16px rgba(0, 0, 0, 0.4);
    pointer-events: none;
    opacity: 0.9;
  }
</style>
</head>
<body>
<canvas id="orb"></canvas>
<div id="label">JARVIS</div>
<script type="importmap">
{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"}}
</script>
<script type="module">
import * as THREE from 'three';

const wsUrl = '__WS_URL__';
let state = 'listening';

const canvas = document.getElementById('orb');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x000000, 0);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 1200);
camera.position.z = 80;

const N = 1500;
const positions = new Float32Array(N * 3);
const phases = new Float32Array(N);
for (let i = 0; i < N; i++) {
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  const r = Math.pow(Math.random(), 0.5) * 18;
  positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
  positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
  positions[i * 3 + 2] = r * Math.cos(phi);
  phases[i] = Math.random() * 1000;
}

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
const mat = new THREE.PointsMaterial({ color: 0x4ca8e8, size: 0.4, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending, depthWrite: false });
const points = new THREE.Points(geo, mat);
scene.add(points);

const lineCount = 5000;
const linePositions = new Float32Array(lineCount * 6);
const lineGeo = new THREE.BufferGeometry();
lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
lineGeo.setDrawRange(0, 0);
const lineMat = new THREE.LineBasicMaterial({ color: 0x4ca8e8, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false });
const lines = new THREE.LineSegments(lineGeo, lineMat);
scene.add(lines);

let targetRadius = 22;
let currentRadius = 22;
let targetSpeed = 0.2;
let currentSpeed = 0.2;
let targetOpacity = 0.8;
let currentOpacity = 0.8;
let targetLineCount = 0.1;
let currentLineCount = 0.1;
let lastState = 'idle';
let transitionEnergy = 0;
let spinX = 0;
let spinY = 0;
let spinZ = 0;
let cloudZ = 0;
let cloudVel = 0;

function updateState() {
  switch (state) {
    case 'listening':
      targetRadius = 18;
      targetSpeed = 0.35;
      targetOpacity = 0.9;
      targetLineCount = 0.35;
      break;
    case 'thinking':
      targetRadius = 14;
      targetSpeed = 0.5;
      targetOpacity = 1.0;
      targetLineCount = 1.0;
      break;
    case 'speaking':
      targetRadius = 18;
      targetSpeed = 0.25;
      targetOpacity = 0.85;
      targetLineCount = 0.6;
      break;
    default:
      targetRadius = 22;
      targetSpeed = 0.2;
      targetOpacity = 0.75;
      targetLineCount = 0.12;
      break;
  }
}

function animate() {
  requestAnimationFrame(animate);
  const time = performance.now() * 0.001;

  if (state !== lastState) {
    transitionEnergy = 1.0;
    lastState = state;
    updateState();
  }
  transitionEnergy *= 0.97;

  currentRadius += (targetRadius - currentRadius) * 0.03;
  currentSpeed += (targetSpeed - currentSpeed) * 0.03;
  currentOpacity += (targetOpacity - currentOpacity) * 0.03;
  currentLineCount += (targetLineCount - currentLineCount) * 0.03;

  mat.opacity = currentOpacity;
  lineMat.opacity = currentOpacity * 0.12;

  if (transitionEnergy > 0.02) {
    spinX += transitionEnergy * 0.015 * Math.sin(time * 1.7);
    spinY += transitionEnergy * 0.014 * Math.cos(time * 1.5);
    spinZ += transitionEnergy * 0.01 * Math.cos(time * 1.2);
  }

  cloudVel += (Math.sin(time * 0.12) * 10 - cloudZ) * 0.01;
  cloudVel *= 0.92;
  cloudZ += cloudVel;

  points.rotation.set(spinX, spinY, spinZ);
  points.position.z = cloudZ;
  lines.rotation.set(spinX, spinY, spinZ);
  lines.position.z = cloudZ;

  const pos = geo.getAttribute('position');
  const arr = pos.array;
  for (let i = 0; i < N; i++) {
    const idx = i * 3;
    arr[idx] += Math.sin(time * 0.12 + phases[i]) * 0.0007 * currentSpeed;
    arr[idx + 1] += Math.cos(time * 0.14 + phases[i] * 1.1) * 0.0007 * currentSpeed;
    arr[idx + 2] += Math.sin(time * 0.1 + phases[i] * 0.9) * 0.0007 * currentSpeed;
  }
  pos.needsUpdate = true;

  const positions = lineGeo.getAttribute('position');
  const lineArray = positions.array;
  let active = Math.floor(currentLineCount * lineCount);
  if (active > lineCount) active = lineCount;
  let ptr = 0;
  for (let i = 0; i < active; i++) {
    const a = Math.floor(Math.random() * N) * 3;
    const b = Math.floor(Math.random() * N) * 3;
    lineArray[ptr++] = arr[a];
    lineArray[ptr++] = arr[a + 1];
    lineArray[ptr++] = arr[a + 2];
    lineArray[ptr++] = arr[b];
    lineArray[ptr++] = arr[b + 1];
    lineArray[ptr++] = arr[b + 2];
  }
  lineGeo.setDrawRange(0, active * 2);
  positions.needsUpdate = true;

  renderer.render(scene, camera);
}

function resize() {
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
}

window.addEventListener('resize', resize);
window.addEventListener('click', () => window.close());

function connectSocket() {
   if (!wsUrl) return;
   try {
     const socket = new WebSocket(wsUrl);
     socket.onopen = () => {
       console.log('JARVIS overlay connected');
     };
     socket.onmessage = (e) => {
       try {
         const msg = JSON.parse(e.data);
         if (msg.type === 'status' && msg.state) {
           state = msg.state;
         }
        } catch (err) {
         console.warn('Invalid overlay ws message', err);
       }
     };
     socket.onclose = () => setTimeout(connectSocket, 2000);
     socket.onerror = () => {};
   } catch (err) {
     console.warn('Overlay socket failed', err);
     setTimeout(connectSocket, 3000);
   }
}

connectSocket();
resize();
animate();
</script>
</body>
</html>
"""


def build_html(ws_url: str) -> str:
    return HTML_TEMPLATE.replace('__WS_URL__', ws_url)


def speak_text(text: str):
    """Speak using festival/espeak (offline)."""
    try:
        subprocess.run(['festival', '--tts'], input=text.encode(), check=True)
    except:
        try:
            subprocess.run(['espeak-ng', '-v', 'en-us', '-s', '150', text], check=True)
        except:
            print(f"JARVIS: {text}")


def main() -> int:
    parser = argparse.ArgumentParser(description='JARVIS Linux overlay')
    parser.add_argument('--host', default='127.0.0.1', help='JARVIS server host')
    parser.add_argument('--port', type=int, default=8340, help='JARVIS server port')
    parser.add_argument('--ssl', action='store_true', help='Use secure WebSocket (wss)')
    parser.add_argument('--width', type=int, default=520, help='Overlay width')
    parser.add_argument('--height', type=int, default=520, help='Overlay height')
    args = parser.parse_args()

    if platform.system() != 'Linux':
        print('This overlay helper is designed for Linux desktop environments.')

    scheme = 'wss' if args.ssl else 'ws'
    ws_url = f'{scheme}://{args.host}:{args.port}/ws/voice'
    html = build_html(ws_url)

    window = webview.create_window(
        'JARVIS',
        html=html,
        width=args.width,
        height=args.height,
        frameless=True,
        transparent=True,
        resizable=False,
        on_top=True,
    )

    # Voice recognition intentionally disabled here.
    # The overlay must NEVER access microphone nor run Vosk.

    # Expose speak to JS (optional). Some pywebview builds require a callable.
    try:
        if callable(speak_text):
            window.expose(speak_text, 'speak')
    except TypeError:
        pass

    window.events.closed += lambda: None
    
    webview.start(debug=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
