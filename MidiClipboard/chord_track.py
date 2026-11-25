"""Chord-symbol accompaniment, ported from abcjs so a paste plays what abcjs plays.

A port of abcjs 6.7.2 ``src/synth/chord-track.js``: the parts that choose
pitches and timings. Instruments, volumes, transposition and rhythm heads are
left out. Times are whole notes, as in ``abc_serde``'s renderer.

The rules, briefly:

- One accompaniment for the whole tune, from the first voice that produces one.
- Each bar plays a pattern of eighth-note slots chosen by the meter, such as
  ``boom . chick . boom . chick .`` in 4/4. A boom is the bass note and a
  chick is the chord. ``%%MIDI gchord`` can replace the pattern.
- A chord holds until the next symbol, across bar lines. A symbol that isn't
  on a slot takes effect at the next one.
- A bar whose length doesn't match the meter (a pickup or a short last bar)
  plays chicks on alternate slots instead.
- Notes last half a beat of the meter: an eighth in x/4, a sixteenth in x/8.

abcjs is Copyright (c) 2009-2026 Paul Rosen and Gregory Dyke, under the MIT
license:

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to permit
    persons to whom the Software is furnished to do so, subject to the
    following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
    NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
    OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
    USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

from fractions import Fraction


_SLOT = Fraction(1, 8)  # pattern slots are eighth notes in every meter
_BASSES = {"A": 33, "B": 35, "C": 36, "D": 38, "E": 40, "F": 41, "G": 43}
_ACCIDENTAL_SHIFT = {"#": 1, "♯": 1, "b": -1, "♭": -1}
_BREAK_SYNONYMS = ("break", "(break)", "no chord", "n.c.", "tacet")
# A leading ^ _ < > or @ makes quoted text an annotation, not a chord symbol.
_ANNOTATIONS = {"^": "above", "_": "below", "<": "left", ">": "right", "@": "relative"}
_GCHORD_STEPS = {
    "z": "", "2": "", "c": "chick", "b": "boom&chick", "f": "boom",
    "G": "DO", "H": "MI", "I": "SOL", "J": "TI", "K": "TOP",
    "g": "do", "h": "mi", "i": "sol", "j": "ti", "k": "top",
}
# Arpeggio steps: (chord tone, wraps into the next octave when the chord is short).
_ARPEGGIO = {"DO": (0, False), "MI": (1, False), "SOL": (2, True), "TI": (3, True), "TOP": (4, True)}

_RHYTHM_PATTERNS = {
    "2/2": ["boom", "", "", "", "chick", "", "", ""],
    "3/2": ["boom", "", "", "", "chick", "", "", "", "chick", "", "", ""],
    "4/2": ["boom", "", "", "", "chick", "", "", "", "boom", "", "", "", "chick", "", "", ""],

    "2/4": ["boom", "", "chick", ""],
    "3/4": ["boom", "", "chick", "", "chick", ""],
    "4/4": ["boom", "", "chick", "", "boom", "", "chick", ""],
    "5/4": ["boom", "", "chick", "", "chick", "", "boom", "", "chick", ""],
    "6/4": ["boom", "", "chick", "", "boom", "", "chick", "", "boom", "", "chick", ""],

    "3/8": ["boom", "", "chick"],
    "5/8": ["boom", "chick", "chick", "boom", "chick"],
    "6/8": ["boom", "", "chick", "boom", "", "chick"],
    "7/8": ["boom", "chick", "chick", "boom", "chick", "boom", "chick"],
    "9/8": ["boom", "", "chick", "boom", "", "chick", "boom", "", "chick"],
    "10/8": ["boom", "chick", "chick", "boom", "chick", "chick", "boom", "chick", "boom", "chick"],
    "11/8": ["boom", "chick", "chick", "boom", "chick", "chick", "boom", "chick", "boom", "chick", "chick"],
    "12/8": ["boom", "", "chick", "boom", "", "chick", "boom", "", "chick", "boom", "", "chick"],
}

# Chord spellings (the text after the root) to semitones above the root,
# from abcjs's chordIntervals table.
_CHORD_INTERVALS = {
    # unusual chords
    "-addb2": [0, 1, 3, 7],
    "maddb2": [0, 1, 3, 7],
    "addb2": [0, 1, 4, 7],
    "susb2": [0, 1, 7],
    "-add2": [0, 2, 3, 7],
    "madd2": [0, 2, 3, 7],
    "add2": [0, 2, 4, 7],
    "sus2": [0, 2, 7],
    "-7sus2": [0, 2, 7, 10],
    "7sus2": [0, 2, 7, 10],
    "m7sus2": [0, 2, 7, 10],
    "min7sus2": [0, 2, 7, 10],
    "7sus2/9": [0, 2, 7, 10, 14],
    "add#2": [0, 3, 4, 7],
    "-add4": [0, 3, 5, 7],
    "madd4": [0, 3, 5, 7],

    # diminished chords
    "dim": [0, 3, 6],
    "m(b5)": [0, 3, 6],
    "\u00b0": [0, 3, 6],
    "\u02da": [0, 3, 6],
    "-add#4": [0, 3, 6, 7],
    "madd#4": [0, 3, 6, 7],
    "dim7": [0, 3, 6, 9],
    "\u00b07": [0, 3, 6, 9],
    "\u02da7": [0, 3, 6, 9],
    "-7(b5)": [0, 3, 6, 10],
    "-7b5": [0, 3, 6, 10],
    "m7(b5)": [0, 3, 6, 10],
    "m7b5": [0, 3, 6, 10],
    "\u00f8": [0, 3, 6, 10],
    "\u00f87": [0, 3, 6, 10],

    # minor chords
    "-": [0, 3, 7],
    "m": [0, 3, 7],
    "-(b6)": [0, 3, 7, 8],
    "-b6": [0, 3, 7, 8],
    "m(b6)": [0, 3, 7, 8],
    "mb6": [0, 3, 7, 8],
    "-6": [0, 3, 7, 9],
    "m6": [0, 3, 7, 9],
    "-6(9)": [0, 3, 7, 9, 14],
    "-6/9": [0, 3, 7, 9, 14],
    "-69": [0, 3, 7, 9, 14],
    "m6(9)": [0, 3, 7, 9, 14],
    "m6/9": [0, 3, 7, 9, 14],
    "m69": [0, 3, 7, 9, 14],
    "-7": [0, 3, 7, 10],
    "m7": [0, 3, 7, 10],
    "-7(b9)": [0, 3, 7, 10, 13],
    "-7b9": [0, 3, 7, 10, 13],
    "-7(9)": [0, 3, 7, 10, 14],
    "-7/9": [0, 3, 7, 10, 14],
    "-9": [0, 3, 7, 10, 14],
    "m7(9)": [0, 3, 7, 10, 14],
    "m7/9": [0, 3, 7, 10, 14],
    "m9": [0, 3, 7, 10, 14],
    "-7(9,11)": [0, 3, 7, 10, 14, 17],
    "-7/9/11": [0, 3, 7, 10, 14, 17],
    "m7(9,11)": [0, 3, 7, 10, 14, 17],
    "m7/9/11": [0, 3, 7, 10, 14, 17],
    "-13": [0, 3, 7, 10, 14, 17, 21],
    "-7(9,11,13)": [0, 3, 7, 10, 14, 17, 21],
    "-7/9/11/13": [0, 3, 7, 10, 14, 17, 21],
    "m13": [0, 3, 7, 10, 14, 17, 21],
    "m7(9,11,13)": [0, 3, 7, 10, 14, 17, 21],
    "m7/9/11/13": [0, 3, 7, 10, 14, 17, 21],
    "-7(9,13)": [0, 3, 7, 10, 14, 21],
    "-7/9/13": [0, 3, 7, 10, 14, 21],
    "m7(9,13)": [0, 3, 7, 10, 14, 21],
    "m7/9/13": [0, 3, 7, 10, 14, 21],
    "-7(11)": [0, 3, 7, 10, 17],
    "-7/11": [0, 3, 7, 10, 17],
    "m7(11)": [0, 3, 7, 10, 17],
    "m7/11": [0, 3, 7, 10, 17],
    "-7(11,13)": [0, 3, 7, 10, 17, 21],
    "-7/11/13": [0, 3, 7, 10, 17, 21],
    "m7(11,13)": [0, 3, 7, 10, 17, 21],
    "m7/11/13": [0, 3, 7, 10, 17, 21],
    "-(maj7)": [0, 3, 7, 11],
    "-7M": [0, 3, 7, 11],
    "-maj7": [0, 3, 7, 11],
    "-\u22067": [0, 3, 7, 11],
    "m(maj7)": [0, 3, 7, 11],
    "mM7": [0, 3, 7, 11],
    "min(maj7)": [0, 3, 7, 11],
    "-9+7": [0, 3, 7, 11, 13],
    "-(maj9)": [0, 3, 7, 11, 14],
    "-7M(9)": [0, 3, 7, 11, 14],
    "-maj9": [0, 3, 7, 11, 14],
    "-\u22069": [0, 3, 7, 11, 14],
    "m(maj9)": [0, 3, 7, 11, 14],
    "mM9": [0, 3, 7, 11, 14],
    "min(maj9)": [0, 3, 7, 11, 14],
    "-11": [0, 3, 7, 11, 14, 17],
    "m11": [0, 3, 7, 11, 14, 17],
    "-addb9": [0, 3, 7, 13],
    "maddb9": [0, 3, 7, 13],
    "-add9": [0, 3, 7, 14],
    "madd9": [0, 3, 7, 14],
    "-add11": [0, 3, 7, 17],
    "madd11": [0, 3, 7, 17],
    "-add#11": [0, 3, 7, 18],
    "madd#11": [0, 3, 7, 18],

    # altered minor chords
    "-#5": [0, 3, 8],
    "-(#5)": [0, 3, 8],
    "m#5": [0, 3, 8],
    "m(#5)": [0, 3, 8],
    "-7#5": [0, 3, 8, 10],
    "-7(#5)": [0, 3, 8, 10],
    "dim7(b13)": [0, 3, 9, 20],
    "\u00b07(b13)": [0, 3, 9, 20],
    "\u02da7(b13)": [0, 3, 9, 20],

    # altered major chords
    "add4": [0, 4, 5, 7],
    "maj(b5)": [0, 4, 6],
    "majb5": [0, 4, 6],
    "add#4": [0, 4, 6, 7],
    "7(b5)": [0, 4, 6, 10],
    "7b5": [0, 4, 6, 10],
    "7(b5,b9)": [0, 4, 6, 10, 13],
    "7(b9,b5)": [0, 4, 6, 10, 13],
    "7b5(b9)": [0, 4, 6, 10, 13],
    "7b9,b5": [0, 4, 6, 10, 13],
    "7b9b5": [0, 4, 6, 10, 13],
    "7(b5,b9,b13)": [0, 4, 6, 10, 13, 20],
    "7/b5/b9/b13": [0, 4, 6, 10, 13, 20],
    "7b5/b9/b13": [0, 4, 6, 10, 13, 20],
    "7(b5,b9,13)": [0, 4, 6, 10, 13, 21],
    "7/b5/b9/13": [0, 4, 6, 10, 13, 21],
    "7b5/b9/13": [0, 4, 6, 10, 13, 21],
    "7(9,b5)": [0, 4, 6, 10, 14],
    "7(b5,9)": [0, 4, 6, 10, 14],
    "7b5(9)": [0, 4, 6, 10, 14],
    "9b5": [0, 4, 6, 10, 14],
    "13(b5)": [0, 4, 6, 10, 14, 21],
    "13b5": [0, 4, 6, 10, 14, 21],
    "7(b5,9,13)": [0, 4, 6, 10, 14, 21],
    "7/b5/9/13": [0, 4, 6, 10, 14, 21],
    "7b5/9/13": [0, 4, 6, 10, 14, 21],
    "7#9b5": [0, 4, 6, 10, 15],
    "7(#9,b5)": [0, 4, 6, 10, 15],
    "7(b5,#9)": [0, 4, 6, 10, 15],
    "7b5(#9)": [0, 4, 6, 10, 15],
    "7(b5,#9,b13)": [0, 4, 6, 10, 15, 20],
    "7/b5/#9/b13": [0, 4, 6, 10, 15, 20],
    "7b5/#9/b13": [0, 4, 6, 10, 15, 20],
    "7(b5,#9,13)": [0, 4, 6, 10, 15, 21],
    "7/b5/#9/13": [0, 4, 6, 10, 15, 21],
    "7b5/#9/13": [0, 4, 6, 10, 15, 21],
    "7(b5,b13)": [0, 4, 6, 10, 20],
    "7/b5/b13": [0, 4, 6, 10, 20],
    "7b5/b13": [0, 4, 6, 10, 20],
    "7(b5,13)": [0, 4, 6, 10, 21],
    "7/b5/13": [0, 4, 6, 10, 21],
    "7b5(13)": [0, 4, 6, 10, 21],
    "7b5/13": [0, 4, 6, 10, 21],
    "7M(b5)": [0, 4, 6, 11],
    "maj7(b5)": [0, 4, 6, 11],
    "maj7b5": [0, 4, 6, 11],
    "7M(b5,9)": [0, 4, 6, 11, 14],
    "maj7(b5,9)": [0, 4, 6, 11, 14],
    "maj7b5/9": [0, 4, 6, 11, 14],
    "7M(b5,9,13)": [0, 4, 6, 11, 14, 21],
    "maj7(b5,9,13)": [0, 4, 6, 11, 14, 21],
    "maj7b5/9/13": [0, 4, 6, 11, 14, 21],
    "7M(b5,13)": [0, 4, 6, 11, 21],
    "maj7(b5,13)": [0, 4, 6, 11, 21],
    "maj7b5/13": [0, 4, 6, 11, 21],

    # major chords
    "M": [0, 4, 7],
    "\u0394": [0, 4, 7],
    "\u2206": [0, 4, 7],
    "6": [0, 4, 7, 9],
    "6(9)": [0, 4, 7, 9, 14],
    "6/9": [0, 4, 7, 9, 14],
    "69": [0, 4, 7, 9, 14],
    "6add9": [0, 4, 7, 9, 14],
    "6(9,11)": [0, 4, 7, 9, 14, 17],
    "6/9/11": [0, 4, 7, 9, 14, 17],
    "6911": [0, 4, 7, 9, 14, 17],
    "6(9,#11)": [0, 4, 7, 9, 14, 18],
    "6/9/#11": [0, 4, 7, 9, 14, 18],
    "69#11": [0, 4, 7, 9, 14, 18],
    "6(11)": [0, 4, 7, 9, 17],
    "6/11": [0, 4, 7, 9, 17],
    "611": [0, 4, 7, 9, 17],
    "6#11": [0, 4, 7, 9, 18],
    "6(#11)": [0, 4, 7, 9, 18],
    "6/#11": [0, 4, 7, 9, 18],
    "7": [0, 4, 7, 10],
    "7(b9)": [0, 4, 7, 10, 13],
    "7b9": [0, 4, 7, 10, 13],
    "7(9)": [0, 4, 7, 10, 14],
    "7/9": [0, 4, 7, 10, 14],
    "9": [0, 4, 7, 10, 14],
    "7(9,11)": [0, 4, 7, 10, 14, 17],
    "7/9/11": [0, 4, 7, 10, 14, 17],
    "7(9,11,13)": [0, 4, 7, 10, 14, 17, 21],
    "7/9/11/13": [0, 4, 7, 10, 14, 17, 21],
    "7#11": [0, 4, 7, 10, 14, 18],
    "7(#11)": [0, 4, 7, 10, 14, 18],
    "9#11": [0, 4, 7, 10, 14, 18],
    "9(#11)": [0, 4, 7, 10, 14, 18],
    "(13)": [0, 4, 7, 10, 14, 21],
    "13": [0, 4, 7, 10, 14, 21],
    "7(9,13)": [0, 4, 7, 10, 14, 21],
    "7/9/13": [0, 4, 7, 10, 14, 21],
    "9/13": [0, 4, 7, 10, 14, 21],
    "7#9": [0, 4, 7, 10, 15],
    "7(#9)": [0, 4, 7, 10, 15],
    "7(#9,b13)": [0, 4, 7, 10, 15, 20],
    "7(11)": [0, 4, 7, 10, 17],
    "7/11": [0, 4, 7, 10, 17],
    "7(11,13)": [0, 4, 7, 10, 17, 21],
    "7/11/13": [0, 4, 7, 10, 17, 21],
    "13#11": [0, 4, 7, 10, 18, 21],
    "13(#11)": [0, 4, 7, 10, 18, 21],
    "7(b13)": [0, 4, 7, 10, 20],
    "7b13": [0, 4, 7, 10, 20],
    "7(13)": [0, 4, 7, 10, 21],
    "7/13": [0, 4, 7, 10, 21],
    "7M": [0, 4, 7, 11],
    "maj7": [0, 4, 7, 11],
    "\u03947": [0, 4, 7, 11],
    "\u22067": [0, 4, 7, 11],
    "7M(9)": [0, 4, 7, 11, 14],
    "7M/9": [0, 4, 7, 11, 14],
    "maj7(9)": [0, 4, 7, 11, 14],
    "maj7/9": [0, 4, 7, 11, 14],
    "maj9": [0, 4, 7, 11, 14],
    "\u03949": [0, 4, 7, 11, 14],
    "\u22069": [0, 4, 7, 11, 14],
    "7M(9,11)": [0, 4, 7, 11, 14, 17],
    "7M/9/11": [0, 4, 7, 11, 14, 17],
    "maj11": [0, 4, 7, 11, 14, 17],
    "maj7(9,11)": [0, 4, 7, 11, 14, 17],
    "maj7/9/11": [0, 4, 7, 11, 14, 17],
    "\u039411": [0, 4, 7, 11, 14, 17],
    "\u220611": [0, 4, 7, 11, 14, 17],
    "7M(9,11,13)": [0, 4, 7, 11, 14, 17, 21],
    "7M/9/11/13": [0, 4, 7, 11, 14, 17, 21],
    "maj13": [0, 4, 7, 11, 14, 17, 21],
    "maj7(9,11,13)": [0, 4, 7, 11, 14, 17, 21],
    "maj7/9/11/13": [0, 4, 7, 11, 14, 17, 21],
    "\u039411(13)": [0, 4, 7, 11, 14, 17, 21],
    "\u039413": [0, 4, 7, 11, 14, 17, 21],
    "\u220611(13)": [0, 4, 7, 11, 14, 17, 21],
    "7M(9,#11)": [0, 4, 7, 11, 14, 18],
    "7M/9/#11": [0, 4, 7, 11, 14, 18],
    "maj7(9,#11)": [0, 4, 7, 11, 14, 18],
    "maj7/9/#11": [0, 4, 7, 11, 14, 18],
    "maj9#11": [0, 4, 7, 11, 14, 18],
    "maj9(#11)": [0, 4, 7, 11, 14, 18],
    "maj9/#11": [0, 4, 7, 11, 14, 18],
    "\u03949(#11)": [0, 4, 7, 11, 14, 18],
    "7M(9,#11,13)": [0, 4, 7, 11, 14, 18, 21],
    "7M/9/#11/13": [0, 4, 7, 11, 14, 18, 21],
    "maj13#11": [0, 4, 7, 11, 14, 18, 21],
    "maj13(#11)": [0, 4, 7, 11, 14, 18, 21],
    "maj13/#11": [0, 4, 7, 11, 14, 18, 21],
    "\u039413(#11)": [0, 4, 7, 11, 14, 18, 21],
    "\u220613(#11)": [0, 4, 7, 11, 14, 18, 21],
    "7M(9,13)": [0, 4, 7, 11, 14, 21],
    "7M/9/13": [0, 4, 7, 11, 14, 21],
    "maj7(9,13)": [0, 4, 7, 11, 14, 21],
    "maj7/9/13": [0, 4, 7, 11, 14, 21],
    "maj9(13)": [0, 4, 7, 11, 14, 21],
    "\u03949(13)": [0, 4, 7, 11, 14, 21],
    "\u22069(13)": [0, 4, 7, 11, 14, 21],
    "7M(11)": [0, 4, 7, 11, 17],
    "7M/11": [0, 4, 7, 11, 17],
    "maj7(11)": [0, 4, 7, 11, 17],
    "maj7/11": [0, 4, 7, 11, 17],
    "\u03947(11)": [0, 4, 7, 11, 17],
    "\u22067(11)": [0, 4, 7, 11, 17],
    "7M(#11)": [0, 4, 7, 11, 18],
    "7M/#11": [0, 4, 7, 11, 18],
    "maj7(#11)": [0, 4, 7, 11, 18],
    "maj7/#11": [0, 4, 7, 11, 18],
    "\u03947(#11)": [0, 4, 7, 11, 18],
    "\u22067(#11)": [0, 4, 7, 11, 18],
    "7M(13)": [0, 4, 7, 11, 21],
    "7M/13": [0, 4, 7, 11, 21],
    "maj7(13)": [0, 4, 7, 11, 21],
    "maj7/13": [0, 4, 7, 11, 21],
    "\u03947(13)": [0, 4, 7, 11, 21],
    "\u22067(13)": [0, 4, 7, 11, 21],
    "addb9": [0, 4, 7, 13],
    "add9": [0, 4, 7, 14],
    "add#9": [0, 4, 7, 15],
    "add11": [0, 4, 7, 17],
    "add#11": [0, 4, 7, 18],

    # augmented chords
    "+": [0, 4, 8],
    "aug": [0, 4, 8],
    "+7": [0, 4, 8, 10],
    "7#5": [0, 4, 8, 10],
    "7(#5)": [0, 4, 8, 10],
    "7+5": [0, 4, 8, 10],
    "aug7": [0, 4, 8, 10],
    "7(b9,#5)": [0, 4, 8, 10, 13],
    "7b9#5": [0, 4, 8, 10, 13],
    "9#5": [0, 4, 8, 10, 14],
    "9(#5)": [0, 4, 8, 10, 14],
    "9+5": [0, 4, 8, 10, 14],
    "13#5": [0, 4, 8, 10, 14, 21],
    "13(#5)": [0, 4, 8, 10, 14, 21],
    "7M(#5)": [0, 4, 8, 11],
    "maj7#5": [0, 4, 8, 11],
    "maj7(#5)": [0, 4, 8, 11],
    "7M(#5,9)": [0, 4, 8, 11, 14],
    "maj7#5/9": [0, 4, 8, 11, 14],
    "maj7(#5,9)": [0, 4, 8, 11, 14],
    "maj7#5#11": [0, 4, 8, 11, 18],
    "maj7(#5,#11)": [0, 4, 8, 11, 18],

    # sus4 chords
    "sus": [0, 5, 7],
    "sus4": [0, 5, 7],
    "-7sus4": [0, 5, 7, 10],
    "7sus": [0, 5, 7, 10],
    "7sus4": [0, 5, 7, 10],
    "m7sus4": [0, 5, 7, 10],
    "min7sus4": [0, 5, 7, 10],
    "7sus(b9)": [0, 5, 7, 10, 13],
    "7sus4(b9)": [0, 5, 7, 10, 13],
    "-9sus4": [0, 5, 7, 10, 14],
    "7sus4(9)": [0, 5, 7, 10, 14],
    "7sus4/9": [0, 5, 7, 10, 14],
    "9sus": [0, 5, 7, 10, 14],
    "9sus4": [0, 5, 7, 10, 14],
    "m9sus4": [0, 5, 7, 10, 14],
    "min9sus4": [0, 5, 7, 10, 14],
    "11sus4": [0, 5, 7, 10, 14, 17],
    "13sus4": [0, 5, 7, 10, 14, 21],
    "7sus(#9)": [0, 5, 7, 10, 15],
    "7sus4(#9)": [0, 5, 7, 10, 15],
    "7sus4(11)": [0, 5, 7, 10, 17],
    "7sus4(13)": [0, 5, 7, 10, 21],
    "7Msus": [0, 5, 7, 11],
    "7Msus4": [0, 5, 7, 11],
    "maj7sus": [0, 5, 7, 11],
    "maj7sus4": [0, 5, 7, 11],

    # power chords and unusual chords
    "#4": [0, 6],
    "b5": [0, 6],
    "sus#4": [0, 6, 7],
    "7Msus#4": [0, 6, 11],
    "maj7sus#4": [0, 6, 11],
    "5": [0, 7],
    "11": [0, 7, 10, 14, 17],
    "5(8)": [0, 7, 12],
    "5add8": [0, 7, 12],
    "5(9)": [0, 7, 14],
    "5add9": [0, 7, 14],
    "#5": [0, 8],
    "b6": [0, 8],
}


def add_symbol(symbols, text):
    """Add one quoted string to a note's (position, name) list, as abcjs does.

    Two strings in the same position on one note join with a newline.
    """
    position = _ANNOTATIONS.get(text[:1])
    if position:
        text = text[1:]
    position = position or "default"
    name = text.replace(";", "\n")
    for i, (other, joined) in enumerate(symbols):
        if other == position:
            symbols[i] = (other, joined + "\n" + name)
            return
    symbols.append((position, name))


def parse_gchord(text):
    """A ``%%MIDI gchord`` string such as ``fzczfzcz`` as a list of slot kinds."""
    return [_GCHORD_STEPS[ch] for ch in text if ch in _GCHORD_STEPS]


def interpret_chord(name):
    """A chord symbol as {boom, boom2, chick}, or None for an unknown root."""
    if not name:
        return None
    if name == "break":
        return {"boom": None, "boom2": None, "chick": []}
    if name[0] == "(":
        name = name[1:-1]
        if not name:
            return None
    bass = _BASSES.get(name[0])
    if bass is None:
        return None
    root = bass
    remaining = name[1:]
    shift = _ACCIDENTAL_SHIFT.get(remaining[:1], 0)
    if shift:
        root += shift
        bass += shift
        remaining = remaining[1:]
    bass2 = bass - 5  # the alternate bass is a fourth below
    parts = remaining.split("/")
    chick = _chord_notes(root, parts[0])
    if len(chick) >= 3:
        bass2 += chick[2] - chick[0] - 7  # follow an altered fifth
    if len(parts) == 2:
        slash = _BASSES.get(parts[1][:1])
        if slash is not None:
            bass = bass2 = slash + _ACCIDENTAL_SHIFT.get(parts[1][1:], 0)
    return {"boom": bass, "boom2": bass2, "chick": chick}


def _chord_notes(bass, modifier):
    modifier = modifier.replace("♭", "b").replace("♯", "#")
    intervals = _CHORD_INTERVALS.get(modifier)
    if intervals is None:
        # Unknown spelling: guess major or minor from how it starts.
        if modifier[:2].lower() == "ma" or modifier[:1] == "M":
            intervals = _CHORD_INTERVALS["M"]
        elif modifier[:1] in ("m", "-"):
            intervals = _CHORD_INTERVALS["m"]
        else:
            intervals = _CHORD_INTERVALS["M"]
    return [bass + 12 + interval for interval in intervals]  # an octave above the bass


class ChordTrack(object):
    """Collects chord symbols as voices are rendered and writes the accompaniment.

    Call ``start_voice`` and ``finish_voice`` around each voice, ``element`` for
    every note and rest (with the chord symbols attached to it), and ``bar`` at
    each bar line that follows at least one note or rest.
    """

    def __init__(self, gchord=None):
        self.notes = []
        self.started = False  # a chord symbol has been seen
        self.finished = False  # one voice already produced the accompaniment
        self.set_pattern(gchord)
        self.tacet = False
        self.current = []  # (eighth-note slot, chord) in the bar so far
        self.last_chord = None
        self.chord_last_bar = None
        self.last_bar_time = Fraction(0)

    def start_voice(self):
        self.last_bar_time = Fraction(0)

    def finish_voice(self):
        if self.notes:
            self.finished = True

    def set_pattern(self, text):
        self.pattern = parse_gchord(text) if text else None

    def set_tacet(self, tacet):
        self.tacet = tacet

    def element(self, symbols, time):
        if self.finished:
            return
        name = self._find(symbols)
        chord = interpret_chord(name) if name else None
        if chord is None:
            return
        self.started = True
        self.last_chord = chord
        self.current.append(((time - self.last_bar_time) * 8, chord))

    def bar(self, time, meter):
        if self.started and not self.finished:
            self._resolve(self.last_bar_time, time, meter or (4, 4))
            self.current = []
        self.chord_last_bar = self.last_chord
        self.last_bar_time = time

    def _find(self, symbols):
        if self.tacet:
            return "break"
        for position, name in symbols:
            if position == "default":
                return name
            if name.lower() in _BREAK_SYNONYMS:
                return "break"
        return None

    def _resolve(self, start, end, meter):
        num, den = meter
        slots = Fraction(8 * num, den)
        note_length = Fraction(1, 2 * den)
        current = self.current
        if not current or current[0][0] != 0:
            current = [(0, self.chord_last_bar)] + current
        chords = _expand(current, slots)

        pattern = self.pattern
        if pattern is None:
            pattern = _RHYTHM_PATTERNS.get("{}/{}".format(num, den))
        if end - start != Fraction(num, den):
            # A bar of the wrong length: chicks on alternate slots.
            present = (end - start) * 8
            pattern = ["chick", ""] * len(range(0, _ceil(present / 2), 2))
        if pattern is None:
            pattern = ["chick", ""] * _ceil(slots / 2)

        first_boom = True
        for slot in range(min(len(pattern), len(chords))):
            chord = chords[slot]
            previous = chords[slot - 1] if slot else None
            changed = previous is None or chord is None or previous["boom"] != chord["boom"]
            if slot and previous is not None and chord is not None and changed:
                first_boom = True
            kind = pattern[slot]
            is_boom = "boom" in kind
            # A chord change between booms gets its own bass note.
            new_bass = not is_boom and slot != 0 and "boom" in pattern[0] and changed
            pitches = _resolve_pitch(chord, kind, first_boom, new_bass)
            if is_boom:
                first_boom = False
            for pitch in pitches:
                if pitch is not None:
                    self.notes.append({
                        "pitch": pitch,
                        "start": start + slot * _SLOT,
                        "duration": note_length,
                    })


def _expand(current, slots):
    """The chord in effect at each eighth-note slot of the bar."""
    chords = []
    chord = current[0][1]
    for beat, following in current[1:]:
        while len(chords) < beat:
            chords.append(chord)
        chord = following
    while len(chords) < slots:
        chords.append(chord)
    return chords


def _resolve_pitch(chord, kind, first_boom, new_bass):
    if chord is None:
        return []
    pitches = []
    if "boom" in kind:
        pitches.append(chord["boom"] if first_boom else chord["boom2"])
    elif new_bass:
        pitches.append(chord["boom"])
    chick = chord["chick"]
    if "chick" in kind:
        pitches.extend(chick)
    step = _ARPEGGIO.get(kind.upper())
    if step is not None:
        index, wraps = step
        if not chick:
            note = None
        elif wraps:
            note = chick[index % len(chick)] + 12 * (index // len(chick))
        else:
            note = chick[index] if index < len(chick) else None
        if note is not None and kind.islower():
            note += 12
        pitches.append(note)
    return pitches


def _ceil(value):
    return -(-value // 1)
