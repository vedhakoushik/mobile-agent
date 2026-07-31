package com.mobileagent.heyagent

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Skeleton entry screen. Its only job is directing the user to enable
 * [HeyAgentAccessibilityService] under system Settings — Android requires
 * that be a manual, explicit user action, it can never be granted from code.
 *
 * Built programmatically (no layout XML) to keep this skeleton's resource
 * surface minimal while the rest of the pipeline is stubbed out.
 */
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
        }

        val status = TextView(this).apply {
            text = if (isAccessibilityServiceEnabled()) {
                "Hey Agent accessibility service: ENABLED"
            } else {
                getString(R.string.enable_accessibility_prompt)
            }
            gravity = Gravity.CENTER
        }
        root.addView(status)

        val openSettingsButton = Button(this).apply {
            text = getString(R.string.open_accessibility_settings)
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }
        root.addView(openSettingsButton)

        setContentView(root)
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val expectedComponent = "$packageName/${HeyAgentAccessibilityService::class.java.name}"
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        val splitter = TextUtils.SimpleStringSplitter(':').apply { setString(enabledServices) }
        while (splitter.hasNext()) {
            if (splitter.next().equals(expectedComponent, ignoreCase = true)) return true
        }
        return false
    }
}
