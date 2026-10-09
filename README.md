# Booklat

An offline oral-reading assessor for Filipino public-school teachers. A learner reads an English or Filipino passage with live word marks, marks revealed after a pause, or automatic completion with marks revealed at the end. Teachers can correct suggestions, review accuracy and reading level, and keep reading history in a local SQLite database.

## Validation, your own passages, and offline history

Choose **As I read** for revisable word marks; **After a pause** for live blue highlighting with marks revealed when the recognizer confirms a phrase; or **Automatic finish** to hide marks until the confirmed ending, then stop and reveal results automatically. Automatic completion requires the last word to be recognized correctly with confirmed timing; use Stop if it is missed. Pause naturally at commas and periods: printed punctuation alone does not trigger confirmation. Whisper confirms at pause or chunk boundaries. Stop remains available in every mode. All modes use the same recognition and scoring rules. Preferences are remembered in the browser. Automatic saving is on by default and can be turned off; it saves completed readings and subsequent teacher corrections. Failed saves are shown with a retry action.

Open **Add your own reading material** to paste notes or import TXT, Markdown, text-based PDF, DOCX, or EPUB, up to 10 MB. The file is processed locally. Review the extracted words, choose English or Filipino and a grade, then save an excerpt of 1–2,000 words. For books, choose a starting word and excerpt length. The preview is capped at 100,000 characters (and 200 PDF pages). Scanned PDFs require OCR first; encrypted documents must be unlocked. Original uploaded files are not stored.

**Offline reading history** supports learner/passage search, more than 20 results through Load more, reopening word marks, and CSV export. **Back up library & history** downloads a consistent database snapshot. New records include engine, device, validation mode, passage text, and word decisions. Legacy CSV records retain their summary scores; their original per-word decisions were never stored.

For a manual restore, stop Booklat, keep a copy of the current database, and replace `data/booklat.sqlite3` with the downloaded snapshot. Remove any stale `booklat.sqlite3-wal` and `booklat.sqlite3-shm` files only while the server is stopped. Restart Booklat. The SQLite file includes both imported passages and reading history.

The expanded implementation brief and further suggestions are in [IMPLEMENTATION_BRIEF.md](IMPLEMENTATION_BRIEF.md).

## Windows 11

See [Windows setup and hardware comparison](WINDOWS.md). Use `setup-windows.cmd` for initial setup and `run-windows.cmd` to launch.

## Live streaming trial (Vosk)

Booklat now offers **Vosk · continuous speech** and **Whisper · phrase recognition** in the Setup screen. Vosk is an optional dependency with separate local English and Filipino models. Prepare it once while online, using the existing project environment:

```bash
./scripts/setup_vosk.sh
./run.sh
```

If a server is already running, stop it with Ctrl+C before `./run.sh`. Refresh the browser, select Vosk, choose a passage, and enable the debugger. Wait for **Vosk ready**, click Start, and begin at **Listening**. Vosk receives continuous 100 ms frames: it does not discard calibration audio or use the Whisper loudness gate. Colored marks with dotted outlines are tentative and can change; the outlines disappear when Vosk finalizes a phrase or you stop. Teacher overrides remain locked. On connection failure, recovered results use confirmed marks plus teacher edits, not tentative recognition.

Vosk's changing partial transcript is re-aligned from the last confirmed phrase. Repeated partial updates never add repetitions to the score. Final timestamps come from Vosk's word results; partial display timestamps may be estimated and are never used for scoring. There is no passage-only grammar that could force incorrect speech into expected words.

The model files live under `models/` (Git-ignored). Setup downloads and verifies `vosk-model-small-en-us-0.15` and `vosk-model-tl-ph-generic-0.6` from the official Vosk model catalog. Runtime loads explicit local paths and cannot download models. English is Apache 2.0; the Filipino model is **CC-BY-NC-SA 4.0 (noncommercial)**. See https://alphacephei.com/vosk/models for model details and licenses.

For a fair trial, read each passage cleanly, then with a deliberate skip and repeat. Compare the actual first-highlight delay, false marks, and the final score. **Processing** measures server decoding time and **Queue** measures waiting before decoding. Neither measures word-end-to-highlight latency. A 100 ms frame does not guarantee recognition within 100 ms. Live previews use Vosk's text-only best path; word timing and final scoring use endpoint results. See the [Vosk partial-result implementation](https://github.com/alphacep/vosk-api/blob/master/src/recognizer.cc) for the distinction. Accuracy and visible latency still need measurement with actual recordings and your microphone.

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

Saved names, scores, word marks, and custom passages are stored in `data/booklat.sqlite3`, ignored by Git. Existing `data/results.csv` entries are imported once and the original CSV is retained. Re-saving the same session updates its database record transactionally. CSV exports neutralize spreadsheet formula prefixes. The database and exported files contain learner names. `BOOKLAT_DB_PATH` can select an alternate database; `BOOKLAT_RESULTS_PATH` selects the legacy CSV source and provides an isolated default database path for tests.

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

