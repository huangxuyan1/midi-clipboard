"""macOS backend for the MidiClipboard bridge.

Keyboard: a listen-only Quartz event tap on key-down events. Listen-only
means the tap can't swallow or change anything, so every keystroke still
reaches Live (Live's own Cmd+C still copies), matching the pass-through of
the Windows hook. The tap needs Input Monitoring permission (System
Settings > Privacy & Security > Input Monitoring). macOS charges that
permission to the "responsible" app: Ableton Live when Live launches the
bridge, or the terminal app when you run `python3 bridge.py` by hand.

Clipboard: pbcopy / pbpaste with a UTF-8 locale, so non-ASCII clip and
track names survive the round trip.

Requires pyobjc-framework-Quartz and pyobjc-framework-Cocoa.
"""

import logging
import os
import signal
import subprocess
import sys
import threading
import time

try:
    import Quartz
    from AppKit import NSWorkspace
except ImportError as _e:
    raise ImportError(
        "{}. The Mac bridge needs pyobjc: {} -m pip install "
        "pyobjc-framework-Quartz pyobjc-framework-Cocoa".format(_e, sys.executable))


log = logging.getLogger("midiclipboard.bridge")

# Virtual key codes name physical key positions. These are C, V and L on the
# ANSI (US) layout.
KEY_C = 8
KEY_V = 9
KEY_L = 37
_HOTKEYS = (KEY_C, KEY_V, KEY_L)

LIVE_BUNDLE_PREFIX = "com.ableton.live"

# Set by the remote script to Live's PID. The bridge exits once that process
# is gone, so a crashed Live doesn't leave a keyboard listener running.
LIVE_PID_ENV = "MIDICLIPBOARD_LIVE_PID"
WATCHDOG_SECONDS = 2.0

PERMISSION_HINT = (
    "System Settings > Privacy & Security > Input Monitoring: turn on the app "
    "that launched the bridge (Ableton Live, or your terminal if you ran "
    "bridge.py by hand), then restart Live")

