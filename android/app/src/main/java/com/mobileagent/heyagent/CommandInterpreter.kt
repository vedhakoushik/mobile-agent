package com.mobileagent.heyagent

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log

/**
 * Speech-to-text for one spoken command.
 *
 *   WakeWordListener detects "Hey Agent"
 *     -> CommandInterpreter captures the utterance
 *     -> hands the raw transcript to [onTranscript]
 *
 * Deliberately does NOT decide what to do with the text. Dispatch lives in
 * HeyAgentAccessibilityService.runCommand(), so this class stays a pure
 * microphone -> string converter and the same transcript can be routed to
 * the on-device loop or anywhere else.
 *
 * Uses Android's built-in SpeechRecognizer with EXTRA_PREFER_OFFLINE — on
 * devices with an offline language pack installed this runs fully on-device
 * (no cloud STT call), but Android does not guarantee offline recognition on
 * every device/OS version; this is the best "local by default" option
 * available without bundling a third-party on-device STT model.
 */
class CommandInterpreter(
    private val context: Context,
    @Suppress("unused") private val backendClient: BackendClient? = null,
    private val onTranscript: (String) -> Unit,
) {
    private var recognizer: SpeechRecognizer? = null

    fun listenForCommand() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.w("CommandInterpreter", "No speech recognizer available on this device")
            return
        }

        val r = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val text = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                if (text.isNullOrBlank()) {
                    Log.w("CommandInterpreter", "Empty recognition result")
                    return
                }
                Log.i("CommandInterpreter", "Heard: $text")
                onTranscript(text)
            }

            override fun onError(error: Int) {
                Log.e("CommandInterpreter", "Speech recognition error code=$error")
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

    fun release() {
        recognizer?.destroy()
        recognizer = null
    }
}
