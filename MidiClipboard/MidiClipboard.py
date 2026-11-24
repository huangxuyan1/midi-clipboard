import errno
import os
import socket
import subprocess

import Live
from ableton.v2.control_surface import ControlSurface

from . import notes_serde


TRIGGER_HOST = "127.0.0.1"
TRIGGER_PORT = 19845
RESULT_HOST = "127.0.0.1"
RESULT_PORT = 19846

DRAIN_DELAY_TICKS = 1      # 100 ms — hotkey latency budget
ANNOUNCE_DELAY_TICKS = 20  # 2 s — wait for spawned bridge to bind before announcing

# The bridge runs windowless so closing a stray console can't kill it.
# Use Ctrl+Shift+L while Ableton is foreground to pop up a log tail viewer.
# Flip to True if you'd rather see the bridge console immediately on spawn.
BRIDGE_VISIBLE = False

PYTHON_EXE = "python"
BRIDGE_SCRIPT = "bridge.py"
BRIDGE_EXE = "bridge.exe"


def _content_duration(clip):
    """The clip's real content length in beats. Prefer end_time - start_time:
    clip.length reports only the LOOP length for looping clips, which
    understates content when the loop is a subset. Fall back to clip.length."""
    try:
        d = clip.end_time - clip.start_time
        if d and d > 0:
            return d
    except Exception:
        pass
    return clip.length


def _gather_meta(song, clip):
    """Best-effort metadata gather. Each property is guarded so any single
    failure (older Live without the attr, weird clip state, etc.) just
    drops that one key rather than poisoning the whole block."""
    meta = {}

    def _try(key, fn):
        try:
            v = fn()
            if v is not None and v != "":
                meta[key] = v
        except Exception:
            pass

    _try("tempo", lambda: song.tempo)
    _try("time_sig", lambda: "{}/{}".format(
        int(clip.signature_numerator), int(clip.signature_denominator)))
    _try("clip_length", lambda: _content_duration(clip))
    _try("clip_name", lambda: clip.name)
    _try("track_name", lambda: _find_track_name(clip))

    # MIDI clips loop by default, so looping=True on its own is noise. Only
    # surface loop info when the loop is a real subset/offset of the content
    # — i.e. NOT the trivial 0..duration full-clip loop.
    try:
        if clip.looping:
            dur = _content_duration(clip)
            ls, le = clip.loop_start, clip.loop_end
            trivial = abs(ls) < 1e-6 and abs(le - dur) < 1e-3
            if not trivial:
                meta["looping"] = True
                meta["loop_start"] = ls
                meta["loop_end"] = le
    except Exception:
        pass

    # clip.start_time is the clip's offset within the arrangement (for
    # arrangement clips). NOT clip.position, which is the loop position.
    try:
        if clip.is_arrangement_clip:
            meta["arrangement_start"] = clip.start_time
    except Exception:
        pass

    return meta


def _find_track_name(clip):
    """Walk canonical_parent up to a Track and return its name. For
    arrangement clips the parent is the Track directly; for session clips
    the parent is a ClipSlot and we need one more hop."""
    parent = clip.canonical_parent
    name = getattr(parent, "name", None)
    if name:
        return name
    grandparent = getattr(parent, "canonical_parent", None)
    return getattr(grandparent, "name", None)


