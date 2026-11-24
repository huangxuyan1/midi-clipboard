"""Wire format for MIDI note payloads.

A minimal, human-readable, LLM-friendly text representation of MIDI notes
for round-tripping through Ableton Live's MidiNoteSpecification API.

Format
======

A ``notes:`` block, with one note per indented line. Three required
positional fields, optional named fields.

    notes:
      <pitch> <start> <duration> [vel=N] [mute=True|False] [prob=F] [vdev=N] [rvel=N]

Required (positional, in this order):

- pitch     note name (``C3`` / ``F#4`` / ``Bb2`` / ``C-1``) OR a plain
            MIDI number 0-127. Convention: **C3 == MIDI 60 (Ableton)**.
            Octave range -2 to 8.
- start     beat time relative to clip start, float.
- duration  length in beats, float.

Optional (named, any order; omit any to use Live's default):

  ============  ====================  ============  ==========
  wire name     API field             type          default
  ============  ====================  ============  ==========
  vel           velocity              int 0-127     100
  mute          mute                  True|False    False
  prob          probability           float 0-1     1.0
  vdev          velocity_deviation    int           0
  rvel          release_velocity      int 0-127     64
  ============  ====================  ============  ==========

Examples
========

C major triad at beat 0::

    notes:
      C3 0 1
      E3 0 1
      G3 0 1

Arpeggio with selective overrides and a comment::

    # opening figure
    notes:
      C3 0 0.5 vel=80
      E3 0.5 0.5
      G3 1 0.5 prob=0.9

Round-trip behaviour
====================

- ``serialize_notes`` emits the ``notes:`` header, sorts notes by
  ``(start_time, pitch)``, indents each line by 2 spaces, and omits any
  optional field whose value equals Live's default.
- ``parse_text`` is **tolerant**:
    - the ``notes:`` header is optional;
    - blank lines and ``#`` comments are ignored;
    - any other line is examined — if its first three tokens parse as
      pitch + float + float, it's treated as a note, otherwise it's
      silently skipped. This lets prose (e.g. LLM explanations around
      the notes block) round-trip without false-positives.
"""

import re

import Live


# --- Pitch ----------------------------------------------------------------

_NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_PITCH_RE = re.compile(r"^([A-Ga-g])([#bB]?)(-?\d+)$")


def pitch_to_midi(s):
    """Parse a pitch token to a MIDI number 0-127.

    Accepts either a plain MIDI number (``'60'``) or a note name (``'C3'``,
    ``'F#4'``, ``'Bb2'``, ``'C-1'``). Ableton convention: C3 = MIDI 60.
    Raises ValueError on bad input or out-of-range result.
    """
    s = s.strip()
    # Plain integer first.
    try:
        n = int(s)
        if 0 <= n <= 127:
            return n
        raise ValueError("MIDI number out of range 0-127: {}".format(n))
    except ValueError:
        if s.lstrip("-").isdigit():
            raise  # was an int but out of range
    m = _PITCH_RE.match(s)
    if not m:
        raise ValueError("not a valid pitch: {!r}".format(s))
    letter = m.group(1).upper()
    accidental = m.group(2).lower()  # accept '#', 'b', or 'B' (flat)
    octave = int(m.group(3))
    semitone = _NOTE_OFFSETS[letter]
    if accidental == "#":
        semitone += 1
    elif accidental == "b":
        semitone -= 1
    midi = (octave + 2) * 12 + semitone  # Ableton convention
    if not 0 <= midi <= 127:
        raise ValueError(
            "pitch {!r} resolves to out-of-range MIDI {}".format(s, midi)
        )
    return midi


