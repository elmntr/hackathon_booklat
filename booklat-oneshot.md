# Booklat: one-shot build spec (6-hour hackathon)

**Offline oral-reading assessor for Filipino public-school teachers.** A learner reads a graded passage aloud. Each word on screen turns green, red, struck-through or marked as repeated as it is spoken. On Stop, Booklat shows reading time, words per minute, accuracy and the Phil-IRI reading level, and saves a row to a CSV. Everything runs on the laptop. No audio is stored or sent.

---

## PART A: For you (the human)

### A1. How to launch the build (Codex CLI)
**One-time setup on Linux Mint (needs internet).** If you only want to run the existing app, follow README.md instead. These commands prepare a new build and assume the Codex CLI is already installed.
```
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs alsa-utils git curl xdg-utils
```

**Create the project, install the Python dependencies now, and start a git repo.** Codex runs in a sandbox with no network by default, so it cannot install packages later. It also warns when the folder is not a git repo.
```
mkdir -p ~/booklat && cd ~/booklat
git init
python3 -m venv .venv
.venv/bin/python -m pip install fastapi "uvicorn[standard]" faster-whisper rapidfuzz pyyaml numpy pytest httpx websockets
```

**Copy this spec into the project** (assuming you saved it in `~/Downloads`):
```
cp ~/Downloads/booklat-oneshot.md ~/booklat/
```

**Launch Codex with the build prompt.** The first run asks you to sign in.
```
cd ~/booklat
codex --full-auto "Read booklat-oneshot.md. Build the entire project described in PART B in this folder, in one pass, without asking me questions. Dependencies are already installed in .venv and there is no network, so run tests with .venv/bin/python -m pytest -q and never run pip, npm or any download. Follow the build order and the acceptance checklist. When finished, reply with: the list of files created, the test results, and the exact commands to set up and run. Nothing else."
```
If your Codex version rejects `--full-auto`, run `codex` with the same quoted prompt and approve the file edits when it asks. You do not need an `AGENTS.md`; the prompt points Codex at this file.

### A2. Things you do by hand (so the agent does not spend tokens on them)
| When | Task | Command or note |
|---|---|---|
| Before | Install Codex and system packages, create the venv | see A1 |
| After build | Download the speech model (**needs internet, once**; the dependencies are already installed, so this mostly fetches the model) | `cd ~/booklat && ./scripts/setup.sh` |
| After build | Run the tests | `cd ~/booklat && source .venv/bin/activate && pytest -q` |
| After build | Start the app | `cd ~/booklat && ./run.sh` then open `http://localhost:8000` in Brave or Chrome and allow the microphone |
| Then | Record test clips (Ctrl+C stops each one). Names must start with `en_` or `tl_` | `arecord -f S16_LE -r 16000 -c 1 clips/en_clean.wav` and the same for `en_skip.wav`, `en_repeat.wav`, `en_swap.wav`, `tl_clean.wav`, `tl_skip.wav` |
| Then | Replay a clip through the real pipeline without using the browser | `python scripts/replay_clip.py clips/en_skip.wav en-g3-1` (the Filipino passage id is `tl-g3-1`) |
| Then | Tune `similarity_threshold` in `server/config.yaml` (try 75, 80, 85) and keep the value that gets the most clips right | edit the file, restart `./run.sh` |
| Before demo | Airplane-mode proof | `nmcli radio all off` then `curl http://localhost:8000/api/health`; afterwards `nmcli radio all on` |
| Before demo | Screen-record one clean successful run as a backup video | any screen recorder |
| Before demo | 3 slides: the problem, the architecture diagram (copy it from B3), why local | |
| Before demo | Rehearse the 2-minute demo twice with a timer. Use a headset mic if the room is noisy | |

