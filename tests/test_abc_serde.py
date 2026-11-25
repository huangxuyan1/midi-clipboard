import json
import os
import random
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MidiClipboard"))

import abc_serde  # noqa: E402


def parse(text):
    return [
        (n["pitch"], round(n["start_time"], 6), round(n["duration"], 6))
        for n in abc_serde.parse_abc(text)
    ]


def tune(body, header="L:1/4\nK:C"):
    return parse("X:1\n" + header + "\n" + body)


class _Note(object):
    def __init__(self, pitch, start_time, duration, mute=False):
        self.pitch, self.start_time, self.duration = pitch, start_time, duration
        self.mute = mute


def write(notes, **meta):
    return abc_serde.serialize_abc([_Note(*n) for n in notes], meta=meta)


def body(text):
    return text.split("\nK:", 1)[1].split("\n", 1)[1]


class PitchTests(unittest.TestCase):
    def test_scale(self):
        self.assertEqual(tune("C D E F"), [(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 3, 1)])

    def test_octave_marks(self):
        self.assertEqual(tune("C, C c c'"), [(48, 0, 1), (60, 1, 1), (72, 2, 1), (84, 3, 1)])

    def test_key_signature_and_bar_scoped_accidentals(self):
        self.assertEqual(
            tune("F ^C C | C =F F", header="L:1/4\nK:G"),
            [(66, 0, 1), (61, 1, 1), (61, 2, 1), (60, 3, 1), (65, 4, 1), (65, 5, 1)],
        )

    def test_modes_and_flat_keys(self):
        self.assertEqual(tune("B", header="L:1/4\nK:Ddor"), [(71, 0, 1)])
        self.assertEqual(tune("B", header="L:1/4\nK:Dm"), [(70, 0, 1)])
        self.assertEqual(tune("E", header="L:1/4\nK:Bb"), [(63, 0, 1)])
        self.assertEqual(tune("G", header="L:1/4\nK:F#m"), [(68, 0, 1)])
        self.assertEqual(tune("F G", header="L:1/4\nK:A mixolydian"), [(66, 0, 1), (67, 1, 1)])

    def test_explicit_key_accidentals(self):
        self.assertEqual(tune("G", header="L:1/4\nK:D ^g"), [(68, 0, 1)])


class LengthTests(unittest.TestCase):
    def test_multipliers(self):
        self.assertEqual(
            tune("C2 C/2 C/ C// C3/2"),
            [(60, 0, 2), (60, 2, 0.5), (60, 2.5, 0.5), (60, 3, 0.25), (60, 3.25, 1.5)],
        )

    def test_default_unit_from_meter(self):
        self.assertEqual(parse("M:4/4\nK:C\nC D"), [(60, 0, 0.5), (62, 0.5, 0.5)])
        self.assertEqual(parse("M:2/4\nK:C\nC D"), [(60, 0, 0.25), (62, 0.25, 0.25)])
        self.assertEqual(parse("K:C\nC"), [(60, 0, 0.5)])

    def test_rests(self):
        self.assertEqual(tune("z2 C x C", header="L:1/8\nK:C"), [(60, 1, 0.5), (60, 2, 0.5)])

    def test_multi_measure_rest(self):
        self.assertEqual(tune("Z2 C", header="M:3/4\nL:1/4\nK:C"), [(60, 6, 1)])

    def test_broken_rhythm(self):
        self.assertEqual(
            tune("A>B c<d", header="L:1/8\nK:C"),
            [(69, 0, 0.75), (71, 0.75, 0.25), (72, 1, 0.25), (74, 1.25, 0.75)],
        )

    def test_triplet(self):
        third = round(1 / 3, 6)
        self.assertEqual(
            tune("(3CDE F", header="L:1/8\nK:C"),
            [(60, 0, third), (62, third, third), (64, round(2 / 3, 6), third), (65, 1, 0.5)],
        )

    def test_tie(self):
        self.assertEqual(tune("C2-C2 D"), [(60, 0, 4), (62, 4, 1)])

    def test_tie_carries_accidental_across_bar(self):
        self.assertEqual(tune("^F2-|F2 F"), [(66, 0, 4), (65, 4, 1)])


