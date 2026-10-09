# Android feature parity

This tracks the port against current `web/index.html`, `web/BRAND.md` and the backend and tests. The Android implementation lives entirely in `android/`. Desktop files are unchanged.

| Web behavior | Android implementation | Evidence |
|---|---|---|
| Landing and Setup | Compose screens, Booklat palette and six original Tupi poses | APK builds; device view pending |
| Learner and four-row searchable passage list | Local library and bounded Compose list | APK builds; device view pending |
| Passage preview and full ruled reading view | Serif ruled layout, native full-window dialog | APK builds; device view pending |
| Preset and positive decimal Custom size | Dropdown and decimal field, no cap or spinner | APK builds; device view pending |
| TXT, Markdown, PDF, DOCX, EPUB and paste | Document picker, bounded parsing on IO worker | APK builds; device import pending |
| Passage title, language, grade, excerpt, edit, save | Compose form, selection, SQLite | APK builds; device view pending |
| Offline English/Filipino recognition | Vosk Android, explicit download/ZIP install | Native library packaged; real audio pending |
| Provisional/confirmed word tracking and timing modes | Ported alignment; live, after-pause, auto-finish | JVM parity tests pass; device pending |
| Progress, timer, Stop, line following, focused line | Native reading screen and measured line layout | APK builds; device view pending |
| Teacher word corrections | Locked correct/wrong/skipped/not-read/repeat marks | JVM mark tests pass; device pending |
| Time, WPM, accuracy, category, Phil-IRI components | Ported formulas; no overall placement | JVM score/grading tests pass |
| Reviewed miscues and comprehension | Validated teacher fields | JVM grading test; device pending |
| Optional recording, playback, word playback, WAV/delete | Private WAV portions, MediaPlayer, FileProvider | APK builds; device audio pending |
| History, search, category colors, reopen, CSV, report, backup | SQLite and share sheet exports | APK builds; device I/O pending |
| Settings, microphone check, autosave, diagnostics, draft recovery | Preferences and confirmed-mark draft | APK builds; device pending |
| Android permission/lifecycle | On-demand permission, safe stop, foreground handling, ViewModel rotation | APK builds; device pending |

Removed web controls are absent: passage filters, favorites, three-dot menu, book sections and thinking dots. No cloud ASR is used. The app is light only, matching current `web/BRAND.md`.

See [VALIDATION.md](VALIDATION.md) for completed checks and remaining runtime limits.
