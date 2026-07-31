package com.mobileagent.heyagent

import android.util.Log
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

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
}

data class ChatResult(val sessionId: String, val appName: String, val task: String)
