package com.mobileagent.heyagent

import android.accessibilityservice.AccessibilityService
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Cross-app control surface — the same capability screen readers and "Hey
 * Google"-style assistants use to read and act on whatever app is currently
 * in the foreground, without that app needing to expose any special API.
 *
 * SKELETON STATUS: event plumbing + a read-only screen dump are real; actual
 * gesture/text-entry execution and the tap-to-element-id mapping used by the
 * backend's Deploy pipeline (see backend/perception/xml_parser.py,
 * backend/agent/executor.py) are NOT ported here yet — see performAction()
 * below.
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

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "Hey Agent accessibility service connected")
        // TODO: start WakeWordListener here once the Porcupine integration
        // (see WakeWordListener.kt) has real credentials configured.
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
     * TODO (not implemented): execute one action against the current screen,
     * using the SAME action vocabulary the backend already defines —
     * tap / text / swipe / long_press / key_event (see
     * backend/demonstrations/player.py's replay() branches for the
     * reference implementation to mirror). Would use
     * dispatchGesture() for tap/swipe/long_press and
     * AccessibilityNodeInfo.performAction(ACTION_SET_TEXT) for text entry.
     */
    fun performAction(actionType: String, params: Map<String, Any?>) {
        Log.w(TAG, "performAction($actionType, $params) — not implemented in this skeleton")
    }
}
