# Mac port handoff

**Goal:** MidiClipboard runs on macOS (Ableton Live 11 Suite on a Mac) with
the same three shortcuts, using Cmd in place of Ctrl, while Windows keeps
working exactly as it does now.

Written 2026-11-24 on the Windows dev machine, on top of commit `5d60b4d`.
Nothing Mac-specific exists yet.

## Where things stand

- Working and tested in Live 11.3 on Windows:
  - Ctrl+C copies the selected notes as ABC (the default) or as the native text format. `COPY_FORMAT` in `MidiClipboard/MidiClipboard.py` picks which.
  - Ctrl+Shift+V pastes either format.
  - Ctrl+Shift+L opens a log viewer.
- `python3 -m unittest discover -s tests` runs 46 ABC tests outside Live.
- The architecture is described in README.md under "How it works": the remote script inside Live talks to an external `bridge` helper over UDP on localhost. The native format is specified in `grammar.md`.

## Portable vs Windows-only

Runs unchanged on a Mac: `abc_serde.py`, `notes_serde.py`, `viewer.py`
(tkinter), the UDP protocol, and all the Live API code in `MidiClipboard.py`.

Windows-only:

- **`MidiClipboard.py` `_spawn_bridge`** builds its `creationflags` from `subprocess.CREATE_NO_WINDOW` / `CREATE_NEW_CONSOLE` *outside* its `try`. Those constants exist only on Windows. On a Mac the `AttributeError` escapes `__init__`, so **the control surface fails to load**. It also launches `bridge.exe`, falling back to `python bridge.py`.
- **`MidiClipboard.py` `_kill_bridge`** uses `taskkill /T`. Its fallback, `terminate()`, is already inside a `try`.
- **`bridge.py`**: every OS-facing part is raw Win32 through ctypes:
  - the `WH_KEYBOARD_LL` key hook
  - the foreground-app check
  - the `CF_UNICODETEXT` clipboard
  - `CREATE_NO_WINDOW` when it opens the viewer
- **`build_bridge.py`** hard-codes the output name `bridge.exe` and passes `--noconsole`.

## Plan

### 1. Make the remote script cross-platform

In `MidiClipboard.py`:

- `_spawn_bridge`: on Windows, keep today's behaviour byte for byte. On a Mac:
  - launch `bridge` (no `.exe`)
  - fall back to `python3 bridge.py`
  - pass no `creationflags`
- `_kill_bridge`: keep `taskkill` on Windows and use `terminate()` elsewhere. On POSIX, PyInstaller's onefile bootloader should pass SIGTERM on to its child process.
- Everything under `MidiClipboard/` except `bridge*.py` runs inside Live's Python 3.7. That means no f-strings, no walrus operator and no 3.8+ APIs. Check each changed file with `python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read(), feature_version=(3,7))" FILE`.

**Done when:** Live on the Mac shows "MidiClipboard ready" in its status bar, and Live's `Log.txt` has no traceback from MidiClipboard.

### 2. Split the bridge into a shared core and one backend per OS

- `bridge.py` keeps the OS-neutral parts:
  - logging
  - UDP sockets and the single-instance bind
  - `result_listener`
  - opening the viewer, and the `--viewer` entry point

  It imports its backend by `sys.platform`.
- `bridge_win.py` holds today's Win32 code, **moved verbatim**. Windows can't be retested from the Mac, so move this code rather than rewriting it.
- `bridge_mac.py` is new.
- Backend interface:
  - `get_clipboard_text()`
  - `set_clipboard_text(text) -> bool`
  - `viewer_popen_kwargs()`: `creationflags=CREATE_NO_WINDOW` on Windows, `{}` on a Mac
  - `run_hotkeys(on_copy, on_paste, on_viewer)`: blocks forever. It calls a callback once per fresh press, and only while Live is the frontmost app.

Mac backend reference (pyobjc: `pyobjc-framework-Quartz`, `pyobjc-framework-Cocoa`):

- **Key tap:** create a listen-only Quartz event tap with `CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly, CGEventMaskBit(kCGEventKeyDown), callback, None)`. Wrap it in a run-loop source with `CFMachPortCreateRunLoopSource`, add that to the current run loop, then call `CFRunLoopRun()`. Because the tap only listens, every keystroke still reaches Live, matching the Windows pass-through.
- **Combos:** read the modifiers with `CGEventGetFlags`. Cmd is `kCGEventFlagMaskCommand` and Shift is `kCGEventFlagMaskShift`. Read the key with `kCGKeyboardEventKeycode`; on the ANSI layout C = 8, V = 9 and L = 37. Skip events whose `kCGKeyboardEventAutorepeat` field is set. That replaces the Windows `_held` set.
- **Tap timeouts:** macOS switches off a tap whose callback is slow. The callback then receives `kCGEventTapDisabledByTimeout` (or `kCGEventTapDisabledByUserInput`), and should call `CGEventTapEnable(tap, True)`. Keep the callback fast: send the UDP trigger inline, and do clipboard reads and viewer launches on worker threads, as on Windows.
- **No permission:** `CGEventTapCreate` returns `None` without Input Monitoring permission. Log one clear line naming the setting, then exit.
- **Frontmost app:** use `NSWorkspace.sharedWorkspace().frontmostApplication()` and match a `bundleIdentifier()` that starts with `com.ableton.live`. Log the identifier the first time to confirm it. The Mac process is named just "Live", so the Windows test ("ableton" in the exe path) won't carry over. The run loop above keeps `frontmostApplication` current.
- **Clipboard:** run `pbcopy` / `pbpaste` through `subprocess` with `LANG=en_US.UTF-8` in the environment, so non-ASCII clip names survive.

