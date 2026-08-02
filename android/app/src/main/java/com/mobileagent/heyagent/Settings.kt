package com.mobileagent.heyagent

import android.content.Context

/**
 * On-device configuration for reaching the mobile-agent backend — replaces
 * the "caller must supply both" placeholder BackendClient originally shipped
 * with. Values are entered once in MainActivity and persisted locally.
 *
 * Deliberately NOT using EncryptedSharedPreferences here: this is a
 * single-user local-dev tool (same posture as frontend/src/api/client.ts's
 * VITE_API_KEY, see that file's doc comment) rather than a hardened secrets
 * store. If this app is ever distributed beyond your own device, revisit
 * that.
 */
object Settings {
    private const val PREFS_NAME = "hey_agent_settings"
    private const val KEY_BASE_URL = "backend_base_url"
    private const val KEY_API_KEY = "backend_api_key"
    private const val KEY_DEVICE_SERIAL = "device_serial"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getBaseUrl(context: Context): String =
        prefs(context).getString(KEY_BASE_URL, "") ?: ""

    fun getApiKey(context: Context): String? =
        prefs(context).getString(KEY_API_KEY, null)?.takeIf { it.isNotBlank() }

    fun getDeviceSerial(context: Context): String? =
        prefs(context).getString(KEY_DEVICE_SERIAL, null)?.takeIf { it.isNotBlank() }

    fun save(context: Context, baseUrl: String, apiKey: String, deviceSerial: String) {
        prefs(context).edit()
            .putString(KEY_BASE_URL, baseUrl.trim().trimEnd('/'))
            .putString(KEY_API_KEY, apiKey.trim())
            .putString(KEY_DEVICE_SERIAL, deviceSerial.trim())
            .apply()
    }

    fun isConfigured(context: Context): Boolean = getBaseUrl(context).isNotBlank()
}
