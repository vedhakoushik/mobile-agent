# Wake-word power optimization

How `ContinuousWakeWordListener` avoids running full speech-to-text
continuously, and why the "proper" low-power path isn't available to this
app.

## Why not Android's real hardware wake-word path

Android exposes DSP-level, near-zero-power hotword detection to apps via
[`AlwaysOnHotwordDetector`](https://source.android.com/docs/core/audio/sound-trigger)
— this is the actual mechanism "Hey Google" uses (a dedicated low-power
audio co-processor stays awake while the main CPU sleeps, listening for one
specific acoustic pattern).

It's not usable here: `AlwaysOnHotwordDetector` is only available to an app
registered as the device's system `VoiceInteractionService` — effectively
"be the phone's default assistant app," which requires the user to replace
their configured assistant (Google Assistant, Bixby, etc.) with this app.
That's a different, much heavier integration than an accessibility-service
add-on, and gated by Android in ways a third-party hobby app generally can't
clear. Confirmed via Android's own docs before ruling it out, not assumed.

## What's implemented instead: a two-stage software pipeline

Same shape as the hardware version, implemented at the app level:

```
[ AudioRecord, 16kHz mono PCM ]
        │  continuous, cheap — no STT engine running
        ▼
┌────────────────────────────────┐
│ Stage 1: VoiceActivityGate     │  RMS energy vs. adaptive noise floor
└──────────────┬─────────────────┘
               │ energy > noiseFloor × 2.5, sustained 3 frames
               ▼
┌────────────────────────────────┐
│ Stage 2: SpeechRecognizer       │  real STT — only runs when Stage 1 fired
│ (checks transcript for          │
│  "hey agent")                   │
└──────────────┬─────────────────┘
               │ session ends (match or not)
               ▼
        back to Stage 1
```

`backend/device/controller.py`-style fail-soft posture applies here too:
if `AudioRecord` can't initialize (unsupported sample rate, permission
missing), `VoiceActivityGate` logs a warning and stops rather than crashing
the accessibility service.

## What this buys, and what it doesn't

- **Does**: SpeechRecognizer — the expensive part (real STT, often
  network-backed even with `EXTRA_PREFER_OFFLINE`) — only starts when
  there's actually sound above ambient noise. Long silent stretches (most of
  a typical day) cost only the Stage 1 `AudioRecord` loop, not a live STT
  session.
- **Doesn't**: reach the near-zero power of a dedicated DSP chip.
  `AudioRecord` + RMS math still runs on the main CPU continuously, just
  much cheaper than STT. This is the realistic ceiling for a third-party app
  without the `VoiceInteractionService` integration above.

## Tuning

Both knobs are constructor parameters on `VoiceActivityGate`:

- `sensitivityMultiplier` (default `2.5`): how many times louder than the
  ambient noise floor counts as "someone's talking." Lower = more sensitive
  (more false Stage-2 wakeups from background noise); higher = less
  sensitive (may miss quiet speech).
- `consecutiveFramesRequired` (default `3`): how many consecutive loud
  frames before firing — filters single-frame spikes (a knock, a door) from
  sustained speech.

If Stage 2 is firing too often on non-speech noise, raise
`sensitivityMultiplier` or `consecutiveFramesRequired` first before assuming
something's broken — a noisy room (traffic, AC) will do this by design.
