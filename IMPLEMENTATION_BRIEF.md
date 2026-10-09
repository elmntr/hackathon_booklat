# Booklat improvement brief

Improve Booklat as an offline English and Filipino reading practice and assessment app. Make recognition feedback responsive, preserve honest scoring, and let teachers use their own reading material.

## Requirements

1. **Responsive recognition.** Reduce avoidable processing, copying, and browser rendering work. Show provisional word decisions as soon as the recognizer supplies them; allow revisions. Report server processing and queue time separately. Use final word timestamps for WPM. Do not claim measured accuracy or latency improvements without comparable recordings.
2. **Validation timing.** Offer “As I read,” “Automatic finish,” and “After a pause.” Live mode shows correct, wrong, skipped, and repeated marks with a dotted outline while provisional. Automatic finish hides marks and ends capture only after the passage ending is confirmed, then reveals final marks together. Require a correctly recognized last word with confirmed timing; keep manual Stop available if recognition misses it. Pause mode highlights recognized words live and reveals decisions when the recognizer confirms a phrase. Pauses at commas and periods guide phrasing; printed punctuation alone is not a speech endpoint. Whisper also confirms at chunk boundaries. All modes use the same recognition and scoring rules. Remember the preference.
3. **Offline history.** Use a local SQLite database for reading sessions and custom passages. Automatically save completed readings when enabled, preserve word marks and recognition metadata, support teacher corrections, search and reopen history, export CSV, and download a database backup. Import existing CSV records once without changing the original file.
4. **Hardware use.** Use CUDA for Whisper when supported and ready, with an explained CPU fallback. Keep CPU thread use bounded and configurable. Show the selected device. Vosk supplies continuous feedback; Whisper supplies phrase recognition. Keep models local after setup.
5. **Personal reading library.** Accept pasted text, TXT, Markdown, text-based PDF, DOCX, and EPUB. Extract locally; preview and edit the words; select language and grade; choose a book excerpt; save it for later offline readings. Explain unreadable, scanned, encrypted, or oversized documents clearly.
6. **Verification.** Check provisional revisions, both display modes, durable history across restarts, CSV migration, backup readability, document extraction, and malformed input. Keep names, documents, and microphone audio on the device. No microphone audio should be recorded automatically.

## Additional improvements included

- Optional automatic saving and automatic saving of teacher edits.
- Searchable history and full word-by-word review of newly saved readings.
- Excerpt selection for books and word counts before starting.
- Persistent validation and engine preferences.
- Session engine/device metadata for meaningful speed and accuracy comparisons.

## Suggested next steps

- Microphone setup check with noise and clipping guidance before a reading.
- Optional offline OCR for scanned pages, with an editable preview.
- Learner progress charts that compare the same passages and recognition settings.
- A replay benchmark using teacher-labeled English and Filipino recordings to measure actual word error rate and word-to-highlight delay.
- Optional automatic scrolling and font-size controls for longer passages.

## Accuracy and latency boundaries

Recognition still depends on the model, microphone, speaker, and available context. A GPU can reduce inference time; it does not guarantee a more accurate transcript. Provisional marks are suggestions. Skipped words can be inferred after later words are recognized, and the final unread tail remains unattempted unless a teacher changes it.


## Follow-up feature status

- **Completion controls:** offer an adjustable end-of-reading grace period so a learner can repeat or correct the last sentence before capture ends. Keep manual Stop available.
- **Microphone readiness:** show an input-level meter and a short microphone check before reading, with useful feedback for silence and clipping.
- **Reading comfort:** optional automatic scrolling, adjustable passage font size, and line spacing; keep the active line visible without jumping on provisional revisions.
- **Review clarity:** filter incorrect, skipped, repeated, and unattempted words; show the expected word beside the recognized word. Keep teacher corrections available.
- **Recognition evidence:** provide an opt-in local recording for comparing recognition against actual speech. Include an explicit retention choice and deletion controls.
- **Long document practice:** divide imported books into named sections, retain the learner's place, and show section progress.
- **Offline reliability:** recover unfinished reading snapshots after a browser refresh, clearly distinguishing confirmed marks from provisional ones. Do not save a draft as a completed assessment.
- **Learner progress:** compare accuracy and fluency across readings of comparable passages, identifying repeated difficulties without treating ASR guesses as teacher-confirmed errors.

Implemented: configurable finish delay and cancellation, confirmed progress with active-line following, five-second input check, focused word review, one browser-local confirmed draft with continuation, and word-count book sections with per-learner browser-local position.

Still proposed: adjustable fonts/spacing, learner progress comparisons, and richer section boundaries. Drafts and section position are browser-local; the library and completed history use SQLite.


## Saved voice playback

Implemented a configurable history voice-recording option (enabled by default), WAV persistence in SQLite, playback and seeking synchronized with saved word times, expected/recognized text, word-level playback controls, WAV download, deletion of audio while retaining scores, and recording-inclusive database backups. Recovery records the remaining portion with a timing offset; missing pre-refresh audio is not reconstructed. Repeated-word counts remain aggregated rather than a timestamp for each separate repetition.


## Phil-IRI component rubric

Implemented separate word-recognition and comprehension criteria from DepEd PPST Module 11 (Phil-IRI), teacher-entered comprehension counts, a teacher-reviewed replacement miscue total, and provisional labelling for incomplete readings. Component calculations and the rubric snapshot are saved with each updated reading. CSV exports include rubric thresholds, source/version, formulas, counted miscue types, component scores and grading status. A printable standalone HTML report includes grading and word timestamps. Combined reading level follows the supplied adapted Phil-IRI table (either Frustration gives Frustration; otherwise use comprehension), when both components are assessed and the reading is complete; standardized administration, comprehension questioning and review of all miscue types remain teacher responsibilities.
