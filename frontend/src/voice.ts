/**
 * Voice input (Web Speech API) and audio output (AudioContext) for JARVIS.
 */

// ---------------------------------------------------------------------------
// Speech Recognition
// ---------------------------------------------------------------------------

export interface VoiceInput {
  start(): void;
  stop(): void;
  pause(): void;
  resume(): void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const webkitSpeechRecognition: any;

export function createVoiceInput(
  onTranscript: (text: string) => void,
  onThinking: () => void,
  onError: (msg: string) => void
): VoiceInput {
  let shouldListen = false;
  let paused = false;
  
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let isRecording = false;
  let silenceTimer: any = null;
  let audioCtx: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let dataArray: Uint8Array;
  let animFrameId: number;

  function initAudio() {
    try {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };
        
        mediaRecorder.onstop = async () => {
          if (audioChunks.length === 0) {
             if (shouldListen && !paused) mediaRecorder?.start();
             return;
          }
          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          audioChunks = [];
          
          // Restart recording immediately to catch the next command
          if (shouldListen && !paused) {
             mediaRecorder?.start();
          }
          
          // If we stopped because of silence, and we had speech, send it
          if (hasSpoken) {
            hasSpoken = false;
            onThinking();
            
            try {
              const formData = new FormData();
              formData.append("file", blob, "audio.webm");
              const res = await fetch("/api/transcribe", { method: "POST", body: formData });
              const data = await res.json();
              if (data.text && data.text.trim()) {
                onTranscript(data.text);
              }
            } catch(e) {
              console.error("Whisper error:", e);
            }
          }
        };

        audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        
        checkVolume();
      }).catch(e => {
        onError("Microphone access denied.");
      });
    } catch (e) {
      onError("Microphone access denied.");
    }
  }

  let hasSpoken = false;

  function checkVolume() {
    if (!analyser) {
      animFrameId = requestAnimationFrame(checkVolume);
      return;
    }
    
    if (shouldListen && !paused) {
      if (mediaRecorder && mediaRecorder.state === "inactive") {
         mediaRecorder.start();
      }
      
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
      const average = sum / dataArray.length;
      
      // A very low threshold just to detect if ANY speech happened in this chunk
      if (average > 5) {
        hasSpoken = true;
        if (silenceTimer) clearTimeout(silenceTimer);
        
        silenceTimer = setTimeout(() => {
          if (mediaRecorder && mediaRecorder.state === "recording") {
            console.log("[voice] VAD: Silence flush");
            mediaRecorder.stop(); // This triggers onstop, which flushes and sends
          }
        }, 1500); // 1.5s of silence triggers the send
      }
    }
    
    animFrameId = requestAnimationFrame(checkVolume);
  }

  initAudio();

  return {
    start() {
      shouldListen = true;
      paused = false;
      if (mediaRecorder && mediaRecorder.state === "inactive") {
        mediaRecorder.start();
      }
    },
    stop() {
      shouldListen = false;
      paused = false;
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
      if (animFrameId) cancelAnimationFrame(animFrameId);
    },
    pause() {
      paused = true;
      if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      }
    },
    resume() {
      paused = false;
      if (shouldListen && mediaRecorder && mediaRecorder.state === "inactive") {
        mediaRecorder.start();
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Audio Player
// ---------------------------------------------------------------------------

export interface AudioPlayer {
  enqueue(base64: string): Promise<void>;
  speakText(text: string): void;
  stop(): void;
  getAnalyser(): AnalyserNode;
  onFinished(cb: () => void): void;
}

export function createAudioPlayer(): AudioPlayer {
  const audioCtx = new AudioContext();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.8;
  analyser.connect(audioCtx.destination);

  const queue: AudioBuffer[] = [];
  let isPlaying = false;
  let currentSource: AudioBufferSourceNode | null = null;
  let finishedCallback: (() => void) | null = null;

  function playNext() {
    if (queue.length === 0) {
      isPlaying = false;
      currentSource = null;
      finishedCallback?.();
      return;
    }

    isPlaying = true;
    const buffer = queue.shift()!;
    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(analyser);
    currentSource = source;

    source.onended = () => {
      if (currentSource === source) {
        playNext();
      }
    };

    source.start();
  }

  return {
    async enqueue(base64: string) {
      if (audioCtx.state === "suspended") await audioCtx.resume();
      try {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
        queue.push(audioBuffer);
        if (!isPlaying) playNext();
      } catch (err) {
        console.error("[audio] decode error:", err);
        if (!isPlaying && queue.length > 0) playNext();
      }
    },

    speakText(text: string) {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
// Idioma configurable: por defecto español.
      // Se espera que el frontend lea STT_LANGUAGE del servidor en el futuro; por ahora, usamos el idioma del navegador si el usuario lo configura.
      utterance.lang = "es-ES"; // (mantener comportamiento actual si no hay config)

      utterance.rate = 1.0;
      utterance.onstart = () => { isPlaying = true; };
      utterance.onend = () => { isPlaying = false; finishedCallback?.(); };
      window.speechSynthesis.speak(utterance);
    },

    stop() {
      queue.length = 0;
      window.speechSynthesis?.cancel();
      if (currentSource) {
        try { currentSource.stop(); } catch {}
        currentSource = null;
      }
      isPlaying = false;
    },

    getAnalyser() {
      return analyser;
    },

    onFinished(cb: () => void) {
      finishedCallback = cb;
    },
  };
}
