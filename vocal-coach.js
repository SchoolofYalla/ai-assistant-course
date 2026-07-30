/**
 * School of Yalla - Custom Arabic Vocal Coach Frontend Client Module (Python API)
 * 
 * Plugs directly into standard HTML pages (e.g., Day-1, Day-2, Day-3-Pronouns index.html).
 * Connects the yellow push-to-talk call button (#vapi-icon-slot) to the Python FastAPI backend.
 */

(function (window, document) {
  'use strict';

  class VocalCoachClient {
    /**
     * @param {Object} config 
     * @param {string} [config.serverUrl="ws://localhost:8000"] - WebSocket backend URL base
     * @param {string} [config.dayId="day_1_greetings"] - ID of the vocabulary set to load
     * @param {string} [config.buttonSlotId="vapi-icon-slot"] - ID of the container slot for the yellow button
     * @param {string} [config.transcriptContainerId="transcript-container"] - ID of chat transcript container
     */
    constructor(config = {}) {
      this.serverUrl = config.serverUrl || 'ws://localhost:8000';
      this.dayId = config.dayId || 'day_1_greetings';
      this.buttonSlotId = config.buttonSlotId || 'vapi-icon-slot';
      this.transcriptContainerId = config.transcriptContainerId || 'transcript-container';

      this.ws = null;
      this.mediaRecorder = null;
      this.audioStream = null;
      this.isRecording = false;

      // Audio Playback Queue
      this.audioQueue = [];
      this.isPlayingAudio = false;
      this.currentAudioPlayer = new Audio();

      // UI States: 'disconnected', 'connected', 'playing_intro', 'listening', 'evaluating'
      this.state = 'disconnected';

      this.initUI();
    }

    /**
     * Creates and injects the yellow call button into the HTML page slot.
     */
    initUI() {
      const slot = document.getElementById(this.buttonSlotId);
      if (!slot) {
        console.warn(`[VocalCoach] Slot #${this.buttonSlotId} not found in DOM.`);
        return;
      }

      slot.innerHTML = `
        <div class="vocal-coach-wrapper">
          <div class="pulse-ring ring-1"></div>
          <div class="pulse-ring ring-2"></div>
          <button id="yalla-call-btn" class="yalla-call-btn idle" title="Start Vocal Coach Call">
            <svg class="phone-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/>
            </svg>
            <span id="call-btn-label" class="btn-label">TAP TO CALL</span>
          </button>
        </div>
      `;

      this.injectStyles();

      this.button = document.getElementById('yalla-call-btn');
      this.buttonLabel = document.getElementById('call-btn-label');

      this.button.addEventListener('click', () => this.handleButtonClick());
    }

    injectStyles() {
      if (document.getElementById('vocal-coach-styles')) return;

      const style = document.createElement('style');
      style.id = 'vocal-coach-styles';
      style.textContent = `
        .vocal-coach-wrapper { position: relative; display: flex; align-items: center; justify-content: center; margin: 1.5rem auto; }
        .yalla-call-btn { position: relative; z-index: 2; width: 80px; height: 80px; border-radius: 50%; background: #ffcc00; border: 3px solid #ffffff; box-shadow: 0 8px 25px rgba(255, 204, 0, 0.4); cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #000000; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .yalla-call-btn:hover { transform: scale(1.08); box-shadow: 0 12px 30px rgba(255, 204, 0, 0.6); }
        .yalla-call-btn .phone-icon { width: 28px; height: 28px; margin-bottom: 2px; }
        .yalla-call-btn .btn-label { font-size: 0.6rem; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase; }
        .vocal-coach-wrapper .pulse-ring { position: absolute; width: 80px; height: 80px; border-radius: 50%; background: rgba(255, 204, 0, 0.3); z-index: 1; opacity: 0; pointer-events: none; }
        .yalla-call-btn.active ~ .ring-1, .yalla-call-btn.listening ~ .ring-1 { animation: pulseRing 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite; }
        .yalla-call-btn.listening { background: #ef4444; color: #ffffff; box-shadow: 0 8px 25px rgba(239, 68, 68, 0.5); }
        @keyframes pulseRing { 0% { transform: scale(0.95); opacity: 0.8; } 50% { transform: scale(1.5); opacity: 0.4; } 100% { transform: scale(1.9); opacity: 0; } }
        .transcript-bubble { margin: 0.5rem 0; padding: 0.8rem 1.2rem; border-radius: 16px; max-width: 85%; font-size: 0.95rem; line-height: 1.4; animation: fadeIn 0.3s ease; }
        .transcript-bubble.ai { background: #1e293b; color: #f8fafc; border-left: 4px solid #ffcc00; align-self: flex-start; }
        .transcript-bubble.user { background: #38bdf8; color: #0f172a; font-weight: 600; align-self: flex-end; margin-left: auto; }
        .transcript-bubble .arabic-target { font-size: 1.4rem; font-weight: 700; color: #ffcc00; display: block; margin-top: 0.3rem; direction: rtl; }
        .typing-indicator { display: flex; align-items: center; gap: 4px; padding: 0.2rem 0.5rem; }
        .typing-indicator span { width: 8px; height: 8px; background: #ffcc00; border-radius: 50%; animation: typing 1.4s infinite both; }
        .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        @keyframes typing { 0%, 80%, 100% { transform: scale(0); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
      `;
      document.head.appendChild(style);
    }

    async handleButtonClick() {
      if (this.state === 'disconnected') {
        this.connectWebSocket();
      } else if (this.state === 'listening') {
        this.stopMicrophone();
      }
    }

    connectWebSocket() {
      this.updateStatus('Connecting to Vocal Coach...');
      const fullUrl = `${this.serverUrl}/ws/practice/${this.dayId}`;
      this.ws = new WebSocket(fullUrl);

      this.ws.onopen = () => {
        console.log('[VocalCoach] Connected to WebSocket backend.');
        this.state = 'connected';
        this.button.classList.add('active');
        this.buttonLabel.textContent = 'CONNECTED';
      };

      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        this.handleServerMessage(msg);
      };

      this.ws.onerror = (err) => {
        console.error('[VocalCoach] WebSocket Error:', err);
        this.updateStatus('Connection Error. Is backend running?');
        this.state = 'disconnected';
      };

      this.ws.onclose = () => {
        console.log('[VocalCoach] Disconnected from server.');
        this.state = 'disconnected';
        this.button.classList.remove('active', 'listening');
        this.buttonLabel.textContent = 'TAP TO CALL';
        this.updateStatus('Disconnected.');
        this.cleanupSession(); // Release mic and AudioContext now that session is over
      };
    }

    handleServerMessage(msg) {
      console.log('[VocalCoach Event]:', msg.type, msg);

      switch (msg.type) {
        case 'session_started':
          this.updateStatus('Session started. Preparing audio...');
          break;

        case 'status':
          this.updateStatus(msg.statusText);
          // Show visual loading hint on button when processing between words
          if (msg.statusText.includes('Synthesizing') || msg.statusText.includes('Evaluating') || msg.statusText.includes('Preparing')) {
            this.buttonLabel.textContent = 'LOADING...';
            this.button.classList.remove('listening');
          }
          break;

        case 'keepalive':
          // Server ping to keep connection alive during long Azure API calls — just update status
          this.updateStatus(msg.statusText || 'Processing...');
          this.buttonLabel.textContent = 'LOADING...';
          break;

        case 'instruction_audio':
          this.addChatBubble('ai', msg.text);
          this.buttonLabel.textContent = 'CONNECTED';
          this.enqueueAudio(msg.audioBase64);
          break;

        case 'target_audio':
          this.addChatBubble('ai', `Repeat after me:`, msg.text, msg.transliteration);
          this.enqueueAudio(msg.audioBase64);
          break;

        case 'prompt_user_speech':
          this.onAudioQueueEmpty = () => {
            this.startMicrophone();
          };
          // If audio queue is already empty (e.g. audio was blocked), open mic immediately
          if (!this.isPlayingAudio && this.audioQueue.length === 0) {
            this.onAudioQueueEmpty();
            this.onAudioQueueEmpty = null;
          }
          break;

        case 'feedback_stream_start': {
          this.hideTypingIndicator();
          const feedbackIcon = msg.passed ? '✅' : '💡';
          if (msg.studentTranscription) {
            this.addChatBubble('user', msg.studentTranscription);
          }
          const bubble = this.addChatBubble('ai', `${feedbackIcon} `);
          this.currentStreamBubbleText = bubble.querySelector('.text');
          this.pcmStreamActive = true;
          this.initPCMPlayer();
          break;
        }

        case 'feedback_text_chunk':
          if (this.currentStreamBubbleText) {
            this.currentStreamBubbleText.innerHTML += msg.text;
          }
          break;

        case 'audio_stream_chunk':
          this.enqueuePCMChunk(msg.audioBase64);
          break;

        case 'evaluation_complete':
          // Signal the end of the PCM stream ONLY if we actually started a PCM stream
          if (this.pcmStreamActive && this.pcmContext) {
            this.pcmEnded = true;
            // If the time is already past or we received no chunks, force next
            if (this.pcmContext.currentTime >= this.nextPcmTime) {
              this.isPlayingAudio = false;
              this.playNextAudio();
            }
            this.pcmStreamActive = false;
          }
          break;

        case 'audio_stream_complete_b64': {
          // Used by Fast-Match fallback and Quota exceeded fallback
          this.pcmStreamActive = false; // Cancel PCM stream expectations
          this.enqueueAudio(msg.audioBase64);
          break;
        }

        case 'feedback_audio': {
          // Legacy support
          this.hideTypingIndicator();
          const feedbackIcon = msg.passed ? '✅' : '💡';
          if (msg.studentTranscription) {
            this.addChatBubble('user', msg.studentTranscription);
          }
          this.addChatBubble('ai', `${feedbackIcon} ${msg.text}`);
          this.enqueueAudio(msg.audioBase64);
          break;
        }

        case 'lesson_complete':
          this.addChatBubble('ai', `🎉 ${msg.text}`);
          this.enqueueAudio(msg.audioBase64);
          this.cleanupSession(); // Lesson done — release mic and AudioContext
          break;

        case 'error':
          this.updateStatus(`Error: ${msg.message}`);
          break;
      }
    }

    enqueueAudio(audioBase64) {
      if (!audioBase64) return;
      this.audioQueue.push(`data:audio/mp3;base64,${audioBase64}`);
      if (!this.isPlayingAudio) {
        this.playNextAudio();
      }
    }

    playNextAudio() {
      if (this.audioQueue.length === 0) {
        this.isPlayingAudio = false;
        if (typeof this.onAudioQueueEmpty === 'function') {
          const callback = this.onAudioQueueEmpty;
          this.onAudioQueueEmpty = null;
          callback();
        }
        return;
      }

      this.isPlayingAudio = true;
      const audioSrc = this.audioQueue.shift();
      this.currentAudioPlayer.src = audioSrc;
      this.currentAudioPlayer.play().catch(e => {
        console.warn('Audio play error:', e);
        // If audio fails to play (e.g. browser policy), force the queue to continue
        this.playNextAudio();
      });

      this.currentAudioPlayer.onended = () => {
        this.playNextAudio();
      };
    }

    initPCMPlayer() {
      this.isPlayingAudio = true; // Lock the standard queue
      this.pcmEnded = false;
      if (!this.pcmContext) {
        this.pcmContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      }
      if (this.pcmContext.state === 'suspended') {
        this.pcmContext.resume();
      }
      this.nextPcmTime = this.pcmContext.currentTime;
    }

    enqueuePCMChunk(base64) {
      if (!this.pcmContext) return;

      const binary = atob(base64);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);

      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      const audioBuffer = this.pcmContext.createBuffer(1, float32Array.length, 16000);
      audioBuffer.getChannelData(0).set(float32Array);

      const source = this.pcmContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.pcmContext.destination);

      if (this.nextPcmTime < this.pcmContext.currentTime) {
        this.nextPcmTime = this.pcmContext.currentTime + 0.05; // 50ms buffer
      }

      source.start(this.nextPcmTime);
      this.nextPcmTime += audioBuffer.duration;

      source.onended = () => {
        if (this.pcmEnded && this.pcmContext.currentTime >= this.nextPcmTime - 0.1) {
          this.isPlayingAudio = false;
          this.playNextAudio();
        }
      };
    }

    async startMicrophone() {
      try {
        // On first call: create the AudioContext and get the mic stream
        // On subsequent calls (next word): reuse existing context and stream
        if (!this.audioStream || this.audioStream.getTracks().every(t => t.readyState === 'ended')) {
          this.audioStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true
            }
          });
          console.log('[VocalCoach] Mic stream opened.');
        }

        if (!this.audioContext || this.audioContext.state === 'closed') {
          this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
          console.log(`[VocalCoach] AudioContext created at ${this.audioContext.sampleRate}Hz`);
        } else if (this.audioContext.state === 'suspended') {
          await this.audioContext.resume();
        }

        // Always create a fresh MediaStreamSource and ScriptProcessor for each word
        this.mediaStreamSource = this.audioContext.createMediaStreamSource(this.audioStream);

        const bufferSize = 4096;
        this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

        this.pcmBuffers = [];
        this.recordingLength = 0;

        // VAD Variables
        this.hasSpoken = false;
        this.silenceStartTime = null;
        this.spokenFrames = 0; // Require a few consecutive loud frames to count as speech (ignore clicks)
        const SILENCE_THRESHOLD = 0.003; // RMS volume threshold (lowered)
        const SILENCE_DURATION_MS = 400; // Stop after 0.4s of silence (ultra-fast stop)

        this.scriptProcessor.onaudioprocess = (e) => {
          if (!this.isRecording) return;
          const inputData = e.inputBuffer.getChannelData(0);
          this.pcmBuffers.push(new Float32Array(inputData));
          this.recordingLength += inputData.length;

          let sumSq = 0;
          for (let i = 0; i < inputData.length; i++) {
            sumSq += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sumSq / inputData.length);

          if (rms > SILENCE_THRESHOLD) {
            this.spokenFrames++;
            if (this.spokenFrames > 5) { // Needs about 5 frames (~400ms) of sustained volume to trigger
              this.hasSpoken = true;
              this.silenceStartTime = null;
            }
          } else {
            this.spokenFrames = 0;
            if (this.hasSpoken) {
              if (!this.silenceStartTime) {
                this.silenceStartTime = Date.now();
              } else if (Date.now() - this.silenceStartTime > SILENCE_DURATION_MS) {
                // User finished speaking, stop immediately!
                this.stopMicrophone();
              }
            }
          }
        };

        this.mediaStreamSource.connect(this.scriptProcessor);
        this.scriptProcessor.connect(this.audioContext.destination);

        this.state = 'listening';
        this.button.classList.add('listening');
        this.buttonLabel.textContent = 'LISTENING...';
        this.updateStatus('🎤 Listening... Speak now!');

        this.isRecording = true;

        // Hard maximum fallback timeout (6 seconds)
        this.inactivityTimer = setTimeout(() => {
          if (this.isRecording) {
            if (!this.hasSpoken) {
              this.cancelMicrophone();
              if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'inactivity_timeout' }));
              }
            } else {
              this.stopMicrophone();
            }
          }
        }, 6000);

      } catch (err) {
        console.error('[VocalCoach] Mic access denied:', err);
        this.updateStatus('Microphone access denied.');
      }
    }

    cancelMicrophone() {
      if (!this.isRecording) return;
      this.isRecording = false;

      if (this.scriptProcessor) {
        this.scriptProcessor.disconnect();
        this.scriptProcessor.onaudioprocess = null;
        this.scriptProcessor = null;
      }
      if (this.mediaStreamSource) {
        this.mediaStreamSource.disconnect();
        this.mediaStreamSource = null;
      }

      this.button.classList.remove('listening');
      this.buttonLabel.textContent = 'START';
      this.updateStatus('Waiting for response...');
    }

    stopMicrophone() {
      if (this.inactivityTimer) clearTimeout(this.inactivityTimer);
      if (!this.isRecording) return;
      this.isRecording = false;

      // Disconnect the ScriptProcessor only — do NOT stop the audio track or close
      // the AudioContext. Killing those resources causes the browser to tear down the
      // entire media session, which also kills our WebSocket connection on Windows/Chrome.
      if (this.scriptProcessor) {
        this.scriptProcessor.disconnect();
        this.scriptProcessor.onaudioprocess = null;
        this.scriptProcessor = null;
      }
      if (this.mediaStreamSource) {
        this.mediaStreamSource.disconnect();
        this.mediaStreamSource = null;
      }
      // NOTE: this.audioStream and this.audioContext are kept ALIVE until cleanupSession().

      this.state = 'evaluating';
      this.button.classList.remove('listening');
      this.buttonLabel.textContent = 'EVALUATING';
      this.updateStatus('Analyzing audio...');
      this.showTypingIndicator();

      // Capture sampleRate before the async send
      const sampleRate = this.audioContext ? this.audioContext.sampleRate : 48000;

      // Convert PCM to WAV and send
      const wavBlob = this.encodeWAV(this.pcmBuffers, this.recordingLength, sampleRate);

      wavBlob.arrayBuffer().then(buffer => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(buffer);
          this.ws.send(JSON.stringify({ type: 'speech_finished' }));
        } else {
          console.warn('[VocalCoach] WebSocket not open when trying to send audio.');
        }
      });
    }

    /**
     * Fully tears down the audio pipeline. Called only when the session is completely over.
     */
    cleanupSession() {
      if (this.audioStream) {
        this.audioStream.getTracks().forEach(track => track.stop());
        this.audioStream = null;
      }
      if (this.audioContext && this.audioContext.state !== 'closed') {
        this.audioContext.close();
        this.audioContext = null;
      }
    }

    /**
     * Converts raw Float32Array PCM buffers into a valid WAV file Blob.
     */
    encodeWAV(buffers, totalLength, sampleRate) {
      const buffer = new ArrayBuffer(44 + totalLength * 2);
      const view = new DataView(buffer);

      const writeString = (view, offset, string) => {
        for (let i = 0; i < string.length; i++) {
          view.setUint8(offset + i, string.charCodeAt(i));
        }
      };

      // RIFF identifier
      writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + totalLength * 2, true);
      // RIFF type
      writeString(view, 8, 'WAVE');
      // format chunk identifier
      writeString(view, 12, 'fmt ');
      // format chunk length
      view.setUint32(16, 16, true);
      // sample format (raw)
      view.setUint16(20, 1, true);
      // channel count
      view.setUint16(22, 1, true);
      // sample rate
      view.setUint32(24, sampleRate, true);
      // byte rate (sample rate * block align)
      view.setUint32(28, sampleRate * 2, true);
      // block align (channel count * bytes per sample)
      view.setUint16(32, 2, true);
      // bits per sample
      view.setUint16(34, 16, true);
      // data chunk identifier
      writeString(view, 36, 'data');
      // data chunk length
      view.setUint32(40, totalLength * 2, true);

      // write PCM samples
      let offset = 44;
      for (let i = 0; i < buffers.length; i++) {
        const float32Array = buffers[i];
        for (let j = 0; j < float32Array.length; j++) {
          let sample = Math.max(-1, Math.min(1, float32Array[j]));
          sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
          view.setInt16(offset, sample, true);
          offset += 2;
        }
      }

      return new Blob([view], { type: 'audio/wav' });
    }

    addChatBubble(role, text, arabicTarget = null, transliteration = null) {
      const container = document.getElementById(this.transcriptContainerId);
      if (!container) return;

      const bubble = document.createElement('div');
      bubble.className = `transcript-bubble ${role}`;

      let htmlContent = `<div>${text}</div>`;
      if (arabicTarget) {
        htmlContent += `<div class="arabic-target">${arabicTarget}</div>`;
      }
      if (transliteration) {
        htmlContent += `<div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">(${transliteration})</div>`;
      }

      bubble.innerHTML = htmlContent;
      container.appendChild(bubble);
      container.scrollTop = container.scrollHeight;
    }

    showTypingIndicator() {
      const container = document.getElementById(this.transcriptContainerId);
      if (!container) return;
      if (document.getElementById('typing-bubble')) return;

      const bubble = document.createElement('div');
      bubble.className = 'transcript-bubble ai';
      bubble.id = 'typing-bubble';
      bubble.innerHTML = `
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      `;
      container.appendChild(bubble);
      container.scrollTop = container.scrollHeight;
    }

    hideTypingIndicator() {
      const bubble = document.getElementById('typing-bubble');
      if (bubble) {
        bubble.remove();
      }
    }

    updateStatus(text) {
      console.log('[Status]:', text);
      const statusElement = document.querySelector('.status-dot + span');
      if (statusElement) {
        statusElement.textContent = text;
      }
    }
  }

  window.VocalCoachClient = VocalCoachClient;

  // ─────────────────────────────────────────────────────────────────────────
  // LiveVocalCoachClient — Gemini Live real-time audio (replaces the old
  // Whisper+eval+TTS pipeline with a single bidirectional audio WebSocket)
  // ─────────────────────────────────────────────────────────────────────────

  class LiveVocalCoachClient {
    /**
     * @param {Object} config
     * @param {string} [config.serverUrl]          - WebSocket backend base URL
     * @param {string} [config.dayId]              - Vocabulary set ID
     * @param {string} [config.buttonSlotId]       - Container for the call button
     * @param {string} [config.transcriptContainerId] - Chat transcript container
     */
    constructor(config = {}) {
      // Smart Environment Detection: Connect to local python server on localhost, or Render WSS on live production
      // const isLocal = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:');
      const isLocal = false; // Set to false to always use the Render production server

      if (isLocal) {
        this.serverUrl = 'ws://localhost:8000';
        console.log('[Live] Running in local environment — connected to ws://localhost:8000');
      } else {
        this.serverUrl = config.serverUrl || window.LIVE_VOCAL_COACH_SERVER_URL || 'wss://ai-assistant-course.onrender.com';
        console.log(`[Live] Running in production environment — connected to ${this.serverUrl}`);
      }
      this.dayId = config.dayId || 'day_1_greetings';
      this.buttonSlotId = config.buttonSlotId || 'vapi-icon-slot';
      this.transcriptContainerId = config.transcriptContainerId || 'transcript-container';

      this.ws = null;
      this.micStream = null;
      this.captureCtx = null;   // AudioContext for mic capture
      this.scriptProc = null;
      this.isStreaming = false;
      this.geminiSpeaking = false;  // True while Gemini is outputting audio
      this.nativeRate = 48000;  // detected from AudioContext
      this.targetRate = 16000;  // Gemini expects 16kHz PCM input

      // Playback — Gemini outputs 24kHz PCM
      this.playCtx = null;
      this.nextPlayTime = 0;
      this.OUTPUT_RATE = 24000;

      this.initUI();
    }

    // ── UI ──────────────────────────────────────────────────────────────────

    initUI() {
      const slot = document.getElementById(this.buttonSlotId);
      if (!slot) { console.warn(`[Live] Slot #${this.buttonSlotId} not found.`); return; }

      slot.innerHTML = `
        <div class="vocal-coach-wrapper">
          <div class="pulse-ring ring-1"></div>
          <div class="pulse-ring ring-2"></div>
          <button id="yalla-call-btn" class="yalla-call-btn idle" title="Start Live Arabic Lesson">
            <svg class="phone-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/>
            </svg>
            <span id="call-btn-label" class="btn-label">TAP TO START</span>
          </button>
        </div>`;

      this._injectLiveStyles();
      this.button = document.getElementById('yalla-call-btn');
      this.buttonLabel = document.getElementById('call-btn-label');
      this.button.addEventListener('click', () => this._handleClick());
    }

    _injectLiveStyles() {
      if (document.getElementById('live-coach-styles')) return;
      const style = document.createElement('style');
      style.id = 'live-coach-styles';
      style.textContent = `
        .vocal-coach-wrapper { position: relative; display: flex; align-items: center; justify-content: center; margin: 1.5rem auto; }
        .yalla-call-btn { position: relative; z-index: 2; width: 80px; height: 80px; border-radius: 50%; background: #ffcc00; border: 3px solid #ffffff; box-shadow: 0 8px 25px rgba(255,204,0,0.4); cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #000; transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
        .yalla-call-btn:hover { transform: scale(1.08); box-shadow: 0 12px 30px rgba(255,204,0,0.6); }
        .yalla-call-btn .phone-icon { width: 28px; height: 28px; margin-bottom: 2px; }
        .yalla-call-btn .btn-label { font-size: 0.6rem; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase; }
        .vocal-coach-wrapper .pulse-ring { position: absolute; width: 80px; height: 80px; border-radius: 50%; background: rgba(255,204,0,0.3); z-index: 1; opacity: 0; pointer-events: none; }
        .yalla-call-btn.live { background: #22c55e; color: #fff; box-shadow: 0 8px 25px rgba(34,197,94,0.5); }
        .yalla-call-btn.live ~ .ring-1 { background: rgba(34,197,94,0.35); animation: liveRing 1.8s cubic-bezier(0.215,0.61,0.355,1) infinite; }
        .yalla-call-btn.live ~ .ring-2 { background: rgba(34,197,94,0.15); animation: liveRing 1.8s cubic-bezier(0.215,0.61,0.355,1) infinite 0.6s; }
        .yalla-call-btn.ending { background: #ef4444; color: #fff; box-shadow: 0 8px 25px rgba(239,68,68,0.5); }
        @keyframes liveRing { 0%{transform:scale(0.95);opacity:0.8} 50%{transform:scale(1.6);opacity:0.4} 100%{transform:scale(2);opacity:0} }
        .transcript-bubble { margin: 0.5rem 0; padding: 0.8rem 1.2rem; border-radius: 16px; max-width: 85%; font-size: 0.95rem; line-height: 1.5; animation: liveFade 0.3s ease; }
        .transcript-bubble.ai   { background: rgba(255,208,0,0.12); border: 1px solid rgba(255,208,0,0.2); color: #ffd000; align-self: flex-start; border-bottom-left-radius: 4px; }
        .transcript-bubble.user { background: rgba(255,255,255,0.08); color: #f3f4f6; align-self: flex-end; margin-left: auto; margin-right: 0; border-bottom-right-radius: 4px; }
        @keyframes liveFade { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
      `;
      document.head.appendChild(style);
    }

    // ── Session control ──────────────────────────────────────────────────────

    _handleClick() {
      if (!this.ws || this.ws.readyState === WebSocket.CLOSED || this.ws.readyState === WebSocket.CLOSING) {
        this._startSession();
      } else {
        this._endSession();
      }
    }

    _startSession() {
      this._updateStatus('Connecting to AI coach...');
      this.buttonLabel.textContent = 'CONNECTING';
      const url = `${this.serverUrl}/ws/live/${this.dayId}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => console.log('[Live] WebSocket open');

      this.ws.onmessage = (event) => {
        try { this._handleMessage(JSON.parse(event.data)); } catch (e) { console.error('[Live] bad message', e); }
      };

      this.ws.onclose = () => {
        console.log('[Live] WebSocket closed');
        this._stopMic();
        this.button.className = 'yalla-call-btn idle';
        this.buttonLabel.textContent = 'TAP TO START';
        this._updateStatus('Session ended. Tap to start a new one.');
      };

      this.ws.onerror = (e) => {
        console.error('[Live] WS error', e);
        this._updateStatus('Connection error — is the backend running?');
      };
    }

    _endSession() {
      this.button.className = 'yalla-call-btn ending';
      this.buttonLabel.textContent = 'ENDING...';
      this._stopMic();
      if (this.ws) this.ws.close();
    }

    // ── Message handling ─────────────────────────────────────────────────────

    _handleMessage(msg) {
      switch (msg.type) {
        case 'session_started':
          this.button.className = 'yalla-call-btn live';
          this.buttonLabel.textContent = 'LIVE';
          this._updateStatus('🟢 Connected — AI is speaking...');
          this._openMic();
          break;

        case 'audio_chunk':
          // Mute mic on first audio chunk to prevent echo
          if (!this.geminiSpeaking) {
            this.geminiSpeaking = true;
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({ type: 'mic_muted' }));
            }
          }
          this._playPCMChunk(msg.data);
          break;

        case 'turn_complete':
          // Wait until speaker audio buffer finishes playing + 400ms echo decay before unmuting mic
          const playNow = (this.playCtx && this.playCtx.currentTime) ? this.playCtx.currentTime : 0;
          const remainingMs = Math.max(0, (this.nextPlayTime - playNow) * 1000);
          const waitMs = Math.max(800, Math.ceil(remainingMs + 400));

          setTimeout(() => {
            this.geminiSpeaking = false;
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({ type: 'mic_unmuted' }));
            }
            this._updateStatus('🎤 Your turn — speak now!');
          }, waitMs);
          break;

        case 'transcript':
          this._addBubble(msg.role || 'ai', msg.text, msg.id, true);
          if (msg.role === 'user') {
            this._clearAudioBuffer();
          }
          break;

        case 'transcript_partial':
          this._addBubble(msg.role, msg.text, msg.id, false);
          break;

        case 'user_transcript':
          this._addBubble('user', msg.text, msg.id, true);
          this._clearAudioBuffer();
          break;

        case 'session_ended':
          const playNowEnd = (this.playCtx && this.playCtx.currentTime) ? this.playCtx.currentTime : 0;
          const remainingEndMs = Math.max(0, (this.nextPlayTime - playNowEnd) * 1000);
          setTimeout(() => {
            this._updateStatus('Session Complete — Goodbye!');
            this._endSession();
          }, Math.max(1500, Math.ceil(remainingEndMs + 800)));
          break;

        case 'error':
          this._addBubble('ai', `❌ Error: ${msg.message}`);
          this._updateStatus(`Error: ${msg.message}`);
          break;
      }
    }

    // ── Microphone streaming ─────────────────────────────────────────────────

    async _openMic() {
      try {
        this.micStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
        });

        this.captureCtx = new (window.AudioContext || window.webkitAudioContext)();
        this.nativeRate = this.captureCtx.sampleRate;
        console.log(`[Live] Mic open at ${this.nativeRate}Hz, streaming at ${this.targetRate}Hz`);

        const source = this.captureCtx.createMediaStreamSource(this.micStream);
        this.scriptProc = this.captureCtx.createScriptProcessor(4096, 1, 1);

        this.scriptProc.onaudioprocess = (e) => {
          if (!this.isStreaming || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
          // Audio is always streamed so the user can interrupt the AI.
          // Echo cancellation is handled by the browser's getUserMedia.
          const float32 = e.inputBuffer.getChannelData(0);
          const resampled = this._downsample(float32, this.nativeRate, this.targetRate);
          const int16 = this._float32ToInt16(resampled);
          this.ws.send(int16.buffer);
        };

        source.connect(this.scriptProc);
        this.scriptProc.connect(this.captureCtx.destination);
        this.isStreaming = true;
        this._updateStatus('🎤 Mic open — speak when the AI is done!');
      } catch (err) {
        console.error('[Live] Mic error:', err);
        this._updateStatus('Microphone access denied.');
      }
    }

    _stopMic() {
      this.isStreaming = false;
      if (this.scriptProc) {
        this.scriptProc.disconnect();
        this.scriptProc.onaudioprocess = null;
        this.scriptProc = null;
      }
      if (this.micStream) {
        this.micStream.getTracks().forEach(t => t.stop());
        this.micStream = null;
      }
      if (this.captureCtx && this.captureCtx.state !== 'closed') {
        this.captureCtx.close();
        this.captureCtx = null;
      }
    }

    // ── Audio helpers ────────────────────────────────────────────────────────

    _clearAudioBuffer() {
      if (this.playCtx && this.playCtx.state !== 'closed') {
        this.playCtx.close();
        this.playCtx = null;
        this.nextPlayTime = 0;
      }
      this.geminiSpeaking = false;
    }

    // ── PCM Playback (Gemini outputs 24kHz PCM) ──────────────────────────────

    _playPCMChunk(base64) {
      if (!this.playCtx) {
        this.playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.OUTPUT_RATE });
        this.nextPlayTime = this.playCtx.currentTime + 0.05;
      }
      if (this.playCtx.state === 'suspended') this.playCtx.resume();

      // Decode base64 → Int16 → Float32
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      const VOLUME_MULTIPLIER = 2.5; // Boost AI voice volume
      for (let i = 0; i < int16.length; i++) {
        let val = (int16[i] / 32768.0) * VOLUME_MULTIPLIER;
        float32[i] = Math.max(-1, Math.min(1, val)); // Clip to prevent distortion
      }

      const buf = this.playCtx.createBuffer(1, float32.length, this.OUTPUT_RATE);
      buf.getChannelData(0).set(float32);

      const src = this.playCtx.createBufferSource();
      src.buffer = buf;
      src.connect(this.playCtx.destination);

      const now = this.playCtx.currentTime;
      if (this.nextPlayTime < now) this.nextPlayTime = now + 0.05;
      src.start(this.nextPlayTime);
      this.nextPlayTime += buf.duration;
    }

    // ── Audio helpers ────────────────────────────────────────────────────────

    _downsample(buffer, fromRate, toRate) {
      if (fromRate === toRate) return buffer;
      const ratio = fromRate / toRate;
      const newLen = Math.round(buffer.length / ratio);
      const result = new Float32Array(newLen);
      for (let i = 0; i < newLen; i++) {
        const src = i * ratio;
        const lo = Math.floor(src);
        const hi = Math.min(lo + 1, buffer.length - 1);
        const f = src - lo;
        result[i] = buffer[lo] * (1 - f) + buffer[hi] * f;
      }
      return result;
    }

    _float32ToInt16(float32) {
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      return int16;
    }

    // ── UI helpers ───────────────────────────────────────────────────────────

    _addBubble(role, text, id = null, isFinal = true) {
      const container = document.getElementById(this.transcriptContainerId);
      if (!container) return;

      let bubble = id ? document.getElementById(id) : null;
      if (!bubble) {
        bubble = document.createElement('div');
        bubble.className = `transcript-bubble ${role}`;
        if (id) bubble.id = id;
        container.appendChild(bubble);
      }

      if (isFinal) {
        bubble.innerHTML = text;
        bubble.style.opacity = '1';
      } else {
        bubble.innerHTML = text + '<span class="typing-cursor" style="display:inline-block;width:6px;height:1.2em;background-color:currentColor;vertical-align:middle;margin-left:4px;animation:blink 1s step-end infinite;opacity:0.7;"></span>';
        bubble.style.opacity = '0.9';

        if (!document.getElementById('cursor-style')) {
          const style = document.createElement('style');
          style.id = 'cursor-style';
          style.innerHTML = '@keyframes blink { 50% { opacity: 0; } }';
          document.head.appendChild(style);
        }
      }
      container.scrollTop = container.scrollHeight;
    }

    _updateStatus(text) {
      const el = document.querySelector('.status-dot + span');
      if (el) el.textContent = text;
      console.log('[Live Status]:', text);
    }
  }

  window.LiveVocalCoachClient = LiveVocalCoachClient;

})(window, document);

