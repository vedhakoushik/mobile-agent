# Hey Agent — ambient voice assistant (skeleton)

Companion Android app for mobile-agent: a "Hey Google"-style ambient assistant
that listens for a wake phrase from inside ANY app and executes the resulting
command through the same automation pipeline the web UI already drives.

**Status: non-functional skeleton.** Project structure, manifest, and class
shapes are in place and reviewed for correctness; the wake-word engine is not
wired up (needs an external account, see below) and no gesture/text-entry
execution has been ported to this app yet. Verification note: this was built
without a working `java`/`gradle` CLI on the authoring machine — a JDK 21 was
found bundled inside the installed Android Studio and used to sanity-check
the toolchain, but a full `./gradlew build` was **not** run. Open this in
Android Studio and let it sync before trusting it compiles.

## Architecture

```
"Hey Agent, send Ramu a message" (spoken while inside YouTube)
        │
        ▼
WakeWordListener (Porcupine, on-device)  ──not wired up──▶  [TODO]
        │ detects wake phrase
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
must be reachable on the same network as the phone. A "fully local, no
laptop" version would instead route straight into
`HeyAgentAccessibilityService.performAction()` and never leave the device —
that's the natural v2, but requires porting the tap/text/swipe action
executor (`backend/agent/executor.py`) to Kotlin. Left as-is for this
skeleton since the user's brief was explicitly "local ON SETUP" (no cloud
wake-word/STT dependency), not "no laptop at all."

## What's real vs. stubbed

| Piece | Status |
|---|---|
| Gradle/AGP/Kotlin project structure | Real, standard, unverified by a full build |
| `AndroidManifest.xml` (permissions, accessibility service declaration) | Real |
| `MainActivity` — checks/opens Accessibility settings | Real, should work as written |
| `HeyAgentAccessibilityService` — event plumbing, read-only screen dump | Real; `performAction()` is a stub (logs only) |
| `BackendClient` — POST to `/agent/chat` | Real, uses OkHttp + org.json (no extra JSON dep) |
| `CommandInterpreter` — SpeechRecognizer -> BackendClient | Real, untested on-device |
| `WakeWordListener` | Interface only — `UnimplementedWakeWordListener` is a no-op |

## Setup to actually run this

1. **Open in Android Studio**, let it sync (this generates the real
   `gradle-wrapper.jar` this repo doesn't ship — it wasn't hand-written here
   to avoid guessing at a binary artifact).
2. Fix whatever the first sync surfaces — AGP/Gradle/Kotlin version pins in
   `build.gradle.kts` / `app/build.gradle.kts` were chosen for currency as of
   this writing but weren't build-verified.
3. **Wake-word engine**: sign up at console.picovoice.ai (free tier), get an
   AccessKey, train a custom "Hey Agent" wake-word model (.ppn file — the
   built-in word list doesn't include it). Uncomment the Porcupine dependency
   in `app/build.gradle.kts` and implement `WakeWordListener` for real. Do
   NOT commit the AccessKey or .ppn file to git — same posture as
   `backend/.env`.
4. **Backend reachability**: `BackendClient` needs a `baseUrl` pointing at
   wherever `backend/api/main.py` is running (e.g. `http://192.168.1.x:8000`)
   and the same `API_KEY` value from `backend/.env`. No settings screen exists
   yet to configure these on-device — currently the caller must supply both
   directly (see `BackendClient`'s constructor).
5. Enable the accessibility service: install the app, open it, tap "Open
   Accessibility Settings", enable "Hey Agent".