### A3. Timeline
| Time | What |
|---|---|
| 0:00 to 0:20 | Install system packages, create the folder, launch the agent |
| 0:20 to 1:00 | Agent builds everything (you wait; draft slides meanwhile) |
| 1:00 to 1:30 | `./scripts/setup.sh`, `pytest -q`, first live test in the browser |
| 1:30 to 3:00 | Record clips, replay them, tune thresholds, collect bugs |
| 3:00 to 4:30 | Fix bugs (small, targeted agent requests; paste only the last 20 lines of an error) |
| **4:30** | **Feature freeze** |
| 4:30 to 5:00 | Three full runs in airplane mode |
| 5:00 to 6:00 | Backup video, slides, rehearsal, judge Q&A |

### A4. Token-saving rules for follow-up requests
- Ask for one fix at a time and name the file.
- Paste only the last 20 lines of a traceback plus the one function involved.
- Ask for patches or the changed function, not whole-file rewrites.
- Commit after every working state (`git init` once, then `git add -A && git commit -m "working"`).

### A5. 2-minute demo script
1. **Hook (15 s):** "Teachers test struggling readers one by one with paper and a stopwatch."
2. **Prove offline (15 s):** turn the radio off on camera, show `/api/health`.
3. **Wow (40 s):** a teammate reads with one skip, one swapped real word and one repeat. Words recolour live.
4. **Result (20 s):** time, WPM, accuracy, level. Click Download CSV, show the row.
5. **Why local (20 s):** no signal needed, no child's voice uploaded.
6. **Close (10 s):** "Phil-IRI scoring in minutes, and no child's voice leaves the room."

If judges say "this exists": "CoBRA showed automated reading assessment is feasible. Booklat is the offline, teacher-run version scored to Phil-IRI categories."

**Honest limits to state if asked:** speech recognition on children's Filipino speech is unproven (no benchmark found), so Booklat suggests marks and the teacher confirms. Whisper tends to auto-correct a mispronounced word to the expected word, so demo with skips, repeats and swapped real words.

### A6. Facts used for scoring (verified against Phil-IRI materials)
- Oral reading score = (number of words − number of miscues) ÷ number of words × 100.
- Word-reading levels: **Independent 97 to 100%**, **Instructional 90 to 96%**, **Frustration 89% and below**.
- Repetition appears as a miscue type on the Phil-IRI summary of miscues, so it is **counted** by default. If your teacher or manual says otherwise, remove `repetition` from `counted_miscues` in `server/config.yaml`; no code change is needed.
- Comprehension thresholds (80 to 100, 59 to 79, 58 and below) exist but comprehension is out of scope here, so the level is by word reading only.

---

# PART B: Build spec (for the coding agent)

You are building a complete, polished, working project in the current folder in one pass. Do not ask questions. Where this spec is silent, choose the simplest option that keeps the app reliable and offline. Do not add features that are not listed. Do not add network calls of any kind.

## B1. Hard constraints
1. **Fully offline at runtime.** No CDN links, no web fonts, no analytics, no external URLs anywhere in `web/`. Use the system font stack only. A test enforces this.
2. **Privacy.** Never write audio to disk. Never log transcribed text beyond what is shown in the UI. The server binds to `127.0.0.1` only.
3. **Stack.** Python 3.10+, FastAPI, uvicorn, faster-whisper, rapidfuzz, PyYAML, numpy. Front end is one `web/index.html` with inline CSS and JS, no build step, no framework.
4. **CPU only.** Whisper model `small`, `compute_type="int8"`.
5. **Language of all UI text:** English. Passage text may be Filipino.
6. Keep code readable: type hints, short docstrings, no dead code.
7. **Sandbox.** Assume there is no network and that all Python dependencies are already installed in `.venv`. Run Python only as `.venv/bin/python` (for example `.venv/bin/python -m pytest -q`). Never run pip, npm, git clone, or any download.

