# Booklat

An offline oral-reading assessor for Filipino public-school teachers. A learner reads an English or Filipino passage while words are marked on screen. Teachers can correct the suggested marks, review word-reading accuracy and reading level, and save results as CSV.

## Windows 11

See [Windows setup and hardware comparison](WINDOWS.md). Use `setup-windows.cmd` for initial setup and `run-windows.cmd` to launch.

## Live streaming trial (Vosk)

Booklat now offers **Vosk · live streaming trial** and **Whisper · original comparison** in the Setup screen. Vosk is an optional dependency with separate local English and Filipino models. Prepare it once while online, using the existing project environment:

```bash
./scripts/setup_vosk.sh
./run.sh
```

If a server is already running, stop it with Ctrl+C before `./run.sh`. Refresh the browser, select Vosk, choose a passage, and enable the debugger. Wait for **Vosk ready**, click Start, and begin at **Listening**. Vosk receives continuous 100 ms frames: it does not discard calibration audio or use the Whisper loudness gate. Dotted blue highlights are tentative and can change; normal marks become confirmed when Vosk finalizes a phrase or you stop. Teacher overrides remain locked. On connection failure, recovered results use confirmed marks plus teacher edits, not tentative recognition.

Vosk's changing partial transcript is re-aligned from the last confirmed phrase. Repeated partial updates never add repetitions to the score. Final timestamps come from Vosk's word results; partial display timestamps may be estimated and are never used for scoring. There is no passage-only grammar that could force incorrect speech into expected words.

The model files live under `models/` (Git-ignored). Setup downloads and verifies `vosk-model-small-en-us-0.15` and `vosk-model-tl-ph-generic-0.6` from the official Vosk model catalog. Runtime loads explicit local paths and cannot download models. English is Apache 2.0; the Filipino model is **CC-BY-NC-SA 4.0 (noncommercial)**. See https://alphacephei.com/vosk/models for model details and licenses.

For a fair trial, read each passage cleanly, then with a deliberate skip and repeat. Compare the actual first-highlight delay, false marks, and the final score. The debugger's **Frame processing** value measures server queue plus decoding for an input frame; it does **not** measure word-end-to-highlight latency. A 100 ms frame does not guarantee a 100 ms recognized word. Streaming accuracy and sub-second perceived response require measurement with the real models and your microphone.

To replay the same manually recorded clip through both engines:

```bash
.venv/bin/python scripts/replay_clip.py clips/tl_clean.wav tl-g3-1 --engine vosk --realtime
.venv/bin/python scripts/replay_clip.py clips/tl_clean.wav tl-g3-1 --engine whisper --realtime
```

The original Whisper setup remains below. You can select it any time for comparison; no Whisper files or saved results are removed.

## Quick start (Linux Mint / Bash)

Install the system packages once in Terminal:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip alsa-utils git curl xdg-utils
```

From this project folder, run the commands below. Setup needs internet and downloads the **small** Whisper model once. It needs Python 3.10 or newer and uses Python's built-in `venv` with project-local pip. It never installs into system Python.

```bash
./scripts/setup.sh
./run.sh
# In another terminal:
xdg-open http://localhost:8000
```

Use Chrome or Brave, allow microphone access, and wait for **Speech model ready**. Enter a learner name, select a passage, and click **Start reading**. Remain quiet during the first second of noise calibration; begin at **Listening. Begin reading.** Click **Stop** or press Space to finish. Tap a word to correct its mark, then click **Save result**. After additional edits, click **Save changes**.

Select **Whisper · original comparison** after the base setup. The default Vosk selection requires `./scripts/setup_vosk.sh` as well. Open `http://localhost:8000` while the server is running; opening `web/index.html` directly cannot load the API.

The server binds only to `127.0.0.1`. After setup, `./run.sh` runs with offline mode enabled, and model loading additionally uses cached files only. A missing model displays a recoverable message. Model initialization can take a little time on a CPU.

## Tests

No microphone or model is needed:

```bash
.venv/bin/python -m pytest -q
```

Tests cover alignment, scoring, audio chunking, API validation, atomic save replacement, CSV safety, WebSocket processing with a fake transcriber, and offline page assets. `BOOKLAT_SKIP_MODEL=1` disables model loading for tests. `BOOKLAT_RESULTS_PATH` can direct test results to a temporary file.

## Record and replay

With `alsa-utils` installed, record a short test clip. Ctrl+C ends recording. Only this deliberate manual recording creates an audio file; the app does not.

```bash
arecord -f S16_LE -r 16000 -c 1 clips/en_clean.wav
# Start ./run.sh in another terminal first:
.venv/bin/python scripts/replay_clip.py clips/en_clean.wav en-g3-1
.venv/bin/python scripts/replay_clip.py clips/tl_clean.wav tl-g3-1 --realtime
```

