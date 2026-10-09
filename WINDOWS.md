# Windows 11 setup (Intel / AMD x64)

Use a fresh clone. Do not copy the Linux `.venv`: environments are platform-specific. These `.cmd` scripts work from PowerShell or Command Prompt without changing PowerShell execution policy. Setup uses uv to create a local Python 3.12 environment; a separate system Python installation is not needed.

1. Install Git (if needed) and uv in PowerShell:

   ```powershell
   winget install --id Git.Git -e
   winget install --id astral-sh.uv -e
   ```

2. Close and reopen PowerShell, then clone the version containing the Windows scripts:

   ```powershell
   git clone https://github.com/elmntr/hackathon_booklat.git
   cd hackathon_booklat
   .\setup-windows.cmd
   ```

   If already cloned, run `git pull` in that folder instead. Setup needs internet for dependencies and both Vosk models. To download Whisper too, run `.\setup-windows.cmd whisper` instead. A missing Whisper model does not prevent Vosk from running.

3. Start the server:

   ```powershell
   .\run-windows.cmd
   ```

4. Open http://localhost:8000 in Chrome, Edge, or Brave. Allow the microphone, select **Vosk · continuous speech**, and wait for **Vosk ready**. Keep the terminal open. Later runs need only `.\run-windows.cmd`; internet is no longer required.

Model files and environments are ignored by Git and must be downloaded separately. You can instead copy the existing `models/` directory for Vosk, but never copy `.venv`. The Filipino model retains its CC-BY-NC-SA 4.0 noncommercial license.

## Optional NVIDIA GPU acceleration

The Vosk live trial runs on the CPU. To use an NVIDIA GPU, install the Whisper model with `.\setup-windows.cmd whisper`, install the CUDA 12 cuBLAS and cuDNN 9 runtime libraries, and make their DLL folders available on `PATH` before starting Booklat. See the [faster-whisper GPU instructions](https://github.com/SYSTRAN/faster-whisper#gpu) for the current Windows library setup. Restart PowerShell after changing `PATH`.

When CTranslate2 detects CUDA, Booklat automatically runs Whisper on the GPU with FP16 and a wider search beam; otherwise it falls back to CPU. The Whisper model chip shows **GPU** or **CPU**; hover over it to see the CUDA fallback reason. Select **Whisper · phrase recognition** in the app to use it. GPU acceleration speeds up Whisper inference, but Whisper still waits for each audio chunk to finish before updating; it does not accelerate the Vosk live stream. GPU support here requires NVIDIA CUDA. Other GPU vendors continue to use the CPU.

Resource settings are in `server/config.yaml`: `asr.device` (`auto`, `cpu`, or `cuda`), `cpu_threads`, `gpu_compute_type`, and `gpu_beam_size`. The default caps Whisper at four CPU threads and uses CUDA when ready. `BOOKLAT_DEVICE` overrides the device for a launch. Restart after changing settings. Both **As I read** and **After Stop** are available with either engine; Whisper still returns phrase-level results. Re-run setup once to install PDF import support, then imports and the SQLite library work offline.

## Compare hardware fairly

Use the same commit (`git rev-parse HEAD`), engine, model, passage, and configuration. Plug both laptops into power, close heavy apps, and use the same headset and speaker. Enable the debugger and compare queue wait and processing times over several readings. Include CPU model, RAM, browser version, and engine with the copied reports.

For a stronger comparison, transfer the same manually recorded 16 kHz mono 16-bit WAV and replay it in real time. This removes microphone and speaker variation. The app itself still never records audio. With the server running, in a second PowerShell window:

```powershell
.\.venv\Scripts\python.exe scripts\replay_clip.py clips\tl_clean.wav tl-g3-1 --engine vosk --realtime
.\.venv\Scripts\python.exe -m pytest -q
```

Replay checks the audio pipeline but is not a word-display-latency benchmark. Lower processing times with similar visible delay point toward recognition stabilization/context rather than CPU time alone. A 100 ms audio frame does not promise recognition within 100 ms.

## Troubleshooting

- Microphone blocked: check Settings → Privacy & security → Microphone, including desktop-app access, then your browser's site permissions.
- Native-library/DLL error: install the Microsoft Visual C++ x64 Redistributable from Microsoft's site and rerun setup.
- Port in use: stop the previous server with Ctrl+C.
- uv not found after installation: close and reopen PowerShell.
- Windows ARM PCs are not covered by these instructions; use an Intel/AMD x64 PC for this comparison.

The Windows launchers have not been executed on Windows by the developer agent. Run the test command above and one microphone reading on the target PC before comparing results.