## B2. Build order (follow it; run the tests at each checkpoint)
1. `server/config.yaml`, `server/config.py`
2. `server/aligner.py` + `tests/test_aligner.py` → run `pytest`
3. `server/scorer.py` + `tests/test_scorer.py` → run `pytest`
4. `server/asr.py` (chunker + transcriber) + `tests/test_chunker.py` → run `pytest`
5. `data/passages.json`, `server/main.py` + `tests/test_api.py` → run `pytest`
6. `web/index.html` + `tests/test_no_external_urls.py` → run `pytest`
7. `scripts/setup.sh`, `scripts/download_model.py`, `scripts/replay_clip.py`, `run.sh`, `requirements.txt`, `README.md`, `.gitignore`
8. Final: run the full test suite with `.venv/bin/python -m pytest -q`. Then confirm that `GET /`, `/api/health` and `/api/passages` respond, using FastAPI's `TestClient` with `BOOKLAT_SKIP_MODEL=1` (do not start a long-running server). Fix anything that fails. Do not download models.

## B3. File tree
```
booklat/
├─ server/
│  ├─ __init__.py
│  ├─ config.yaml
│  ├─ config.py
│  ├─ aligner.py
│  ├─ scorer.py
│  ├─ asr.py
│  └─ main.py
├─ web/index.html
├─ data/
│  ├─ passages.json
│  └─ results.csv          # created on first save, git-ignored
├─ clips/.gitkeep          # user test recordings, git-ignored except .gitkeep
├─ scripts/
│  ├─ setup.sh
│  ├─ download_model.py
│  └─ replay_clip.py
├─ tests/
│  ├─ test_aligner.py  test_scorer.py  test_chunker.py
│  └─ test_api.py      test_no_external_urls.py
├─ run.sh
├─ requirements.txt
├─ README.md
└─ .gitignore
```

Architecture:
```
Browser (localhost:8000, one index.html)
  mic → AudioWorklet → 16 kHz mono Int16 frames
        │ WebSocket binary            ▲ WebSocket JSON events
        ▼                             │
FastAPI (127.0.0.1)
  Chunker (loudness-based pauses) → faster-whisper small int8 → Aligner → events
  Scorer (config thresholds)      → CSV (data/results.csv)
```

## B4. `server/config.yaml` (create exactly this)
```yaml
asr:
  model: small
  compute_type: int8
  beam_size: 1
  min_word_probability: 0.1
  ignore_words: [uh, um, ah, hmm, eh, oh, huh]
chunker:
  sample_rate: 16000
  frame_ms: 250
  calibration_frames: 4        # first 4 frames (1 s) set the noise floor
  threshold_floor: 250         # minimum speech threshold, int16 RMS
  threshold_multiplier: 2.5    # threshold = max(floor, multiplier * median noise RMS)
  pause_frames: 2              # 2 silent frames (0.5 s) end a chunk
  min_chunk_frames: 3
  max_chunk_frames: 16         # 4 s hard cap
  lead_in_frames: 1            # keep 1 frame before speech starts
  min_speech_frames: 1
aligner:
  similarity_threshold: 80     # rapidfuzz ratio, 0 to 100
  exact_match_max_len: 3       # words this short must match exactly
  lookahead: 3
  lookback: 3
scoring:
  counted_miscues: [substitution, omission, repetition]
  min_time_s: 1.0              # below this, WPM is not computed
  levels:                      # word-reading accuracy %, Phil-IRI
    independent: 97.0
    instructional: 90.0        # below this is frustration
```
`config.py`: `load_config()` reads this file once (cached) and returns a plain dict. Path is relative to the file, not the working directory.

## B5. `data/passages.json` (create exactly this)
```json
[
  {
    "id": "en-g3-1",
    "language": "en",
    "grade": 3,
    "title": "Mina's Garden",
    "text": "Mina has a small garden behind her house. Every morning, she waters the plants with a red can. Today, she sees a green bean on the vine. She picks it and smiles. Her little brother runs to see it. They share the bean with their mother at lunch."
  },
  {
    "id": "tl-g3-1",
    "language": "tl",
    "grade": 3,
    "title": "Ang Alaga ni Ben",
    "text": "Si Ben ay may alagang pusa. Puti ang kulay nito at malambot ang balahibo. Tuwing umaga, binibigyan niya ito ng gatas. Pagkatapos, naglalaro sila sa bakuran. Kapag gabi na, natutulog ang pusa sa tabi ni Ben. Mahal na mahal ni Ben ang kanyang pusa."
  }
]
```
The English passage has 48 words and the Filipino passage has 44. Display tokens are `text.split()` (punctuation kept for display). The API returns `word_count`.

