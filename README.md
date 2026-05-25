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

1. The helper starts automatically in the background when Ableton loads
   the script — there's no console window to manage. It writes to a log
   file at `MidiClipboard/helper.log`.
2. Open a MIDI clip in the detail view and select some notes.
3. **Copy:** press **Ctrl+C** while Ableton is the active window —
   Ableton does its normal copy *and* the notes are placed on the
   Windows clipboard as text. Paste anywhere with Ctrl+V.
   - If nothing is selected (or you're in a text field, etc.), Ctrl+C
     behaves exactly like Ableton's native Ctrl+C — the OS clipboard
     isn't touched.
4. **Paste:** open the target MIDI clip in the detail view, then press
   **Ctrl+Shift+V**. The helper reads the OS clipboard, the script
   parses the note text, and the notes are added via
   `clip.add_new_notes()`. Ctrl+Z to undo.
   - Notes are inserted at their recorded `start_time` (so a perfect
     round-trip back into the source clip lands them on top of the
     originals). Shift them in Ableton if you need different positions.
5. Press **Ctrl+Shift+L** (also while Ableton is foreground) to open a
   live tail of the helper's log in a PowerShell window, when you want
   to see what's happening. Close the viewer window any time — it's a
   separate process, the helper keeps running.

Both hotkeys only fire when Ableton is in the foreground, so your normal
Ctrl+C/paste, IDE shortcuts, etc. in other apps are untouched.
Deactivating the script in Ableton's preferences (or closing Ableton)
shuts down the helper.

> Requires `python` to be on your system PATH so the script can launch
> the helper. If it isn't, you'll see `helper=FAILED: 'python' not on PATH`
> in the activation status message — install Python from python.org and
> tick "Add to PATH" during setup.

## Status

| What | Works today |
|---|---|
| Read selected notes from Ableton on hotkey | yes |
| Captures all per-note properties (pitch, time, duration, velocity, mute, probability, velocity deviation, release velocity) | yes |
| Hotkey scoped to Ableton (no global hijack) | yes |
| Auto-write to the OS clipboard | yes (Ctrl+C) |
| Paste text → notes back into Ableton | yes (Ctrl+Shift+V) |

## Troubleshooting

- **Nothing happens when I press Ctrl+Shift+C.** Open the log viewer
  with **Ctrl+Shift+L** to see what the helper is (or isn't) doing.
  If the viewer shows nothing, the helper probably isn't running — toggle
  the script off and on in Ableton's preferences.
- **Log shows "BIND FAILED".** A previous helper is still running.
  Kill leftover `python.exe` instances in Task Manager, then toggle the
  script.
- **The script doesn't appear in the Control Surface dropdown.** Confirm
  the folder name is exactly `MidiClipboard` and lives under
  `Documents\Ableton\User Library\Remote Scripts\`.

## Requirements

- Windows 10/11
- Ableton Live 11 or 12
- Python 3.x for the helper (only standard library is used)
