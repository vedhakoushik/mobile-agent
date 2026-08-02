package com.mobileagent.heyagent

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings as AndroidSettings
import android.text.TextUtils
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

/**
 * Entry screen: directs the user to enable [HeyAgentAccessibilityService]
 * (Android requires that be a manual, explicit user action — it can never be
 * granted from code), holds the backend connection settings, and provides a
 * manual "Test Listen" button so the mic -> backend -> chat pipeline can be
 * validated independently of the wake-word engine (which starts on its own
 * once the accessibility service is enabled — see HeyAgentAccessibilityService).
 *
 * Built programmatically (no layout XML) to keep this skeleton's resource
 * surface minimal while the rest of the pipeline is stubbed out.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var baseUrlInput: EditText
    private lateinit var apiKeyInput: EditText
    private lateinit var deviceSerialInput: EditText
    private lateinit var resultText: TextView
    private var commandInterpreter: CommandInterpreter? = null

    private val requestMicPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) startTestListen() else toast("Microphone permission is required to test listening")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
        }

        statusText = TextView(this).apply { gravity = Gravity.CENTER }
        root.addView(statusText)

        val openSettingsButton = Button(this).apply {
            text = getString(R.string.open_accessibility_settings)
            setOnClickListener {
                startActivity(Intent(AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }
        root.addView(openSettingsButton)

        root.addView(sectionLabel("Backend connection"))

        baseUrlInput = labeledInput(root, "Backend URL", "http://192.168.1.x:8000")
        apiKeyInput = labeledInput(root, "API_KEY (from backend/.env)", "")
        deviceSerialInput = labeledInput(root, "Device serial (optional)", "auto-detect any idle device")

        root.addView(
            Button(this).apply {
                text = "Save settings"
                setOnClickListener { saveSettings() }
            },
        )

        root.addView(sectionLabel("Manual test"))

        root.addView(
            Button(this).apply {
                text = "Test Listen (speak a command)"
                setOnClickListener { onTestListenClicked() }
            },
        )

        resultText = TextView(this).apply { setPadding(0, 24, 0, 0) }
        root.addView(resultText)

        setContentView(root)

        loadSettingsIntoFields()
    }

    override fun onResume() {
        super.onResume()
        // Accessibility enablement happens in a separate Settings screen the
        // user navigates back from, so re-check every time this resumes.
        statusText.text = if (isAccessibilityServiceEnabled()) {
            "Hey Agent accessibility service: ENABLED"
        } else {
            getString(R.string.enable_accessibility_prompt)
        }
    }

    // ── Settings ────────────────────────────────────────────────────────────

    private fun loadSettingsIntoFields() {
        baseUrlInput.setText(Settings.getBaseUrl(this))
        apiKeyInput.setText(Settings.getApiKey(this) ?: "")
        deviceSerialInput.setText(Settings.getDeviceSerial(this) ?: "")
    }

    private fun saveSettings() {
        val baseUrl = baseUrlInput.text.toString().trim()
        if (baseUrl.isBlank()) {
            toast("Backend URL is required")
            return
        }
        Settings.save(
            this,
            baseUrl = baseUrl,
            apiKey = apiKeyInput.text.toString(),
            deviceSerial = deviceSerialInput.text.toString(),
        )
        toast("Saved")
    }

    // ── Manual test-listen flow ──────────────────────────────────────────────

    private fun onTestListenClicked() {
        if (!Settings.isConfigured(this)) {
            toast("Save a backend URL first")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestMicPermission.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        startTestListen()
    }

    private fun startTestListen() {
        resultText.text = "Listening…"
        val client = BackendClient(
            baseUrl = Settings.getBaseUrl(this),
            apiKey = Settings.getApiKey(this),
        )
        val interpreter = CommandInterpreter(this, client, deviceSerial = Settings.getDeviceSerial(this))
        commandInterpreter = interpreter
        interpreter.listenForCommand { result ->
            runOnUiThread {
                result.fold(
                    onSuccess = { r ->
                        resultText.text =
                            "Sent: \"${r.task}\" on ${r.appName}\nsession_id=${r.sessionId}"
                    },
                    onFailure = { e ->
                        resultText.text = "Failed: ${e.message}"
                    },
                )
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        commandInterpreter?.release()
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    private fun sectionLabel(text: String): TextView =
        TextView(this).apply {
            this.text = text
            setPadding(0, 48, 0, 12)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

    private fun labeledInput(root: LinearLayout, label: String, hintText: String): EditText {
        root.addView(
            TextView(this).apply {
                text = label
                setPadding(0, 16, 0, 4)
            },
        )
        val input = EditText(this).apply { hint = hintText }
        root.addView(input)
        return input
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()

    private fun isAccessibilityServiceEnabled(): Boolean {
        val expectedComponent = "$packageName/${HeyAgentAccessibilityService::class.java.name}"
        val enabledServices = AndroidSettings.Secure.getString(
            contentResolver,
            AndroidSettings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        val splitter = TextUtils.SimpleStringSplitter(':').apply { setString(enabledServices) }
        while (splitter.hasNext()) {
            if (splitter.next().equals(expectedComponent, ignoreCase = true)) return true
        }
        return false
    }
}