## B6. `server/aligner.py`

### Types
- Statuses: `"not_reached" | "correct" | "substitution" | "omission"`.
- Repetition is **not a status**. It is a per-word integer `repeats` (the word was read, then re-read). A word can be `correct` with `repeats=2`.
- `HeardWord(text: str, t0: float, t1: float)`.
- `Mark` dataclass: `idx, status, repeats, heard: str|None, t0: float|None, t1: float|None, self_corrected: bool`.

### `normalize(s: str) -> str`
Lowercase; remove every character that is not a letter or digit (Unicode-aware, so `ñ` and accented letters survive); apostrophes and hyphens are removed, not replaced by spaces. Return `""` if nothing is left.

### `matches(a, b, cfg) -> bool`
Both normalised and non-empty. If `min(len(a), len(b)) <= exact_match_max_len`, require `a == b`. Otherwise require `rapidfuzz.fuzz.ratio(a, b) >= similarity_threshold`.

### `class Aligner`
```
Aligner(passage_text: str, cfg: dict)
  .tokens: list[str]          # display tokens
  .norm:   list[str]          # normalised tokens
  .marks:  list[Mark]         # all start as not_reached, repeats 0
  .p: int                     # next expected passage index
  .first_t / .last_t: float|None
  .feed(words: list[HeardWord]) -> set[int]   # indices whose mark changed
  .snapshot() -> list[Mark]
```
`feed` processes heard words in order. For each word:
1. Normalise; skip if empty or in `asr.ignore_words`. Update `first_t` (first accepted word's `t0`) and `last_t` (latest accepted word's `t1`).
2. Apply these rules **in this order** and stop at the first that fires:
   1. **Expected word.** If `p < n` and `matches(h, norm[p])` → mark `p` as `correct` (store heard text and times), `p += 1`.
   2. **Look back (repetition or self-correction).** For `k` in `1..lookback`, `j = p-k`, if `j >= 0` and `matches(h, norm[j])`:
      - if `marks[j].status == "substitution"` → set it to `correct`, set `self_corrected = True` (the learner fixed themselves; this is not a miscue);
      - otherwise → `marks[j].repeats += 1`.
      The pointer does not move.
   3. **Look ahead (omission).** For `k` in `1..lookahead`, `j = p+k`, if `j < n` and `matches(h, norm[j])` → mark `p..j-1` as `omission`, mark `j` as `correct`, `p = j+1`.
   4. **No match.** If `p < n` → mark `p` as `substitution` (store the heard text), `p += 1`. If `p >= n`, ignore the word.
3. Collect every index touched into the returned set.

Words after the last reached word stay `not_reached`. The aligner never converts them to omissions; the teacher may do so by tapping.

## B7. `server/scorer.py`
`score(marks: list[dict], first_t, last_t, cfg) -> dict` where each mark dict has `status` and `repeats`.

```
attempted_idx   = index of the last mark whose status != "not_reached" (else none)
words_attempted = attempted_idx + 1        (0 if none)
counts          = over marks[0:words_attempted]:
                  correct = count status correct
                  substitutions, omissions = counts by status
                  repetitions = sum of repeats
miscues         = sum of counts for the types listed in scoring.counted_miscues
accuracy_pct    = round((words_attempted - miscues) / words_attempted * 100, 1), floor at 0.0; None if words_attempted == 0
reading_time_s  = round(last_t - first_t, 1) if both set and last_t > first_t else None
wpm             = round(correct / (reading_time_s / 60)) if reading_time_s and reading_time_s >= min_time_s else None
level           = None if accuracy is None
                  "independent"   if accuracy >= levels.independent
                  "instructional" if accuracy >= levels.instructional
                  else "frustration"
```
Return: `words_total, words_attempted, correct, substitutions, omissions, repetitions, miscues, accuracy_pct, reading_time_s, wpm, level, partial` where `partial = words_attempted < words_total`.

## B8. `server/asr.py`

