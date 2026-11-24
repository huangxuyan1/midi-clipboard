"""ABC notation reader and writer for the clipboard.

Pure Python (no ``Live`` import) so it can be tested outside Ableton. Times
are Live beats (quarter notes); ABC ``C`` is MIDI 60.
"""

import re
from fractions import Fraction


_BEATS_PER_WHOLE = 4
_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_FIFTHS = {"F": -1, "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
_SHARP_ORDER = "FCGDAEB"
_FLAT_ORDER = "BEADGCF"
_MODE_FIFTHS = {
    "": 0, "maj": 0, "ion": 0, "lyd": 1, "mix": -1, "dor": -2,
    "m": -3, "min": -3, "aeo": -3, "phr": -4, "loc": -5,
}
_ACCIDENTALS = {"^^": 2, "^": 1, "=": 0, "_": -1, "__": -2}
_TUPLET_Q = {2: 3, 3: 2, 4: 3, 6: 2, 8: 3}

_KEY_LINE_RE = re.compile(r"^[ \t]*K:", re.M)
_FIELD_RE = re.compile(r"^([A-Za-z]):(?!\|)(.*)$")
_KEY_RE = re.compile(r"^([A-G])([#b]?)\s*([A-Za-z]*)")
_KEY_ACC_RE = re.compile(r"^(\^\^|\^|__|_|=)([A-Ga-g])$")
_METER_RE = re.compile(r"^\(?([\d+ ]+)\)?\s*/\s*(\d+)")

_LENGTH = r"(\d*)((?:/\d*)*)"
_NOTE_RE = re.compile(r"(\^\^|\^|__|_|=)?([A-Ga-g])([,']*)" + _LENGTH + r"(\.?-)?")
_CHORD_TAIL_RE = re.compile(_LENGTH + r"(\.?-)?")
_REST_RE = re.compile(r"[zx]" + _LENGTH)
_MREST_RE = re.compile(r"[ZX](\d*)")
_INLINE_FIELD_RE = re.compile(r"\[([A-Za-z]):([^\]]*)\]")
_ENDING_RE = re.compile(r"\[(\d+(?:[,-]\d+)*)")
_BAR_RE = re.compile(r"(:*)(\[\||\|\]|\|\||\|)(:*)(?:\[?(\d+(?:[,-]\d+)*))?")
_DOUBLE_COLON_RE = re.compile(r"::+")
_TUPLET_RE = re.compile(r"\(([2-9])(?::(\d*))?(?::(\d*))?")
_BROKEN_RE = re.compile(r">+|<+")

# Quoted text, decorations, inline fields and grace notes can hold any letter,
# so strip them before deciding whether a line is music or trailing prose.
_NOISE_RE = re.compile(r'"[^"]*"|![^!]*!|\+[^+]*\+|\[[A-Za-z]:[^\]]*\]|\{[^}]*\}|%.*')
_MUSIC_LINE_RE = re.compile(r"^[A-Ga-gzxZXHLMOPSTuvy0-9/,'^_=\[\]|:()<>\-.~&\\`$\s]*$")


# --- Public API ----------------------------------------------------------

def looks_like_abc(text):
    """True when the text has a ``K:`` field line, which ends every ABC tune header."""
    return _KEY_LINE_RE.search(text) is not None


def parse_abc(text):
    """Parse the first ABC tune in ``text`` into ``{pitch, start_time, duration}`` dicts."""
    header, body = _split_tune(text)
    meter, unit, key = _header_state(header)
    tokenizer = _Tokenizer()
    for line in body:
        tokenizer.feed(line)
    notes = []
    for events in tokenizer.voices.values():
        notes.extend(_Renderer(meter, unit, key).run(_unroll(events)))
    notes.sort(key=lambda n: (n["start"], n["pitch"]))
    return [
        {
            "pitch": n["pitch"],
            "start_time": float(n["start"] * _BEATS_PER_WHOLE),
            "duration": float(n["duration"] * _BEATS_PER_WHOLE),
        }
        for n in notes
        if 0 <= n["pitch"] <= 127 and n["duration"] > 0
    ]


# --- Tune extraction & header --------------------------------------------

def _split_tune(text):
    lines = [ln.strip() for ln in text.splitlines()]
    k = next((i for i, ln in enumerate(lines) if ln.startswith("K:")), None)
    if k is None:
        return [], []
    start = k
    while start > 0 and (_FIELD_RE.match(lines[start - 1]) or lines[start - 1].startswith("%")):
        start -= 1
    body = []
    for ln in lines[k + 1:]:
        if ln.startswith("```") or ln.startswith("X:"):
            break
        if not ln or ln.startswith("%"):
            continue
        if not _FIELD_RE.match(ln) and not _MUSIC_LINE_RE.match(_NOISE_RE.sub("", ln)):
            break
        body.append(ln)
    return lines[start:k + 1], body


def _header_state(header):
    meter, unit, key = None, None, {}
    for ln in header:
        m = _FIELD_RE.match(ln)
        if m is None:
            continue
        letter, value = m.group(1), _field_value(m.group(2))
        if letter == "M":
            meter = _parse_meter(value)
        elif letter == "L":
            unit = _parse_unit(value, unit)
        elif letter == "K":
            key = _parse_key(value)
    if unit is None:
        short_meter = meter is not None and Fraction(*meter) < Fraction(3, 4)
        unit = Fraction(1, 16) if short_meter else Fraction(1, 8)
    return meter, unit, key


def _field_value(raw):
    return raw.split("%")[0].strip()


def _parse_meter(value):
    if value == "C":
        return (4, 4)
    if value == "C|":
        return (2, 2)
    m = _METER_RE.match(value)
    if m is None or int(m.group(2)) == 0:
        return None
    beats = sum(int(x) for x in m.group(1).replace(" ", "").split("+") if x)
    return (beats, int(m.group(2)))


def _parse_unit(value, fallback):
    try:
        unit = Fraction(value.split()[0])
    except (IndexError, ValueError, ZeroDivisionError):
        return fallback
    return unit if unit > 0 else fallback


def _parse_key(value):
    """Map a K: value like ``G``, ``F#m``, ``Ador`` or ``D ^g`` to {letter: semitone shift}."""
    alters = {}
    m = _KEY_RE.match(value)
    if m:
        letter, accidental, mode = m.groups()
        fifths = _FIFTHS[letter] + {"#": 7, "b": -7}.get(accidental, 0)
        fifths += _MODE_FIFTHS.get(mode[:3].lower(), 0)
        order = _SHARP_ORDER if fifths > 0 else _FLAT_ORDER
        step = 1 if fifths > 0 else -1
        for i in range(abs(fifths)):
            alters[order[i % 7]] = alters.get(order[i % 7], 0) + step
    for token in value.split()[1:]:
        m = _KEY_ACC_RE.match(token)
        if m:
            alters[m.group(2).upper()] = _ACCIDENTALS[m.group(1)]
    return alters


# --- Body tokenizing -----------------------------------------------------

def _length(num, slashes):
    value = Fraction(int(num)) if num else Fraction(1)
    for part in slashes.split("/")[1:]:
        divisor = int(part) if part else 2
        value /= divisor or 1
    return value


def _ending_numbers(spec):
    numbers = set()
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        numbers.update(range(int(lo), int(hi or lo) + 1))
    return numbers


def _note_entry(m):
    accidental, letter, octave_marks, num, slashes, tie = m.groups()
    octave = octave_marks.count("'") - octave_marks.count(",")
    return (accidental, letter, octave, _length(num, slashes), bool(tie))


class _Tokenizer(object):
    """Splits body lines into per-voice event lists."""

    def __init__(self):
        self.voices = {"": []}
        self.events = self.voices[""]

    def feed(self, line):
        m = _FIELD_RE.match(line)
        if m:
            self._field(m.group(1), _field_value(m.group(2)))
            return
        pos = 0
        while pos < len(line):
            pos = self._token(line, pos)

    def _field(self, letter, value):
        if letter == "V":
            voice_id = value.split()[0] if value.split() else ""
            self.events = self.voices.setdefault(voice_id, [])
        elif letter in "KLM":
            self.events.append(("field", letter, value))

    def _token(self, line, pos):
        char = line[pos]
        emit = self.events.append
        if char == "%":
            return len(line)
        if char in '"!+{':
            end = line.find("}" if char == "{" else char, pos + 1)
            return end + 1 if end >= 0 else pos + 1
        if char == "[":
            m = _INLINE_FIELD_RE.match(line, pos)
            if m:
                self._field(m.group(1), _field_value(m.group(2)))
                return m.end()
            m = _ENDING_RE.match(line, pos)
            if m:
                emit(("ending", _ending_numbers(m.group(1))))
                return m.end()
        if char in "[|:":
            m = _BAR_RE.match(line, pos)
            if m:
                emit(("bar", m.group(2) != "|"))
                if m.group(1):
                    emit(("rep_end",))
                if m.group(3):
                    emit(("rep_start",))
                if m.group(4):
                    emit(("ending", _ending_numbers(m.group(4))))
                return m.end()
            m = _DOUBLE_COLON_RE.match(line, pos)
            if m:
                emit(("bar", False))
                emit(("rep_end",))
                emit(("rep_start",))
                return m.end()
        if char == "[":
            return self._chord(line, pos)
        m = _TUPLET_RE.match(line, pos)
        if m:
            p, q, r = m.groups()
            emit(("tuplet", int(p), int(q) if q else None, int(r) if r else None))
            return m.end()
        m = _NOTE_RE.match(line, pos)
        if m:
            emit(("notes", [_note_entry(m)], Fraction(1)))
            return m.end()
        m = _REST_RE.match(line, pos)
        if m:
            emit(("rest", _length(m.group(1), m.group(2))))
            return m.end()
        m = _MREST_RE.match(line, pos)
        if m:
            emit(("mrest", int(m.group(1) or 1)))
            return m.end()
        m = _BROKEN_RE.match(line, pos)
        if m:
            emit(("broken", m.group(0)))
            return m.end()
        if char == "&":
            emit(("overlay",))
        return pos + 1

    def _chord(self, line, pos):
        entries = []
        j = pos + 1
        while j < len(line) and line[j] not in "]|":
            m = _NOTE_RE.match(line, j)
            if m:
                entries.append(_note_entry(m))
                j = m.end()
            elif line[j] in '"!+':
                end = line.find(line[j], j + 1)
                j = end + 1 if end >= 0 else j + 1
            else:
                j += 1
        if j >= len(line) or line[j] != "]" or not entries:
            return pos + 1
        tail = _CHORD_TAIL_RE.match(line, j + 1)
        multiplier = _length(tail.group(1), tail.group(2))
        if tail.group(3):
            entries = [entry[:4] + (True,) for entry in entries]
        self.events.append(("notes", entries, multiplier))
        return tail.end()


# --- Repeats -------------------------------------------------------------

def _unroll(events):
    """Expand |: :| repeats and numbered endings into playing order."""
    out = []
    start, pass_no, skipping = 0, 1, False
    i = 0
    while i < len(events):
        event = events[i]
        kind = event[0]
        if kind == "rep_start":
            start, pass_no, skipping = i + 1, 1, False
        elif kind == "ending":
            skipping = pass_no not in event[1]
        elif skipping:
            # A double bar closes an ending, so a stray one can't swallow the tune.
            if kind == "bar" and event[1]:
                skipping = False
                out.append(event)
        elif kind == "rep_end":
            if pass_no == 1 or _ending_ahead(events, i, pass_no + 1):
                pass_no += 1
                i = start
                continue
            start, pass_no = i + 1, 1
        else:
            out.append(event)
        i += 1
    return out


def _ending_ahead(events, i, pass_no):
    for event in events[i + 1:]:
        if event[0] == "rep_start":
            return False
        if event[0] == "ending" and pass_no in event[1]:
            return True
    return False


# --- Timing --------------------------------------------------------------

class _Renderer(object):
    """Walks one voice's events, tracking time, key, accidentals and ties."""

    def __init__(self, meter, unit, key):
        self.meter, self.unit, self.key = meter, unit, key
        self.notes = []
        self.t = self.bar_start = Fraction(0)
        self.overlay_end = None
        self.bar_accidentals = {}
        self.ties = {}
        self.tuplet_left, self.tuplet_factor = 0, Fraction(1)
        self.broken_next = None
        self.last = None

    def run(self, events):
        for event in events:
            getattr(self, "_" + event[0])(*event[1:])
        return self.notes

    def _field(self, letter, value):
        if letter == "K":
            self.key = _parse_key(value)
            self.bar_accidentals = {}
        elif letter == "L":
            self.unit = _parse_unit(value, self.unit)
        else:
            self.meter = _parse_meter(value)

    def _bar(self, is_double):
        self.bar_accidentals = {}
        if self.overlay_end is not None:
            self.t = max(self.t, self.overlay_end)
            self.overlay_end = None
        self.bar_start = self.t

    def _overlay(self):
        self.overlay_end = self.t if self.overlay_end is None else max(self.t, self.overlay_end)
        self.t = self.bar_start
        self.ties = {}
        self.last = None

    def _tuplet(self, p, q, r):
        if q is None:
            compound = self.meter is not None and self.meter[0] % 3 == 0 and self.meter[0] > 3
            q = _TUPLET_Q.get(p, 3 if compound else 2)
        self.tuplet_left = r or p
        self.tuplet_factor = Fraction(q, p)

    def _broken(self, arrows):
        if self.last is None:
            return
        shrink = Fraction(1, 2 ** len(arrows))
        grow = 2 - shrink
        prev, self.broken_next = (grow, shrink) if arrows[0] == ">" else (shrink, grow)
        start, advance, sounding = self.last
        self.t = start + advance * prev
        for note, contribution in sounding:
            note["duration"] += contribution * (prev - 1)
        self.last = None

    def _mrest(self, bars):
        bar_length = Fraction(*self.meter) if self.meter else Fraction(1)
        self.t += bars * bar_length
        self.ties = {}
        self.last = None

    def _rest(self, length):
        advance = self.unit * length * self._factor()
        self.last = (self.t, advance, [])
        self.ties = {}
        self.t += advance

    def _notes(self, entries, multiplier):
        factor = self._factor()
        start = self.t
        advance = None
        sounding, ties = [], {}
        for accidental, letter, octave, length, tie in entries:
            duration = self.unit * length * multiplier * factor
            if advance is None:
                advance = duration  # a chord lasts as long as its first note
            slot = (letter.upper(), octave + (1 if letter.islower() else 0))
            held = self.ties.get(slot)
            if accidental is not None:
                self.bar_accidentals[slot] = _ACCIDENTALS[accidental]
                pitch = _midi(slot, _ACCIDENTALS[accidental])
            elif held is not None:
                pitch = held["pitch"]  # a tie carries its accidental across the bar line
            else:
                pitch = _midi(slot, self.bar_accidentals.get(slot, self.key.get(slot[0], 0)))
            if held is not None and held["pitch"] == pitch:
                note = held
                note["duration"] = max(note["duration"], start + duration - note["start"])
            else:
                note = {"pitch": pitch, "start": start, "duration": duration}
                self.notes.append(note)
            sounding.append((note, duration))
            if tie:
                ties[slot] = note
        self.ties = ties
        self.last = (start, advance, sounding)
        self.t = start + advance

    def _factor(self):
        factor = Fraction(1)
        if self.tuplet_left:
            factor *= self.tuplet_factor
            self.tuplet_left -= 1
        if self.broken_next is not None:
            factor *= self.broken_next
            self.broken_next = None
        return factor


def _midi(slot, alter):
    letter, octave = slot
    return 60 + _SEMITONE[letter] + 12 * octave + alter


# --- Writing -------------------------------------------------------------

_GRID = 12  # steps per beat: sixteenths plus eighth- and sixteenth-note triplets
_WRITE_UNIT = Fraction(1, 2)  # beats per ABC unit, matching the L:1/8 we write
_BARS_PER_LINE = 4
_KEY_NAMES = {
    -5: "Db", -4: "Ab", -3: "Eb", -2: "Bb", -1: "F", 0: "C",
    1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#",
}
_ACCIDENTAL_TEXT = {alter: text for text, alter in _ACCIDENTALS.items()}
# Live's Song.scale_name values that have an ABC key signature. Scales without
# one (Whole Tone, the diminished and exotic scales) fall back to guessing.
_LIVE_SCALE_MODES = {
    "Major": "", "Minor": "m", "Dorian": "dor", "Mixolydian": "mix",
    "Lydian": "lyd", "Phrygian": "phr", "Locrian": "loc",
    "Harmonic Minor": "m", "Melodic Minor": "m", "Minor Pentatonic": "m",
    "Minor Blues": "m", "Major Pentatonic": "", "Harmonic Major": "",
}


def serialize_abc(notes, meta=None):
    """Render Live notes as an ABC tune, or return None if none are audible.

    ABC can't mark a note as muted, so muted notes are left out rather than
    coming back switched on. Lossy: times snap to a 1/12-beat grid, and
    velocity and probability are dropped.
    """
    events = _quantize(note for note in notes if not getattr(note, "mute", False))
    if not events:
        return None
    meta = meta or {}
    meter = _parse_meter(str(meta.get("time_sig", ""))) or (4, 4)
    bar = Fraction(meter[0] * _BEATS_PER_WHOLE, meter[1])
    key_name, fifths = _song_key(meta) or _guessed_key(events)
    key = _parse_key(key_name)
    origin = min(Fraction(0), min(start for start, _, _ in events) // bar * bar)
    bar_count = -((origin - max(end for _, end, _ in events)) // bar)

    lines = ["X:1"]
    title = meta.get("clip_name") or meta.get("track_name")
    if title:
        lines.append("T:{}".format(title))
    lines.append("M:{}/{}".format(*meter))
    lines.append("L:1/8")
    if meta.get("tempo"):
        lines.append("Q:1/4={}".format(int(round(meta["tempo"]))))
    lines.append("K:{}".format(key_name))
    voices = _assign_voices(events)
    for number, voice in enumerate(voices, 1):
        if len(voices) > 1:
            lines.append("V:{}".format(number))
        bars = _split_bars(voice, origin, bar, bar_count)
        lines.extend(_bar_lines([_render_bar(pieces, key, fifths < 0) for pieces in bars]))
    return "\n".join(lines)


def _quantize(notes):
    """Snap notes to the grid as (start, end, pitch); a repeated pitch+start keeps the longest."""
    ends = {}
    for note in notes:
        start = _snap(note.start_time)
        end = max(_snap(note.start_time + note.duration), start + Fraction(1, _GRID))
        slot = (int(note.pitch), start)
        ends[slot] = max(end, ends.get(slot, end))
    return [(start, end, pitch) for (pitch, start), end in ends.items()]


def _snap(beats):
    return Fraction(int(round(beats * _GRID)), _GRID)


def _song_key(meta):
    """(K: value, fifths) for Live's root_note and scale_name, or None if they have no key signature."""
    mode = _LIVE_SCALE_MODES.get(meta.get("scale_name"))
    root = meta.get("root_note")
    if mode is None or root is None:
        return None
    spellings = []
    for letter, semitone in _SEMITONE.items():
        for accidental, shift in (("", 0), ("#", 1), ("b", -1)):
            if (semitone + shift) % 12 == int(root) % 12:
                fifths = _FIFTHS[letter] + 7 * shift + _MODE_FIFTHS[mode]
                spellings.append((abs(fifths), -fifths, letter + accidental + mode, fifths))
    # Fewest accidentals wins; on a tie (F# vs Gb) prefer sharps.
    return min(spellings)[2:]


def _guessed_key(events):
    fifths = _guess_fifths(events)
    return _KEY_NAMES[fifths], fifths


def _guess_fifths(events):
    """Pick the key signature whose major scale covers the most note time."""
    weight = [Fraction(0)] * 12
    for start, end, pitch in events:
        weight[pitch % 12] += end - start

    def coverage(fifths):
        tonic = 7 * fifths % 12
        return sum(weight[(tonic + step) % 12] for step in (0, 2, 4, 5, 7, 9, 11))

    return max(_KEY_NAMES, key=lambda fifths: (coverage(fifths), -abs(fifths)))


def _assign_voices(events):
    """Pack notes into voices with no overlaps; notes sharing start and end form chords."""
    chords = {}
    for start, end, pitch in events:
        chords.setdefault((start, end), []).append(pitch)
    voices = []
    for (start, end), pitches in sorted(chords.items(), key=lambda c: (c[0][0], -max(c[1]))):
        chord = (start, end, sorted(pitches))
        for voice in voices:
            if voice[-1][1] <= start:
                voice.append(chord)
                break
        else:
            voices.append([chord])
    voices.sort(key=lambda v: -sum(sum(c[2]) for c in v) / sum(len(c[2]) for c in v))
    return voices


def _split_bars(voice, origin, bar, bar_count):
    """Cut a voice, with rests in its gaps, into per-bar (length, pitches, tied) pieces."""
    segments = []
    t = origin
    for start, end, pitches in voice:
        if start > t:
            segments.append((t, start, None))
        segments.append((start, end, pitches))
        t = end
    segments.append((t, origin + bar_count * bar, None))
    bars = [[] for _ in range(bar_count)]
    for start, end, pitches in segments:
        while start < end:
            index = (start - origin) // bar
            cut = min(end, origin + (index + 1) * bar)
            bars[index].append((cut - start, pitches, pitches is not None and cut < end))
            start = cut
    return bars


def _render_bar(pieces, key, prefer_flats):
    if all(pitches is None for _, pitches, _ in pieces):
        return None
    in_effect = {}
    tokens = []
    for length, pitches, tied in pieces:
        length_text = _length_text(length / _WRITE_UNIT)
        if pitches is None:
            tokens.append("z" + length_text)
            continue
        names = []
        for pitch in pitches:
            letter, alter, octave = _spell(pitch, key, prefer_flats)
            slot = (letter, octave)
            accidental = ""
            if in_effect.get(slot, key.get(letter, 0)) != alter:
                accidental = _ACCIDENTAL_TEXT[alter]
                in_effect[slot] = alter
            names.append(accidental + _note_name(letter, octave))
        chord = names[0] if len(names) == 1 else "[" + "".join(names) + "]"
        tokens.append(chord + length_text + ("-" if tied else ""))
    return " ".join(tokens)


def _spell(pitch, key, prefer_flats):
    """Name a MIDI pitch as (letter, alteration, octave): in-key first, then natural."""
    pc = pitch % 12
    options = [
        (letter, alter)
        for letter, natural in _SEMITONE.items()
        for alter in (-1, 0, 1)
        if (natural + alter) % 12 == pc
    ]
    unwanted = 1 if prefer_flats else -1
    letter, alter = min(
        options,
        key=lambda o: (o[1] != key.get(o[0], 0), o[1] != 0, o[1] == unwanted),
    )
    return letter, alter, (pitch - alter - _SEMITONE[letter] - 60) // 12


def _note_name(letter, octave):
    if octave >= 1:
        return letter.lower() + "'" * (octave - 1)
    return letter + "," * -octave


def _length_text(units):
    if units == 1:
        return ""
    if units.denominator == 1:
        return str(units.numerator)
    if units.numerator == 1:
        return "/" if units.denominator == 2 else "/{}".format(units.denominator)
    return "{}/{}".format(units.numerator, units.denominator)


def _bar_lines(bars):
    """Join rendered bars into lines, folding runs of empty bars into Z rests."""
    while bars[-1] is None:
        bars.pop()
    items, empty = [], 0
    for bar in bars:
        if bar is None:
            empty += 1
            continue
        if empty:
            items.append("Z{}".format(empty if empty > 1 else ""))
            empty = 0
        items.append(bar)
    lines = [
        " | ".join(items[i:i + _BARS_PER_LINE]) + " |"
        for i in range(0, len(items), _BARS_PER_LINE)
    ]
    lines[-1] += "]"
    return lines
