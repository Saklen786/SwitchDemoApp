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
# comma separated e.g. requirements = sqlite3,kivy
# CRUCIAL: bleak and android must be here for BLE to function
requirements = python3,kivy,bleak,android

# (str) Supported orientations (landscape, sensorPortrait or all)
# Locks the app to portrait mode natively
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# --- Android specific ---

# (list) Permissions
# CRUCIAL: These exact permissions are required for Bleak to scan/connect on modern Android devices.
android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (bool) If True, then skip trying to update the Android sdk
# This can be useful to avoid internet issues or delayed downloads
android.skip_update = False

# (bool) If True, then automatically accept SDK license
# agreements. This is intended for automation only. If set to False,
# the default, you will be shown the license when first run and
# you will need to accept it.
android.accept_sdk_license = True

# (str) The format used to package the app for release mode (aab or apk or aar).
android.release_artifact = aab

# (str) The format used to package the app for debug mode (apk or aar).
android.debug_artifact = apk

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
```