### `Chunker`
Reframes any incoming int16 audio into 250 ms frames (4000 samples at 16 kHz). Methods: `push(samples) -> list[Chunk]`, `flush() -> list[Chunk]`, properties `calibrated`, `threshold`.
- `Chunk` = `(audio: np.ndarray int16, t_start: float)`. `t_start` is seconds on the **audio clock** (frame index × 0.25, minus the lead-in).
- **Calibration:** the first `calibration_frames` frames are not chunked. `threshold = max(threshold_floor, threshold_multiplier * median(RMS of those frames))`. `push` must report when calibration completes (e.g. `calibrated` flips to true) so the server can send `ready`.
- **Chunking:** a frame is speech if RMS > threshold. Start collecting at the first speech frame, including `lead_in_frames` before it. A chunk ends when `silent_run >= pause_frames` and the chunk has at least `min_chunk_frames` frames, or when it reaches `max_chunk_frames`. Chunks with fewer than `min_speech_frames` speech frames are discarded. `flush()` emits any collected chunk that meets the same discard rule.

### `Transcriber`
- `load()` creates `WhisperModel(cfg.asr.model, device="cpu", compute_type=cfg.asr.compute_type, cpu_threads=os.cpu_count() or 4)` then warms up with 1 second of silence. Sets `loaded=True`, or stores the error string in `error`.
- `transcribe(audio_int16, language, t_start) -> list[HeardWord]`: convert to float32 in `[-1, 1]`; call `model.transcribe(audio, language=language, beam_size=cfg.asr.beam_size, temperature=0, condition_on_previous_text=False, word_timestamps=True, vad_filter=False)` with **no** `initial_prompt`. Collect words across segments, drop words whose `probability < min_word_probability`, offset `t0`/`t1` by `t_start`. Guard the model with a `threading.Lock`.

## B9. `server/main.py`

Startup: lifespan loads config and passages, then loads the Transcriber **unless** env `BOOKLAT_SKIP_MODEL=1` (used by tests). Never crash if the model fails to load; record the error. Mount nothing from the network.

### Routes
| Method | Path | Behaviour |
|---|---|---|
| GET | `/` | Return `web/index.html` |
| GET | `/api/health` | `{"status":"ok","model":"small","loaded":bool,"error":str|null,"network_needed":false}` |
| GET | `/api/passages` | List of `{id, language, grade, title, text, tokens, word_count}` |
| WS | `/ws/read?passage_id=...` | See below. Unknown passage id → send an error message and close |
| POST | `/api/score` | See below |
| GET | `/api/results` | Last 20 saved rows as JSON, newest first |
| GET | `/api/export.csv` | `text/csv` download named `booklat-results.csv`; header-only file if there are no rows |

### WebSocket protocol
Client → server:
- binary frames: little-endian Int16 mono PCM at 16 kHz, any size (the server reframes);
- text `{"type":"stop"}`.

Server → client (JSON text):
- `{"type":"ready"}` once calibration finishes;
- `{"type":"update","marks":[{"idx":int,"status":str,"repeats":int,"heard":str|null,"t0":float|null,"t1":float|null,"self_corrected":bool}],"pointer":int,"latency_ms":int}` containing only changed words;
- `{"type":"done","marks":[...all words...],"first_t":float|null,"last_t":float|null}` after a stop, once all queued chunks are processed;
- `{"type":"error","message":str}` (for example when the model is not loaded).

Implementation: one `Aligner` and one `Chunker` per connection. The receive loop pushes audio and puts chunks on an `asyncio.Queue`; a worker task takes chunks in order, runs `transcribe` with `asyncio.to_thread`, feeds the aligner, and sends an `update`. `latency_ms` = time from when the chunk was queued to when its update is sent. On `stop`: flush the chunker, wait for the queue to drain, send `done`. If the client disconnects, cancel the worker and discard all state.

