plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.mobileagent.heyagent"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.mobileagent.heyagent"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0-skeleton"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("com.google.android.material:material:1.12.0")

    // HTTP client for talking to the mobile-agent FastAPI backend (POST /agent/chat).
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Wake-word engine. Compiling only needs this dependency — the actual
    // AccessKey (console.picovoice.ai, free tier) and a custom "Hey Agent"
    // .ppn wake-word model are supplied at runtime (see Settings.kt /
    // WakeWordListener.kt), not required to build.
    implementation("ai.picovoice:porcupine-android:3.0.3")

    testImplementation("junit:junit:4.13.2")
}
