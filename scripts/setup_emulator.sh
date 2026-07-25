#!/usr/bin/env bash
# Creates and boots a headless Android emulator suitable for the agent.
# Requires Android SDK cmdline-tools (avdmanager, emulator) on PATH.
set -euo pipefail

AVD_NAME="${AVD_NAME:-MobileAgent}"
API_LEVEL="${API_LEVEL:-34}"
SYSTEM_IMAGE="system-images;android-${API_LEVEL};google_apis;x86_64"
DEVICE_PROFILE="${DEVICE_PROFILE:-pixel_7_pro}"

echo "== Installing system image: ${SYSTEM_IMAGE} =="
sdkmanager --install "${SYSTEM_IMAGE}" "platform-tools"

if ! avdmanager list avd | grep -q "${AVD_NAME}"; then
  echo "== Creating AVD: ${AVD_NAME} =="
  echo "no" | avdmanager create avd \
    -n "${AVD_NAME}" \
    -k "${SYSTEM_IMAGE}" \
    -d "${DEVICE_PROFILE}" \
    --force
else
  echo "== AVD ${AVD_NAME} already exists, skipping create =="
fi

echo "== Starting emulator headless =="
emulator -avd "${AVD_NAME}" -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect &
EMULATOR_PID=$!

echo "== Waiting for device =="
adb wait-for-device

echo "== Waiting for boot to complete =="
until [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; do
  sleep 2
done

adb shell input keyevent 82   # dismiss keyguard

echo "== Emulator ready (pid ${EMULATOR_PID}) =="
adb devices -l