### `POST /api/score`
Body (validate with pydantic):
```json
{"session_id":"str","learner":"str","passage_id":"str",
 "marks":[{"status":"correct","repeats":0}],
 "first_t":1.2,"last_t":30.4,"teacher_edited":false,"save":false}
```
Rules: `marks` length must equal the passage word count; `status` must be one of the four values; `repeats` is an integer 0 to 20; `learner` is trimmed, 1 to 60 characters. Invalid input → HTTP 422 with a readable message. Return the scorer's dict plus `saved: bool`.

If `save` is true, write to `data/results.csv` (create with header if missing). Columns:
```
session_id,timestamp,learner,passage_id,language,grade,words_attempted,words_total,reading_time_s,wpm,accuracy_pct,level,substitutions,omissions,repetitions,teacher_edited
```
`timestamp` is local ISO 8601 to the second. **If a row with the same `session_id` already exists, replace it** (write to a temp file in the same folder, then `os.replace`), so re-saving after an edit never duplicates a row. Neutralise spreadsheet-formula injection: any text cell starting with `=`, `+`, `-` or `@` gets a leading `'`. Use the `csv` module.

## B10. `web/index.html`: design and behaviour

### Visual design tokens (CSS variables)
```
--bg:#f6f3ec;  --surface:#fffdf8;  --ink:#1f2430;  --muted:#5d6577;  --line:#e3ddd0;
--primary:#0f766e;  --primary-ink:#ffffff;  --focus:#1d4ed8;
--ok-bg:#d9f2e3;   --ok-ink:#14532d;
--bad-bg:#fbdcd8;  --bad-ink:#991b1b;
--skip-bg:#eceff3; --skip-ink:#4b5563;
--rep-bg:#fff3bf;  --rep-ink:#854d0e;
--lvl-ind:#15803d; --lvl-ind-bg:#dcfce7;
--lvl-ins:#a16207; --lvl-ins-bg:#fef3c7;
--lvl-fru:#b91c1c; --lvl-fru-bg:#fee2e2;
--radius:14px;  --shadow:0 1px 2px rgba(31,36,48,.06), 0 8px 24px rgba(31,36,48,.06);
font-family: ui-sans-serif, system-ui, "Segoe UI", Roboto, "Noto Sans", sans-serif;
```
Large, projector-friendly type: base 18px; passage text `clamp(1.75rem, 3vw, 2.75rem)`, line-height 1.8. Minimum button height 48px. Visible focus ring (3px `--focus`). Respect `prefers-reduced-motion` (no animations when set). Colour is never the only signal (see word styles).

### Page structure
- **Header:** wordmark "Booklat" with the tagline "Offline oral-reading assessor". On the right, two status chips: model status ("Speech model ready" green / "Loading speech model…" amber / "Model missing" red, from polling `/api/health` every 2 s until loaded) and "Works offline".
- **Footer line (always visible):** "Everything runs on this device. No audio is stored or sent."
- Three screens, only one visible at a time: **Setup**, **Reading**, **Results**.

### Setup screen
- Card with: learner name input (label "Learner name", required), passage select (option text: "Title · English/Filipino · N words"), a read-only passage preview, and a large **Start reading** button.
- Start is disabled until the model is loaded and a name is entered; show the reason in small text under the button.
- Below the card: **Recent readings** table from `/api/results` (Learner, Passage, WPM, Accuracy, Level badge) with a **Download CSV** link to `/api/export.csv`. Empty state: "No readings saved yet."

### Reading screen
- Top bar: learner name, passage title, a running timer (mm:ss from when `ready` arrives), a latency chip ("Marking delay: 640 ms", the median of the last 5 `latency_ms`), and a large **Stop** button (Space key also stops).
- A status line (`aria-live="polite"`): "Quiet for a moment…" until `ready`, then "Listening. Begin reading."
- The passage as one `<span class="w">` per display token, with a space between. Word states:
  - not reached: plain ink
  - correct: `--ok-bg` background, `--ok-ink` text
  - substitution: `--bad-bg`, `--bad-ink`, wavy underline
  - omission: `--skip-bg`, `--skip-ink`, line-through
  - repeats > 0: `--rep-bg` background with a small superscript "↻" (plus the count if greater than 1), dotted underline
  - self-corrected: as correct, plus a small "✓" superscript
  - pointer word (the next expected, from `pointer`): 3px bottom border in `--primary`
