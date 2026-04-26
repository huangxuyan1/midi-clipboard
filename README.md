# midi-clipboard

Copy and paste MIDI notes between Ableton Live and any other app, as text.

Pick notes in a clip, press a hotkey, paste them into a chat, an email, a
text editor, another DAW — anywhere that takes text. Going the other way:
copy text in the agreed format from anywhere, hit a hotkey, and the notes
land in your selected clip.

## Install

1. Copy the `MidiClipboard` folder into Ableton's user remote-scripts folder:
   ```
   C:\Users\<you>\Documents\Ableton\User Library\Remote Scripts\MidiClipboard\
   ```
2. In Ableton: **Preferences → Link/Tempo/MIDI → Control Surface →
   MidiClipboard**. Leave Input and Output set to **None**.
3. The status bar should briefly show `MidiClipboard ready`.

## Use

1. Start the helper:
   ```
   python receiver.py
   ```
   Keep the window open while you work.
2. In Ableton, open a MIDI clip and select some notes.
3. Press **Ctrl+Shift+C** while Ableton is the active window.
   The notes are printed in the helper's window, ready to be copied.

The hotkey only fires when Ableton is in the foreground — your normal
Ctrl+C, copy/paste, etc. in other apps are untouched.

## Status

| What | Works today |
|---|---|
| Read selected notes from Ableton on hotkey | yes |
| Captures all per-note properties (pitch, time, duration, velocity, mute, probability, velocity deviation, release velocity) | yes |
| Hotkey scoped to Ableton (no global hijack) | yes |
| Auto-write to the OS clipboard | not yet — output currently goes to the helper window |
| Paste text → notes back into Ableton | not yet |

## Troubleshooting

- **Nothing happens when I press the hotkey.** Make sure both the helper
  window and Ableton are running, and that Ableton is the focused window.
- **Helper says "BIND FAILED".** A previous helper is still running.
  Close any other terminals running `receiver.py` (or kill stray
  `python.exe` from Task Manager) and start it again.
- **The script doesn't appear in the Control Surface dropdown.** Confirm
  the folder name is exactly `MidiClipboard` and lives under
  `Documents\Ableton\User Library\Remote Scripts\`.

## Requirements

- Windows 10/11
- Ableton Live 11 or 12
- Python 3.x for the helper (only standard library is used)
