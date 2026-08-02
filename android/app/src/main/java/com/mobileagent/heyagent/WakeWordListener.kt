package com.mobileagent.heyagent

import android.content.Context
import android.util.Log
import ai.picovoice.porcupine.PorcupineManager
import ai.picovoice.porcupine.PorcupineManagerCallback

/**
 * On-device wake-word detection ("Hey Agent"). Runs fully on-device (no
 * cloud calls, matches the "local for now" requirement).
 *
 * Interface + no-op fallback (below) let the rest of the app depend on
 * "some WakeWordListener" without caring which implementation is active.
 */
interface WakeWordListener {
    fun start(onWakeWordDetected: () -> Unit)
    fun stop()
}

/** No-op placeholder — used when Picovoice isn't configured yet. */
class UnimplementedWakeWordListener : WakeWordListener {
    override fun start(onWakeWordDetected: () -> Unit) = Unit
    override fun stop() = Unit
}

/**
 * Real implementation, using Picovoice Porcupine
 * (https://picovoice.ai/platform/porcupine/). Requires two things this class
 * cannot supply itself — see android/README.md's setup section:
 *
 *   1. A Picovoice Console AccessKey (console.picovoice.ai, free tier) —
 *      read from Settings.getPicovoiceAccessKey(), entered on-device.
 *   2. A custom wake-word model trained for the phrase "Hey Agent" (a .ppn
 *      file — the built-in word list doesn't include it), placed at
 *      app/src/main/assets/hey_agent.ppn.
 *
 * VERIFICATION STATUS: written against Porcupine's documented Android SDK
 * shape (PorcupineManager.Builder + PorcupineManagerCallback) from memory,
 * NOT compiled against the real `ai.picovoice:porcupine-android` artifact —
 * that dependency is commented out in app/build.gradle.kts and wasn't
 * fetched in this environment (no network dependency resolution available).
 * Once you uncomment it and Android Studio syncs, treat any compile errors
 * here as the SDK's real API differing slightly from what's written below —
 * this is the one piece of the skeleton that should be double-checked
 * against Picovoice's current docs rather than trusted as-is.
 */
class PorcupineWakeWordListener(
    private val context: Context,
    private val accessKey: String,
    private val keywordAssetFileName: String = "hey_agent.ppn",
) : WakeWordListener {

    private var manager: PorcupineManager? = null

    override fun start(onWakeWordDetected: () -> Unit) {
        if (manager != null) return // already listening

        try {
            manager = PorcupineManager.Builder()
                .setAccessKey(accessKey)
                .setKeywordPath("$keywordAssetFileName") // resolved relative to assets/ by the SDK
                .setSensitivity(0.7f)
                .build(
                    context,
                    object : PorcupineManagerCallback {
                        override fun invoke(keywordIndex: Int) {
                            Log.i("WakeWordListener", "Wake word detected (index=$keywordIndex)")
                            onWakeWordDetected()
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
