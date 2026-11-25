"""OS-side bridge for the MidiClipboard Ableton remote script.

Owns the three things the remote script can't reach from inside Live's
stripped Python interpreter (no ctypes there):
  1. Keyboard listener — Ctrl+C / Ctrl+Shift+V / Ctrl+Shift+L on Windows,
     Cmd+C / Cmd+Shift+V / Cmd+Shift+L on a Mac, gated on Ableton being
     the frontmost app.
  2. OS clipboard — read on paste, write on copy.
  3. UDP socket pair with the remote script (trigger out, results in).

This file is the OS-neutral core: logging, the UDP sockets, the
single-instance gate, and the log viewer. The keyboard listener and the
clipboard live in one backend per OS, imported by sys.platform:
  bridge_win.py  WH_KEYBOARD_LL hook + CF_UNICODETEXT clipboard (raw Win32)
  bridge_mac.py  listen-only Quartz event tap + pbcopy / pbpaste
Each backend provides:
  get_clipboard_text()          -> str, or None when there's no text
  set_clipboard_text(text)      -> bool
  last_error()                  -> str, detail after a failed set
  viewer_popen_kwargs()         -> dict of extra Popen kwargs for the viewer
  run_hotkeys(on_copy, on_paste, on_viewer)
      blocks forever; calls one callback per fresh press, and only while
      Live is the frontmost app

The wire format itself lives in ``notes_serde.py`` inside the remote
script package; this file shuttles bytes and does not interpret them
beyond a ``HOTKEY: count=`` prefix check used to decide whether a payload
should land on the clipboard.
"""

import logging
import os
import socket
import subprocess
import sys
import threading


TRIGGER_HOST = "127.0.0.1"
TRIGGER_PORT = 19845
RESULT_HOST = "127.0.0.1"
RESULT_PORT = 19846

# --- Logging ---
# In a PyInstaller onefile build, __file__ lives in a temp extraction dir
# (sys._MEIPASS) that's deleted on exit — so derive the base dir from the
# exe location when frozen, and from this file when running as source.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    if sys.platform == "darwin":
        # The Mac build is a onedir folder (bridge-macos/) inside the
        # remote script folder; keep the log beside the remote script.
        _BASE_DIR = os.path.dirname(_BASE_DIR)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_BASE_DIR, "bridge.log")

# File handler always on (so we can tail it on demand even when no console).
# A StreamHandler is added only when stdout exists — in a frozen
# --noconsole build sys.stdout is None and StreamHandler(None) would crash.
_handlers = [logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")]
if sys.stdout is not None:
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=_handlers,
)
log = logging.getLogger("midiclipboard.bridge")

# The OS backend, loaded by main(). The `--viewer` role never loads it.
backend = None


def _load_backend():
    if sys.platform == "win32":
        import bridge_win as mod
    elif sys.platform == "darwin":
        import bridge_mac as mod
    else:
        raise RuntimeError("no bridge backend for platform {!r}".format(sys.platform))
    return mod


# Persistent UDP socket for trigger sends; keep at module scope so the
# hotkey callback (which must be fast) doesn't pay socket-construction cost
# per key.
_trigger_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def _viewer_launch_cmd():
    """Command to launch the tkinter log window as its own process.

    Frozen (bundled binary): re-invoke ourselves as `bridge --viewer <log>`.
    Dev (python bridge.py): `python bridge.py --viewer <log>`.
    Either way the viewer ships in the same artifact — no separate Python
    install and no separate viewer file to locate at runtime.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--viewer", LOG_PATH]
    return [sys.executable, os.path.abspath(__file__), "--viewer", LOG_PATH]


def _spawn_log_viewer():
    """Open the tkinter log window. Closing it does NOT affect the bridge —
    they're independent processes."""
    try:
        subprocess.Popen(
            _viewer_launch_cmd(),
            **backend.viewer_popen_kwargs()
        )
        log.info("[hotkey] log viewer opened")
    except Exception as e:
        log.error("[hotkey] log viewer spawn failed: %s", e)