def midi_to_pitch(n):
    """Render a MIDI number 0-127 as a note name like 'C3' or 'F#4'."""
    n = int(n)
    octave = (n // 12) - 2  # Ableton: MIDI 60 -> C3
    return _NOTE_NAMES[n % 12] + str(octave)


# --- Optional-field metadata ---------------------------------------------

# (wire_name, api_name, default_value). Ordered so serialize emits kwargs
# in a stable, predictable order.
_OPTIONAL_FIELDS = [
    ("vel",  "velocity",            100),
    ("mute", "mute",                False),
    ("prob", "probability",         1.0),
    ("vdev", "velocity_deviation",  0),
    ("rvel", "release_velocity",    64),
]
_WIRE_TO_API_OPT = {w: a for w, a, _ in _OPTIONAL_FIELDS}


# --- Formatting helpers --------------------------------------------------

def _fmt_num(x):
    """Compact: 1.0 -> '1', 0.5 -> '0.5', 100 -> '100'."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _fmt_meta_value(v):
    """Format a meta-block value. Numbers/bools as bare tokens; strings
    quoted only if they contain whitespace, are empty, or contain a quote."""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return _fmt_num(v)
    s = str(v)
    if not s or " " in s or '"' in s or "\t" in s:
        return '"{}"'.format(s.replace("\\", "\\\\").replace('"', '\\"'))
    return s


def _parse_value(v):
    v = v.strip()
    if v == "True":
        return True
    if v == "False":
        return False
    if "." in v or "e" in v or "E" in v:
        return float(v)
    return int(v)


# --- Public API ----------------------------------------------------------

def serialize_notes(notes, meta=None):
    """Render an iterable of Live.Clip.MidiNote objects as wire-format text.

    Output shape (meta block omitted if ``meta`` is None or empty)::

        meta:
          tempo=120
          time_sig=4/4
          clip_length=4

        notes:
          C3 0 1
          E3 0 1

    Notes are sorted by (start_time, pitch). Optional per-note fields are
    omitted when equal to Live's default. ``meta`` is an ordered mapping
    of free-form key->value pairs preserved in insertion order. Values may
    be bool, int, float, or str; strings are quoted only when needed.
    """
    lines = []
    if meta:
        lines.append("meta:")
        for k, v in meta.items():
            lines.append("  {}={}".format(k, _fmt_meta_value(v)))
        lines.append("")  # blank line between blocks for readability

    lines.append("notes:")
    lines.append("  note start dur ...")  # column header; skipped on parse
    sorted_notes = sorted(notes, key=lambda n: (n.start_time, n.pitch))
    for n in sorted_notes:
        parts = [
            midi_to_pitch(n.pitch),
            _fmt_num(n.start_time),
            _fmt_num(n.duration),
        ]
        for wire_name, api_name, default in _OPTIONAL_FIELDS:
            value = getattr(n, api_name)
            if value == default:
                continue
            if isinstance(value, bool):
                parts.append("{}={}".format(wire_name, value))
            else:
                parts.append("{}={}".format(wire_name, _fmt_num(value)))
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def parse_text(text):
    """Parse wire-format text into a list of Live.Clip.MidiNoteSpecification.

    Tolerant: ``notes:`` header is optional, ``#`` comments are ignored,
    and any line whose first three tokens don't parse as pitch + float +
    float is silently skipped (so prose around the block round-trips
    cleanly). Unknown ``key=value`` kwargs are also dropped silently.
    """
    specs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if len(tokens) < 3:
            continue
        try:
            pitch = pitch_to_midi(tokens[0])
            start = float(tokens[1])
            duration = float(tokens[2])
        except (ValueError, KeyError):
            continue  # not a note line — skip
        kwargs = {"pitch": pitch, "start_time": start, "duration": duration}
        for tok in tokens[3:]:
            if "=" not in tok:
                continue
            k, _, v = tok.partition("=")
            api_key = _WIRE_TO_API_OPT.get(k.strip())
            if api_key is None:
                continue
            try:
                kwargs[api_key] = _parse_value(v)
            except ValueError:
                continue
        specs.append(Live.Clip.MidiNoteSpecification(**kwargs))
    return specs