class StructureTests(unittest.TestCase):
    def test_chord(self):
        self.assertEqual(tune("[CEG]2 c"), [(60, 0, 2), (64, 0, 2), (67, 0, 2), (72, 2, 1)])

    def test_tied_chord(self):
        self.assertEqual(tune("[CE]-[CE] G"), [(60, 0, 2), (64, 0, 2), (67, 2, 1)])

    def test_simple_repeat(self):
        self.assertEqual(
            tune("|: C D :| E"),
            [(60, 0, 1), (62, 1, 1), (60, 2, 1), (62, 3, 1), (64, 4, 1)],
        )

    def test_numbered_endings(self):
        self.assertEqual(
            tune("|: C |1 D :|2 E |]"),
            [(60, 0, 1), (62, 1, 1), (60, 2, 1), (64, 3, 1)],
        )

    def test_repeat_without_start_sign(self):
        self.assertEqual(
            tune("C :| D :|"),
            [(60, 0, 1), (60, 1, 1), (62, 2, 1), (62, 3, 1)],
        )

    def test_voices_start_together(self):
        self.assertEqual(tune("V:1\nc2\nV:2\nC,2"), [(48, 0, 2), (72, 0, 2)])

    def test_chord_symbols_written_out_as_a_bass_voice(self):
        # The midishare site copies "Dm" "Bb" "C" "A" as real notes in V:2, the
        # 48 notes its piano roll shows (abcjs's accompaniment, snapped to 16ths).
        notes = tune(
            "V:1\n"
            "D2 F2 A2 d2 | B,2 D2 F2 B2 | C2 E2 G2 c2 | A,2 _D2 E2 A2 |]\n"
            "V:2 clef=bass\n"
            "D,, z [D,F,A,] z A,,, z [D,F,A,] z | B,,, z [B,,D,F,] z F,,, z [B,,D,F,] z | "
            "C,, z [C,E,G,] z G,,, z [C,E,G,] z | A,,, z [A,,_D,E,] z E,,, z [A,,D,E,] z |]",
            header="M:4/4\nL:1/8\nK:Dm",
        )
        melody = [62, 65, 69, 74, 58, 62, 65, 70, 60, 64, 67, 72, 57, 61, 64, 69]
        expected = [(pitch, beat, 1) for beat, pitch in enumerate(melody)]
        # Per bar: root, chord, fifth, chord, each an eighth. The last bar's
        # plain D, is still Db from the _D, earlier in that bar.
        bass = [
            (38, [50, 53, 57], 33),  # Dm
            (34, [46, 50, 53], 29),  # Bb
            (36, [48, 52, 55], 31),  # C
            (33, [45, 49, 52], 28),  # A
        ]
        for bar, (root, chord, fifth) in enumerate(bass):
            beat = 4 * bar
            expected.append((root, beat, 0.5))
            expected.extend((pitch, beat + 1, 0.5) for pitch in chord)
            expected.append((fifth, beat + 2, 0.5))
            expected.extend((pitch, beat + 3, 0.5) for pitch in chord)
        self.assertEqual(len(notes), 48)
        self.assertEqual(sorted(notes), sorted(expected))

    def test_inline_fields(self):
        self.assertEqual(tune("C [K:D] F [L:1/8] C"), [(60, 0, 1), (66, 1, 1), (61, 2, 0.5)])

    def test_overlay(self):
        self.assertEqual(
            tune("C4 & E E E E | G"),
            [(60, 0, 4), (64, 0, 1), (64, 1, 1), (64, 2, 1), (64, 3, 1), (67, 4, 1)],
        )

    def test_annotations_decorations_and_grace_notes_ignored(self):
        self.assertEqual(
            tune('"^lively"!f!.A ~B {g}c'),
            [(69, 0, 1), (71, 1, 1), (72, 2, 1)],
        )


def _as_roll(notes):
    """One note per pitch and start, the longest, as the midishare piano roll shows them."""
    longest = {}
    for pitch, start, duration in notes:
        slot = (pitch, round(start, 4))
        longest[slot] = max(longest.get(slot, 0), round(duration, 4))
    return sorted((pitch, start, duration) for (pitch, start), duration in longest.items())


