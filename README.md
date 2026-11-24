# midi-clipboard

**Copy MIDI notes out of Ableton Live as plain text — and paste text back in as notes.**

![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Ableton Live 11 | 12](https://img.shields.io/badge/Ableton%20Live-11%20%7C%2012-1A1A1A?logo=abletonlive&logoColor=white)
![Install: none required](https://img.shields.io/badge/install-none%20required-3FB950)
![Built with Python](https://img.shields.io/badge/built%20with-Python%203-3776AB?logo=python&logoColor=white)
![Status: working](https://img.shields.io/badge/status-working-3FB950)

Select notes in a clip, press **Ctrl+C**, and they land on your system
clipboard as clean, human-readable text. Copy text in the same format from
anywhere, press **Ctrl+Shift+V**, and the notes appear in your selected
clip. Ableton's own copy/paste keep working exactly as before — this rides
alongside them.

```text
notes:
  note start dur ...
  C3 0 1
  E3 0 1
  G3 0 1
```

That's a C major triad. Paste it into a chat, an email, a text file,
another DAW — or hand it to an AI and ask for a variation.

---

## Why

- **Share musical ideas as text** — drop a riff into a message, no file export.
- **Use LLMs as a co-writer** — ask a model to harmonize, transpose, extend,
  or reharmonize a progression, then paste the result straight back into Live.
- **Diff and version-control MIDI** — notes become readable lines you can
  commit and compare.
- **Move ideas between projects** without bouncing stems or dragging files.

## Features

- **Two-way** — clip → clipboard and clipboard → clip.
- **Readable format** — note names (`C#3`), beats, and only the fields that
  matter. See [the format guide](grammar.md).
- **Context metadata** — copies carry tempo, time signature, clip length,
  clip/track name, and arrangement position.
- **Foreground-scoped hotkeys** — they only fire while Ableton is the active
  window, so your shortcuts in every other app are untouched.
- **No Python install** — the background helper ships as a self-contained
  `bridge.exe`.

## Install

1. Download/copy the **`MidiClipboard`** folder (it includes the prebuilt
   `bridge.exe`) into Ableton's user remote-scripts folder:
   ```text
   C:\Users\<you>\Documents\Ableton\User Library\Remote Scripts\MidiClipboard\
   ```
2. In Ableton: **Preferences → Link/Tempo/MIDI → Control Surface →
   `MidiClipboard`**. Leave **Input** and **Output** set to **None**.
3. The status bar briefly shows **`MidiClipboard ready`**. Done — no other
   dependencies.

## Usage

| Shortcut | Where | Action |
|---|---|---|
| **Ctrl + C** | MIDI editor, notes selected | Ableton's normal copy **plus** the selected notes are written to the clipboard as text. Nothing selected → behaves like plain Ctrl+C, clipboard untouched. |
| **Ctrl + Shift + V** | a MIDI clip open in detail view | Reads the clipboard, parses the notes, and inserts them into the clip (`Ctrl+Z` to undo). |
| **Ctrl + Shift + L** | anywhere in Ableton | Opens a small live-updating log window so you can see what the helper is doing. Close it any time. |

All shortcuts require Ableton to be the foreground window.

The background helper starts automatically when Ableton loads the script
and shuts down when you deactivate it (or quit Live). It logs to
`MidiClipboard/bridge.log`.

## The text format

A `notes:` block, one note per line — `pitch start duration` plus optional
named fields — preceded by an optional `meta:` block of context:

```text
meta:
  tempo=120
  time_sig=4/4
  clip_length=8
  clip_name="Verse Riff"
  track_name="Grand Piano"

notes:
  note start dur ...
  A2 0 0.5 vel=90
  C#3 0 0.5 vel=90
  E3 0 0.5 vel=90
  C#4 0 0.5 vel=127
```

- **Pitch** is a note name (`C3`, `F#4`, `Bb2`) where **`C3` = middle C =
  MIDI 60** (Ableton's convention), or a raw MIDI number `0–127`.
- **start** and **duration** are in beats.
- Optional fields (`vel`, `mute`, `prob`, `vdev`, `rvel`) are shown only
  when they differ from Live's defaults.
- The `meta:` block is read-only context; it's never written back on paste.

The formal grammar (EBNF + tolerance rules) lives in
**[`grammar.md`](grammar.md)**.

## How it works

Ableton's embedded Python is sandboxed — it has no `ctypes` (so no global
hotkeys or OS clipboard) and no working GUI toolkit. So the project is two
cooperating processes that talk over localhost UDP:

```text
        Ableton Live process                     external helper
   ┌──────────────────────────┐            ┌──────────────────────────┐
   │  MidiClipboard remote     │  UDP :19845│  bridge.exe              │
   │  script (Live's Python)   │ ◄──────────│   • global keyboard hook │
   │   • reads/writes clip     │  trigger   │     (foreground-aware)   │
   │     notes via Live API    │            │   • OS clipboard r/w     │
   │   • serializes/parses     │  UDP :19846│   • spawns the log window│
   │     the text format       │ ──────────►│                          │
   └──────────────────────────┘   notes    └──────────────────────────┘
```

The remote script handles everything that needs the Live API; the bridge
handles everything that needs the operating system. `bridge.exe` is a
PyInstaller bundle that carries its own Python + Tk, so end users install
nothing.

## Building from source (developers)

```text
pip install pyinstaller
python build_bridge.py        # → MidiClipboard/bridge.exe
```

`build_bridge.py` bundles `MidiClipboard/bridge.py` + `viewer.py` into a
single `bridge.exe` (one artifact, two roles via `--viewer`). If
`bridge.exe` is absent, the remote script falls back to launching
`python bridge.py` — convenient while iterating, but it then requires a
system Python on `PATH`.

## Troubleshooting

- **Nothing happens on Ctrl+C.** Press **Ctrl+Shift+L** to open the log.
  If it's empty, the bridge isn't running — toggle the script off/on in
  Ableton's preferences.
- **Log says `BIND FAILED`.** Another helper is still holding the port.
  End stray `bridge.exe` / `python.exe` processes in Task Manager, then
  toggle the script.
- **Not in the Control Surface dropdown.** The folder must be named exactly
  `MidiClipboard` under `Documents\Ableton\User Library\Remote Scripts\`.

## Requirements

- Windows 10 / 11
- Ableton Live 11 or 12
- No Python required for end users (it ships in `bridge.exe`)

## Roadmap

- macOS support (the bridge is Windows-only today)
- Configurable hotkeys and ports
- Optional time-shift on paste (to playhead instead of recorded positions)

