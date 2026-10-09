# Android validation log

- `:app:assembleDebug`: passed on this Arch Linux host with Android SDK 36 and JDK 21.
- `:app:testDebugUnitTest`: 9 tests passed. Fixtures cover alignment, omission, substitution, repetition, self-correction, ignored words, Filipino normalization, provisional isolation, score boundaries, partial reading, WPM, grading, manual correction, WAV structure and JSON roundtrip.
- APK manifest/package inspection: `ph.booklat`, minimum API 26, target 36, Vosk native libraries for ARM and x86 are present, six original Tupi poses are packaged. APK is a native app and does not contain a WebView.
- Desktop alignment and scoring tests: 17 passed. The full desktop suite was attempted but stalled during test execution on this host; it was interrupted.
- The existing desktop repository files were not modified.

## Unverified on this host

No Android device is connected. This host has no AVD, system image, or `/dev/kvm`. Device installation, screenshots, real Vosk recognition with English and Filipino model ZIPs, microphone interruption and permission flows, document picker, playback, import/export, TalkBack, large text, screen rotation, portrait/landscape and tablet rendering are **not verified**. The debug APK builds, but runtime feature parity must not be considered proven until those checks run on an Android device.

No representative audio fixtures were provided in the repository (`clips/` contains only `.gitkeep`). The local desktop model folders are not packaged in the APK because the app requires explicit model installation and because the Filipino model has noncommercial share-alike terms. This prevents a real Android speech test here even apart from the absent device.

Screenshots of Landing, Setup, Reading, Results, Settings, Import and full passage are unavailable because no Android runtime can be launched on this host. Do not substitute mock screenshots for runtime evidence.
