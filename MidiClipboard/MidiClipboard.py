import errno
import os
import re
import socket
import subprocess

import Live
from ableton.v2.control_surface import ControlSurface


# --- Wire format ---
# Abbreviated keys used in the text payload <-> full Live API field names.
_WIRE_TO_API = {
    "pitch": "pitch",
    "start": "start_time",
    "dur":   "duration",
    "vel":   "velocity",
    "mute":  "mute",
    "prob":  "probability",
    "vd":    "velocity_deviation",
    "rv":    "release_velocity",
}
_INT_FIELDS = {"pitch", "velocity", "velocity_deviation", "release_velocity"}
_FLOAT_FIELDS = {"start_time", "duration", "probability"}
_NOTE_BLOCK_RE = re.compile(r"\{([^}]*)\}")


def _parse_scalar(v):
    v = v.strip()
    if v == "True":
        return True
    if v == "False":
        return False
    if "." in v or "e" in v or "E" in v:
        return float(v)
    return int(v)


def _parse_note_specs(text):
    """Parse the wire format produced by _format_notes back into a list of
    keyword-arg dicts ready for Live.Clip.MidiNoteSpecification(**spec).
    Tolerates whitespace and unknown keys (silently dropped)."""
    specs = []
    for m in _NOTE_BLOCK_RE.finditer(text):
        spec = {}
        for kv in m.group(1).split(","):
            if not kv.strip():
                continue
            k, _, v = kv.partition(":")
            api_key = _WIRE_TO_API.get(k.strip())
            if api_key is None:
                continue
            value = _parse_scalar(v)
            # Coerce to the type Live expects, defensively.
            if api_key in _INT_FIELDS:
                value = int(value)
            elif api_key in _FLOAT_FIELDS:
                value = float(value)
            spec[api_key] = value
        if spec:
            specs.append(spec)
    return specs


TRIGGER_HOST = "127.0.0.1"
TRIGGER_PORT = 19845
RESULT_HOST = "127.0.0.1"
RESULT_PORT = 19846

DRAIN_DELAY_TICKS = 1     # 100 ms — hotkey latency budget
ANNOUNCE_DELAY_TICKS = 20 # 2 s — wait for spawned helper to bind before announcing

# The helper runs windowless so closing a stray console can't kill it.
# Use Ctrl+Shift+L while Ableton is foreground to pop up a log tail viewer.
# Flip to True if you'd rather see the helper console immediately on spawn.
HELPER_VISIBLE = False

PYTHON_EXE = "python"
HELPER_SCRIPT = "receiver.py"


def _format_notes(notes):
    return [
        "{{pitch:{}, start:{}, dur:{}, vel:{}, mute:{}, prob:{}, vd:{}, rv:{}}}".format(
            n.pitch, n.start_time, n.duration, n.velocity,
            n.mute, n.probability, n.velocity_deviation, n.release_velocity,
        )
        for n in notes
    ]


class MidiClipboard(ControlSurface):
    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_sock = None
        self._helper_proc = None

        self._bind_status = self._open_listen_socket()
        self._helper_status = self._spawn_helper()

        self.show_message("MidiClipboard ready")
        self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)
        # Delay the activation message so the freshly-spawned helper has time
        # to bind its result port; otherwise we'd send into the void.
        self.schedule_message(ANNOUNCE_DELAY_TICKS, self._announce)

    # ---------------- startup helpers ----------------

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

    def _spawn_helper(self):
        receiver_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), HELPER_SCRIPT
        )
        if not os.path.exists(receiver_path):
            return "FAILED: {} not found".format(receiver_path)
        flags = (
            subprocess.CREATE_NEW_CONSOLE if HELPER_VISIBLE
            else subprocess.CREATE_NO_WINDOW
        )
        try:
            self._helper_proc = subprocess.Popen(
                [PYTHON_EXE, receiver_path],
                creationflags=flags,
            )
            return "ok pid={}".format(self._helper_proc.pid)
        except FileNotFoundError:
            return "FAILED: '{}' not on PATH".format(PYTHON_EXE)
        except Exception as e:
            return "FAILED: {}".format(e)

    def _announce(self):
        self._send("STATUS: MidiClipboard activated (trigger_bind={}, helper={})".format(
            self._bind_status, self._helper_status))

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
                        self._handle_hotkey()
        finally:
            self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)

    def _handle_hotkey(self):
        # Only emit a HOTKEY payload when there's something real to copy.
        # Other branches send STATUS so the helper logs them but does NOT
        # touch the OS clipboard — important now that Ctrl+C is overloaded.
        try:
            song = Live.Application.get_application().get_document()
            clip = song.view.detail_clip
            if clip is None or not clip.is_midi_clip:
                self._send("STATUS: hotkey ignored (no MIDI clip in detail view)")
                return
            notes = clip.get_selected_notes_extended()
            if len(notes) == 0:
                self._send("STATUS: hotkey ignored (no notes selected)")
                return
            note_strs = _format_notes(notes)
            self._send("HOTKEY: count={} [{}]".format(
                len(note_strs), ", ".join(note_strs)))
        except Exception as e:
            self._send("HOTKEY ERROR: {}".format(e))

    def _handle_paste(self, text):
        try:
            specs = _parse_note_specs(text)
            if not specs:
                self._send("STATUS: paste ignored (no notes parsed from clipboard)")
                return
            song = Live.Application.get_application().get_document()
            clip = song.view.detail_clip
            if clip is None or not clip.is_midi_clip:
                self._send("STATUS: paste ignored (no MIDI clip in detail view)")
                return
            note_objs = []
            for spec in specs:
                try:
                    note_objs.append(Live.Clip.MidiNoteSpecification(**spec))
                except Exception as e:
                    self._send("PASTE ERROR: bad note {}: {}".format(spec, e))
                    return
            clip.add_new_notes(tuple(note_objs))
            self._send("STATUS: pasted {} notes into {!r}".format(
                len(note_objs), clip.name))
        except Exception as e:
            self._send("PASTE ERROR: {}".format(e))

    def _send(self, payload):
        try:
            self._sock.sendto(payload.encode("utf-8"), (RESULT_HOST, RESULT_PORT))
        except Exception:
            pass

    # ---------------- shutdown ----------------

    def disconnect(self):
        if self._helper_proc is not None:
            try:
                self._helper_proc.terminate()
            except Exception:
                pass
        for s in (self._sock, self._listen_sock):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
        super().disconnect()
