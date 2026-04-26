import errno
import socket

import Live
from ableton.v2.control_surface import ControlSurface


TRIGGER_HOST = "127.0.0.1"
TRIGGER_PORT = 19845
RESULT_HOST = "127.0.0.1"
RESULT_PORT = 19846

DRAIN_DELAY_TICKS = 1    # 100 ms — hotkey latency budget


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

        bind_status = "no attempt"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setblocking(False)
            s.bind((TRIGGER_HOST, TRIGGER_PORT))
            self._listen_sock = s
            bind_status = "ok"
        except Exception as e:
            bind_status = "FAILED: {}".format(e)

        self._send("STATUS: MidiClipboard activated (trigger_bind={})".format(bind_status))
        self.show_message("MidiClipboard ready")
        self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)

    def _drain_trigger(self):
        try:
            if self._listen_sock is not None:
                while True:
                    try:
                        data, addr = self._listen_sock.recvfrom(4096)
                    except socket.error as e:
                        if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.ECONNRESET):
                            break
                        self._send("ERROR: drain recv: {}".format(e))
                        break
                    self._handle_hotkey()
        finally:
            self.schedule_message(DRAIN_DELAY_TICKS, self._drain_trigger)

    def _handle_hotkey(self):
        try:
            song = Live.Application.get_application().get_document()
            clip = song.view.detail_clip
            if clip is None or not clip.is_midi_clip:
                self._send("HOTKEY: no MIDI clip in detail view")
                return
            notes = clip.get_selected_notes_extended()
            note_strs = _format_notes(notes)
            self._send("HOTKEY: count={} [{}]".format(
                len(note_strs), ", ".join(note_strs)))
        except Exception as e:
            self._send("HOTKEY ERROR: {}".format(e))

    def _send(self, payload):
        try:
            self._sock.sendto(payload.encode("utf-8"), (RESULT_HOST, RESULT_PORT))
        except Exception:
            pass

    def disconnect(self):
        for s in (self._sock, self._listen_sock):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
        super().disconnect()
