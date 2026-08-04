package com.mobileagent.heyagent

import android.util.Log
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Talks to the mobile-agent FastAPI backend's conversational endpoint
 * (POST /api/v1/agent/chat — see backend/api/routers/agent.py's start_chat)
 * over the local network. This reuses the SAME intent-inference + Deploy
 * pipeline the web Chat page (frontend/src/pages/ChatPage.tsx) already
 * drives — voice is just a different front door onto it.
 *
 * IMPORTANT limitation carried over from the wider "Hey Agent" design: the
 * backend controls the phone via ADB from wherever it's running (a laptop on
 * the same network), not via this app directly. So this skeleton's
 * BackendClient path assumes a companion-device setup (phone listens for the
 * wake word, backend on a laptop executes the task on this same phone over
 * ADB) — it does NOT yet perform actions locally via
 * HeyAgentAccessibilityService.performAction(). Wiring voice commands
 * straight into the on-device AccessibilityService (no laptop/ADB required)
 * is the natural next step once this skeleton is validated end-to-end.
 *
 * CONFIGURATION: baseUrl and apiKey are NOT hardcoded here — there is no
 * secrets file to load them from on-device yet (TODO: a settings screen or
 * local.properties-driven BuildConfig field). Callers must supply both.
 */
class BackendClient(
    private val baseUrl: String,
    private val apiKey: String?,
) {
    private val client = OkHttpClient()

    fun sendChatCommand(
        message: String,
        deviceSerial: String? = null,
        onResult: (Result<ChatResult>) -> Unit,
    ) {
        val body = JSONObject().apply {
            put("message", message)
            if (deviceSerial != null) put("device_serial", deviceSerial)
        }

        val requestBuilder = Request.Builder()
            .url("$baseUrl/api/v1/agent/chat")
            .post(body.toString().toRequestBody("application/json".toMediaType()))
        if (apiKey != null) {
            requestBuilder.addHeader("X-API-Key", apiKey)
        }

        client.newCall(requestBuilder.build()).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("BackendClient", "chat request failed", e)
                onResult(Result.failure(e))
            }

            override fun onResponse(call: Call, response: okhttp3.Response) {
                response.use {
                    val text = it.body?.string().orEmpty()
                    if (!it.isSuccessful) {
                        onResult(Result.failure(IOException("HTTP ${it.code}: $text")))
                        return
                    }
                    try {
                        val json = JSONObject(text)
                        onResult(
                            Result.success(
                                ChatResult(
                                    sessionId = json.getString("session_id"),
                                    appName = json.getString("app_name"),
                                    task = json.getString("task"),
                                ),
                            ),
                        )
                    } catch (e: Exception) {
                        onResult(Result.failure(e))
                    }
                }
            }
        })
    }

    /**
     * Turn free speech into {app_name, task} without starting anything.
     *
     * Synchronous, same reasoning as decideSync — call off the main thread.
     * Uses /agent/interpret rather than /agent/chat because chat also spins
     * up an ADB Deploy run, which a cloud backend with no phone attached
     * cannot do.
     */
    fun interpretSync(message: String): Pair<String, String> {
        val body = JSONObject().apply { put("message", message) }
        val requestBuilder = Request.Builder()
            .url("$baseUrl/api/v1/agent/interpret")
            .post(body.toString().toRequestBody("application/json".toMediaType()))
        if (apiKey != null) requestBuilder.addHeader("X-API-Key", apiKey)

        decideClient.newCall(requestBuilder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException("HTTP ${response.code}: $text")
            val json = JSONObject(text)
            return json.getString("app_name") to json.getString("task")
        }
    }

    /**
     * Ask the backend for the next action, given the current screen.
     *
     * Synchronous on purpose: OnDeviceAgentLoop already runs on its own
     * background thread, and a read -> decide -> act -> repeat loop written
     * with chained async callbacks would be far harder to follow and to stop
     * cleanly. Never call this from the main thread.
     */
    fun decideSync(
        task: String,
        appName: String,
        elements: List<ScreenElement>,
        roundNum: Int,
        maxRounds: Int,
        history: List<RoundRecord>,
    ): AgentDecision {
        val body = JSONObject().apply {
            put("task", task)
            put("app_name", appName)
            put("elements", ScreenElement.toJsonArray(elements))
            put("round_num", roundNum)
            put("max_rounds", maxRounds)
            put("history", JSONArray().apply { history.forEach { put(it.toJson()) } })
        }

        val requestBuilder = Request.Builder()
            .url("$baseUrl/api/v1/agent/decide")
            .post(body.toString().toRequestBody("application/json".toMediaType()))
        if (apiKey != null) requestBuilder.addHeader("X-API-Key", apiKey)

        decideClient.newCall(requestBuilder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw IOException("HTTP ${response.code}: $text")
            }
            val json = JSONObject(text)
            return AgentDecision(
                action = json.optString("action"),
                elementId = if (json.isNull("element_id")) null else json.optInt("element_id"),
                textInput = if (json.isNull("text_input")) null else json.optString("text_input"),
                direction = if (json.isNull("direction")) null else json.optString("direction"),
                thought = json.optString("thought"),
                tokensUsed = json.optInt("tokens_used", 0),
                estimatedCostUsd = json.optDouble("estimated_cost_usd", 0.0),
            )
        }
    }

    /**
     * Separate client for /decide: an LLM round trip can take far longer than
     * OkHttp's 10s default read timeout, and the backend additionally retries
     * 429/5xx internally with backoff.
     */
    private val decideClient = OkHttpClient.Builder()
        .callTimeout(90, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .build()
}

data class ChatResult(val sessionId: String, val appName: String, val task: String)

data class AgentDecision(
    val action: String,
    val elementId: Int?,
    val textInput: String?,
    val direction: String?,
    val thought: String,
    val tokensUsed: Int,
    val estimatedCostUsd: Double,
)

/** One completed round, sent back so the model can see what it already did. */
data class RoundRecord(val round: Int, val action: String, val elementId: Int?, val thought: String) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("round", round)
        put(
            "action",
            JSONObject().apply {
                put("action", action)
                if (elementId != null) put("element_id", elementId)
                put("thought", thought)
            },
        )
    }
}
