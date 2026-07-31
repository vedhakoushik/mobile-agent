package com.mobileagent.heyagent

/**
 * On-device wake-word detection ("Hey Agent") — NOT implemented in this
 * skeleton. The intended integration is Picovoice Porcupine
 * (https://picovoice.ai/platform/porcupine/), which runs fully on-device
 * (no cloud calls, matches the "local for now" requirement) but requires:
 *
 *   1. A free Picovoice Console account (console.picovoice.ai) for an
 *      AccessKey.
 *   2. A custom wake-word model trained for the phrase "Hey Agent"
 *      (a .ppn file, generated on their console — the built-in word list
 *      doesn't include it).
 *   3. The `ai.picovoice:porcupine-android` dependency (commented out in
 *      app/build.gradle.kts) uncommented once the above two are in hand.
 *
 * Neither the AccessKey nor the .ppn model are secrets that belong in this
 * repo — they'd be supplied at build/runtime (e.g. via local.properties or
 * a runtime settings screen), the same way backend/.env keeps LLM provider
 * keys out of git.
 *
 * This interface defines the shape the real implementation will fill in, so
 * CommandInterpreter can be wired against it now without waiting on the
 * Picovoice integration.
 */
interface WakeWordListener {
    fun start(onWakeWordDetected: () -> Unit)
    fun stop()
}

/** No-op placeholder so the app builds/runs before Porcupine is wired in. */
class UnimplementedWakeWordListener : WakeWordListener {
    override fun start(onWakeWordDetected: () -> Unit) {
        // Intentionally does nothing — see class doc above for what's needed
        // to replace this with the real Porcupine-backed listener.
    }

    override fun stop() = Unit
}