Use filenames starting with `en_` or `tl_`. Test clean readings, skipped words, repeated words, and swapped real words. Replay adds one second of calibration silence before the recording, then sends it through the same local WebSocket pipeline. Replay does not save a result. Clips are ignored by Git.

## Tune and extend

Edit `server/config.yaml` and restart the app. Try `aligner.similarity_threshold` values of 75, 80, and 85 against your clips. Short words require exact matches. The `chunker` settings control noise calibration and phrase boundaries; sample rate and frame length should remain 16000 Hz and 250 ms to match the browser audio protocol. All server settings come from this file.

To add a passage, edit `data/passages.json` with a unique `id`, Whisper language code (`en` or `tl`), `grade`, `title`, and `text`; then restart. Word counts follow whitespace-separated display tokens.

Scoring uses the last reached word as the attempted-word boundary. Substitutions, omissions, and repetitions count by default; remove `repetition` from `scoring.counted_miscues` if required by your teacher/manual. Self-corrections do not count as miscues. Accuracy is floored at zero. Levels use word-reading thresholds of 97% independent and 90% instructional; below 90% is frustration. This does **not** assess comprehension or provide a complete Phil-IRI assessment. WPM is correctly read words per minute, measured between first and last accepted recognizer timestamps; the on-screen timer measures elapsed listening time.

## Privacy and local storage

Everything runs on this device. No microphone audio is stored or uploaded. Audio travels only between the browser and the loopback server, and stays in memory while processed. Transcribed text is not logged. Model setup is the only application step that downloads from the internet; dependency installation also requires internet initially. The page uses system fonts and no external assets.

Saved names and scores are stored in `data/results.csv`, ignored by Git. The newest 20 readings appear on the setup screen, and **Download CSV** exports all saved rows. Re-saving the same session replaces its row atomically. Spreadsheet formula prefixes in text fields are neutralized. Keep the laptop and exported files private: the CSV contains learner names.

## Known limits

- Recognition accuracy for children's Filipino speech is unproven. Marks are suggestions; teacher override is the safety net.
- Whisper may auto-correct mispronunciations to the expected word. Demonstrate with skips, repeats, and swapped real words.
- CPU recognition may lag in real time. Use a headset microphone and a quiet room; test on the demo laptop.
- Alignment uses a short lookahead/lookback and can misalign larger skips or repeated phrases. Review the final marks.
- A stopped passage leaves trailing words unread. Teachers may mark them as skipped when appropriate.
- No real model or live microphone is exercised by the automated suite. Download the model and complete a real reading before the demo.

## Troubleshooting

- **Microphone unavailable:** connect the microphone and allow it in Chrome/Brave site settings for localhost, then retry.
- **Model missing:** while online, run `./scripts/setup.sh` and restart `./run.sh`. Use the same OS user account so the cache is accessible.
- **Port in use:** stop the previous Booklat process (Ctrl+C in its terminal) before starting another.
- **Connection lost / finishing timeout:** use **Go to results** to review marks already received, or **Start over**. Check the server terminal and retry. Recovered timing may be incomplete.
- **No speech detected:** retry after the quiet calibration period, check the selected microphone and input level, and reduce background noise.
- **Cannot save:** check free disk space and write permissions for `data/`, then retry.

For an offline demo, disable wireless manually, keep the server running, and check `curl http://localhost:8000/api/health`. Restore wireless afterwards. Record a backup demo after verifying a clean run.

## Speech debugger

On Setup, select **Enable speech debugger** before starting. The panel appears below the passage and remains available on Results. It shows incoming microphone RMS, the calibration threshold, clipping, received audio duration, and queued chunks. A quiet microphone can produce low RMS; loud background noise can raise the threshold. These are signal measurements, not a guarantee of speech detection.

Expand a chunk to inspect every recognizer word with timestamps and confidence (including low-confidence words filtered out), followed by the aligner's expected word, pointer movement, and marks. Confidence is the recognizer's estimate, not learner accuracy. The panel separates queue wait from processing time; processing includes waiting for the shared model lock. A processing/audio ratio above 1 means that chunk took longer to process than its duration. Chunk collection time comes before these measurements.

**Copy debug report** copies the latest 100 chunks, latest audio measurements, browser capture settings, and teacher-overridden word indices. It omits the learner-name field and device identifiers, but recognized speech may itself contain names. No audio is recorded, no diagnostic text is logged by the server, and no report is saved automatically. Refreshing or starting a new reading clears it. Debugging does not change recognition or scoring settings. Restart the server and refresh the browser after installing this update.

Calibration now caps the speech threshold at `chunker.threshold_ceiling` (1500 RMS by default). During idle audio, a full calibration-sized window of quieter frames can lower it toward the configured floor. This prevents loud startup audio from permanently setting an unusably high gate. A startup warning appears if the cap was needed. The cap is a tuning default, not a speech/noise classifier: in persistent noise it may send more background audio to recognition. Remain quiet during startup and validate with a real microphone reading.
