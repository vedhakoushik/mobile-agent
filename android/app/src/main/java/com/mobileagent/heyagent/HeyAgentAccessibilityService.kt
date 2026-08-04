package com.mobileagent.heyagent

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlin.concurrent.thread

/**
 * Cross-app control surface — the same capability screen readers and "Hey
 * Google"-style assistants use to read and act on whatever app is currently
 * in the foreground, without that app needing to expose any special API.
 *
 * This is also where the full ambient chain gets wired together:
 * ContinuousWakeWordListener detects "Hey Agent" -> CommandInterpreter
 * listens for the rest of the utterance (unless it was already caught in the
 * same breath, see WakeWordListener's remainderText) -> BackendClient sends
 * it to the backend's /agent/chat endpoint. Starts automatically as soon as
 * the accessibility service is enabled — no external account needed, see
 * ContinuousWakeWordListener's doc comment for how it works.
 */
class HeyAgentAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "HeyAgentA11yService"

        // Set by the OS once the service is bound & connected; other
        // components (WakeWordListener, CommandInterpreter) will read this to
        // reach the live instance. Null whenever the user hasn't enabled the
        // service in Settings > Accessibility.
        var instance: HeyAgentAccessibilityService? = null
            private set
    }

    private var wakeWordListener: WakeWordListener? = null
    private var commandInterpreter: CommandInterpreter? = null
    private var agentLoop: OnDeviceAgentLoop? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "Hey Agent accessibility service connected")
        startWakeWordListening()
    }

    private fun startWakeWordListening() {
        val listener = ContinuousWakeWordListener(this)
        wakeWordListener = listener
        listener.start { remainderText -> onWakeWordDetected(remainderText) }
    }

    /**
     * @param remainderText Command text already captured in the same breath
     *   as the wake phrase, when the user said the whole thing in one go
     *   ("hey agent send a message to ramu"). When present, skip the extra
     *   listen and dispatch straight away.
     */
    private fun onWakeWordDetected(remainderText: String?) {
        if (!Settings.isConfigured(this)) {
            Log.w(TAG, "Wake word heard but no backend URL configured in Settings")
            return
        }

        if (!remainderText.isNullOrBlank()) {
            Log.i(TAG, "Wake word + command in one breath: \"$remainderText\"")
            runCommand(remainderText)
            return
        }

        // Wake phrase alone — listen for the command as a second utterance.
        val client = BackendClient(
            baseUrl = Settings.getBaseUrl(this), apiKey = Settings.getApiKey(this)
        )
        val interpreter = CommandInterpreter(this, client, onTranscript = { spoken ->
            runCommand(spoken)
        })
        commandInterpreter = interpreter
        interpreter.listenForCommand()
    }

    /**
     * Run a spoken command end to end on this device.
     *
     * The backend only interprets and decides; every tap/swipe/keystroke
     * happens here via performAction(). That's what lets the backend live in
     * the cloud, where it has no ADB path to this phone.
     */
    fun runCommand(spoken: String) {
        val client = BackendClient(
            baseUrl = Settings.getBaseUrl(this), apiKey = Settings.getApiKey(this)
        )
        val loop = OnDeviceAgentLoop(this, client)
        agentLoop = loop

        // interpretSync blocks on the network, so keep it off the main thread.
        thread(name = "HeyAgentInterpret") {
            val (appName, task) = try {
                client.interpretSync(spoken)
            } catch (e: Exception) {
                Log.e(TAG, "interpret failed: ${e.message}")
                return@thread
            }
            Log.i(TAG, "Understood: task='$task' app='$appName'")
            loop.start(task, appName) { event -> Log.i(TAG, event) }
        }
    }

    fun stopAgentLoop() {
        agentLoop?.stop()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // TODO: on window-state/content-change events, snapshot the current
        // screen (dumpVisibleElements()) and feed it to whatever is waiting
        // on the next command's element-grounding step. Left as a no-op for
        // the skeleton — CommandInterpreter currently talks to the backend's
        // /agent/chat endpoint instead, which does its own screen capture
        // over ADB (see backend/api/routers/agent.py's start_chat).
    }

    override fun onInterrupt() {
        Log.w(TAG, "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        wakeWordListener?.stop()
        wakeWordListener = null
        commandInterpreter?.release()
        commandInterpreter = null
        instance = null
    }

    /**
     * Read-only dump of the current screen's interactive nodes — the
     * on-device analog of backend/perception/xml_parser.py's element list,
     * but sourced from the live accessibility tree instead of `adb shell
     * uiautomator dump`. Not yet wired into any command-execution path.
     */
    fun dumpVisibleElements(): List<AccessibilityNodeInfo> {
        val root = rootInActiveWindow ?: return emptyList()
        val elements = mutableListOf<AccessibilityNodeInfo>()
        collectInteractive(root, elements)
        return elements
    }

    private fun collectInteractive(node: AccessibilityNodeInfo, out: MutableList<AccessibilityNodeInfo>) {
        if (node.isClickable || node.isEditable || node.isScrollable) {
            out.add(node)
        }
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectInteractive(it, out) }
        }
    }

    /**
     * Execute one action against the current screen. Mirrors the SAME action
     * vocabulary + timings the backend already uses (see
     * backend/device/controller.py's tap/text/swipe/long_press — this is a
     * deliberate 1:1 port so behavior is consistent whether an action came
     * from the ADB-based backend or ran locally through this service).
     *
     * Expected params per actionType (all values are boxed Int/String):
     *   "tap"         -> {"x": Int, "y": Int}
     *   "long_press"  -> {"x": Int, "y": Int}
     *   "swipe"       -> {"direction": String ("up"|"down"|"left"|"right"),
     *                      "from_x": Int?, "from_y": Int?}
     *   "text"        -> {"content": String}  — sets text on the currently
     *                      FOCUSED editable node; caller must tap the target
     *                      field first (a separate "tap" action) so Android
     *                      has something focused to write into
     *   "back"        -> {} (no params)
     *
     * "key_event" from the backend's vocabulary is NOT supported here —
     * AccessibilityService has no equivalent to `adb shell input keyevent
     * <code>` for arbitrary key codes, only performGlobalAction() constants
     * (back/home/recents/...). "back" covers the one keyevent this project
     * actually uses (KEYCODE_BACK); anything else logs a warning and no-ops.
     */
    fun performAction(actionType: String, params: Map<String, Any?>) {
        when (actionType) {
            "tap" -> {
                val x = (params["x"] as? Int) ?: return warnMissingParam("tap", "x")
                val y = (params["y"] as? Int) ?: return warnMissingParam("tap", "y")
                dispatchTap(x, y, durationMs = 100L)
            }
            "long_press" -> {
                val x = (params["x"] as? Int) ?: return warnMissingParam("long_press", "x")
                val y = (params["y"] as? Int) ?: return warnMissingParam("long_press", "y")
                dispatchTap(x, y, durationMs = 1000L)
            }
            "swipe" -> {
                val direction = (params["direction"] as? String) ?: "up"
                val fromX = params["from_x"] as? Int
                val fromY = params["from_y"] as? Int
                dispatchSwipe(direction, fromX, fromY)
            }
            "text" -> {
                val content = (params["content"] as? String)
                    ?: return warnMissingParam("text", "content")
                setTextOnFocusedNode(content)
            }
            "back" -> {
                performGlobalAction(GLOBAL_ACTION_BACK)
            }
            else -> {
                Log.w(TAG, "performAction: unsupported actionType='$actionType' (params=$params)")
            }
        }
    }

    private fun warnMissingParam(actionType: String, param: String) {
        Log.w(TAG, "performAction($actionType): missing required param '$param'")
    }

    // ── Gesture dispatch (tap / long_press / swipe) ──────────────────────────

    private fun dispatchTap(x: Int, y: Int, durationMs: Long) {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        dispatchGesture(
            GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0, durationMs))
                .build(),
            null,
            null,
        )
    }

    private fun dispatchSwipe(direction: String, fromX: Int?, fromY: Int?) {
        val bounds = rootInActiveWindow?.let { android.graphics.Rect().apply { it.getBoundsInScreen(this) } }
        val width = bounds?.width()?.takeIf { it > 0 } ?: 1080
        val height = bounds?.height()?.takeIf { it > 0 } ?: 2400

        // Same deltas as backend/device/controller.py's swipe() — kept in
        // sync deliberately so a swipe behaves the same whether it ran over
        // ADB or locally through this service.
        val (dx, dy) = when (direction) {
            "up" -> 0 to -500
            "down" -> 0 to 500
            "left" -> -400 to 0
            "right" -> 400 to 0
            else -> 0 to 0
        }
        val x1 = fromX ?: (width / 2)
        val y1 = fromY ?: (height / 2)
        val x2 = (x1 + dx).coerceIn(0, width)
        val y2 = (y1 + dy).coerceIn(0, height)

        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        dispatchGesture(
            GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0, 300L))
                .build(),
            null,
            null,
        )
    }

    // ── Text entry ────────────────────────────────────────────────────────────

    private fun setTextOnFocusedNode(content: String) {
        val focused = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        if (focused == null) {
            Log.w(TAG, "performAction(text): no focused input field — tap the field first")
            return
        }
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, content)
        }
        focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }
}