class ChordSymbolTests(unittest.TestCase):
    def test_matches_abcjs(self):
        # Every track abcjs 6.7.2 plays for 40 tunes, accompaniment included,
        # made by tests/fixtures/gen_abcjs_chords.ts.
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "abcjs_chords.json")
        with open(path, encoding="utf-8") as f:
            cases = json.load(f)
        self.assertEqual(len(cases), 40)
        for case in cases:
            with self.subTest(case["name"]):
                abcjs = [(n["pitch"], n["start"], n["duration"]) for track in case["tracks"] for n in track]
                self.assertEqual(_as_roll(parse(case["abc"])), _as_roll(abcjs))

    def test_accompaniment(self):
        # 4/4 plays boom . chick . boom . chick . in eighths; the second boom is a fourth below.
        self.assertEqual(
            tune('"G"z8 |]', header="M:4/4\nL:1/8\nK:C"),
            [(43, 0, 0.5), (55, 1, 0.5), (59, 1, 0.5), (62, 1, 0.5),
             (38, 2, 0.5), (55, 3, 0.5), (59, 3, 0.5), (62, 3, 0.5)],
        )

    def test_off_ignores_chord_symbols(self):
        notes = abc_serde.parse_abc('X:1\nM:4/4\nL:1/8\nK:Dm\n"Dm"D2 F2 A2 d2 |]', chords="off")
        self.assertEqual([n["pitch"] for n in notes], [62, 65, 69, 74])

    def test_unknown_mode_is_an_error(self):
        with self.assertRaises(ValueError):
            abc_serde.parse_abc("X:1\nK:C\nC", chords="block")

    def test_same_pitch_and_start_keeps_the_longer(self):
        # The C bass (MIDI 36) on beat 0 lands on the melody's C,, and merges into it.
        notes = tune('"C"C,,8 |]', header="M:4/4\nL:1/8\nK:C")
        self.assertIn((36, 0, 4), notes)
        self.assertNotIn((36, 0, 0.5), notes)


class ExtractionTests(unittest.TestCase):
    def test_detection(self):
        self.assertTrue(abc_serde.looks_like_abc("X:1\nK:C\nCDE"))
        self.assertFalse(abc_serde.looks_like_abc("notes:\n  C3 0 1\n  E3 0 1"))

    def test_prose_and_code_fence_around_tune(self):
        text = (
            "Here is a tune:\n\n```abc\nX:1\nT:Climb\nM:4/4\nL:1/4\nK:C\n"
            "C D E F|\n```\n\nThis melody climbs stepwise."
        )
        self.assertEqual(parse(text), [(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 3, 1)])

    def test_trailing_prose_without_fence(self):
        self.assertEqual(parse("X:1\nL:1/4\nK:C\nC D\nEnjoy the tune!"), [(60, 0, 1), (62, 1, 1)])

    def test_only_first_tune(self):
        self.assertEqual(parse("X:1\nL:1/4\nK:C\nC\n\nX:2\nL:1/4\nK:C\nD"), [(60, 0, 1)])

    def test_full_tune(self):
        text = (
            "X:1\nT:Speed the Plough\nM:4/4\nL:1/8\nK:G\n"
            "|:GABc dedB|dedB dedB|c2ec B2dB|c2A2 A2BA|\n"
            "GABc dedB|dedB dedB|c2ec B2dB|A2F2 G4:|\n"
        )
        notes = parse(text)
        self.assertEqual(len(notes), 2 * 52)
        self.assertEqual(notes[-1], (67, 62, 2))
        self.assertIn(66, {pitch for pitch, _, _ in notes})