_UTF8_ENV = dict(os.environ, LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8")
_last_error = ""


# ---------------- clipboard ----------------

def get_clipboard_text():
    """Read the clipboard as text. Returns None if there's no text on it,
    or on any error."""
    try:
        p = subprocess.run(
            ["/usr/bin/pbpaste", "-Prefer", "txt"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=_UTF8_ENV, timeout=5,
        )
    except Exception as e:
        log.error("[clipboard] pbpaste failed: %s", e)
        return None
    if p.returncode != 0 or not p.stdout:
        return None
    return p.stdout.decode("utf-8", errors="replace")


def set_clipboard_text(text):
    """Put text on the clipboard. Returns True on success; on failure
    last_error() says why."""
    global _last_error
    try:
        p = subprocess.run(
            ["/usr/bin/pbcopy"], input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=_UTF8_ENV, timeout=5,
        )
    except Exception as e:
        _last_error = "pbcopy: {}".format(e)
        return False
    if p.returncode != 0:
        _last_error = "pbcopy exited {}: {}".format(
            p.returncode, p.stderr.decode("utf-8", errors="replace").strip())
        return False
    return True


def last_error():
    """Detail for the log line after set_clipboard_text returns False."""
    return _last_error


def viewer_popen_kwargs():
    return {}


# ---------------- frontmost app ----------------

def frontmost_bundle_id():
    """Bundle identifier of the frontmost app, or "" if there is none.
    NSWorkspace keeps this current from notifications that arrive on the
    main run loop, which run_hotkeys keeps running."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return ""
    return app.bundleIdentifier() or ""


_logged_first_press = False


def is_live_frontmost():
    global _logged_first_press
    bundle_id = frontmost_bundle_id()
    if not _logged_first_press:
        # Logged once, so a Live build with an unexpected bundle identifier
        # shows up in bridge.log instead of failing silently.
        _logged_first_press = True
        log.info("[hook] first shortcut press; frontmost app is %r",
                 bundle_id)
    return bundle_id.startswith(LIVE_BUNDLE_PREFIX)


# ---------------- event tap ----------------

_tap = None
_callbacks = None  # (on_copy, on_paste, on_viewer) from the core

_TAP_DISABLED = (
    Quartz.kCGEventTapDisabledByTimeout,
    Quartz.kCGEventTapDisabledByUserInput,
)


def _tap_callback(proxy, event_type, event, refcon):
    # Runs on the main thread inside CFRunLoopRun. macOS disables a tap
    # whose callback is slow, so this only sends the UDP trigger inline;
    # the core moves clipboard reads and viewer launches to worker threads.
    try:
        if event_type in _TAP_DISABLED:
            log.warning("[hook] macOS disabled the tap (event type %#x); "
                        "re-enabling", event_type)
            Quartz.CGEventTapEnable(_tap, True)
            return event
        if event_type != Quartz.kCGEventKeyDown:
            return event
        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode)
        if keycode not in _HOTKEYS:
            return event
        # Held keys auto-repeat; act on the first press only.
        if Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventAutorepeat):
            return event
        flags = Quartz.CGEventGetFlags(event)
        if not flags & Quartz.kCGEventFlagMaskCommand:
            return event
        shift = bool(flags & Quartz.kCGEventFlagMaskShift)
        if not is_live_frontmost():
            return event
        on_copy, on_paste, on_viewer = _callbacks
        if keycode == KEY_C:
            # Plain Cmd+C: fires in addition to Live's own copy.
            on_copy()
            log.info("[hotkey] Cmd+C -> trigger sent")
        elif keycode == KEY_V and shift:
            on_paste()
            log.info("[hotkey] Cmd+Shift+V -> paste requested")
        elif keycode == KEY_L and shift:
            on_viewer()
    except Exception as e:
        log.error("[hotkey] callback error: %s", e)
    return event


def _has_input_monitoring():
    """True when this process may listen to keystrokes. Asks macOS to show
    its permission prompt when it may not. macOS before 10.15 has no such
    permission, and pyobjc has no preflight call there."""
    preflight = getattr(Quartz, "CGPreflightListenEventAccess", None)
    if preflight is None or preflight():
        return True
    request = getattr(Quartz, "CGRequestListenEventAccess", None)
    if request is not None:
        request()
    return False


def _start_live_watchdog():
    raw = os.environ.get(LIVE_PID_ENV)
    if not raw:
        return
    try:
        pid = int(raw)
    except ValueError:
        return

    def watch():
        while True:
            time.sleep(WATCHDOG_SECONDS)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            except PermissionError:
                pass  # the PID now belongs to another user's process
            else:
                continue
            log.info("[bridge] Live (pid %d) is gone; exiting", pid)
            os._exit(0)

    threading.Thread(target=watch, daemon=True).start()
    log.info("[bridge] watching Live pid %d", pid)


def run_hotkeys(on_copy, on_paste, on_viewer):
    """Install the event tap and run the main run loop until the process
    ends. Exits the process if there's no Input Monitoring permission."""
    global _tap, _callbacks
    _callbacks = (on_copy, on_paste, on_viewer)

    # CFRunLoopRun never hands control back to Python, so Python's own
    # SIGINT handler would only run on the next keystroke. Restore the
    # default so Ctrl+C in a terminal stops the bridge at once. SIGTERM,
    # which Live sends, already has the default action.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    if not _has_input_monitoring():
        log.error("[hook] no Input Monitoring permission. %s.", PERMISSION_HINT)
        sys.exit(1)

    _tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        _tap_callback,
        None,
    )
    if _tap is None:
        log.error("[hook] CGEventTapCreate failed, most likely for lack of "
                  "Input Monitoring permission. %s.", PERMISSION_HINT)
        sys.exit(1)

    source = Quartz.CFMachPortCreateRunLoopSource(None, _tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(_tap, True)
    _start_live_watchdog()
    log.info("[hook] tap installed; Cmd+C = copy notes (no-op when nothing "
             "selected), Cmd+Shift+V = paste notes, Cmd+Shift+L = log "
             "viewer. All gated on Live frontmost.")
    Quartz.CFRunLoopRun()
