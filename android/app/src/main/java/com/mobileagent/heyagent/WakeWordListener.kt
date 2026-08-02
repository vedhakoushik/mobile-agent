package com.mobileagent.heyagent

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

/**
 * On-device wake-word detection ("Hey Agent").
 *
 * `onWakeWordDetected` carries an optional `remainderText`: if the user said
 * the whole command in one breath ("hey agent send a message to ramu"),
 * ContinuousWakeWordListener passes everything after the wake phrase so the
 * caller can skip a second listen.
 */
interface WakeWordListener {
    fun start(onWakeWordDetected: (remainderText: String?) -> Unit)
    fun stop()
}

/** No-op placeholder — used when no wake-word implementation is configured. */
class UnimplementedWakeWordListener : WakeWordListener {
    override fun start(onWakeWordDetected: (String?) -> Unit) = Unit
    override fun stop() = Unit
}

/**
 * The wake-word implementation this app actually uses: no external account
 * required. Two-stage pipeline matching the same shape "Hey Google" uses at
 * the hardware level (see VoiceActivityGate's doc comment for why the true
 * DSP-level API, AlwaysOnHotwordDetector, isn't realistic for this app):
 *
 *   Stage 1 (cheap):  VoiceActivityGate — raw AudioRecord + energy
 *                      thresholding, no STT engine running, waits for
 *                      speech-level sound before doing anything else.
 *   Stage 2 (costly):  SpeechRecognizer session, only started once Stage 1
 *                      fires. Checks the transcript for "hey agent". On
 *                      completion (match or not), goes back to Stage 1
 *                      rather than immediately starting another Stage 2
 *                      session — this is what actually saves battery vs.
 *                      the naive always-be-transcribing loop this replaced.
 *
 * Still not free: Stage 2 is real STT (network-backed unless an offline
 * language pack is installed — EXTRA_PREFER_OFFLINE is a hint, not a
 * guarantee, same caveat as CommandInterpreter), and Stage 1's AudioRecord
 * loop itself has some baseline cost (far cheaper than STT, but not the
 * near-zero a dedicated DSP chip achieves).
 */
class ContinuousWakeWordListener(
    private val context: Context,
    private val wakePhrase: String = "hey agent",
) : WakeWordListener {

    private var recognizer: SpeechRecognizer? = null
    private var vadGate: VoiceActivityGate? = null
    private var listening = false
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun start(onWakeWordDetected: (String?) -> Unit) {
        if (listening) return
        listening = true
        gateThenListen(onWakeWordDetected)
    }

    /** Stage 1: wait for speech-level energy before paying for real STT. */
    private fun gateThenListen(onWakeWordDetected: (String?) -> Unit) {
        if (!listening) return
        val gate = VoiceActivityGate()
        vadGate = gate
        gate.start {
            // Fires on VoiceActivityGate's own worker thread — SpeechRecognizer
            // must be created/started on the main thread, so hop back.
            mainHandler.post { listenOnce(onWakeWordDetected) }
        }
    }

    /** Stage 2: one real SpeechRecognizer session. */
    private fun listenOnce(onWakeWordDetected: (String?) -> Unit) {
        if (!listening) return
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.w(TAG, "No speech recognizer available — wake-word loop cannot start")
            listening = false
            return
        }

        val r = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val text = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                    ?.trim()

                if (!text.isNullOrBlank()) {
                    val lower = text.lowercase()
                    val idx = lower.indexOf(wakePhrase)
                    if (idx >= 0) {
                        Log.i(TAG, "Wake phrase detected in: \"$text\"")
                        val remainder = text.substring(idx + wakePhrase.length).trim().ifBlank { null }
                        onWakeWordDetected(remainder)
                    }
                }
                backToGate(onWakeWordDetected)
            }

            override fun onError(error: Int) {
                // ERROR_NO_MATCH / ERROR_SPEECH_TIMEOUT happen when the VAD
                // gate fired on a noise burst that wasn't actually speech
                // (or speech too short/quiet for STT to transcribe) — just
                // go back to gating. Anything else still loops but is worth
                // seeing in logs if this is misbehaving.
                if (error != SpeechRecognizer.ERROR_NO_MATCH && error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                    Log.w(TAG, "Recognition error code=$error")
                }
                backToGate(onWakeWordDetected)
            }

            // Unused callbacks required by the RecognitionListener interface.
            override fun onReadyForSpeech(params: Bundle?) = Unit
            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() = Unit
            override fun onPartialResults(partialResults: Bundle?) = Unit
            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        }
        r.startListening(intent)
    }

    private fun backToGate(onWakeWordDetected: (String?) -> Unit) {
        recognizer?.destroy()
        recognizer = null
        gateThenListen(onWakeWordDetected)
    }

    override fun stop() {
        listening = false
        vadGate?.stop()
        vadGate = null
        recognizer?.destroy()
        recognizer = null
    }

    companion object {
        private const val TAG = "ContinuousWakeWord"
    }
}
