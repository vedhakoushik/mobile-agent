package com.mobileagent.heyagent

import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Maps the short app names the agent reasons about ("youtube", "gmail") to
 * real Android packages, and launches them.
 *
 * On-device counterpart to backend/device/app_registry.py. Kept in sync with
 * it deliberately: the LLM picks an app_name from the same vocabulary either
 * way, so a name the backend understands must resolve here too.
 *
 * Unlike the backend version, this also falls back to querying the package
 * manager by label, so apps missing from the table can still be found.
 */
object AppRegistry {
    private const val TAG = "AppRegistry"

    private val KNOWN_PACKAGES = mapOf(
        "youtube" to "com.google.android.youtube",
        "gmail" to "com.google.android.gm",
        "mail" to "com.google.android.gm",
        "linkedin" to "com.linkedin.android",
        "chrome" to "com.android.chrome",
        "twitter" to "com.twitter.android",
        "x" to "com.twitter.android",
        "settings" to "com.android.settings",
        "whatsapp" to "com.whatsapp",
        "instagram" to "com.instagram.android",
        "maps" to "com.google.android.apps.maps",
        "messages" to "com.google.android.apps.messaging",
        "playstore" to "com.android.vending",
        "play store" to "com.android.vending",
        "calendar" to "com.google.android.calendar",
        "photos" to "com.google.android.apps.photos",
        "spotify" to "com.spotify.music",
    )

    fun resolvePackage(context: Context, appName: String): String? {
        val key = appName.trim().lowercase()
        KNOWN_PACKAGES[key]?.let { return it }

        // Fall back to a label match over installed apps, so this doesn't hard
        // fail on anything not in the table above.
        return try {
            val pm = context.packageManager
            pm.getInstalledApplications(0)
                .firstOrNull { pm.getApplicationLabel(it).toString().lowercase() == key }
                ?.packageName
        } catch (e: Exception) {
            Log.w(TAG, "package lookup failed for '$appName': ${e.message}")
            null
        }
    }

    /** Bring an app to the foreground. Returns false if it can't be resolved. */
    fun launch(context: Context, appName: String): Boolean {
        val pkg = resolvePackage(context, appName) ?: run {
            Log.w(TAG, "no package for app_name='$appName'")
            return false
        }
        val intent = context.packageManager.getLaunchIntentForPackage(pkg) ?: run {
            Log.w(TAG, "'$pkg' has no launch intent (not installed?)")
            return false
        }
        // An AccessibilityService is not an Activity, so this needs its own task.
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.w(TAG, "failed to launch '$pkg': ${e.message}")
            false
        }
    }
}