def _trigger_paste():
    """Read the OS clipboard and ship it to the remote script as a paste
    trigger. Runs on a worker thread so the hotkey callback returns
    quickly."""
    try:
        text = backend.get_clipboard_text()
        if text is None or not text.strip():
            log.info("[paste] clipboard empty or non-text; nothing to send")
            return
        payload = b"paste:" + text.encode("utf-8", errors="replace")
        _trigger_sock.sendto(payload, (TRIGGER_HOST, TRIGGER_PORT))
        log.info("[paste] sent %d chars from clipboard", len(text))
    except Exception as e:
        log.error("[paste] trigger failed: %s", e)


# --- Hotkey callbacks, called by the backend on the thread that receives
# keyboard events. Each must return fast: copy sends its UDP trigger
# inline, paste and viewer hand their slow work to a worker thread.

def _on_copy():
    _trigger_sock.sendto(b"go", (TRIGGER_HOST, TRIGGER_PORT))


def _on_paste():
    threading.Thread(target=_trigger_paste, daemon=True).start()


def _on_viewer():
    threading.Thread(target=_spawn_log_viewer, daemon=True).start()


def result_listener(sock):
    log.info("[bridge] listening on udp %s:%d", RESULT_HOST, RESULT_PORT)
    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except OSError as e:
            log.error("[bridge] recv error: %s", e)
            continue
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = repr(data)
        log.info("[from %s:%d] %s", addr[0], addr[1], text)
        # Only touch the OS clipboard for HOTKEY messages. The script only
        # sends HOTKEY when notes are actually selected; STATUS/ERROR lines
        # just get logged. This is the safety layer that lets the Ctrl/Cmd+C
        # overload coexist with Ableton's own copy of text in track names,
        # plugin search fields, etc.
        if text.startswith("HOTKEY: "):
            payload = text[len("HOTKEY: "):]
            if backend.set_clipboard_text(payload):
                log.info("[clipboard] copied %d chars", len(payload))
            else:
                log.error("[clipboard] copy FAILED (%s)", backend.last_error())


def main():
    global backend
    log.info("=" * 60)
    log.info("bridge starting (%s, %s); log at %s", sys.platform,
             "frozen" if getattr(sys, "frozen", False) else sys.executable,
             LOG_PATH)

    try:
        backend = _load_backend()
    except Exception as e:
        log.error("[bridge] could not load the OS backend: %s", e)
        sys.exit(1)

    # Single-instance gate. Bind the result port up front WITHOUT
    # SO_REUSEADDR: a second bind then fails (on Windows and macOS alike),
    # so if another bridge already owns the port we exit *without
    # installing a hook*. This is what prevents duplicate hooks (multiplied
    # viewer windows / repeated pastes) when an old bridge wasn't cleaned up.
    result_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        result_sock.bind((RESULT_HOST, RESULT_PORT))
    except OSError as e:
        log.error("[bridge] result port %s:%d already in use (%s) — another "
                  "bridge is running; exiting without installing a hook.",
                  RESULT_HOST, RESULT_PORT, e)
        return
    threading.Thread(target=result_listener, args=(result_sock,), daemon=True).start()

    try:
        backend.run_hotkeys(_on_copy, _on_paste, _on_viewer)
    finally:
        _trigger_sock.close()


if __name__ == "__main__":
    # Single artifact, two roles. `--viewer <log>` runs the tkinter log
    # window; no args runs the bridge. This lets one binary serve both
    # (the viewer is re-launched as `bridge --viewer <log>`).
    if "--viewer" in sys.argv:
        import viewer  # bundled alongside; resolves in dev via sys.path[0]
        _i = sys.argv.index("--viewer")
        _path = sys.argv[_i + 1] if len(sys.argv) > _i + 1 else LOG_PATH
        viewer.run(_path)
    else:
        main()