**Copy debug report** copies the latest 100 chunks, latest audio measurements, browser capture settings, and teacher-overridden word indices. It omits the learner-name field and device identifiers, but recognized speech may itself contain names. The debugger itself does not record audio; the separate voice-recording option controls history audio. No diagnostic text is logged by the server, and no report is saved automatically. Refreshing or starting a new reading clears it. Debugging does not change recognition or scoring settings. Restart the server and refresh the browser after installing this update.

Calibration now caps the speech threshold at `chunker.threshold_ceiling` (1500 RMS by default). During idle audio, a full calibration-sized window of quieter frames can lower it toward the configured floor. This prevents loud startup audio from permanently setting an unusably high gate. A startup warning appears if the cap was needed. The cap is a tuning default, not a speech/noise classifier: in persistent noise it may send more background audio to recognition. Remain quiet during startup and validate with a real microphone reading.


## Reading and recovery controls

- Choose a **1, 2, or 3 second finish delay** (default 2). The countdown starts after a confirmed ending. Recognized corrections or detected speech cancel the countdown; a new confirmed endpoint starts it again. **Keep reading** cancels automatic finish for that reading, and Stop finishes manually.
- **Confirmed reading progress** counts words attempted, including inferred omissions. It does not count correct words alone. Optional active-line following scrolls only when the recognized word goes outside the visible reading area.
- **Check microphone** continuously displays the input level and reports silence or excessive volume until you choose **Stop microphone check**. It does not record or send check audio, and remains an optional check. Thresholds are approximate input-level guidance, not recognition confidence.
- **Review words** filters wrong, skipped, repeated, or unread words. Filtered entries show expected text and what the recognizer heard. Hovering an entry also shows that comparison. Teacher corrections remain editable.
- A **single unfinished draft** is stored in this browser after confirmed phrases, teacher edits, and page unload. Refresh recovery offers continued reading from the next unread word, review, or discard. Provisional guesses are excluded. Continuation uses the same passage/session and offsets word positions and timing; the refresh break is excluded from duration. One new draft replaces the previous one. Browser storage is separate from the SQLite backup.
- **Save entire text as book sections** splits extracted document text or pasted notes into 50–2,000-word sections (default 300). Sections save together in SQLite. Imported text is bounded by the extraction preview limit; only that extracted text is split. Editing an excerpt does not alter the imported full text. Section boundaries are word-count based and can fall inside a sentence. The next section becomes available after a complete reading. Each learner's section position is remembered in this browser; entering that learner's name restores it.

These controls have not yet been exercised with a live microphone after this change.


## Voice recordings and word playback

**Save voice recording with reading history** is enabled by default and can be turned off before reading. Captured mono 16 kHz PCM samples are the same samples sent to the local recognizer, including startup silence. The WAV is saved alongside the result in SQLite; automatic saving also saves its recording. With automatic saving off, use **Save result** to retain both. If audio saving fails after the score is saved, the page reports that separately and provides Retry scoring to retry the save without duplicating the recording.

Open a history row labelled **Open · voice** to play or seek the recording. Passage words highlight at their saved recognition start/end times, with expected text, recognized text, status, and passage time shown beside playback. Select a timestamped word and choose **Play from this word**. Skipped words do not have spoken audio; repeated-word counts are aggregated marks and do not provide a separate timestamp for every repeat. Teacher corrections change marks without changing the original audio.

Recordings have a 50 MB limit per portion (about 27 minutes). Recognition continues if that limit is reached; the page reports that audio covers only the beginning. A resumed draft records a new portion with its own passage-time offset; earlier audio lost in a refresh cannot be reconstructed. Audio already saved for the same reading is retained as separate portions. Old readings and readings made with recording disabled show that no audio is available.

Download individual WAV files or delete all voice portions from a reading while retaining its marks and scores. **Back up library & history** includes saved audio, so database backups are larger and contain learner voices. The microphone check is never recorded. Playback timing uses recognizer estimates and has not yet been measured against live speech after this change.


## Phil-IRI component grading and exports

The results show Phil-IRI 2018 component criteria using DepEd's PPST Resource Package Module 11: word recognition **97–100 / 90–96 / 89 and below**, and comprehension **80–100 / 59–79 / 58 and below**, for Independent / Instructional / Frustration respectively. Continuous decimal scores are classified before display rounding at word thresholds 97/90 and comprehension thresholds 80/59. WPM is a separate fluency measure.

The rubric word score uses the full passage word count: `(words − counted miscues) / words × 100`, floored at zero. The existing app accuracy uses the attempted portion and the configured miscue types. Incomplete readings retain a provisional word score and do not receive a rubric word component level. Automatic counts cover the app's available marks; they do not identify every official miscue type. Teachers may enter a **reviewed total miscues** to replace that count. Teacher self-corrections and dialectal variation should be reviewed according to the administered manual.

