[app]

# (str) Title of your application
title = Switch Demonstrator

# (str) Package name
package.name = switchdemo

# (str) Package domain (needed for android/ios packaging)
package.domain = org.ssay.switch

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,mp3,json

# (str) Application versioning
version = 1.0.0

# (str) Icon of the application
icon.filename = %(source.dir)s/ELMOS_LOGO.png

# (list) Application requirements
# CRUCIAL: pyjnius is required for bleak. Kivy pinned to 2.3.0 for stability.
requirements = python3,kivy==2.3.0,pyjnius,bleak,android

# (str) Supported orientations (landscape, sensorPortrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# --- Android specific ---

# (list) Permissions
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (bool) If True, then skip trying to update the Android sdk
android.skip_update = False

# (bool) If True, then automatically accept SDK license agreements.
android.accept_sdk_license = True

# (bool) Enable AndroidX support (CRUCIAL for API 33+)
android.enable_androidx = True

# (list) The Android archs to build for
# CRUCIAL: Limit to arm64-v8a to prevent Gradle Out-Of-Memory crashes
android.archs = arm64-v8a

# (str) The format used to package the app for release mode
android.release_artifact = aab

# (str) The format used to package the app for debug mode
android.debug_artifact = apk

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1
