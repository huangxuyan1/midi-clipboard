# midi-clipboard wire format — grammar

A context-free grammar (EBNF, ISO-14977-flavoured) for the text written to
and read from the OS clipboard by the `midi-clipboard` remote script.

This grammar defines what a **canonical** payload looks like. The parser
is intentionally more permissive than the grammar (see
[Tolerance](#tolerance) at the bottom) so that prose, headers, and
unexpected lines around the data are silently skipped.

---

## Grammar

```ebnf
(* ============ Top level ============ *)

payload         = meta_block? notes_block ;

(* ============ Meta block (optional, informational) ============ *)

meta_block      = "meta:" NL { meta_line | blank_line | comment_line } ;
meta_line       = INDENT meta_entry NL ;
meta_entry      = identifier "=" meta_value ;
meta_value      = quoted_string | bare_token ;

(* ============ Notes block ============ *)

notes_block     = "notes:" header_defaults? NL
                  { note_line | column_header | blank_line | comment_line } ;

header_defaults = "(" param ( "," WS? param )* ")" ;
param           = "dur" "=" number ;          (* future params reserved *)

column_header   = INDENT "note" WS "start" WS "dur" WS "..." NL ;
note_line       = INDENT note_spec NL ;

(* ============ Note specification ============ *)

note_spec       = pitch_spec WS start_time ( WS duration )? { WS attr } ;

pitch_spec      = chord_bracket | pitch ;
chord_bracket   = "[" pitch ( WS pitch )+ "]" ;     (* 2 or more pitches *)

pitch           = note_name | midi_int ;
note_name       = letter accidental? octave ;
letter          = "A" | "B" | "C" | "D" | "E" | "F" | "G"
                | "a" | "b" | "c" | "d" | "e" | "f" | "g" ;
accidental      = "#" | "b" | "B" ;                  (* B == flat alias *)
octave          = "-"? digit+ ;                      (* C-2 .. G8 *)
midi_int        = digit+ ;                           (* 0..127 *)

start_time      = number ;                           (* beats from clip start *)
duration        = number ;                           (* beats; optional when header_defaults sets dur *)

attr            = attr_key "=" attr_value ;
attr_key        = "vel" | "mute" | "prob" | "vdev" | "rvel" ;
attr_value      = boolean | number ;
boolean         = "True" | "False" ;

(* ============ Lexical ============ *)

quoted_string   = '"' ( escaped | not_quote_or_backslash )* '"' ;
escaped         = "\\" ( '"' | "\\" ) ;
not_quote_or_backslash = ? any character other than '"' or '\\' ? ;
bare_token      = ( ? any character that is not whitespace or NL ? )+ ;

identifier      = ( letter_lc | "_" ) ( letter_lc | digit | "_" )* ;
letter_lc       = "a" | "b" | "c" | ... | "z" | "A" | "B" | ... | "Z" ;
number          = "-"? digit+ ( "." digit+ )? ;
digit           = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

blank_line      = WS* NL ;
comment_line    = WS* "#" ( ? any character other than NL ? )* NL ;

INDENT          = WS+ ;
WS              = " " | "\t" ;
NL              = "\n" | "\r\n" ;
```

---

## Semantics

What the grammar can't say directly:

### Chord bracket expansion

`[p1 p2 … pN] s d attr*` denotes **N notes**, one per listed pitch, each
with start `s`, duration `d`, and the same attribute list. Bracket lines
are pure shorthand — `[C3 E3 G3] 0 1 vel=90` is identical in meaning to
three separate lines `C3 0 1 vel=90`, `E3 0 1 vel=90`, `G3 0 1 vel=90`.

Brackets are only emitted when all of `start`, `duration`, and every
optional attribute coincide for the grouped notes. Any difference
demotes the offending note to its own line.

### Header defaults

`notes:(dur=X)` sets the default duration for any `note_line` in that block
that omits its `duration` token. Per-line durations always override.
Only `dur` is defined today; the production is open for future keys.

### Optional-attribute defaults (when absent from the line)

| `attr_key` | Default | Range |
|---|---|---|
| `vel`   | `100`  | int 0–127 |
| `mute`  | `False`| `True` / `False` |
| `prob`  | `1.0`  | float 0–1 |
| `vdev`  | `0`    | int |
| `rvel`  | `64`   | int 0–127 |

Writers omit attributes that match the default; readers apply the default
when the attribute is absent.

### Pitch convention

`note_name` follows **Ableton's** octave numbering: `C3` is middle C, i.e.
MIDI 60. Computation:

```
midi = (octave + 2) * 12 + semitone_offset
semitone_offset(C..B) = 0, 2, 4, 5, 7, 9, 11
# accidental: +1, b/B accidental: -1
```

Both `F#4` and `Gb4` are accepted on read and resolve to MIDI 78.
On write, sharps are emitted.

### Sort order on write

A canonical writer sorts notes by `(start, lowest_pitch_in_group)`
ascending. Readers must not rely on order — chords and lines may appear
in any sequence.

### Numeric formatting on write

A canonical writer drops trailing `.0` (so `1.0` is emitted as `1`, but
`0.5` stays `0.5`). Both forms are accepted on read.

---

## Tolerance

The parser accepts **strict supersets** of the grammar:

1. **The whole `notes:` / `meta:` headers may be omitted.** A bare list of
   note lines parses successfully.
2. **Any line whose first three whitespace-separated tokens fail to parse
   as `pitch_spec`, `start_time`, `duration` is silently skipped.** This
   covers prose around the block, the column header line, an unknown
   header, and accidental garbage.
3. **Unknown `attr_key`s are ignored**, not rejected.
4. **Unknown `meta_entry` keys are ignored.** Meta is read-only context;
   the script never applies it on paste.
5. **Trailing whitespace, mixed indent widths, and either LF or CRLF
   line endings** are accepted.

This combination means the format round-trips cleanly *and* survives a
broad spectrum of LLM-generated text that wraps the block in
explanation.

---

## Example

A canonical payload exercising every production:

```text
meta:
  tempo=120
  time_sig=4/4
  clip_length=4
  clip_name="C# Min Verse"

notes:(dur=0.5)
  note start dur ...
  [A2 C#3 E3] 0 vel=90
  C#4 0 vel=127
  [A2 C#3 E3] 0.5 vel=90
  G#4 0.5 1 vel=127
  # melody breath
  A2 1 4 vel=80
```

Parses to nine `MidiNoteSpecification` objects: three `A2/C#3/E3` notes at
beat 0 sharing `dur=0.5 vel=90`, a `C#4` melody note at beat 0
(`dur=0.5 vel=127`), three more `A2/C#3/E3` at beat 0.5, a `G#4` at 0.5
with explicit duration 1 (overriding the header default) and `vel=127`,
and a sustained `A2` from beat 1 lasting 4 beats at `vel=80`.
