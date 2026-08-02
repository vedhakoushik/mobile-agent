# Hey Agent — ambient voice assistant

Companion Android app for mobile-agent: a "Hey Google"-style ambient assistant
that listens for a wake phrase from inside ANY app and executes the resulting
command through the same automation pipeline the web UI already drives.

**Status: code complete for v1 (laptop-assisted), unbuilt.** Every class is
now real — wake word (two implementations, see below), speech-to-text,
backend dispatch, on-device gesture execution (the last is a building block
for a future fully-local v2, not wired into the voice flow yet — see "Known
architectural gap" below). What's left is entirely on your side: a first
Android Studio build, and optionally a Picovoice account. Verification note:
built without a working `java`/`gradle` CLI — a JDK 21 was found bundled
inside Android Studio and used with its bundled `kotlinc` to syntax/type-check
every file against the real `android.jar` SDK jar (caught and fixed one real
bug this way — a variable-shadowing mistake in `MainActivity`). A full
`./gradlew build` was **never run** — that first real compile happens when
you open this in Android Studio.

**Picovoice signup update:** their self-service console now gates signup to
recognized company/institutional email domains — confirmed live against the
real form (`gmail.com` and a test `.ac.in` address were both rejected with
"Please enter a valid company email", `microsoft.com` was accepted). Your
real college email might pass, worth trying, but no guarantee. Because of
this, wake-word detection defaults to `ContinuousWakeWordListener` (below) —
**no external account needed, works out of the box** — and automatically
upgrades to Porcupine only if you do get a Picovoice AccessKey and save it in
Settings.

## Architecture

```
"Hey Agent, send Ramu a message" (spoken while inside YouTube)
        │
        ▼
WakeWordListener — ContinuousWakeWordListener (default, no account needed)
                    or PorcupineWakeWordListener (if you have an AccessKey)
        │ detects wake phrase → HeyAgentAccessibilityService.onWakeWordDetected()
        │ (ContinuousWakeWordListener may already have the command text too,
        │  if it was spoken in the same breath — skips the step below)
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
| Gradle/AGP/Kotlin project structure | Real, standard, unverified by a full build |
| `AndroidManifest.xml` (permissions, accessibility service, mic) | Real |
| `MainActivity` — accessibility status, settings screen, manual "Test Listen" | Real |
| `Settings` — SharedPreferences for backend URL/key, device serial, Picovoice AccessKey | Real |
| `HeyAgentAccessibilityService` — event plumbing, screen dump, **performAction()** (real gesture dispatch), wake-word wiring | Real |
| `BackendClient` — POST to `/agent/chat` | Real, uses OkHttp + org.json |
| `CommandInterpreter` — SpeechRecognizer → BackendClient | Real |
| `ContinuousWakeWordListener` + `VoiceActivityGate` — two-stage: cheap `AudioRecord` energy gate before SpeechRecognizer, no account needed | Real — this is the **default** wake-word implementation; see [docs/wake-word-power-optimization.md](docs/wake-word-power-optimization.md) for why it's two-stage and how to tune it |
| `PorcupineWakeWordListener` | Real, written against Porcupine's documented API shape — **not compiled against the real SDK artifact** (no network dependency fetch available here); treat any first-build errors in this one file as the SDK's actual API differing slightly from what's written. Only used if you save a Picovoice AccessKey in Settings |

## Your part — step by step

### 1. Open the project and get it compiling
- Install Android Studio if you don't have it (you do — it's already at
  `C:\Program Files\Android\Android Studio`).
- Open `mobile-agent/android/` as a project. Let it sync — this generates the
  real `gradle-wrapper.jar` (not committed here, Android Studio creates it)
  and downloads androidx/Material/OkHttp/Porcupine.
- Fix whatever the sync/first build surfaces. Most likely spot: `WakeWordListener.kt`
  if Porcupine's real API differs from what's written (flagged above) — but
  even if that whole file's Porcupine class is broken, `ContinuousWakeWordListener`
  in the same file doesn't depend on it and should be unaffected.

### 2. Wake-word model — OPTIONAL, skip if you don't have a Picovoice AccessKey
The app works without this (defaults to `ContinuousWakeWordListener`, no
account needed). Only do this if you got a Picovoice AccessKey (see the
status note above — signup is gated to company/institutional emails now):
1. In console.picovoice.ai, under **AccessKey**, copy your key — you'll paste
   this into the app later, not into any file in this repo.
2. Under **Porcupine → Create Wake Word**, train a model for the phrase
   **"Hey Agent"**, target platform **Android**. Download the resulting
   `.ppn` file.
3. Copy that file into `android/app/src/main/assets/hey_agent.ppn` (that
   exact path/filename — `PorcupineWakeWordListener` expects it). This file
   is yours, not committed to git (same posture as API keys).

### 3. Backend reachability
- Find your laptop's LAN IP (`ipconfig` → IPv4 Address) while the backend is
  running (`uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`, which
  it already does in this project — `--host 0.0.0.0` matters, `localhost`
  won't be reachable from the phone).
- Phone and laptop must be on the same Wi-Fi network.

### 4. Install and configure on-device
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
5. (Optional) Under **Wake word**, paste your Picovoice AccessKey, tap
   **Save AccessKey** — skip this to use the default `ContinuousWakeWordListener`
   instead, no account needed.
6. Tap **Open Accessibility Settings**, find "Hey Agent", enable it. This is
   what actually starts the wake-word listener (see
   `HeyAgentAccessibilityService.onServiceConnected()`) — do this LAST, after
   steps 2–5, since mic permission needs to already be granted (step 4) for
   the listener (Porcupine or the default) to start successfully when the
   service auto-connects.

### 5. Say "Hey Agent" from inside any app
If all of the above is done, this should now work ambiently. If it doesn't,
check Logcat filtered to `HeyAgentA11yService` / `WakeWordListener` /
`CommandInterpreter` — every failure path in this codebase logs rather than
silently swallowing errors.
