package com.mobileagent.heyagent

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject

/**
 * One interactive element on screen.
 *
 * Deliberately mirrors the shape produced by the backend's
 * perception/xml_parser.py (`id`, `class_name`, `text`, `content_desc`,
 * `resource_id`) so /agent/decide can feed it straight into the same prompt
 * builder used by the ADB pipeline. `bounds` is kept on-device only — the
 * model picks an element by id, and we translate that id back into a tap
 * coordinate here.
 */
data class ScreenElement(
    val id: Int,
    val className: String,
    val text: String,
    val contentDesc: String,
    val resourceId: String,
    val bounds: Rect,
    /** Kept so text entry can focus the right field before typing. */
    val node: AccessibilityNodeInfo? = null,
) {
    val centerX: Int get() = bounds.centerX()
    val centerY: Int get() = bounds.centerY()

    fun toJson(): JSONObject = JSONObject().apply {
        put("id", id)
        put("class_name", className)
        put("text", text)
        put("content_desc", contentDesc)
        put("resource_id", resourceId)
    }

    companion object {
        /**
         * Build the element list the backend will reason over.
         *
         * Two details matter for correctness, both copied from
         * xml_parser.py so the two paths agree:
         *  - zero-area nodes are dropped (they can't be tapped and only add
         *    prompt noise)
         *  - ordering is top-to-bottom, then left-to-right, and ids are
         *    assigned after sorting, so "element 3" means the same thing to
         *    the model as it does to us
         */
        fun fromNodes(nodes: List<AccessibilityNodeInfo>): List<ScreenElement> {
            val rect = Rect()
            val withBounds = nodes.mapNotNull { node ->
                node.getBoundsInScreen(rect)
                val b = Rect(rect)
                if (b.width() <= 0 || b.height() <= 0) return@mapNotNull null
                Triple(node, b, b.top * 100000L + b.left)
            }
            return withBounds
                .sortedBy { it.third }
                .mapIndexed { index, (node, b, _) ->
                    ScreenElement(
                        id = index + 1,
                        className = node.className?.toString().orEmpty(),
                        text = node.text?.toString().orEmpty(),
                        contentDesc = node.contentDescription?.toString().orEmpty(),
                        resourceId = node.viewIdResourceName.orEmpty(),
                        bounds = b,
                        node = node,
                    )
                }
        }

        fun toJsonArray(elements: List<ScreenElement>): JSONArray =
            JSONArray().apply { elements.forEach { put(it.toJson()) } }
    }
}
