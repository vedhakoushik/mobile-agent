package com.mobileagent.heyagent

import android.util.Log
import kotlin.concurrent.thread

/**
 * Runs the agent loop entirely on the phone: read the screen, ask the backend
 * what to do, do it, repeat.
 *
 * This is the mobile counterpart to the backend's run_deploy(). The ADB
 * pipeline needs the backend to reach the device directly, which a cloud
 * deployment cannot do — here the phone owns the loop and the backend only
 * reasons (POST /agent/decide), so the backend can live anywhere.
 *
 * Runs on its own thread and uses synchronous HTTP. Every callback to
 * [onEvent] is invoked from that background thread; callers touching UI must
 * post to the main thread themselves.
 */
class OnDeviceAgentLoop(
    private val service: HeyAgentAccessibilityService,
    private val client: BackendClient,
    private val maxRounds: Int = 15,
) {
    @Volatile private var running = false
    private var worker: Thread? = null

    fun isRunning(): Boolean = running

    /** Ask the loop to stop; it finishes the round in flight and exits. */
    fun stop() {
        running = false
    }

    fun start(task: String, appName: String, onEvent: (String) -> Unit) {
        if (running) {
            onEvent("Already running a task")
            return
        }
        running = true
        worker = thread(name = "OnDeviceAgentLoop") {
            try {
                runLoop(task, appName, onEvent)
            } catch (e: Exception) {
                Log.e(TAG, "loop crashed", e)
                onEvent("Failed: ${e.message}")
            } finally {
                running = false
            }
        }
    }

    private fun runLoop(task: String, appName: String, onEvent: (String) -> Unit) {
        // Bring the target app forward first. Without this the agent reasons
        // about whatever happened to be on screen -- the exact bug that made
        // an early Gmail run spend 20 rounds swiping the notification shade.
        if (!AppRegistry.launch(service, appName)) {
            onEvent("Couldn't launch '$appName' — continuing from the current screen")
        }
        Thread.sleep(APP_LAUNCH_SETTLE_MS)

        val history = mutableListOf<RoundRecord>()
        var totalTokens = 0
        var totalCost = 0.0

        for (round in 0 until maxRounds) {
            if (!running) {
                onEvent("Stopped after $round round(s)")
                return
            }

            val elements = ScreenElement.fromNodes(service.dumpVisibleElements())
            if (elements.isEmpty()) {
                Log.w(TAG, "round $round: no interactive elements found")
            }

            val decision = try {
                client.decideSync(task, appName, elements, round, maxRounds, history)
            } catch (e: Exception) {
                onEvent("Backend error: ${e.message}")
                return
            }

            totalTokens += decision.tokensUsed
            totalCost += decision.estimatedCostUsd
            onEvent("R$round ${decision.action.uppercase()} — ${decision.thought.take(90)}")

            if (decision.action == "finish") {
                onEvent("Done in ${round + 1} round(s) · $totalTokens tokens · $${"%.4f".format(totalCost)}")
                return
            }

            if (!execute(decision, elements)) {
                onEvent("Couldn't execute '${decision.action}' — stopping")
                return
            }

            history.add(
                RoundRecord(round, decision.action, decision.elementId, decision.thought.take(100))
            )
            Thread.sleep(ACTION_SETTLE_MS)
        }
        onEvent("Hit the $maxRounds-round limit without finishing")
    }

    /** Translate a decision into a real gesture. Returns false if it can't. */
    private fun execute(decision: AgentDecision, elements: List<ScreenElement>): Boolean {
        val target = decision.elementId?.let { id -> elements.find { it.id == id } }

        return when (decision.action) {
            "tap", "long_press" -> {
                if (target == null) {
                    Log.w(TAG, "${decision.action} with unknown element_id=${decision.elementId}")
                    return false
                }
                service.performAction(
                    decision.action,
                    mapOf("x" to target.centerX, "y" to target.centerY),
                )
                true
            }

            "text" -> {
                val content = decision.textInput ?: return false
                // Focus the field first: performAction("text") writes into
                // whatever currently holds input focus, which may not be the
                // element the model picked.
                if (target != null) {
                    service.performAction("tap", mapOf("x" to target.centerX, "y" to target.centerY))
                    Thread.sleep(FOCUS_SETTLE_MS)
                }
                service.performAction("text", mapOf("content" to content))
                true
            }

            "swipe" -> {
                service.performAction(
                    "swipe",
                    mapOf(
                        "direction" to (decision.direction ?: "up"),
                        "from_x" to target?.centerX,
                        "from_y" to target?.centerY,
                    ),
                )
                true
            }

            "back" -> {
                service.performAction("back", emptyMap())
                true
            }

            // "escalate" asks for a screenshot, which this path can't supply
            // yet (the backend prompt offers it for the vision-capable ADB
            // flow). Treat it as "look further" rather than failing the run.
            "escalate" -> {
                service.performAction("swipe", mapOf("direction" to "up"))
                true
            }

            else -> {
                Log.w(TAG, "unsupported action '${decision.action}'")
                false
            }
        }
    }

    companion object {
        private const val TAG = "OnDeviceAgentLoop"
        private const val APP_LAUNCH_SETTLE_MS = 2000L
        private const val ACTION_SETTLE_MS = 1200L
        private const val FOCUS_SETTLE_MS = 400L
    }
}