class WriterTests(unittest.TestCase):
    def test_header_and_melody(self):
        self.assertEqual(
            write([(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 3, 1)],
                  tempo=120.0, time_sig="4/4", clip_name="Riff"),
            "X:1\nT:Riff\nM:4/4\nL:1/8\nQ:1/4=120\nK:C\nC2 D2 E2 F2 |]",
        )

    def test_key_signature_is_guessed(self):
        scale = [(p, i, 1) for i, p in enumerate((64, 66, 68, 69, 71, 73, 75, 76))]
        text = write(scale)
        self.assertIn("\nK:E\n", text)
        self.assertEqual(body(text), "E2 F2 G2 A2 | B2 c2 d2 e2 |]")
        self.assertEqual(parse(text), [(p, s, d) for p, s, d in scale])

    def test_key_comes_from_song_scale(self):
        notes = [(60, 0, 1), (62, 1, 1), (64, 2, 1), (65, 3, 1)]
        text = write(notes, root_note=9, scale_name="Minor")
        self.assertIn("\nK:Am\n", text)
        self.assertEqual(body(text), "C2 D2 E2 F2 |]")

    def test_song_key_sets_accidentals(self):
        scale = [(p, i, 1) for i, p in enumerate((69, 71, 72, 74, 76, 77, 80, 81))]
        text = write(scale, root_note=9, scale_name="Harmonic Minor")
        self.assertIn("\nK:Am\n", text)
        self.assertEqual(body(text), "A2 B2 c2 d2 | e2 f2 ^g2 a2 |]")
        self.assertEqual(parse(text), scale)

    def test_song_key_names(self):
        for root, scale, name in (
            (1, "Major", "Db"), (6, "Major", "F#"), (2, "Dorian", "Ddor"),
            (10, "Minor", "Bbm"), (8, "Minor", "G#m"), (7, "Mixolydian", "Gmix"),
            (11, "Locrian", "Bloc"), (5, "Lydian", "Flyd"), (4, "Phrygian", "Ephr"),
        ):
            self.assertIn("\nK:{}\n".format(name), write([(60, 0, 1)], root_note=root, scale_name=scale))

    def test_scale_without_key_signature_falls_back_to_guess(self):
        scale = [(p, i, 1) for i, p in enumerate((64, 66, 68, 69, 71, 73, 75, 76))]
        self.assertIn("\nK:E\n", write(scale, root_note=0, scale_name="Whole Tone"))

    def test_flat_key(self):
        text = write([(65, 0, 1), (67, 1, 1), (69, 2, 1), (70, 3, 1)])
        self.assertIn("\nK:F\n", text)
        self.assertEqual(body(text), "F2 G2 A2 B2 |]")

    def test_bar_scoped_accidentals(self):
        notes = [(60, 0, 1), (61, 1, 1), (60, 2, 1), (62, 3, 1)]
        self.assertEqual(body(write(notes)), "C2 ^C2 =C2 D2 |]")
        self.assertEqual(parse(write(notes)), notes)

    def test_tie_across_bar(self):
        text = write([(60, 3, 2)])
        self.assertEqual(body(text), "z6 C2- | C2 z6 |]")
        self.assertEqual(parse(text), [(60, 3, 2)])

    def test_different_lengths_split_into_voices(self):
        notes = [(48, 0, 2), (72, 0, 1), (74, 1, 1)]
        text = write(notes)
        self.assertEqual(body(text), "V:1\nc2 d2 z4 |]\nV:2\nC,4 z4 |]")
        self.assertEqual(parse(text), [(48, 0, 2), (72, 0, 1), (74, 1, 1)])

    def test_chord(self):
        self.assertEqual(body(write([(60, 0, 2), (64, 0, 2), (67, 0, 2)])), "[CEG]4 z4 |]")

    def test_leading_empty_bars_become_multi_measure_rest(self):
        text = write([(60, 8, 1)])
        self.assertEqual(body(text), "Z2 | C2 z6 |]")
        self.assertEqual(parse(text), [(60, 8, 1)])

    def test_timing_is_quantized(self):
        self.assertEqual(parse(write([(60, 0.02, 0.47291666)])), [(60, 0, 0.5)])

    def test_notes_before_clip_start_shift_to_bar_line(self):
        self.assertEqual(parse(write([(60, -1, 1), (62, 0, 1)])), [(60, 3, 1), (62, 4, 1)])

    def test_triplets(self):
        third = 1 / 3
        notes = [(60, 0, third), (62, third, third), (64, 2 * third, third)]
        self.assertEqual(body(write(notes)), "C2/3 D2/3 E2/3 z6 |]")
        self.assertEqual(len(parse(write(notes))), 3)

    def test_muted_notes_are_skipped(self):
        notes = [_Note(60, 0, 1), _Note(62, 1, 1, mute=True), _Note(64, 2, 1)]
        text = abc_serde.serialize_abc(notes)
        self.assertEqual(body(text), "C2 z2 E2 z2 |]")
        self.assertEqual(parse(text), [(60, 0, 1), (64, 2, 1)])

    def test_muted_notes_do_not_set_the_key(self):
        notes = [_Note(60, 0, 1)] + [_Note(66, i, 1, mute=True) for i in range(1, 4)]
        self.assertIn("\nK:C\n", abc_serde.serialize_abc(notes))

    def test_nothing_to_write_returns_none(self):
        self.assertIsNone(abc_serde.serialize_abc([]))
        self.assertIsNone(abc_serde.serialize_abc([_Note(60, 0, 1, mute=True)]))

    def test_random_round_trip(self):
        rng = random.Random(7)
        for meter in ("4/4", "3/4", "6/8", "5/4"):
            notes = {}
            for _ in range(60):
                step = rng.choice((Fraction(1, 4), Fraction(1, 3), Fraction(1, 2)))
                start = rng.randrange(64) * step
                notes[(rng.randint(30, 100), start)] = rng.randint(1, 8) * step
            expected = sorted(
                (p, round(float(s), 6), round(float(d), 6)) for (p, s), d in notes.items()
            )
            text = write([(p, float(s), float(d)) for (p, s), d in notes.items()], time_sig=meter)
            self.assertEqual(sorted(parse(text)), expected, meter)


if __name__ == "__main__":
    unittest.main()
