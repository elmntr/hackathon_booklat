# Booklat feature demo

Latest motion edit: `Booklat-demo-v3-57s.mp4` — 57 seconds at 1080p/30 fps. Transitions use 550 ms cubic ease-out and 150 ms entrance staggers: background, screenshot, chapter label, headline, supporting text. Directions alternate, screenshots scale from 98.5% to 100%, and the existing score panels reveal in sequence. The teacher-correction scene enters through black, then returns to the light palette. Closing text fades in within the history scene. No separate closing card, video header or footer. Short scenes were extended to retain readable holds. The continuous reading sequence retains direct word-mark updates.

### Earlier versions

Latest revision: `Booklat-demo-v2-53s.mp4` — 53 seconds. Animated Tupi introduction, no video header/footer or progress strip, deleted closing card, and a brighter original 124 BPM backing track. `verification-v2.json` records the measured export. The actual app navigation remains visible inside the walkthrough captures.

## Original version

`Booklat-demo-58s.mp4` is a 58.000-second, 1920×1080, 30 fps H.264 video with AAC audio and an original synthesized instrumental soundtrack. It has on-screen feature copy and no spoken narration.

The walkthrough uses actual Booklat browser screens with a fictional learner and synthetic recognizer events. Scores were calculated by the app's real scoring API against a separate temporary database. This is a mock demonstration, not a recording of speech-recognition performance.

Timeline:
- 00–04: Introduction
- 04–10: Learner and English / Filipino passage selection
- 10–15: Custom passage import
- 15–23: Progressive word marks
- 23–28: Large passage view
- 28–34: Teacher correction
- 34–40: Accuracy, pace and reading category
- 40–46: Teacher comprehension entry and grading report
- 46–53: Offline history and exports
- 53–58: Closing card

`source/capture.cjs` records the mock UI states with a temporary server and isolated database. It requires Playwright and a local Chromium browser; runtime paths reflect this workstation. `source/render.py` composes the captured screens, original soundtrack and final movie using Pillow, NumPy and FFmpeg. No application files or real learner records are modified.

`verification.json` records the export's measured duration, frame count and resolution.
