# midi-clipboard

**Copy MIDI notes out of Ableton Live as plain text — and paste text back in as notes.**

![Platform: Windows | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-0078D6)
![Ableton Live 11 | 12](https://img.shields.io/badge/Ableton%20Live-11%20%7C%2012-1A1A1A?logo=abletonlive&logoColor=white)
![Install: none required](https://img.shields.io/badge/install-none%20required-3FB950)
![Built with Python](https://img.shields.io/badge/built%20with-Python%203-3776AB?logo=python&logoColor=white)
![Status: working](https://img.shields.io/badge/status-working-3FB950)

Select notes in a clip, press **Ctrl+C** (**Cmd+C** on a Mac), and they land
on your system clipboard as [ABC notation](https://abcnotation.com/) — the
plain-text music format that notation apps, tune sites and LLMs already
read. Copy ABC from anywhere, press **Ctrl+Shift+V** (**Cmd+Shift+V**), and
the notes appear in your selected clip. Ableton's own copy/paste keep
working exactly as before — this rides alongside them.

```text
X:1
T:Triad
M:4/4
L:1/8
Q:1/4=120
K:C
[CEG]8 |]
```

That's a C major triad held for one bar. Paste it into a chat, an email, a
text file, a notation app — or hand it to an AI and ask for a variation.

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
- **ABC notation by default** — copies are standard ABC, and paste accepts
  ABC from the web or an LLM. See [ABC notation](#abc-notation).
- **Lossless native format** — an alternative text format that also keeps
  velocity, probability and exact timing. See
  [Native text format](#native-text-format).
- **Context metadata** — copies carry tempo, time signature, key and clip name;
  the native format adds clip length, track name and arrangement position.
- **Foreground-scoped hotkeys** — they only fire while Ableton is the active
  window, so your shortcuts in every other app are untouched.
- **No Python install** — the background helper ships self-contained:
  `bridge.exe` on Windows, the `bridge-macos` folder on a Mac.

## Install

### Windows

1. Download/copy the **`MidiClipboard`** folder (it includes the prebuilt
   `bridge.exe`) into Ableton's user remote-scripts folder:
   ```text
   C:\Users\<you>\Documents\Ableton\User Library\Remote Scripts\MidiClipboard\
   ```
2. In Ableton: **Preferences → Link/Tempo/MIDI → Control Surface →
   `MidiClipboard`**. Leave **Input** and **Output** set to **None**.
3. The status bar briefly shows **`MidiClipboard ready`**. Done — no other
   dependencies.

### macOS

1. Copy the **`MidiClipboard`** folder (it includes the prebuilt
   `bridge-macos` helper) to:
   ```text
   ~/Music/Ableton/User Library/Remote Scripts/MidiClipboard/
   ```
   Create the `Remote Scripts` folder if it doesn't exist. Use `git clone`
   rather than a zip download: macOS quarantines downloaded zips, and the
   helper isn't notarized.
2. In Ableton: **Live → Preferences** (**Settings** in Live 12) **→
   Link/Tempo/MIDI → Control Surface → `MidiClipboard`**. Leave **Input**
   and **Output** set to **None**.
3. **Allow keystroke monitoring.** The helper listens for the shortcuts, so
   macOS asks whether **Ableton Live** may *receive keystrokes from any
   application*. Turn on **Ableton Live** in **System Settings → Privacy &
   Security → Input Monitoring**, then quit and reopen Live. The listener
   only acts on the three shortcuts below while Live is frontmost, and it
   never blocks or changes a keystroke.
4. The status bar briefly shows **`MidiClipboard ready`**. The very first
   start after installing takes about 20 seconds while macOS checks the
   helper's bundled libraries; after that it starts instantly.

## Usage

| Windows | Mac | Where | Action |
|---|---|---|---|
| **Ctrl + C** | **Cmd + C** | MIDI editor, notes selected | Ableton's normal copy **plus** the selected notes are written to the clipboard as ABC (or native text, see [Choosing the copy format](#choosing-the-copy-format)). Nothing selected → behaves like plain copy, clipboard untouched. |
| **Ctrl + Shift + V** | **Cmd + Shift + V** | a MIDI clip open in detail view | Reads the clipboard (ABC or native text, detected automatically), parses the notes, and inserts them into the clip (Ctrl+Z / Cmd+Z to undo). |
| **Ctrl + Shift + L** | **Cmd + Shift + L** | anywhere in Ableton | Opens a small live-updating log window so you can see what the helper is doing. Close it any time. |

All shortcuts require Ableton to be the foreground window. On a Mac they
follow key positions on the US layout, so they're the same keys on QWERTZ
and AZERTY, but not on Dvorak.

The background helper starts automatically when Ableton loads the script
and shuts down when you deactivate it (or quit Live). It logs to
`MidiClipboard/bridge.log`.

## ABC notation

Clipboard text containing a `K:` (key) line is read as ABC; anything else
is read as the [native text format](#native-text-format).

```text
X:1
T:Little Waltz
M:3/4
L:1/8
K:Dm
"Dm"A3 B A2 | "Gm"G4 F2 | "A7"E2 ^C2 E2 | "Dm"D6 |
```

ABC `C` is middle C (MIDI 60, Ableton `C3`), and times are Live beats
(quarter notes) from the clip's beat 0.

### Copying (Ctrl+C / Cmd+C)

- The key signature is the clip's scale. (Live reports the scale of the clip
  you're editing through `song.root_note` and `song.scale_name`.) Scales
  with no ABC key signature, such as Whole Tone, fall back to guessing the
  key from the notes. Notes outside the key get accidentals.
- Timing snaps to a 1/12-beat grid, which covers sixteenths and eighth- and
  sixteenth-note triplets.
- Notes that start together with the same length become chords (`[CEG]`).
  Notes that overlap with different lengths go into separate voices
  (`V:1`, `V:2`, …), highest first.
- Notes crossing a bar line are tied; runs of empty bars become `Z` rests,
  so positions survive a round trip.
- Muted (deactivated) notes are left out, since ABC can't mark a note as
  muted. If every selected note is muted, the clipboard is left untouched.
  Use the native format to keep them.
- Velocity and probability are not written (pasted notes come back at
  Live's default velocity). Notes before the clip start shift to the
  nearest earlier bar line.

### Pasting (Ctrl+Shift+V / Cmd+Shift+V)

- **Understood:** `M:` / `L:` / `K:` (all modes, plus explicit accidentals
  such as `K:D ^g`), note lengths, rests (`z`, `x`, `Z`, `X`), chords,
  ties, broken rhythm (`>` `<`), tuplets, key-signature and bar-scoped
  accidentals, inline fields (`[K:G]`), voices (`V:`, each from beat 0),
  voice overlay (`&`), and repeats with numbered endings, which are written
  out in full.
- **Ignored:** chord symbols, decorations and dynamics, grace notes, slurs,
  lyrics, tempo (`Q:`), and part order (`P:`).
- Prose and Markdown code fences around the tune are skipped. Only the first
  tune in the clipboard is pasted.

## Choosing the copy format

Copy writes ABC by default. To copy the lossless native format instead,
set `COPY_FORMAT = "text"` near the top of `MidiClipboard/MidiClipboard.py`
and restart Live. Paste reads both formats either way.

## Native text format

A `notes:` block, one note per line — `pitch start duration` plus optional
named fields — preceded by an optional `meta:` block of context:

```text
meta:
  tempo=120
  time_sig=4/4
  root_note=9
  scale_name="Major"
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
   │  MidiClipboard remote     │  UDP :19845│  bridge                  │
   │  script (Live's Python)   │ ◄──────────│   • keyboard listener    │
   │   • reads/writes clip     │  trigger   │     (foreground-aware)   │
   │     notes via Live API    │            │   • OS clipboard r/w     │
   │   • serializes/parses     │  UDP :19846│   • spawns the log window│
   │     ABC / native text     │ ──────────►│                          │
   └──────────────────────────┘   notes    └──────────────────────────┘
```

The remote script handles everything that needs the Live API; the bridge
handles everything that needs the operating system. `bridge.py` is the
shared core (UDP, logging, the log window) and loads one backend per OS:

- `bridge_win.py` — a `WH_KEYBOARD_LL` hook and the Win32 clipboard, through
  `ctypes`.
- `bridge_mac.py` — a listen-only Quartz event tap and `pbcopy` / `pbpaste`,
  through pyobjc. Listen-only means it can't block or change keystrokes.

The bridge is a PyInstaller bundle that carries its own Python + Tk, so end
users install nothing: `bridge.exe` on Windows, the `bridge-macos/` folder on
a Mac.

## Building from source (developers)

Windows:

```text
pip install pyinstaller
python build_bridge.py        # → MidiClipboard/bridge.exe
```

macOS, using the [python.org](https://www.python.org/downloads/macos/)
universal2 Python (it ships the Tk the log window needs):

```text
python3 -m pip install pyinstaller pyobjc-framework-Quartz pyobjc-framework-Cocoa
python3 build_bridge.py       # → MidiClipboard/bridge-macos/bridge (universal2)
```

`build_bridge.py` bundles `MidiClipboard/bridge.py` + `viewer.py` + the OS
backend into one artifact with two roles (the second via `--viewer`). On a
Mac it's a folder rather than a single file: a single-file bundle unpacks
fresh libraries on every launch, and macOS then re-checks each one, so every
start took about 17 seconds. The folder gets checked once.

If the built helper is absent, the remote script falls back to launching
`bridge.py` from source — convenient while iterating. On Windows that runs
`python` from `PATH`. On a Mac, Live started from the Dock has a minimal
`PATH`, so the script looks for the python.org Python first, then Homebrew's;
set `MAC_PYTHON_EXE` in `MidiClipboard.py` to force one. That Python needs
the two pyobjc packages above.

The ABC reader/writer has unit tests that run outside Live:

```text
python -m unittest discover -s tests
```

For live development, point the Remote Scripts folder at the repo so Live
loads your working copy, then restart Live after each change (it doesn't
reload remote-script code while running).

Windows:

```text
mklink /J "%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\MidiClipboard" "<repo>\MidiClipboard"
```

macOS:

```text
ln -s "<repo>/MidiClipboard" ~/Music/Ableton/User\ Library/Remote\ Scripts/MidiClipboard
```

Script import errors go to Live's own log (`Log.txt`, in
`%APPDATA%\Ableton\Live 11.*\Preferences\` on Windows and
`~/Library/Preferences/Ableton/Live 11.*/` on a Mac).

## Troubleshooting

- **Nothing happens on Ctrl+C / Cmd+C.** Press **Ctrl+Shift+L** /
  **Cmd+Shift+L** to open the log. If no window opens, read
  `MidiClipboard/bridge.log` directly. If its last lines aren't from today,
  the bridge isn't running — toggle the script off/on in Ableton's
  preferences.
- **Mac: log says `no Input Monitoring permission`.** Turn on Ableton Live in
  **System Settings → Privacy & Security → Input Monitoring**, then quit and
  reopen Live. If Live isn't listed, click **+** and add it from
  `/Applications`.
- **Log says `already in use`.** Another helper is still holding the port.
  On Windows end stray `bridge.exe` / `python.exe` processes in Task Manager;
  on a Mac run `pkill -f MidiClipboard/bridge`. Then toggle the script.
- **Not in the Control Surface dropdown.** The folder must be named exactly
  `MidiClipboard` under `Documents\Ableton\User Library\Remote Scripts\`
  (Windows) or `~/Music/Ableton/User Library/Remote Scripts/` (Mac).

## Requirements

- Windows 10 / 11, or macOS 10.15+ (Apple Silicon or Intel)
- Ableton Live 11 or 12
- No Python required for end users (it ships in the bundled helper)

## Roadmap

- Sign and notarize the Mac helper, so it also runs from a zip download
- Configurable hotkeys and ports
- Optional time-shift on paste (to playhead instead of recorded positions)
- A hotkey to switch the copy format without editing the script
