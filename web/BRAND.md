Booklat joins “book” with the sound of “buklat”: opening a page, together.
The idea is a place held for each reader, like a folded bookmark made by a teacher.
Personality: patient, tactile, companionable.
It is not a game, a judgement, a tourist postcard, or a technology showroom.
Vermilion #A33A26 gives the bookmark a recognisable ink colour; peach #F4B39D softens its paper folds.
Mist #EEF1ED and chalk #FAFBF8 keep the classroom bright; charcoal #252C2A and slate #53605A keep text clear.
Semantic green, wine, grey, amber and blue remain separate from the brand, paired with marks and distinct underlines.
Trebuchet MS with system sans fallbacks makes the wordmark and headings feel like classroom lettering; system-ui keeps controls familiar.
Georgia with system serif fallbacks gives passages the rhythm of a printed reader, with large type and generous line spacing.
Tupi is a folded bookmark with a notched hem, a turned corner and small paper-fold arms: a companion holding your place and listening.
Rejected: a talking booklet would become a book with eyes; a voice-wave creature would become an abstract blob without a tangible classroom connection.
Tupi welcomes, listens, cheers, offers a hand, stays kindly beside a difficult reading, and waits patiently when nothing is heard; it never covers a word.

## Landing and voice
The landing introduces oral-reading assessment with the same folded bookmark, vermilion ink and system type as the app.
It names the reading task, shows real word marks, and states the speech recognizer's validation limit for children's voices.
Copy describes what the teacher does on their laptop. No slogans, exclamation marks or decorative status labels.
Surfaces have square edges, controls use 4px corners, temporary messages use 8px, and word marks use 2px. Table cells stay continuous inside their rounded container. Borders and tone carry hierarchy; ordinary surfaces have no drop shadow.
All layout spacing comes from the shared 4px-based CSS scale. The existing ruled passage preview represents the teacher's reading notebook.
The demo reveals the app's actual word states in sequence. Reduced motion shows the final marks without a loop.
Entry is remembered in a JavaScript variable only. Reloading brings the landing back.
Secondary explanations sit inside the closed About Booklat disclosure. Main screens use headings, labels and live state; mascot captions and repeated helper paragraphs are omitted.
The landing pairs large classroom lettering with a slightly turned reading sheet. Its folded corner and firm offset edge come from Tupi’s paper bookmark; the live passage remains clear of the mascot.

The setup greeting sits above Tupi’s right shoulder without a bubble. Tupi gently waves there. The landing mascot stays still, and reduced motion keeps the waving arm still.


## Application integration

Landing, Setup, Reading and Results each have one screen and one set of script hooks. Tupi and the existing typography and palette remain the visual language. The landing describes the current optional local voice recording and SQLite history; CSV is an export of that history. It describes Phil-IRI component criteria rather than claiming an automatic overall assessment. Teacher corrections, recording playback, imports, draft recovery and rubric reports remain available through the same flow.


## Reading controls and large view

Passage titles sit in a searchable four-row list, beside the selected reading preview. History uses a measured four-row viewport. Preferences have a separate Settings page, reached from the header icon. It groups reading timing, microphone checks and saved readings. Diagnostics stay in a closed Advanced disclosure. Vosk is selected internally; the classroom setup does not ask a teacher to choose a recognition engine. Large passage view uses the same live word elements, reader typeface and marks in a nearly full-window dialog, with text-size, collapse and Stop controls. The preview card moves into the overlay with its title and passage options intact. Native dialogs contain keyboard focus and the page returns each passage to its original position on close.


## Favorites and classroom projection

The selected passage has a three-dot options menu with the favorite action; grade, language and favorite filters share the searchable four-row list. Projector mode centers the current line with the same reader typeface, ink palette and word marks. It reuses the reading's validation timing, teacher editor and Stop control. Full-passage mode remains one button away.


## Minimal classroom controls

Booklat links back to the landing page from the shared header. The header contains one Settings icon. The expand and collapse shapes follow the supplied reference. Other control icons come from Tabler and are stored inline for offline use. Buttons have accessible labels and visible keyboard focus.

History offers optional category colors for actual reading levels. Save a copy groups score downloads and a recording-inclusive backup with plain explanations. Older readings load when the teacher scrolls to the end of the four-row history area.

Taste-skill design read: preserve the Booklat classroom identity with low motion and compact controls. DESIGN_VARIANCE 4, MOTION_INTENSITY 2, VISUAL_DENSITY 4. Keep the local HTML and CSS architecture. Tupi remains the original bookmark illustration. No additional decorative images are needed for these controls.

## Restored classroom composition
The earlier mist-and-chalk classroom identity is restored. Vermilion anchors the setup controls; charcoal anchors the passage and report. The landing is a slightly turned reading sheet with a hard offset edge. Results use an asymmetric report: reading category and Tupi on the left, time and pace in the middle, accuracy on the right. Settings use a ruled sheet, not a collection of rounded cards. New passage filters, favorites, imports, history, recordings, grading and projector controls keep their existing behavior. No new assets or dependencies. DESIGN_VARIANCE 5, MOTION_INTENSITY 2, VISUAL_DENSITY 3.

Helper paragraphs are removed from the main screens. Passage search and its optional filter menu share one row under Passages. The expand control sits beside the selected title with a solid vermilion background. Live statuses, empty states and errors remain.

Passages use a searchable combobox with up to four visible rows and scrolling. Optional grade, language and favorite filters live inside the dropdown; the passage count is kept hidden. Arrow keys navigate, Enter selects, Escape closes, and outside focus dismisses the list.

Passage filters and favorites are removed. Search alone chooses a passage. The title has one expand control at its right edge, replacing the three-dot menu. Full passage view uses the same paper binding and ruled lines, with rule spacing following the selected text size.

Full passage text size accepts any positive number of pixels, with no upper cap. Import controls use one document action, a filename, a compact metadata column and a larger passage editor. Save actions sit together below the editor; the native file input remains hidden behind a keyboard-accessible button.

Book-section creation is removed from the import section. Text size uses the original preset dropdown plus Custom, which reveals a plain decimal text field with no spinner. Remaining numeric form controls also omit spinner arrows.