**Done when:** `python3 MidiClipboard/bridge.py`, run from a terminal (which needs Input Monitoring itself), logs that the tap is installed, and the Mac checklist passes with Live using this bridge.

### 3. Build a Mac binary

- `build_bridge.py`: on macOS, output `bridge` and leave out `--noconsole`. On a Mac that flag produces an `.app` bundle, while a plain executable launched by Live shows no window anyway.
- Build with the python.org **universal2** Python, which ships Tk for the viewer. Add `--target-arch universal2` so the result runs on both Apple Silicon and Intel. Install the build tools with `pip install pyinstaller pyobjc-framework-Quartz pyobjc-framework-Cocoa`.
- Commit `MidiClipboard/bridge` from the Mac so git records its execute bit.

**Done when:** Live launches `MidiClipboard/bridge`, the activation line in `bridge.log` reports the binary, and the Mac checklist passes again.

### 4. Permissions

The tap needs **Input Monitoring** (System Settings → Privacy & Security). Live launches the bridge, so macOS will most likely charge the permission to **Ableton Live**, the "responsible process", rather than to `bridge`. Find out which app actually appears in the list and write that into the README. Code signing and notarization matter only for zip downloads, which macOS quarantines. A `git clone` is not quarantined.

### 5. README

Cover:
- the Mac install folder, `~/Music/Ableton/User Library/Remote Scripts/MidiClipboard`
- the Cmd shortcuts
- the Input Monitoring step
- the Mac requirements and the Mac build steps

Then remove "macOS support" from the Roadmap.

## Mac checklist

- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] Live shows "MidiClipboard ready", and `MidiClipboard/bridge.log` shows `STATUS: MidiClipboard activated (... bridge=ok ...)`.
- [ ] Cmd+C with notes selected puts ABC on the clipboard (check with `pbpaste`). With nothing selected the clipboard is unchanged. Live's own copy still works.
- [ ] Cmd+Shift+V pastes both ABC and native text into the open clip, and Cmd+Z undoes it.
- [ ] Cmd+Shift+L opens exactly one viewer per press, even while held.
- [ ] No shortcut fires while another app is frontmost.
- [ ] A second bridge exits instead of installing a second tap. (The single-instance bind on UDP 19846 has no `SO_REUSEADDR`; confirm macOS refuses the second bind.)
- [ ] Turning the control surface off, or quitting Live, leaves no bridge process (`pgrep -fl bridge`).

## Back on Windows afterwards

The split changes `bridge.py`, so the committed `bridge.exe` is stale.
On Windows:
1. Run `python build_bridge.py`.
2. Restart Live.
3. Re-run the checklist with the Ctrl shortcuts.

## Mac dev setup

- Link the script folder into Live: `ln -s "$PWD/MidiClipboard" ~/Music/Ableton/User\ Library/Remote\ Scripts/MidiClipboard`.
- Live loads remote-script code only at startup, so restart Live after every change (save the set first).
- Script import errors go to Live's log, `~/Library/Preferences/Ableton/Live 11.*/Log.txt`. The bridge logs to `MidiClipboard/bridge.log`.
- **Live API reference:** `Live11.0.xml`, which documents every `Live.*` class and property. It is gitignored, so copy it from the Windows repo into the repo root on the Mac. Grep it for any Live API question.

## Lessons from the Windows side

- Live's embedded Python has no ctypes and no working tkinter, so anything that talks to the OS belongs in the bridge.
- Log from the script with `self._send("STATUS: ...")` or the `logging` module. Calling `self.log_message` on an `ableton.v2` ControlSurface silently aborts the rest of `__init__`.
- In a PyInstaller onefile build, `__file__` is a temporary folder. Find files next to the binary from `sys.executable`'s folder, as `bridge.py` already does. In a build with no console, `sys.stdout` is `None`.
- A clip has no scale property, but `song.root_note` and `song.scale_name` follow the clip being edited. The ABC writer turns them into the `K:` line.
