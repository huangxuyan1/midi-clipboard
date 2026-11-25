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
- **Chord symbols play** — `"Am"` and friends paste as bass and chord notes,
  matching what abcjs plays. See [Chord symbols](#chord-symbols).
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

MidiClipboard is an Ableton *remote script*: a folder you drop into Live's
`Remote Scripts` folder and switch on in Live's preferences. It takes about
five minutes, and there's nothing else to install. The background helper
carries its own Python.

### 1. Download

Get the zip for your computer from the
[latest release](https://github.com/huangxuyan1/midi-clipboard/releases/latest):

| Computer | File |
|---|---|
| Windows 10 or 11 | [`MidiClipboard-Windows.zip`](https://github.com/huangxuyan1/midi-clipboard/releases/latest/download/MidiClipboard-Windows.zip) |
| Mac with macOS 10.15 or later (Apple Silicon or Intel) | [`MidiClipboard-macOS.zip`](https://github.com/huangxuyan1/midi-clipboard/releases/latest/download/MidiClipboard-macOS.zip) |

Each zip holds a single folder, `MidiClipboard`.

### 2. Put the folder in Live's Remote Scripts folder

**Windows**

1. Right-click `MidiClipboard-Windows.zip` and choose **Properties**. If
   there's an **Unblock** checkbox near the bottom, tick it and click
   **OK**. Otherwise Windows may treat the helper as an untrusted download.
2. Right-click the zip and choose **Extract All…**.
3. Open the extracted folder and move the **`MidiClipboard`** folder inside
   it (the one that contains `MidiClipboard.py` and `bridge.exe`) into:
   ```text
   C:\Users\<you>\Documents\Ableton\User Library\Remote Scripts\
   ```
   Create the `Remote Scripts` folder if it doesn't exist. You should end up
   with `Remote Scripts\MidiClipboard\MidiClipboard.py`, not one folder
   deeper. If you moved your User Library, use that location instead. Live
   shows it under **Preferences → Library**.

**Mac, using Terminal (simplest)**

Open **Terminal** and paste these four lines. They download the zip and
unpack it straight into place:

```bash
mkdir -p ~/Music/Ableton/User\ Library/Remote\ Scripts
cd ~/Music/Ableton/User\ Library/Remote\ Scripts
curl -LO https://github.com/huangxuyan1/midi-clipboard/releases/latest/download/MidiClipboard-macOS.zip
unzip -q MidiClipboard-macOS.zip && rm MidiClipboard-macOS.zip
```

**Mac, using the browser and Finder**

1. Download `MidiClipboard-macOS.zip` and double-click it to unzip.
2. In Finder choose **Go → Go to Folder…**, enter
   `~/Music/Ableton/User Library/Remote Scripts`, and move the
   **`MidiClipboard`** folder there. Create `Remote Scripts` if it doesn't
   exist.
3. The helper isn't notarized by Apple, so macOS refuses to run a copy that
   came from a browser download. Clear that mark by pasting this into
   **Terminal**:
   ```bash
   xattr -dr com.apple.quarantine ~/Music/Ableton/User\ Library/Remote\ Scripts/MidiClipboard
   ```

### 3. Switch it on in Live

1. Start Live, or quit and restart it if it was open. Live only looks for
   new remote scripts when it starts.
2. Open Live's preferences (**Options → Preferences** on Windows, **Live →
   Settings** on a Mac; **Ctrl+,** / **Cmd+,**) and go to the
   **Link/Tempo/MIDI** tab (**Link, Tempo & MIDI** in Live 12).
3. In an empty **Control Surface** slot choose **MidiClipboard**. Leave its
   **Input** and **Output** set to **None**.
4. Live's status bar briefly shows **`MidiClipboard ready`**.

### 4. Mac only: allow Input Monitoring

The helper listens for the three shortcuts, so macOS asks whether **Ableton
Live** may *receive keystrokes from any application*. Turn on **Ableton
Live** in **System Settings → Privacy & Security → Input Monitoring**, then
quit and reopen Live. If Live isn't in the list, click **+** and add it from
`/Applications`. The listener reacts only to the three shortcuts, only while
Live is in front, and it can't block or change a keystroke.

The very first start after installing takes about 20 seconds while macOS
checks the helper's bundled libraries. After that it starts at once.

### 5. Check that it works

With Live in front, press **Ctrl+Shift+L** (**Cmd+Shift+L** on a Mac). A
small log window opens showing the helper's recent activity, including a
line such as `STATUS: MidiClipboard activated (trigger_bind=ok, bridge=ok …)`
from when Live started. If no window opens, see
[Troubleshooting](#troubleshooting).

### Updating and uninstalling

- **Update:** quit Live, delete the old `MidiClipboard` folder, install the
  new one as above, and start Live. If you changed any
  [settings](#settings), make the same changes again in the new copy.
- **Uninstall:** set the Control Surface slot back to **None**, quit Live,
  and delete the `MidiClipboard` folder.

## Usage

| Windows | Mac | Where | Action |
|---|---|---|---|
| **Ctrl + C** | **Cmd + C** | MIDI editor, notes selected | Ableton's normal copy **plus** the selected notes are written to the clipboard as ABC (or native text, see [Settings](#settings)). Nothing selected → behaves like plain copy, clipboard untouched. |
| **Ctrl + Shift + V** | **Cmd + Shift + V** | a MIDI clip open in detail view | Reads the clipboard (ABC or native text, detected automatically), parses the notes, and inserts them into the clip (Ctrl+Z / Cmd+Z to undo). |
| **Ctrl + Shift + L** | **Cmd + Shift + L** | anywhere in Ableton | Opens a small live-updating log window so you can see what the helper is doing. Close it any time. |

All shortcuts require Ableton to be the foreground window. On a Mac they
follow key positions on the US layout, so they're the same keys on QWERTZ
and AZERTY, but not on Dvorak.

The background helper starts automatically when Ableton loads the script
and shuts down when you deactivate it (or quit Live). It logs to
`MidiClipboard/bridge.log`.

### Copy notes out of Live

1. Double-click a MIDI clip so it opens in the detail view at the bottom of
   Live.
2. Select notes in the MIDI editor: click them, drag a box around them, or
   press **Ctrl+A** / **Cmd+A** for all of them.
3. Press **Ctrl+C** / **Cmd+C**. Live copies the notes as usual, and your
   system clipboard now also holds them as ABC text.
4. Paste the text anywhere: a chat, an email, a notation site, or a prompt
   to an AI model.

With no notes selected, the shortcut is just Live's normal copy and the
clipboard is left alone. Muted notes are left out of the ABC.

### Paste notes into Live

1. Copy some ABC text: a tune from a website, an AI model's reply, or
   something you copied out of Live. Any explanation or Markdown code fence
   around the tune is skipped.
2. In Live, open the MIDI clip that should receive the notes so it shows in
   the detail view. For a new clip, double-click an empty clip slot on a MIDI
   track.
3. Click anywhere in Live so it's the window in front, then press
   **Ctrl+Shift+V** / **Cmd+Shift+V**.
4. The notes appear in the clip, starting at its first beat. Paste adds to
   what's already in the clip, and **Ctrl+Z** / **Cmd+Z** takes it back out.

If the tune is longer than the clip, lengthen the clip (or its loop) to hear
the rest. Chord symbols such as `"Am"` become a bass-and-chord
accompaniment; see [Chord symbols](#chord-symbols). Text in the
[native format](#native-text-format) pastes the same way.

To try it, copy the triad example at the top of this page and paste it into
an empty clip.

### Use it with an AI model

- Ask for music in ABC: *"Write an 8-bar melody in D minor in ABC notation,
  with chord symbols."* Copy the reply and paste it into a clip.
- Or copy a few bars out of Live, paste them into the chat, and ask for a
  harmony line, a variation or a bassline. Then paste the answer back.

### Read the log

**Ctrl+Shift+L** / **Cmd+Shift+L** opens the log window. Every copy and
paste adds a line, such as `pasted 48 notes (ABC) into 'Verse'`, or says why
nothing happened, such as `copy ignored (no notes selected)`. The same lines
are saved in `MidiClipboard/bridge.log`.

## Settings

Settings live near the top of `MidiClipboard/MidiClipboard.py`. Open it in
any text editor, change the value, save, and restart Live.

| Setting | Default | What it does |
|---|---|---|
| `COPY_FORMAT` | `"abc"` | What copy writes: `"abc"` for ABC notation, or `"text"` for the lossless [native format](#native-text-format), which also keeps velocity, probability and exact timing. Paste reads both either way. |
| `CHORD_SYMBOLS` | `"abcjs"` | What paste does with chord symbols: `"abcjs"` plays them as an accompaniment, `"off"` pastes only the written notes. See [Chord symbols](#chord-symbols). |
| `BRIDGE_VISIBLE` | `False` | Windows only: `True` shows the helper's console window. |

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
- **Chord symbols** such as `"Dm"` become an accompaniment. See
  [Chord symbols](#chord-symbols).
- **Ignored:** decorations and dynamics, grace notes, slurs, lyrics, tempo
  (`Q:`), and part order (`P:`).
- Prose and Markdown code fences around the tune are skipped. Only the first
  tune in the clipboard is pasted.
- Two notes of the same pitch starting together become one, the longer.

### Chord symbols

Pasted chord symbols play the accompaniment the [abcjs](https://www.abcjs.net/)
library plays, note for note. That is also what the midishare site's piano
roll shows.

- Each bar plays a pattern set by the meter: in 4/4, bass on beats 1 and 3
  and the chord on beats 2 and 4. Notes last half a beat (eighths in x/4,
  sixteenths in x/8).
- The bass sits between MIDI 33 and 44 (Ableton's A0 to G#1), and the chord
  starts an octave above it. Slash chords such as `"D/F#"` put the slash note
  in the bass. Unknown chord types play as major, or minor when they start
  with `m`.
- A chord holds until the next symbol, across bar lines. Bars before the
  first symbol stay silent, and so does a bar with `"break"`. An unknown
  root, including `"N.C."`, is ignored, so the previous chord keeps playing.
- A pickup or short last bar plays the chord on alternate eighths only.
- `%%MIDI gchord` patterns (such as `fzczfzcz`) replace the meter's pattern.

To paste only the written notes, set `CHORD_SYMBOLS = "off"` (see
[Settings](#settings)).

The rules and the chord table are ported from abcjs 6.7.2 (MIT license,
© Paul Rosen and Gregory Dyke) in `MidiClipboard/chord_track.py`.

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
- **Windows: the helper never starts.** Check that `bridge.exe` is still in
  the `MidiClipboard` folder. Antivirus software sometimes quarantines
  self-contained Python apps like it. Restore it (or reinstall) and add an
  exception for the folder.
- **Mac: the helper never starts after a browser download.** Run the
  `xattr` command from [step 2](#2-put-the-folder-in-lives-remote-scripts-folder),
  then restart Live.
- **Mac: log says `no Input Monitoring permission`.** Turn on Ableton Live in
  **System Settings → Privacy & Security → Input Monitoring**, then quit and
  reopen Live. If Live isn't listed, click **+** and add it from
  `/Applications`.
- **Log says `already in use`.** Another helper is still holding the port.
  On Windows end stray `bridge.exe` / `python.exe` processes in Task Manager;
  on a Mac run `pkill -f MidiClipboard/bridge`. Then toggle the script.
- **Not in the Control Surface dropdown.** The folder must be named exactly
  `MidiClipboard` under `Documents\Ableton\User Library\Remote Scripts\`
  (Windows) or `~/Music/Ableton/User Library/Remote Scripts/` (Mac), with
  `MidiClipboard.py` directly inside it. A common slip is one folder too
  many, such as `Remote Scripts\MidiClipboard-Windows\MidiClipboard`. Live
  also needs a restart to see a newly added script.

## Requirements

- Windows 10 / 11, or macOS 10.15+ (Apple Silicon or Intel)
- Ableton Live 11 or 12
- No Python required for end users (it ships in the bundled helper)

## Roadmap

- Sign and notarize the Mac helper, so a browser download runs without the
  `xattr` step
- Configurable hotkeys and ports
- Optional time-shift on paste (to playhead instead of recorded positions)
- A hotkey to switch the copy format without editing the script