- Words are tappable. A tapped word is outlined and a **floating edit bar** appears at the bottom of the screen with five buttons: **✓ Correct**, **✗ Wrong**, **⊘ Skipped**, **↻ Repeated** (toggles between 0 and 1), **– Not read**. An edit sets the word's status or repeats, adds its index to a `locked` set (server updates for locked words are ignored from then on), and marks the session as teacher-edited. Escape or tapping elsewhere closes the bar.
- A short legend under the passage: ✓ correct · ✗ wrong · ⊘ skipped · ↻ repeated.

### Results screen
- Learner and passage heading.
- Four tiles: **Time** (mm:ss.s or "n/a"), **Words per minute** (or "n/a"), **Accuracy** (one decimal), **Reading level** (badge: Independent green, Instructional amber, Frustration red).
- A breakdown row: "Words attempted 41 of 48 · Wrong 2 · Skipped 1 · Repeated 1". If `partial` is true, add the note "Stopped before the end of the passage."
- The same tappable passage and edit bar. Each edit re-posts to `/api/score` (debounced 150 ms, `save:false`) and the tiles update.
- Buttons: **Save result** (posts with `save:true`; button then reads "Saved ✓", and returns to **Save changes** if the teacher edits again), **Download CSV**, **New reading**.
- A one-line honesty note: "Marks are suggestions. Tap any word to correct it."

### Audio capture
- On Start: request the microphone with `{audio:{channelCount:1, echoCancellation:false, noiseSuppression:true, autoGainControl:true}}`; create an `AudioContext`; register the worklet from a `Blob` URL (the processor code lives inline in the page, so no extra file is needed).
- The worklet receives Float32 input at the context's sample rate, resamples to 16 kHz by averaging samples within each output step, converts to Int16, and posts a 4000-sample `Int16Array` (transferred, not copied) each time it has 4000.
- Open `ws://localhost:8000/ws/read?passage_id=...` (build the URL from `location`), send each posted buffer as a binary message.
- On Stop: stop the tracks, close the audio context, send `{"type":"stop"}`, show "Finishing up…", and wait for `done` (15 s timeout, then show an error). Generate a `session_id` (`crypto.randomUUID()`) at Start. Apply the `done` marks except for locked words, call `/api/score` once, then show Results.

### Error and edge states (all with plain-language messages and a way to recover)
- Microphone permission denied or no microphone: message on Setup with how to allow it.
- Model missing or still loading: Start disabled, message "Speech model not found. Run ./scripts/setup.sh once while online." for the missing case.
- WebSocket closes unexpectedly during reading: stop capture, show a banner "Connection to the local server was lost", keep any marks received so far, and offer **Go to results** and **Start over**.
- Nothing heard when Stop is pressed: Results shows "No speech was detected" with **Try again**.
- Toasts for save success and errors (auto-dismiss after 3 s, `role="status"`).

## B11. Tests (all must pass without the Whisper model or a microphone)
- `test_aligner.py`: clean read; one skipped word; two skipped words; one repeated word (`repeats == 1`, pointer unchanged); a substituted real word; self-correction (wrong word then right word → `correct`, `self_corrected`, no miscue); stopping early (trailing words stay `not_reached`); a short word such as "ng" must not match "ang"; "mahal na mahal" read correctly in the Filipino passage; extra words after the end of the passage are ignored; ignore-words are skipped; `first_t`/`last_t` are taken from accepted words only.
- `test_scorer.py`: the Phil-IRI computation-guide example (65 words, 15 miscues → 76.9, frustration); boundary values (97.0 independent, 96.9 instructional, 90.0 instructional, 89.9 frustration); partial reading uses attempted words; WPM calculation; WPM is `None` under `min_time_s`; repetition counted or not according to config; zero attempted words returns `None` accuracy and level.
- `test_chunker.py`: synthetic audio (silence, tone bursts, silence): calibration sets the threshold; a burst followed by 0.5 s of silence yields one chunk; a long continuous tone is cut at `max_chunk_frames`; `t_start` values are correct; silence-only input yields no chunks; arbitrary push sizes give the same chunks as frame-sized pushes; `flush()` emits the trailing chunk.
- `test_api.py` (FastAPI `TestClient`, env `BOOKLAT_SKIP_MODEL=1`, temp results path via env var `BOOKLAT_RESULTS_PATH`): `/api/health`; `/api/passages` word counts are 48 and 44; `/api/score` validation errors (wrong length, bad status, empty learner); save creates the CSV with the right header; saving the same `session_id` twice replaces the row; a learner named `=cmd` is stored as `'=cmd`; `/api/export.csv` returns a header-only file when empty; `/api/results` ordering; a WebSocket connection with an unknown passage id returns an error message.
- `test_no_external_urls.py`: fail if `web/index.html` contains any `http://` or `https://` URL (the `ws://` URL must be built from `location` at runtime, not written out).

