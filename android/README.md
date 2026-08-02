# Hey Agent — ambient voice assistant

Companion Android app for mobile-agent: a "Hey Google"-style ambient assistant
that listens for a wake phrase from inside ANY app and executes the resulting
command through the same automation pipeline the web UI already drives.

**Status: code complete for v1 (laptop-assisted), builds successfully.** Every
class is real — wake word, speech-to-text, backend dispatch, on-device
gesture execution (the last is a building block for a future fully-local v2,
not wired into the voice flow yet — see "Known architectural gap" below).

Wake word is `ContinuousWakeWordListener` + `VoiceActivityGate` — no external
account, no third-party wake-word SDK. (An earlier version of this app used
Picovoice Porcupine; dropped after confirming their self-service signup is
now gated to company/institutional email domains, and because a self-built,
fully-verifiable implementation was preferable anyway. See git history if
you want to revisit that path.)

Verification history: the code was originally written and syntax/type-checked
file-by-file against the real `android.jar` SDK jar using Android Studio's
bundled `kotlinc` (no `./gradlew` available at authoring time — caught and
fixed one real bug this way, a variable-shadowing mistake in `MainActivity`).
It has since been opened in Android Studio for real and synced —
**`BUILD SUCCESSFUL in 8m 29s`**, every dependency resolved (androidx,
Material, OkHttp), Gradle JDK set to the embedded one
(`C:\Program Files\Android\Android Studio\jbr`) after the first sync attempt
flagged an invalid Gradle JDK config. Not yet done: running the app on a
device, and exercising the actual wake-word/voice flow live.

## Architecture

```
"Hey Agent, send Ramu a message" (spoken while inside YouTube)
        │
        ▼
ContinuousWakeWordListener (VoiceActivityGate energy-gate → SpeechRecognizer)
        │ detects wake phrase → HeyAgentAccessibilityService.onWakeWordDetected()
        │ (may already have the command text too, if it was spoken in the
        │  same breath — skips the step below)
        ▼
CommandInterpreter
        │ Android SpeechRecognizer (EXTRA_PREFER_OFFLINE), captures the rest
        │ of the utterance as text
        ▼
BackendClient
        │ POST http://<laptop-ip>:8000/api/v1/agent/chat  { message }
        ▼
backend/api/routers/agent.py :: start_chat()   (already shipped, see
backend/api/routers/agent.py + frontend/src/pages/ChatPage.tsx)
        │ LLM infers app_name + task, starts a normal Deploy session
        ▼
Deploy session runs against the phone over ADB, from wherever the backend
process is running (today: a laptop on the same network)
```

See [docs/wake-word-power-optimization.md](docs/wake-word-power-optimization.md)
for why wake-word detection is a two-stage pipeline and how to tune its
sensitivity.

**Known architectural gap:** the flow above executes the command via the
existing ADB-based Deploy pipeline, which means a laptop running the backend
must be reachable on the same network as the phone. `HeyAgentAccessibilityService
.performAction()` (tap/text/swipe/long_press/back, real gesture dispatch) is
implemented and ready to be the local-execution path for a v2 that never
leaves the device — but nothing currently calls it from the voice flow.
Left as-is since the brief was explicitly "local ON SETUP" (no cloud
wake-word/STT dependency), not "no laptop at all." Wiring v2 would mean:
CommandInterpreter's recognized text → an LLM decision call made directly
from the app (reusing something like `backend/llm/prompts.py`'s prompt
shape) using `dumpVisibleElements()` as context → `performAction()`. Ask if
you want this built out next.

## What's real vs. stubbed

| Piece | Status |
|---|---|
| Gradle/AGP/Kotlin project structure | Real, confirmed by a successful build |
| `AndroidManifest.xml` (permissions, accessibility service, mic) | Real |
| `MainActivity` — accessibility status, settings screen, manual "Test Listen" | Real |
| `Settings` — SharedPreferences for backend URL/key, device serial | Real |
| `HeyAgentAccessibilityService` — event plumbing, screen dump, **performAction()** (real gesture dispatch), wake-word wiring | Real |
| `BackendClient` — POST to `/agent/chat` | Real, uses OkHttp + org.json |
| `CommandInterpreter` — SpeechRecognizer → BackendClient | Real |
| `ContinuousWakeWordListener` + `VoiceActivityGate` — two-stage: cheap `AudioRecord` energy gate before SpeechRecognizer | Real — the only wake-word implementation, no account needed |

## Your part — step by step

### 1. Open the project and get it compiling — DONE, confirmed working
Already done once: opened the `mobile-agent` repo in Android Studio, linked
the `android/settings.gradle.kts` Gradle project (Android Studio detects it
and offers a "Link Gradle project" banner), fixed one JDK setting (Gradle
JDK → Embedded JDK, since none was configured yet), and synced —
`BUILD SUCCESSFUL in 8m 29s`. If you're setting this up fresh on a different
machine, expect the same two steps (open + link, then possibly the same JDK
fix) before it syncs cleanly.

### 2. Backend reachability
- Find your laptop's LAN IP (`ipconfig` → IPv4 Address) while the backend is
  running (`uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`, which
  it already does in this project — `--host 0.0.0.0` matters, `localhost`
  won't be reachable from the phone).
- Phone and laptop must be on the same Wi-Fi network.

### 3. Install and configure on-device
1. Build & install the app on your phone (Android Studio's Run button, phone
   connected via USB with debugging enabled, or build an APK and sideload).
2. Open the app. Under **Backend connection**, enter:
   - Backend URL: `http://<your-laptop-LAN-IP>:8000`
   - API_KEY: the value of `API_KEY` in `backend/.env`
   - Device serial: leave blank unless you specifically want commands to
     always target one device with multiple connected
3. Tap **Save settings**.
4. Tap **Test Listen** — grant microphone permission when prompted, speak a
   command (e.g. "search for cats on youtube"). This exercises the full
   mic → backend → Deploy pipeline WITHOUT needing the wake word yet. Confirm
   this works before moving on — it's the same pipeline the wake word will
   trigger, just manually invoked.
5. Tap **Open Accessibility Settings**, find "Hey Agent", enable it. This is
   what actually starts the wake-word listener (see
   `HeyAgentAccessibilityService.onServiceConnected()`) — do this LAST, after
   step 4, since mic permission needs to already be granted for the listener
   to start successfully when the service auto-connects.

### 4. Say "Hey Agent" from inside any app
If all of the above is done, this should now work ambiently. If it doesn't,
check Logcat filtered to `HeyAgentA11yService` / `ContinuousWakeWord` /
`VoiceActivityGate` / `CommandInterpreter` — every failure path in this
codebase logs rather than silently swallowing errors.
