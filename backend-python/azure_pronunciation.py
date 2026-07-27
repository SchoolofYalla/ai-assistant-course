import os
import re
import tempfile
import azure.cognitiveservices.speech as speechsdk


def _normalize_arabic(text: str) -> str:
    """Strip harakat, normalize Alif variants, and remove punctuation."""
    # Remove harakat (diacritics)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # Normalize Alif variants (أ إ آ) to bare Alif
    text = re.sub(r'[أإآ]', 'ا', text)
    # Remove all punctuation/non-word characters
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def _build_speech_config() -> speechsdk.SpeechConfig:
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
    if not speech_key:
        raise ValueError("AZURE_SPEECH_KEY not set.")
    config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    return config


def evaluate_pronunciation_azure(audio_buffer: bytes, target_arabic: str) -> dict:
    """
    Two-pass Arabic pronunciation evaluator:
      Pass 1 — Free STT: Confirm the user said the correct word at all.
      Pass 2 — Pronunciation Assessment: Grade exactly how well they said it.
    """
    # Save buffer to a temporary WAV file
    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_wav.write(audio_buffer)
    temp_wav.close()

    # Removed debug_audio file write because it was triggering Uvicorn --reload and killing the connection!
    recognizer_1 = None
    recognizer_2 = None

    try:
        # ------------------------------------------------------------------ #
        # Run Pass 1 and Pass 2 concurrently to cut time in half
        # ------------------------------------------------------------------ #
        import concurrent.futures

        def run_pass_1():
            config_1 = _build_speech_config()
            audio_config_1 = speechsdk.audio.AudioConfig(filename=temp_wav.name)
            recognizer_1 = speechsdk.SpeechRecognizer(
                speech_config=config_1,
                language="ar-JO",  # Reverting to Jordanian so it recognizes colloquial speech
                audio_config=audio_config_1
            )
            print(f"[Azure Pass 1] Free STT for target: {target_arabic}...")
            res = recognizer_1.recognize_once_async().get()
            return res

        def run_pass_2():
            config_2 = _build_speech_config()
            audio_config_2 = speechsdk.audio.AudioConfig(filename=temp_wav.name)
            recognizer_2 = speechsdk.SpeechRecognizer(
                speech_config=config_2,
                language="ar-SA",
                audio_config=audio_config_2
            )
            pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=target_arabic,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True
            )
            pronunciation_config.apply_to(recognizer_2)
            print(f"[Azure Pass 2] Pronunciation Assessment for: {target_arabic}...")
            return recognizer_2.recognize_once_async().get()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_1 = executor.submit(run_pass_1)
            future_2 = executor.submit(run_pass_2)
            
            result_1 = future_1.result()
            result_2 = future_2.result()

        if result_1.reason == speechsdk.ResultReason.NoMatch:
            print("[Azure Pass 1] No speech detected.")
            return {
                "passed": False,
                "accuracy": 0.0,
                "feedback": "I didn't hear anything clearly. Speak louder and try again!",
                "recognized_text": ""
            }

        if result_1.reason == speechsdk.ResultReason.Canceled:
            details = result_1.cancellation_details
            print(f"[Azure Pass 1] Canceled: {details.reason} — {details.error_details}")
            return {
                "passed": False,
                "accuracy": 0.0,
                "feedback": "Connection error with Azure. Please try again.",
                "recognized_text": ""
            }

        raw_recognized = result_1.text
        clean_recognized = _normalize_arabic(raw_recognized)
        clean_target = _normalize_arabic(target_arabic)

        print(f"[Azure Pass 1] Heard: '{raw_recognized}' → normalized: '{clean_recognized}'")
        print(f"[Azure Pass 1] Target: '{target_arabic}' → normalized: '{clean_target}'")

        # Strict word check — must match the target root word
        if clean_target not in clean_recognized and clean_recognized not in clean_target:
            return {
                "passed": False,
                "accuracy": 0.0,
                "feedback": f"Wrong word! You said '{clean_recognized}' but we need '{clean_target}'. Try again!",
                "recognized_text": raw_recognized
            }

        if result_2.reason == speechsdk.ResultReason.RecognizedSpeech:
            pron_result = speechsdk.PronunciationAssessmentResult(result_2)
            acc_score = pron_result.accuracy_score
            pron_score = pron_result.pronunciation_score

            print(f"[Azure Pass 2] Accuracy: {acc_score} | Pronunciation: {pron_score}")
            
            if acc_score >= 80.0:
                passed = True
                feedback = f"Perfect! Score: {int(acc_score)}%"
            elif acc_score >= 55.0:
                passed = False
                feedback = f"Almost there! Score: {int(acc_score)}%. Watch the vowels carefully."
            else:
                passed = False
                feedback = f"Not quite. Score: {int(acc_score)}%. Listen again and focus on each sound."

            return {
                "passed": passed,
                "accuracy": acc_score,
                "feedback": feedback,
                "recognized_text": raw_recognized
            }

        # If assessment failed, still pass them since Pass 1 confirmed correct word
        return {
            "passed": True,
            "accuracy": 75.0,
            "feedback": "Word recognized correctly! Keep practising the vowels.",
            "recognized_text": raw_recognized
        }

    except Exception as e:
        print(f"[Azure Exception] {e}")
        return {"passed": False, "accuracy": 0.0, "feedback": "Server error during evaluation.", "recognized_text": ""}

    finally:
        if recognizer_1 is not None:
            del recognizer_1
        if recognizer_2 is not None:
            del recognizer_2
        if os.path.exists(temp_wav.name):
            try:
                os.remove(temp_wav.name)
            except Exception as e:
                print(f"[Warning] Could not delete temp file: {e}")