## B12. Scripts and project files
- **`requirements.txt`:** `fastapi`, `uvicorn[standard]`, `faster-whisper`, `rapidfuzz`, `pyyaml`, `numpy`, `pytest`, `httpx`.
- **`scripts/setup.sh`:** `set -euo pipefail`; `cd` to the repo root; create `.venv` with `python3 -m venv .venv` (reuse it if it already exists); activate it; `pip install -r requirements.txt`; run `python scripts/download_model.py`; print "Setup complete. Run ./run.sh". Make it executable.
- **`scripts/download_model.py`:** load the config, create `WhisperModel` with the configured size so it downloads and caches (this is the only network use in the project; say so in a comment), then print the model name and where it was cached.
- **`run.sh`:** `set -euo pipefail`; `cd` to the repo root; activate `.venv`; `export HF_HUB_OFFLINE=1`; `exec uvicorn server.main:app --host 127.0.0.1 --port 8000`. Make it executable.
- **`scripts/replay_clip.py <wav> <passage_id> [--realtime]`:** read a 16 kHz mono 16-bit WAV with the `wave` module (exit with a clear message otherwise); connect to the running server's WebSocket with the `websockets` library; stream 4000-sample frames (sleep 0.25 s per frame with `--realtime`, 0.02 s otherwise); print each update as `idx word status` lines; after `done`, POST to `/api/score` with `save:false` using `urllib.request` and print accuracy, WPM, level.
- **`README.md`:** what Booklat is, three-command quick start (`./scripts/setup.sh`, `./run.sh`, open `http://localhost:8000`), how to run tests, how to record and replay clips, where to tune `server/config.yaml`, how to add a passage (edit `data/passages.json`), the privacy statement, known limits (children's speech accuracy unproven, Whisper may auto-correct mispronunciations, teacher override is the safety net), and a troubleshooting list (no microphone permission, model missing, port in use).
- **`.gitignore`:** `.venv/`, `__pycache__/`, `.pytest_cache/`, `data/results.csv`, `clips/*` with `!clips/.gitkeep`.

## B13. Acceptance checklist (verify before you finish)
- [ ] `.venv/bin/python -m pytest -q` passes.
- [ ] With `BOOKLAT_SKIP_MODEL=1` under `TestClient`: `/`, `/api/health`, `/api/passages`, `/api/results`, `/api/export.csv` respond.
- [ ] No external URLs in `web/`; the page uses only system fonts.
- [ ] The server listens on `127.0.0.1` only; no audio is written to disk anywhere in the code.
- [ ] Every setting named in B4 is read from `config.yaml`, not hard-coded.
- [ ] Word states have non-colour cues (underline styles, strike-through, symbols).
- [ ] All buttons are at least 48px tall; focus is visible; status messages use `aria-live`.
- [ ] The final reply lists files created, test results, and the exact setup and run commands (`./scripts/setup.sh`, then `./run.sh`).

## B14. Do not
Do not add a database, accounts, a framework or build step for the front end, comprehension grading, insertion or mispronunciation categories, a second ASR model, GPU code, telemetry, or any feature not listed above. Do not download models during the build.
