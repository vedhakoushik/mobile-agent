package com.mobileagent.heyagent

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import kotlin.concurrent.thread
import kotlin.math.sqrt

/**
 * Stage 1 of a two-stage wake-word pipeline: a cheap, always-on energy
 * check that only wakes the expensive Stage 2 (SpeechRecognizer — the full
 * STT engine) when there's actually sound worth transcribing.
 *
 * This is the practical equivalent, at the app level, of what "Hey Google"
 * does with a dedicated low-power DSP chip: Android exposes that same
 * capability to apps via AlwaysOnHotwordDetector/SoundTrigger, but ONLY to
 * an app registered as the device's system VoiceInteractionService — a
 * heavy, Google-gated integration that isn't realistic for a third-party
 * accessibility-service-based app like this one (confirmed via Android's
 * own docs: https://source.android.com/docs/core/audio/sound-trigger).
 * Raw AudioRecord + energy thresholding is the next-best option available
 * without that integration, and it's what this class does.
 *
 * Pure Kotlin/Android SDK, no third-party dependency (unlike Porcupine)
 * — nothing here needed a network fetch to write or verify.
 */
class VoiceActivityGate(
    /** How many times louder than the adaptive noise floor counts as speech. */
    private val sensitivityMultiplier: Double = 2.5,
    /** Consecutive loud frames required before firing — filters single-frame spikes (a knock, a click) from real speech. */
    private val consecutiveFramesRequired: Int = 3,
) {
    companion object {
        private const val TAG = "VoiceActivityGate"
        private const val SAMPLE_RATE = 16000
    }

    @Volatile private var running = false
    private var workerThread: Thread? = null

    /**
     * Runs on a background thread until speech-level energy is detected,
     * then calls [onSpeechDetected] ONCE and stops itself — this is a
     * one-shot gate, not a continuous stream. Caller restarts it (via a new
     * VoiceActivityGate instance) after handling that detection, same
     * pattern as WakeWordListener.
     *
     * [onSpeechDetected] fires on THIS class's own worker thread, not the
     * main thread — callers that need to touch UI or call SpeechRecognizer
     * (which requires the main thread) must post back themselves.
     */
    fun start(onSpeechDetected: () -> Unit) {
        if (running) return
        running = true
        workerThread = thread(name = "VoiceActivityGate") { runLoop(onSpeechDetected) }
    }

    fun stop() {
        running = false
        workerThread?.interrupt()
        workerThread = null
    }

    @Suppress("MissingPermission") // caller is required to have RECORD_AUDIO granted already
    private fun runLoop(onSpeechDetected: () -> Unit) {
        val minBufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBufferSize <= 0) {
            Log.w(TAG, "AudioRecord.getMinBufferSize returned $minBufferSize — device doesn't support 16kHz mono PCM, gate disabled")
            running = false
            return
        }

        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                minBufferSize * 2,
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "RECORD_AUDIO not granted: ${e.message}")
            running = false
            return
        }

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            Log.w(TAG, "AudioRecord failed to initialize (state=${record.state}) — gate disabled")
            record.release()
            running = false
            return
        }

        val frame = ShortArray(minBufferSize / 2)
        // Adaptive noise floor: starts at a conservative estimate and drifts
        // toward whatever "quiet" actually reads as in this environment
        // (a fan, AC hum, traffic) — see the exponential-moving-average
        // update below, which only runs on QUIET frames so it doesn't chase
        // the very speech it's trying to detect.
        var noiseFloor = 200.0
        var consecutiveLoud = 0

        record.startRecording()
        try {
            while (running) {
                val read = record.read(frame, 0, frame.size)
                if (read <= 0) continue

                var sumSquares = 0.0
                for (i in 0 until read) {
                    val s = frame[i].toDouble()
                    sumSquares += s * s
                }
                val rms = sqrt(sumSquares / read)

                if (rms > noiseFloor * sensitivityMultiplier) {
                    consecutiveLoud++
                    if (consecutiveLoud >= consecutiveFramesRequired) {
                        onSpeechDetected()
                        return
                    }
                } else {
                    consecutiveLoud = 0
                    noiseFloor = noiseFloor * 0.98 + rms * 0.02
                }
            }
        } finally {
            record.stop()
            record.release()
        }
    }
}
