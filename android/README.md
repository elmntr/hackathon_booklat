# Booklat for Android

Native Kotlin/Jetpack Compose port. The desktop app stays in `web/` and `server/`.

## Build and install

Install JDK 17 or 21, Android SDK 36, and Android SDK Platform Tools. Android Studio can open this `android/` directory. The project uses Gradle 8.13 and Android Gradle Plugin 8.13.2. From a terminal:

```sh
cd android
printf 'sdk.dir=%s/Android/Sdk\n' "$HOME" > local.properties
./gradlew :app:assembleDebug :app:testDebugUnitTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The debug APK is `android/app/build/outputs/apk/debug/app-debug.apk` after a successful build. Java and Android dependencies are fetched by Gradle on the first build. No Python installation is required.

## Offline speech models

Open **Settings > Offline models**. Choose **Download English**, **Download Filipino**, or **Import ZIP** for each language. Downloads occur only after pressing Download and come from `alphacephei.com`. ZIP imports use the Android document picker. Install models before going offline. A reading cannot start without the selected language model. No system SpeechRecognizer, cloud fallback, learner-audio upload, or silent model download is used. Installed models and recordings are app-private. The app needs microphone permission only when starting a reading or microphone check.

- English: `vosk-model-small-en-us-0.15`, about 40 MB downloaded, [Apache 2.0](https://alphacephei.com/vosk/models). Allow roughly 150 MB installed storage and 300 MB runtime memory.
- Filipino/Tagalog: `vosk-model-tl-ph-generic-0.6`, about 314 MiB downloaded, [CC BY-NC-SA 4.0](https://github.com/alphacep/vosk-space/blob/master/models.md). This model is for noncommercial use with attribution and share-alike terms. Allow at least 1.3 GB free storage during installation and substantial runtime memory. Download progress appears in Settings; retrying an interrupted download resumes its saved portion.

The models are **not bundled in the APK**. The ZIP importer checks archive paths, extracted size and required model files before replacing an installed model. Vosk loads the model when a reading starts. Downloading a model requires internet, but normal reading works in airplane mode after installation. Speech recognition marks are suggestions; the teacher reviews all miscues. The app reports Phil-IRI word and comprehension components separately, with no automatic overall placement.

## Reading and exports

Choose or import a passage, enter a learner name, then start. Stop finalizes the Vosk stream and opens Results. A draft contains confirmed marks and teacher corrections, not tentative word highlights. Recovery appears in Setup after process death. Settings controls whether completed readings and raw audio are saved. Audio is 16 kHz mono PCM WAV. Recordings can be played, shared as WAV, or deleted. The word editor can begin playback from the corresponding word when Vosk supplied a timestamp.

Teacher grading includes a **Teacher confirms Non-Reader** checkbox. Apply the teacher review, then save the result if autosave is off. The status appears in history and exports while the numeric word-reading category stays unchanged. A 0% speech match alone does not set this status.

**Export CSV**, **Export report**, **Export WAV**, and **Backup** use Android's share sheet. Backup is a ZIP containing JSON passages/readings/preferences plus local WAV files. Copy it to a safe location via the share sheet. It is an export, not an in-app restore feature. Scanned PDFs require OCR before import. PDF parsing is local. Files are limited to 10 MB and 100,000 extracted characters.

For verification status and known gaps, see [FEATURE_PARITY.md](FEATURE_PARITY.md).