class MidiClipboard(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_sock = None
        self._bridge_proc = None

        self._bind_status = self._open_listen_socket()
        self._bridge_status = self._spawn_bridge()

        self.show_message("MidiClipboard ready")
        self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)
        # Delay the activation message so the freshly-spawned bridge has time
        # to bind its result port; otherwise we'd send into the void.
        self.schedule_message(ANNOUNCE_DELAY_TICKS, self._announce)

    # ---------------- startup ----------------

    def _open_listen_socket(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setblocking(False)
            s.bind((TRIGGER_HOST, TRIGGER_PORT))
            self._listen_sock = s
            return "ok"
        except Exception as e:
            return "FAILED: {}".format(e)

    def _spawn_bridge(self):
        # Prefer the bundled standalone exe (no Python install needed by the
        # end user). Fall back to `python bridge.py` for development on a
        # machine that has Python.
        here = os.path.dirname(os.path.abspath(__file__))
        exe = os.path.join(here, BRIDGE_EXE)
        bridge_py = os.path.join(here, BRIDGE_SCRIPT)

        if os.path.exists(exe):
            cmd, how = [exe], "exe"
        elif os.path.exists(bridge_py):
            cmd, how = [PYTHON_EXE, bridge_py], "python"
        else:
            return "FAILED: neither {} nor {} found".format(BRIDGE_EXE, BRIDGE_SCRIPT)

        flags = (
            subprocess.CREATE_NEW_CONSOLE if BRIDGE_VISIBLE
            else subprocess.CREATE_NO_WINDOW
        )
        try:
            self._bridge_proc = subprocess.Popen(cmd, creationflags=flags)
            return "ok ({}) pid={}".format(how, self._bridge_proc.pid)
        except FileNotFoundError:
            return "FAILED: '{}' not found (install Python or build {})".format(
                cmd[0], BRIDGE_EXE)
        except Exception as e:
            return "FAILED: {}".format(e)

    def _announce(self):
        self._send("STATUS: MidiClipboard activated (trigger_bind={}, bridge={})".format(
            self._bind_status, self._bridge_status))

    # ---------------- runtime ----------------

    def _drain_trigger(self):
        try:
            if self._listen_sock is not None:
                while True:
                    try:
                        data, addr = self._listen_sock.recvfrom(65535)
                    except socket.error as e:
                        if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.ECONNRESET):
                            break
                        self._send("ERROR: drain recv: {}".format(e))
                        break
                    if data.startswith(b"paste:"):
                        text = data[len(b"paste:"):].decode("utf-8", errors="replace")
                        self._handle_paste(text)
                    else:
                        self._handle_copy()
        finally:
            self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)

    def _handle_copy(self):
        # Only emit a HOTKEY payload when there's something real to copy.
        # Other branches send STATUS so the bridge logs them but does NOT
        # touch the OS clipboard — important since Ctrl+C is overloaded.
        try:
            song = Live.Application.get_application().get_document()
            clip = song.view.detail_clip
            if clip is None or not clip.is_midi_clip:
                self._send("STATUS: copy ignored (no MIDI clip in detail view)")
                return
            notes = clip.get_selected_notes_extended()
            if len(notes) == 0:
                self._send("STATUS: copy ignored (no notes selected)")
                return
            meta = _gather_meta(song, clip)
            self._send("HOTKEY: " + notes_serde.serialize_notes(notes, meta=meta))
        except Exception as e:
            self._send("COPY ERROR: {}".format(e))

    def _handle_paste(self, text):
        try:
            specs = notes_serde.parse_text(text)
            if not specs:
                self._send("STATUS: paste ignored (no notes parsed from clipboard)")
                return
            song = Live.Application.get_application().get_document()
            clip = song.view.detail_clip
            if clip is None or not clip.is_midi_clip:
                self._send("STATUS: paste ignored (no MIDI clip in detail view)")
                return
            clip.add_new_notes(tuple(specs))
            self._send("STATUS: pasted {} notes into {!r}".format(
                len(specs), clip.name))
        except Exception as e:
            self._send("PASTE ERROR: {}".format(e))

    def _send(self, payload):
        try:
            self._sock.sendto(payload.encode("utf-8"), (RESULT_HOST, RESULT_PORT))
        except Exception:
            pass

    # ---------------- shutdown ----------------

    def disconnect(self):
        self._kill_bridge()
        for s in (self._sock, self._listen_sock):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
        super().disconnect()

    def _kill_bridge(self):
        # bridge.exe is a PyInstaller onefile: the process we spawned is the
        # bootloader, which launches a child holding the keyboard hook.
        # terminate() only hits the bootloader and orphans the child, so we
        # kill the whole tree with taskkill /T. Falls back to terminate()
        # for the dev path (python bridge.py, a single process).
        if self._bridge_proc is None:
            return
        pid = self._bridge_proc.pid
        try:
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            try:
                self._bridge_proc.terminate()
            except Exception:
                pass