Teachers can enter comprehension correct answers and total administered questions. Empty fields remain **Not assessed**; speech is never used to infer comprehension. The app reports component levels and combines them using the supplied adapted Phil-IRI rubric: either component at Frustration gives Frustration; otherwise the comprehension level is the reading level. Both components and a complete reading are required. Custom passages and automated marks do not constitute an official administration.

In Results, a teacher can confirm **Non-Reader** and apply the review. This status is saved separately from the automated word-reading category: a 0% speech match still falls in the Frustration score band and does not by itself label a learner Non-Reader. History shows a confirmed status as “Non-Reader (teacher)”; CSV, reports, and backups retain both the score and teacher decision. Reopen a reading to clear the checkbox if needed.

Saved records retain a grading snapshot. CSV exports add component percentages, levels, teacher counts, grading status, formulas' criteria thresholds, and source/version. Legacy records retain their original scores; unassessed components remain empty. **Download grading report**, available after saving, produces a standalone printable HTML report with scores, rubric, source, and word recognition timestamps. Open that report in a browser to print or save as PDF. Database backups retain the rubric snapshot along with readings and audio.

Source: [DepEd PPST Resource Package Module 11 — DepEd Manila copy](https://depedph-my.sharepoint.com/:b:/g/personal/lrms_manila_deped_gov_ph/EcCrs5zU1fZKqzNFxzbKgoUBBvvgAwjtsX9j4XKZpYtT5g?e=Lk2UtR), printed page 20.
Policy: https://www.deped.gov.ph/2018/03/26/do-14-s-2018-policy-guidelines-on-the-administration-of-the-revised-philippine-informal-reading-inventory/


## Integration verification

The landing and classroom screens use one set of IDs and event bindings. The feature-complete behavior and branded screens are integrated; conflicting fragments from the UI merge were removed. History still loads if passage loading fails. Pending scores clear previous results; late errors from older requests do not replace current results. Escape closes the editor and returns focus to the selected word.

`python -m pytest -q` checks API contracts, unique frontend hooks and screen ownership, audio resampling, saved WAV range playback and deletion, recording-inclusive SQLite backup, Phil-IRI scoring/report exports, book sections, resumed WebSockets and the browser state unit checks. POSIX setup-script orchestration checks run only on POSIX hosts; Windows uses the CMD setup scripts.

For the optional full browser integration check, start a separate server using `BOOKLAT_SKIP_MODEL=1`, `BOOKLAT_DB_PATH` and `BOOKLAT_RESULTS_PATH` pointing at disposable test storage, on port 8765. With Playwright and Edge available, run `node tests/browser_integration.cjs`; `BOOKLAT_TEST_URL` can change the test server URL. This check creates synthetic readings and deletes their recordings, so use isolated test storage. It uses a synthetic microphone and recognition events with real HTTP routes; actual microphone recognition quality requires a separate speech trial. Layouts are checked at 1280×720, 1366×768 and 360px wide, and page requests must stay local.


## Classroom screen controls

- **Reading passage** has a title/language search and four visible options. Scroll for more; arrow keys move through options and Enter selects. The chosen passage remains in the preview even if a search hides its title.
- The **Settings** icon in the header opens a separate page containing validation timing, finish delay, active-line following, microphone check, automatic saving, recording and debugging. Mode, delay, saving and recording choices are captured for the next reading. The classroom interface always uses Vosk. Previously saved Whisper readings remain available in history.
- **Large view** is available for preview, live reading and result review. It moves the existing passage into a modal overlay, so word validation and edits stay synchronized. Expand and collapse use icon buttons. Text sizes range from 32 to 72 px. Stop reading is available inside the live overlay; Close returns to the same passage. Escape closes the word editor first and then the overlay. The overlay closes when the reading finishes.
- **Offline history** shows four rows and its column header at a time, with vertical scrolling for other loaded readings and horizontal scrolling on smaller screens. Search remains available. Older readings load as you scroll to the bottom. Category colors are optional. Save a copy contains Download scores and Back up this computer.


### Favorites, filters and projector mode

Open the three-dot menu beside the selected title and choose **Add favorite** to bookmark a passage. Stars and **Favorites only** are available alongside grade, language and title filters. Favorites are saved in this browser, separately from database backups. Filtering preserves the selected preview; **Reset filters** shows the full library. Newly imported passages clear filters so their titles are visible.

During reading, **Projector mode** shows the current recognized line in the large view. It follows speech progress, retains validation timing and teacher edits, and displays line/word progress. Choose **Show full passage** to see all words, change **Text size** to suit the room, or use **Stop reading**. Closing the overlay returns to the regular reading screen; completed readings open the full results.


The Booklat wordmark returns to the landing page. During a reading it finishes capture and opens the landing after scoring succeeds. A scoring failure keeps the results available for review. Settings can be opened before or after a reading; finish the active reading before changing settings.
