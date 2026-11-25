// Regenerates abcjs_chords.json. Run from a project that has abcjs 6.7.2
// installed, e.g. with tsx: npx tsx gen_abcjs_chords.ts abcjs_chords.json
import abcjs from 'abcjs'
import { writeFileSync } from 'node:fs'

const H = (m: string, k = 'C', l = '1/8') => `X:1\nM:${m}\nL:${l}\nK:${k}\n`
const cases: [string, string][] = [
  ['example_4_4_Dm', `X:1\nT:Example\nM:4/4\nL:1/8\nQ:1/4=90\nK:Dm\n"Dm"D2 F2 A2 d2 | "Bb"B,2 D2 F2 B2 | "C"C2 E2 G2 c2 | "A"A,2 ^C2 E2 A2 |]`],
  ['waltz_3_4', H('3/4', 'G') + `"G"B2 d2 g2 | "D7"A2 c2 f2 | "Em"G6 | "C"e4 "D"d2 |]`],
  ['jig_6_8', H('6/8', 'D') + `"D"A2A AFA | "G"B2B BGB | "A7"c2c cde | "D"d3 d3 |]`],
  ['polka_2_4', H('2/4', 'G') + `"G"GA Bc | "D"d2 d2 | "C"ec "G"dB | "D7"A4 |]`],
  ['cut_time', H('C|', 'A') + `"A"A4 c4 | "E"B4 e4 | "D"d2 f2 "A"e2 c2 | "E7"B8 |]`],
  ['common_time_C', H('C', 'F') + `"F"F2 A2 c2 f2 | "Bb"d2 B2 "C7"c2 e2 |]`],
  ['slip_jig_9_8', H('9/8', 'G') + `"G"B2B BAG AGE | "Am"A2A ABc "D"d2A |]`],
  ['five_four', H('5/4', 'C') + `"C"C2 E2 G2 c2 e2 | "F"F2 A2 "G"G2 B2 d2 |]`],
  ['seven_eight', H('7/8', 'D') + `"D"D2D F2 A2 | "A"A2A c2 e2 |]`],
  ['twelve_eight', H('12/8', 'Am') + `"Am"A3 c3 e3 a3 | "E7"e3 ^g3 b3 e3 |]`],
  ['three_eight', H('3/8', 'C') + `"C"CEG | "G7"GBd |]`],
  ['unknown_meter_3_2', H('3/2', 'C') + `"C"C4 E4 G4 | "G"G4 B4 d4 |]`],
  ['chord_types', H('4/4') + `"C"C8 | "Cm"C8 | "C7"C8 | "Cmaj7"C8 | "Cm7"C8 | "Cdim"C8 | "Csus4"C8 | "C6"C8 | "Caug"C8 | "C9"C8 | "Cm7b5"C8 | "Cadd9"C8 |]`],
  ['unknown_type_is_major', H('4/4') + `"Cfoo"C8 | "Gmystery"G8 |]`],
  ['accidental_roots', H('4/4') + `"Bb"B,8 | "F#m"F8 | "Eb7"E8 | "C#dim"C8 | "Ab"A,8 | "G#m"G8 |]`],
  ['slash_bass', H('4/4') + `"D/F#"D8 | "C/E"C8 | "G/B"G8 | "Am/G"A8 | "F/Bb"F8 |]`],
  ['two_chords_per_bar', H('4/4', 'G') + `"G"G2 B2 "C"c2 e2 | "D"d2 f2 "G"g4 |]`],
  ['four_chords_per_bar', H('4/4') + `"C"C2 "F"F2 "G"G2 "Am"A2 |]`],
  ['chord_on_beat_two', H('4/4') + `C2 "F"F2 A2 c2 | "G"G8 |]`],
  ['chord_off_the_beat', H('4/4') + `"C"C3 "G"G E2 G2 | "F"F "Am"A6 A |]`],
  ['chord_carries_over_bars', H('4/4') + `"Am"A8 | c8 | e8 | "E"e8 |]`],
  ['no_chord_in_first_bars', H('4/4') + `C8 | E8 | "G"G8 | B8 |]`],
  ['pickup_bar', H('4/4', 'G') + `D2 | "G"G2 B2 d2 g2 | "D"f2 d2 A2 F2 |]`],
  ['pickup_bar_with_chord', H('3/4', 'G') + `"D7"D2 | "G"G2 B2 d2 | "C"e2 c2 G2 |]`],
  ['short_last_bar', H('4/4') + `"C"C2 E2 G2 c2 | "G"G4 |]`],
  ['no_chord_marks', H('4/4') + `"C"C8 | "N.C."z8 | "G"G8 | "break"z8 | "C"C8 |]`],
  ['chord_on_rest', H('4/4') + `"C"z8 | "F"z4 "G"z4 |]`],
  ['annotations_are_not_chords', H('4/4') + `"^above"C4 "_below"E4 | "<left"G4 "C"c4 |]`],
  ['parenthesised_chord', H('4/4') + `"(Am)"A8 | "(D7)"d8 |]`],
  ['repeats', H('4/4', 'G') + `|: "G"G4 B4 | "D"d8 :| "C"c8 |]`],
  ['first_second_endings', H('4/4', 'G') + `|: "G"G8 |1 "D"d8 :|2 "C"c8 |]`],
  ['unit_length_sixteenth', H('4/4', 'C', '1/16') + `"C"C4 E4 G4 c4 | "F"F8 "G"G8 |]`],
  ['unit_length_quarter', H('4/4', 'C', '1/4') + `"C"C E G c | "F"F2 "G"G2 |]`],
  ['two_voices_chords_in_first', H('4/4') + `V:1\n"C"c4 e4 | "G"d8 |]\nV:2\nC,8 | G,,8 |]`],
  ['two_voices_chords_in_second', H('4/4') + `V:1\nc4 e4 | d8 |]\nV:2\n"C"C,8 | "G"G,,8 |]`],
  ['meter_change', H('4/4') + `"C"C8 | [M:3/4] "F"F6 | "G"G6 | [M:4/4] "C"c8 |]`],
  ['tied_melody_under_chords', H('4/4') + `"C"c8- | "F"c8- | "G"c4 d4 |]`],
  ['triplet_melody', H('4/4') + `"C"(3cde (3fga "G"g4 | "C"c8 |]`],
  ['gchord_override', H('4/4') + `%%MIDI gchord fzczfzcz\n"C"C8 | "G"G8 |]`],
  ['gchord_arpeggio', H('4/4') + `%%MIDI gchord GHIHGHIH\n"C"C8 | "Am"A8 |]`],
]

const beats = (whole: number) => Math.round(whole * 4 * 1e6) / 1e6
const out: any[] = []
for (const [name, abc] of cases) {
  const [tune] = abcjs.parseOnly(abc)
  const audio = (tune as any).setUpAudio({})
  const tracks = audio.tracks.map((track: any[]) =>
    track.filter((e) => e.cmd === 'note').map((e) => ({ pitch: e.pitch, start: beats(e.start), duration: beats(e.duration), volume: e.volume })))
  // abcjs puts the accompaniment in one extra track after the voices; its notes have no "gap"-shortened melody shape.
  const chordIndex = audio.tracks.findIndex((track: any[]) => track.some((e) => e.cmd === 'note' && (e.volume === 64 || e.volume === 48) && e.instrument !== undefined && e.gap === 0 && e.duration === e.duration) && track[0]?.cmd === 'program' && track[0].channel === audio.tracks.length - 1)
  out.push({ name, abc, total_beats: beats(audio.totalDuration), chord_track: chordIndex, tracks })
}
writeFileSync(process.argv[2], JSON.stringify(out, null, 1))
for (const c of out) console.log(c.name.padEnd(32), 'tracks', c.tracks.map((t: any[]) => t.length).join('+'), 'chord track', c.chord_track)
