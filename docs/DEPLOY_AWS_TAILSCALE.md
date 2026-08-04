# Personal deployment: AWS free tier + Tailscale

Single-user setup. The backend runs on a free-tier EC2 box; your phone runs
the agent loop itself and talks to that backend over Tailscale.

Everything scriptable is in `scripts/provision_ec2.sh`. The steps below are
the ones that need your AWS account, your browser, or your phone.

---

## What this is (and why it's shaped this way)

The original design has the **backend** drive the phone over ADB. That can't
work from the cloud — AWS has no route to your phone, and you wouldn't want
it to. So for this deployment the roles are inverted:

```
Phone                                    EC2 (over Tailscale)
─────                                    ────────────────────
"hey agent, search youtube for lofi"
   ↓ wake word + speech-to-text
   ↓ POST /agent/interpret  ──────────→  LLM infers {app_name, task}
   ↓ launch the app
   ↓ read screen (AccessibilityService)
   ↓ POST /agent/decide     ──────────→  LLM picks the next action
   ↓ tap / type / swipe on-device
   └─ repeat until finish
```

The backend only reasons. It never needs ADB, a device, or a privileged
container — which is exactly why it fits on a 1 GB free-tier instance.

Your existing laptop + USB/wireless-ADB setup keeps working unchanged; this
adds a second path rather than replacing one.

---

## What you'll need

- An AWS account still inside the 12-month free tier
- A Tailscale account (free tier covers this — up to 100 devices)
- The Tailscale app on your phone
- ~20 minutes, most of it waiting on `pip install`

**Cost:** $0/month while inside the free tier (750 hrs/month of t2.micro or
t3.micro is one instance running continuously). Outside it, roughly
$8–10/month. LLM API usage is separate and billed by your provider.

---

## 1. Launch the instance

In the EC2 console → **Launch instance**:

| Setting | Value |
|---|---|
| Name | `mobile-agent` |
| AMI | **Ubuntu Server 24.04 LTS** (must show "Free tier eligible") |
| Instance type | **t3.micro** (or t2.micro if t3 isn't free-tier in your region) |
| Key pair | Create one, download the `.pem`, keep it safe |
| Storage | 20 GB gp3 (free tier allows 30 GB — the default 8 GB is tight once ChromaDB's deps land) |

**Network settings — this is the part worth getting right:**

- Allow SSH (port 22) from **My IP** only. Not `0.0.0.0/0`.
- Do **not** add a rule for port 8000.

That second point is deliberate: with Tailscale, the backend is reachable
over the tailnet only. Leaving 8000 closed to the internet means a leaked or
guessed API key still gets an attacker nowhere.

Launch it, then SSH in:

```bash
ssh -i /path/to/your-key.pem ubuntu@<public-ip>
```

## 2. Run the provisioning script

On the instance:

```bash
curl -fsSL https://raw.githubusercontent.com/vedhakoushik/mobile-agent/main/scripts/provision_ec2.sh -o provision.sh
bash provision.sh
```

It creates swap (needed — `pip install chromadb` gets OOM-killed on 1 GB
without it), installs Python deps, clones the repo, installs Tailscale, sets
up a `mobile-agent` systemd service, and generates an `API_KEY`.

It prints that API key at the end. Note it down — the phone needs it.

## 3. Add your LLM key

```bash
nano ~/mobile-agent/.env      # set GEMINI_API_KEY=...
```

Any supported provider works (`gemini`, `openai`, `anthropic`, `cerebras`,
`glm`); set `LLM_PROVIDER` to match. Note that `ollama` is *not* practical
here — a local model won't run in 1 GB.

> Gemini's free tier is **20 requests/day per project**. Each round of the
> agent loop is one request, so a handful of tasks exhausts it. If you hit
> `429 RESOURCE_EXHAUSTED`, that's the daily cap, not a bug — this already
> bit us during local testing.

## 4. Join the tailnet

```bash
sudo tailscale up
```

Open the printed URL, sign in, approve the machine. Then:

```bash
tailscale ip -4        # e.g. 100.101.102.103 — this is your backend address
```

## 5. Start the backend

```bash
sudo systemctl start mobile-agent
systemctl status mobile-agent --no-pager
```

Confirm it's serving (from the instance):

```bash
curl -s localhost:8000/api/v1/health
# {"status":"ok"}
```

## 6. Point your phone at it

1. Install **Tailscale** from the Play Store, sign in with the same account,
   connect.
2. Open **Hey Agent** and set:
   - **Backend URL:** `http://<tailscale-ip-from-step-4>:8000`
   - **API_KEY:** the key from step 2
   - **Device serial:** leave blank
3. **Save settings**.
4. Tap **Test Listen** and say something like *"search for lofi music on
   youtube"*.

The accessibility service must be enabled for this to do anything — the app
performs the taps itself now, so it needs that permission. If it isn't on,
Test Listen will say so.

## 7. Go hands-free

Once Test Listen works, enable the accessibility service (if you haven't) and
just say **"hey agent …"** from any app.

---

## Checking on it

```bash
journalctl -u mobile-agent -f          # live logs
sudo systemctl restart mobile-agent    # after editing .env
curl -s localhost:8000/api/v1/device/health/detailed -H "X-API-Key: $(grep '^API_KEY=' ~/mobile-agent/.env | cut -d= -f2-)"
```

`neo4j: {"reachable": false}` in that output is expected and fine — the
navigation graph is optional, fail-soft, and deliberately not installed here
(it doesn't fit in 1 GB alongside everything else).

To deploy code changes:

```bash
cd ~/mobile-agent && git pull && sudo systemctl restart mobile-agent
```

---

## If something doesn't work

| Symptom | Likely cause |
|---|---|
| Phone: "failed to connect … after 10000ms" | Tailscale not connected on one end. Check `tailscale status` on EC2 and that the phone's Tailscale toggle is on. |
| `pip` dies with "Killed", no traceback | Out of memory — swap wasn't created. Re-run the provisioning script. |
| 401 from the phone | API_KEY mismatch between `.env` and the app. |
| 429 / `RESOURCE_EXHAUSTED` | LLM provider daily quota (see step 3). |
| Agent does nothing after "Heard: …" | Accessibility service disabled — it can't tap without it. |
| Service won't start | `journalctl -u mobile-agent -n 50 --no-pager` |

---

## Security notes

Worth being explicit about, since this is a tool that can drive your phone.

- **Nothing is exposed publicly.** No inbound port for the backend; Tailscale
  is the only path in, and it's encrypted end to end.
- **The API key still matters.** It's the only thing standing between anyone
  else on your tailnet and your phone. Don't share the tailnet.
- **Don't skip Tailscale and open port 8000 instead.** That would put an
  endpoint that can control your phone on the public internet behind a single
  static key.
- **The web frontend is not deployed here, on purpose.** Vite inlines
  `VITE_API_KEY` into the JS bundle, so anyone who loads the page can read
  the key. Fine on localhost, not fine on a public box. See
  `docs/DEPLOYMENT.md` for what a multi-user setup would need instead.
