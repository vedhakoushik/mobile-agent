package com.mobileagent.heyagent

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import ai.picovoice.porcupine.PorcupineManager
import ai.picovoice.porcupine.PorcupineManagerCallback

/**
 * On-device wake-word detection ("Hey Agent").
 *
 * `onWakeWordDetected` carries an optional `remainderText`: if the user said
 * the whole command in one breath ("hey agent send a message to ramu"),
 * implementations that have access to the transcript (ContinuousWakeWordListener)
 * pass everything after the wake phrase so the caller can skip a second
 * listen. Implementations that only get a bare detection event (Porcupine —
 * it's a pure keyword spotter, no transcript) pass null, and the caller
 * falls back to starting a fresh CommandInterpreter listen.
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
 * Zero-account fallback: no Picovoice signup required. Runs Android's
 * built-in SpeechRecognizer in a restart loop (there's no public "continuous
 * streaming" mode — SpeechRecognizer sessions end after a pause in speech,
 * so this is the standard workaround: start a new session immediately after
 * each one ends) and checks each transcript for the phrase "hey agent".
 *
 * Tradeoffs vs. a dedicated wake-word engine (Porcupine): keeps the mic
 * actively decoding rather than a lightweight always-on keyword spotter, so
 * more battery/CPU, and (like CommandInterpreter) only genuinely on-device
 * if the phone has an offline recognition language pack installed —
 * EXTRA_PREFER_OFFLINE is a hint, not a guarantee. Trade made deliberately:
 * this needs zero external account and works today, unlike Porcupine which
 * currently requires a Picovoice Console signup that rejects personal email
 * domains (confirmed against the real signup form — gmail.com and a test
 * .ac.in address were both rejected with "Please enter a valid company
 * email"; a recognized institutional domain might pass, untested).
 */
class ContinuousWakeWordListener(
    private val context: Context,
    private val wakePhrase: String = "hey agent",
) : WakeWordListener {

    private var recognizer: SpeechRecognizer? = null
    private var listening = false

    override fun start(onWakeWordDetected: (String?) -> Unit) {
        if (listening) return
        listening = true
        listenOnce(onWakeWordDetected)
    }

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
                relisten(onWakeWordDetected)
            }

            override fun onError(error: Int) {
                // ERROR_NO_MATCH / ERROR_SPEECH_TIMEOUT are the expected steady
                // state (most listening windows end in silence) — just loop
                // again immediately. Anything else still loops but is worth
                // seeing in logs if this is misbehaving.
                if (error != SpeechRecognizer.ERROR_NO_MATCH && error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                    Log.w(TAG, "Recognition error code=$error")
                }
                relisten(onWakeWordDetected)
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

    private fun relisten(onWakeWordDetected: (String?) -> Unit) {
        recognizer?.destroy()
        recognizer = null
        // Immediate restart — SpeechRecognizer instances are one-shot per
        // session, this is what makes the loop "continuous" in practice.
        listenOnce(onWakeWordDetected)
    }

    override fun stop() {
        listening = false
        recognizer?.destroy()
        recognizer = null
    }

    companion object {
        private const val TAG = "ContinuousWakeWord"
    }
}

/**
 * Real implementation, using Picovoice Porcupine
 * (https://picovoice.ai/platform/porcupine/). Requires two things this class
 * cannot supply itself — see android/README.md's setup section:
 *
 *   1. A Picovoice Console AccessKey (console.picovoice.ai) — signup is
 *      gated to recognized institutional/company email domains (confirmed
 *      live against the real form; gmail.com and a test .ac.in address were
 *      both rejected). If you can get an AccessKey, read it from
 *      Settings.getPicovoiceAccessKey(), entered on-device.
 *   2. A custom wake-word model trained for the phrase "Hey Agent" (a .ppn
 *      file — the built-in word list doesn't include it), placed at
 *      app/src/main/assets/hey_agent.ppn.
 *
 * VERIFICATION STATUS: written against Porcupine's documented Android SDK
 * shape (PorcupineManager.Builder + PorcupineManagerCallback) from memory,
 * NOT compiled against the real `ai.picovoice:porcupine-android` artifact —
 * that dependency wasn't fetched in this environment (no network dependency
 * resolution available). Treat any first-build compile errors here as the
 * SDK's real API differing slightly from what's written below.
 */
class PorcupineWakeWordListener(
    private val context: Context,
    private val accessKey: String,
    private val keywordAssetFileName: String = "hey_agent.ppn",
) : WakeWordListener {

    private var manager: PorcupineManager? = null

    override fun start(onWakeWordDetected: (String?) -> Unit) {
        if (manager != null) return // already listening

        try {
            manager = PorcupineManager.Builder()
                .setAccessKey(accessKey)
                .setKeywordPath(keywordAssetFileName) // resolved relative to assets/ by the SDK
                .setSensitivity(0.7f)
                .build(
                    context,
                    object : PorcupineManagerCallback {
                        override fun invoke(keywordIndex: Int) {
                            Log.i("WakeWordListener", "Wake word detected (index=$keywordIndex)")
                            onWakeWordDetected(null) // Porcupine is keyword-only, no transcript
                        }
                    },
                )
            manager?.start()
        } catch (e: Exception) {
            // Covers PorcupineException and anything else init/start can throw
            // (missing mic permission, bad AccessKey, missing/invalid .ppn) —
            // fail loud in logs rather than crash the accessibility service.
            Log.e("WakeWordListener", "Failed to start Porcupine: ${e.message}", e)
            manager = null
        }
    }

    override fun stop() {
        try {
            manager?.stop()
            manager?.delete()
        } catch (e: Exception) {
            Log.w("WakeWordListener", "Error stopping Porcupine: ${e.message}")
        } finally {
            manager = null
        }
    }
}
