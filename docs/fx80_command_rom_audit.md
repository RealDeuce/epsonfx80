# FX-80 command ROM audit

This is the current verification ledger for the Dreamulator FX-80 path. It is
not a history log: it describes the current expected emulator behavior and the
current evidence behind it.

Status meanings:

* `ROM verified`: the command behavior was traced in the Version 2.00 FX-80
  firmware disassembly and the important addresses are listed here.
* `ROM partial`: ROM tables or helper paths are identified, but the full command
  handler has not been walked end to end.
* `ROM dispatch`: the command byte is tied to a firmware dispatch-table entry,
  but the handler body has not yet been fully interpreted.
* `Manual`: implemented from the FX-80 command documentation summarized in
  `fx80_emulator_notes.md`; the ROM handler is not yet identified here.
* `Approx`: current Dreamulator behavior is intentionally approximate because
  the PDF renderer has no real print buffer, timing, or parallel-port status
  model.
* `Gap`: documented behavior is known, but current Dreamulator behavior is
  incomplete or unverified enough to need emulator work.

## ROM anchors already identified

| Area | ROM evidence | Notes |
| --- | --- | --- |
| ROM glyph data | Table range `0x17A3..0x23A2`, 12 bytes per character, 256 entries | Byte 0 is the prefix/attribute byte; bytes 1-11 are inverted column data. The high half begins at `0x1DA3`, which is the `0x17A3 + 128 * 12` italic/control-alias region. |
| `ESC *` mode dispatch | `0x3371..0x339A` | Reads mode byte, masks with `0x7F`, compares against `0..7`, jumps to one of eight setup entries. |
| Graphics width reader | `0x33B5..0x33D9` | Consumes `n1,n2`, stores count at `$8053`, skip-returns when count is nonzero. |
| Graphics mode setup entries | `0x33DA`, `0x33FA`, `0x341C`, `0x343E`, `0x3464`, `0x348A`, `0x34B4`, `0x34D8` | These correspond to `ESC *` modes `0..7`. |
| Graphics phase table copy | `0x350E..0x351C` | Copies per-mode phase/timing table data to RAM at `$8032` until a zero word. |
| Common 8-pin graphics engine | `0x3727` | Shared output path after the per-mode setup. |
| `ESC ?` reassignment | `0x38CD..0x38FE`, pointer table at `0x38FF..0x390E` | Accepts `K`, `L`, `Y`, `Z`; accepts target modes `< 8`; patches the corresponding vector at `$9739..$973F`. |
| On/off parameter helper | `0x0A6F..0x0A8A` | Consumes one byte and returns to one of three consecutive caller branches: on, off, or invalid. Used by underline, script, direction, expanded, proportional, half-speed, immediate print, and related toggles. |
| Text-mode priority resolver | `0x3AF0..0x3B34` | Recomputes effective mode flags from raw mode bits. Effective priority is Elite over Proportional over Emphasized over Compressed over Pica; Proportional forces effective Emphasized; Script forces the double-strike/script pass. Lower-priority raw bits are masked, not cleared. |
| International remap table | `0x0AF7..0x0B7A`, helper at `0x0AC8..0x0AF6` | The table is data, not code. The helper maps selected printable characters through the active international set at `$804F`. |
| User character RAM helpers | `0x164C..0x166B`, `0x176E..0x1788` | Clears/initializes RAM glyph area and computes 12-byte ROM/RAM glyph entry addresses. |
| ROM-to-RAM glyph copy | `0x166C..0x16A0` | Dispatch-linked from `ESC :`; reads three parameters, proceeds only for `0,0,0`, then copies 256 12-byte entries from ROM table `0x17A3` to RAM glyph area. |
| Main command dispatch | `0x095E..0x09C4` | Dispatches low control codes through the triple table at `0x0970`; dispatches explicit ESC commands through the triple table at `0x09FD`; dispatches uppercase `ESC @..Z` through the compact table at `0x09C7`. |
| `ESC &` live handler | Dispatch table entry `0x09FD` maps byte `0x26` to `0x16E1`, which clears a state bit and unconditionally jumps to `0x2AD4`; raw byte search finds no pointer to `0x16E7`. | The live handler is not the 12-byte FX manual format. It matches the LQ-style `0,c1,c2,d0,d1,d2,data` shape with three data bytes per column. |
| 12-byte download-character parser | Code at `0x16E7..0x1752` reads `0,c1,c2`, computes 12-byte RAM glyph addresses through `0x1786`, and stores one transformed prefix byte plus 11 transformed column bytes. | This is adjacent to the dispatched `ESC &` stub, but the stub jumps over it. No dispatch-table entry, direct call, direct jump, raw little-endian pointer, or nearby relative branch to `0x16E7` was found. Treat it as unreachable in this ROM until a computed entry path is proven. |
| Three-plane glyph rendering | `0x2B60..0x2C98`, `0x2C99..0x2E41`, and `0x2E42..0x30D2` consume the `0x5A5A + code*0x41` records, compose scratch raster buffers at `0x472C..`, and call the existing graphics/text print engine setup. | The three bytes per column are logical glyph planes. They are not fired as 24 physical pins; the firmware converts/composes them into passes for the 9-pin mechanism. |

### `ESC &` format split

The public FX manuals and the Version 2.00 ROM-dispatched parser describe
incompatible byte streams:

| Format | Stream per command | Per-character payload | Storage/rendering implication |
| --- | --- | --- | --- |
| FX manual 12-byte format | `ESC & 0 c1 c2 [A d1..d11]...` | One attribute byte plus exactly 11 column bytes per character. Attribute bit 7 selects top/bottom 8 pins; bits 6-4 are proportional start column; bits 3-0 are proportional end column. | Matches the ROM glyph record format at `0x17A3..0x23A2` and the unreachable parser at `0x16E7..0x1752`. |
| LQ-style three-plane format | `ESC & 0 c1 c2 [d0 d1 d2 data...]...` | `d0` left space, `d1` body width, `d2` right space, then three data bytes per body column. The live handler clamps metric bytes around 20 and consumes `3 * d1` data bytes. | Matches the dispatch path `0x16E1 -> 0x2AD4`, which stores 65-byte records at `0x5A5A + code*0x41` and later composes the three logical planes into 9-pin print-engine passes. |

These formats are not stream-compatible. If manual FX data is sent to the
live Version 2.00 handler, the manual attribute byte is interpreted as `d0`,
the first column byte is interpreted as `d1`, and the command consumes a
different number of following bytes. If LQ-style data is sent to a 12-byte FX
parser, the three metric bytes become the attribute and first two columns, and
extra plane data remains in the input stream. This argues against "poor
documentation" as the general explanation: the FX manuals explicitly teach the
12-byte format, including examples, and the ROM still contains a matching
12-byte parser. The reachable LQ-style path is more likely a ROM-version,
late-shared-code, or model/dump-specific behavior than normal FX-series
behavior.

## Decoded dispatch tables

Low control dispatch table at `0x0970`, used by the parser around `0x095E`:

| Byte | Handler | Notes |
| --- | --- | --- |
| `BEL` `0x07` | `0x392B` | Beeper/status side effect path. |
| `BS` `0x08` | `0x0093` | Backspace/motion helper. |
| `HT` `0x09` | `0x3F01` | Horizontal tab path. |
| `LF` `0x0A` | `0x0FD2` | Line feed path. |
| `VT` `0x0B` | `0x11DC` | Vertical tab path. |
| `FF` `0x0C` | `0x1064` | Form feed path. |
| `CR` `0x0D` | `0x0087` | Carriage return path, with auto-LF path through `0x0FD2`. |
| `SO` `0x0E` | `0x3A2B` | Expanded-line enable. |
| `SI` `0x0F` | `0x3A12` | Condensed enable. |
| `DC2` `0x12` | `0x3A1D` | Condensed disable. |
| `DC3` `0x13` | `0x0B8E` | Select/deselect path; later loop at `0x0BAD` waits for `DC1`. |
| `DC4` `0x14` | `0x3A2F` | Expanded-line disable. |
| `CAN` `0x18` | `0x23FE` | Cancels buffered output state. |
| `ESC` `0x1B` | `0x099D` | ESC command parser entry. |

Explicit ESC dispatch table at `0x09FD`:

| Command | Handler | Command | Handler | Command | Handler |
| --- | --- | --- | --- | --- | --- |
| `ESC ?` | `0x38CD` | `ESC SO` | `0x3A2B` | `ESC SI` | `0x3A12` |
| `ESC EM` | `0x140D` | `ESC !` | `0x3A36` | `ESC #` | `0x0A8B` |
| `ESC :` | `0x166C` | `ESC %` | `0x16A7` | `ESC &` | `0x16E1` |
| `ESC *` | `0x3371` | `ESC -` | `0x3A52` | `ESC $` | `0x2A32` |
| `ESC \` | `0x2A66` | `ESC /` | `0x1186` | `ESC space` | `0x2A24` |
| `ESC 0` | `0x0FAE` | `ESC 1` | `0x0FB0` | `ESC 2` | `0x0FB2` |
| `ESC 3` | `0x0FB5` | `ESC 4` | `0x0AAC` | `ESC 5` | `0x0AB0` |
| `ESC 6` | `0x0BC7` | `ESC 7` | `0x0BCB` | `ESC 8` | `0x0E64` |
| `ESC 9` | `0x0E68` | `ESC <` | `0x266E` | `ESC >` | `0x0A8F` |
| `ESC =` | `0x0A93` | `ESC ^` | `0x351D` | `ESC a` | `0x2A92` |
| `ESC b` | `0x1170` | `ESC i` | `0x08B3` | `ESC j` | `0x1126` |
| `ESC k` | `0x2A14` | `ESC l` | `0x24B9` | `ESC p` | `0x3AD5` |
| `ESC s` | `0x2679` | `ESC x` | `0x29A7` |  |  |

Uppercase ESC compact table at `0x09C7`, indexed by `command - 0x40`:

| Command | Handler | Command | Handler | Command | Handler |
| --- | --- | --- | --- | --- | --- |
| `ESC @` | `0x078D` | `ESC A` | `0x0FBC` | `ESC B` | `0x1191` |
| `ESC C` | `0x1021` | `ESC D` | `0x3F60` | `ESC E` | `0x3A60` |
| `ESC F` | `0x3A6B` | `ESC G` | `0x3A79` | `ESC H` | `0x3A7D` |
| `ESC I` | `0x0BB9` | `ESC J` | `0x10C7` | `ESC K` | `0x390F` |
| `ESC L` | `0x3914` | `ESC M` | `0x3A84` | `ESC N` | `0x109A` |
| `ESC O` | `0x10C3` | `ESC P` | `0x3A8F` | `ESC Q` | `0x2486` |
| `ESC R` | `0x0ABE` | `ESC S` | `0x3A9D` | `ESC T` | `0x3AAF` |
| `ESC U` | `0x3AB3` | `ESC V` | `0x09BF` | `ESC W` | `0x3AC1` |
| `ESC X` | `0x09BF` | `ESC Y` | `0x3919` | `ESC Z` | `0x391E` |

## Command audit

| Command | Dreamulator current behavior | Manual source | ROM evidence | Status | Notes/divergence |
| --- | --- | --- | --- | --- | --- |
| `NUL` | Terminates tab-setting lists. | Notes `Control codes` | Not traced | Manual | Normal data `NUL` is otherwise ignored. |
| `BEL` | Not rendered or signaled. | Notes `Control codes` | Control dispatch `0x0970`: `0x07 -> 0x392B` | Approx | ROM dispatch exists, but PDF output has no beeper/status side effect. |
| `BS` | Moves left one current-pitch cell, clamped at left margin. | Notes `Control codes` | Control dispatch `0x0970`: `0x08 -> 0x0093` | ROM dispatch | Does not erase rendered dots. |
| `HT` | Moves to next configured horizontal tab. | Notes `Control codes`, tabs | Control dispatch `0x0970`: `0x09 -> 0x3F01` | ROM dispatch | Default tabs and `ESC D` tabs are modeled as physical positions fixed at the pitch/margin active when set. |
| `LF` | Advances by current line spacing; handles perf skip/form feed. | Notes `Control codes` | Control dispatch `0x0970`: `0x0A -> 0x0FD2` | ROM dispatch | Blank feeds do not consume one-line unidirectional state; exact line-direction side effects still need handler trace. |
| `VT` | Advances to next vertical tab in current channel, otherwise LF. | Notes `Control codes`, tabs | Control dispatch `0x0970`: `0x0B -> 0x11DC` | ROM dispatch | Vertical tab storage is modeled; exact top-of-form edge cases need ROM trace. |
| `FF` | Flushes current page and starts a new page. | Notes `Control codes` | Control dispatch `0x0970`: `0x0C -> 0x1064` | ROM dispatch | Logical top-of-form modeled as page break in PDF output. |
| `CR` | Returns to left margin; optional auto-LF; resolves bidirectional direction state. | Notes `Control codes`, direction notes | Control dispatch `0x0970`: `0x0D -> 0x0087` | ROM dispatch | Correctness around line direction is code-audited, not fully ROM-traced. |
| `SO` | Enables one-line expanded. | Notes `Control codes` | Control dispatch `0x0970`: `0x0E -> 0x3A2B`; explicit ESC table also maps `ESC SO -> 0x3A2B` | ROM dispatch | Canceled by line end, `DC4`, or `ESC W 0`. |
| `SI` | Enables condensed. | Notes `Control codes` | Control dispatch `0x0970`: `0x0F -> 0x3A12`; explicit ESC table also maps `ESC SI -> 0x3A12`; handler sets raw `$8001` bit `0x04` and calls resolver `0x3AF0` | ROM verified | Condensed is masked by active Elite, Proportional, or Emphasized rather than clearing those raw modes. |
| `DC1` | Selects/enables input. | Notes `Control codes`, parallel interface | `DC3` handler path at `0x0B8E` includes a later input loop at `0x0BAD` that waits for `0x11` | ROM partial | No standalone control-table entry; DIP gating and ACK/BUSY behavior are not modeled. |
| `DC2` | Cancels condensed. | Notes `Control codes` | Control dispatch `0x0970`: `0x12 -> 0x3A1D` | ROM dispatch |  |
| `DC3` | Deselects input until `DC1`. | Notes `Control codes`, parallel interface | Control dispatch `0x0970`: `0x13 -> 0x0B8E` | ROM partial | Handler interacts with hardware input/status; ACK/BUSY and DIP gating are not modeled. |
| `DC4` | Cancels one-line expanded only. | Notes `Control codes` | Control dispatch `0x0970`: `0x14 -> 0x3A2F` | ROM dispatch | Does not cancel continuous `ESC W 1`. |
| `CAN` | Cancels pending buffered text, returns X to left margin, and clears line-direction bookkeeping. | Notes `Control codes` | Control dispatch `0x0970`: `0x18 -> 0x23FE` | ROM dispatch | Dreamulator now has a logical pending-line buffer, so CAN discards unprinted text instead of trying to erase rendered dots. |
| `DEL` | Deletes the most recent pending text character in the current line buffer. | Notes `Control codes` | Not traced | Manual | Dreamulator now removes the most recent logical buffered text character before rendering. If no text is pending, it has no visible effect. |
| `ESC ! n` | FX Master Select applies bits `0x01`, `0x04`, `0x08`, `0x10`, and `0x20`; FX ignores LQ proportional/italic bits `0x02`/`0x40` and does not apply parameter bit `0x80`. | Notes `Master Select` | Explicit ESC dispatch `0x09FD`: `0x21 -> 0x3A36`; handler reads `n`, clears raw low mode bits with `$8001 &= 0xC0`, handles Expanded through `0x3AC7/0x3ACE`, stores `n & 0x3D`, then calls resolver `0x3AF0` | ROM verified | The mask proves LQ proportional/italic bits are model-specific and ignored on this FX ROM. |
| `ESC #` | Accepts eighth bit as sent. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x23 -> 0x0A8B`; handler clears `$8003` bit `0x01` | ROM verified | This is the neutral high-bit mode. The ESC parser masks command bytes to 7-bit before dispatch, so this primarily controls normal data/control alias handling. |
| `ESC % n1 n2` | FX selects ROM for `0,0`, user RAM for `1,0`. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x25 -> 0x16A7`, which jumps to `0x29F4` | ROM dispatch | DIP 1-4 gating is not modeled. |
| `ESC & 0 c1 c2 ...` | FX path currently implements the manual 12-byte format: one prefix byte and 11 data bytes per char. | Notes `ROM glyph table`, `Escape commands`; LQ comparison `../lq500/data/lq500_commands.json` | Explicit ESC dispatch `0x09FD`: `0x26 -> 0x16E1 -> 0x2AD4`; live handler reads `0,c1,c2,d0,d1,d2,data`, allocates 65 bytes per character at `0x5A5A + code*0x41`, and consumes `3 * width` data bytes. The 12-byte parser at `0x16E7..0x1752` is adjacent to the stub but not reached by the known dispatch path. | Gap | Manual and live ROM disagree. Current Dreamulator follows the FX manuals, not this ROM path. Two parser forms are plausible historically, but only the LQ-style parser is reachable in this Version 2.00 ROM by the known command dispatcher. |
| `ESC * m n1 n2 data` | Variable-density 8-pin graphics, modes `0..7`, fixed byte quota. | Notes `Graphics modes` | `0x3371..0x339A`, setup entries `0x33DA..0x34D8`, width reader `0x33B5` | ROM verified | Mode 7 is ROM-supported 144 dpi. Modes 2/3 suppress adjacent same-row dots. |
| `ESC - n` | Underline off/on from low bit. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x2D -> 0x3A52` | ROM dispatch |  |
| `ESC / n` | Selects vertical tab channel `(n & 0x7F)` when it is `< 8`. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x2F -> 0x1186`; handler masks high bit and stores `$8051` only for values `0..7` | ROM verified | Values whose low 7 bits are `8..127` are ignored. |
| `ESC 0` | Sets 1/8 inch line spacing. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x30 -> 0x0FAE` | ROM dispatch |  |
| `ESC 1` | Sets 7/72 inch line spacing. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x31 -> 0x0FB0` | ROM dispatch |  |
| `ESC 2` | Sets 1/6 inch line spacing. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x32 -> 0x0FB2` | ROM dispatch |  |
| `ESC 3 n` | Sets `n/216` inch line spacing. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x33 -> 0x0FB5` | ROM dispatch |  |
| `ESC 4` | Selects italic glyph rendering. | Notes `Character sets and fonts` | Explicit ESC dispatch `0x09FD`: `0x34 -> 0x0AAC`; handler sets `$805B` bit `0x10`; high glyph half begins at `0x1DA3` | ROM verified |  |
| `ESC 5` | Selects roman glyph rendering. | Notes `Character sets and fonts` | Explicit ESC dispatch `0x09FD`: `0x35 -> 0x0AB0`; handler clears `$805B` bit `0x10`; roman glyph table begins at `0x17A3` | ROM verified |  |
| `ESC 6` | Makes 128-159 and 255 printable. | Notes `Character sets and fonts` | Explicit ESC dispatch `0x09FD`: `0x36 -> 0x0BC7` | ROM dispatch |  |
| `ESC 7` | Restores 128-159 and 255 as controls. | Notes `Character sets and fonts` | Explicit ESC dispatch `0x09FD`: `0x37 -> 0x0BCB` | ROM dispatch |  |
| `ESC 8` | Consumed. | Notes `Escape commands`, parallel interface | Explicit ESC dispatch `0x09FD`: `0x38 -> 0x0E64` | Approx | ROM dispatch exists, but paper-out sensor/parallel status is not modeled in PDF output. |
| `ESC 9` | Consumed. | Notes `Escape commands`, parallel interface | Explicit ESC dispatch `0x09FD`: `0x39 -> 0x0E68` | Approx | ROM dispatch exists, but paper-out sensor/parallel status is not modeled in PDF output. |
| `ESC : 0 0 0` | FX copies ROM glyphs to user-char RAM. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x3A -> 0x166C`; source table `0x17A3`; RAM helper `0x1786` | ROM verified | Handler confirms nonzero parameters are consumed without copy. |
| `ESC <` | Sets one-line unidirectional left-to-right for the next printed line. | Notes `Escape commands`, direction notes | Explicit ESC dispatch `0x09FD`: `0x3C -> 0x266E` | ROM dispatch | Blank-feed interaction still needs handler trace. |
| `ESC =` | Forces incoming data high bit to 0 outside raw graphics/data payloads. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x3D -> 0x0A93`; handler sets `$8003` bit `0x01` and clears bit `0x02` | ROM verified | The ESC parser masks command bytes to 7-bit before dispatch, so escape-command recognition is unaffected. |
| `ESC >` | Forces incoming data high bit to 1 outside raw graphics/data payloads. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x3E -> 0x0A8F`; handler sets `$8003` bits `0x01` and `0x02` | ROM verified | The ESC parser masks command bytes to 7-bit before dispatch, so escape-command recognition is unaffected. |
| `ESC ? s n` | Reassigns `K/L/Y/Z` to graphics mode `0..7`. | Notes `Escape commands`, graphics notes | `0x38CD..0x38FE`, pointer table `0x38FF..0x390E` | ROM verified | Invalid command consumes the following byte through the input routine; current parser ignores reassignment when `s` is invalid. |
| `ESC @` | Resets printer state, reapplies config defaults, resets tabs and graphics reassignment. | Notes `Reset and defaults`, `Escape commands` | Uppercase ESC table `0x09C7`: `@ -> 0x078D`; reset path calls `0x3359` to initialize graphics reassignment vectors | ROM dispatch | Does not cancel already reserved graphics bytes, matching notes. |
| `ESC A n` | Sets `n/72` inch line spacing. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `A -> 0x0FBC`; handler masks `n & 0x7F` and accepts only values `< 0x56` | ROM verified | Dreamulator masks to low 7 bits, accepts `0..85` and `128..213`, and ignores values whose low 7 bits are `86..127`. |
| `ESC B n...0` | Sets channel 0 vertical tabs; stops stored in current line spacing. | Notes `Escape commands`, tabs | Uppercase ESC table `0x09C7`: `B -> 0x1191`; channel storage cleared through `0x1157`, list parser at `0x119B..0x11C7` | ROM verified | Stops terminate on zero, nonascending value, more than 16 stops, or any converted stop not less than the current form length. After an early termination that is not zero, the handler consumes bytes until zero or a nonascending byte. |
| `ESC C n` | Sets form length in current lines when `(n & 0x7F) >= 1`; `n=0` starts inch form. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `C -> 0x1021`; handler calls `0x114D` to clear vertical-tab storage, converts to motion units, stores `$889F`, clears skip-over-perf, and calls `ESC O` path `0x10C3` | ROM verified |  |
| `ESC C 0 n` | Sets form length in inches for `(n & 0x7F) = 1..22`. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `C -> 0x1021`; inch path multiplies by 216 and rejects zero, values `>= 23`, and values smaller than current line spacing | ROM verified |  |
| `ESC D n...0` | Sets horizontal tabs in current pitch. | Notes `Escape commands`, tabs | Uppercase ESC table `0x09C7`: `D -> 0x3F60`; handler clears table at `$9749`, converts each stop through the current pitch width, adds left margin `$8010`, and stores 16-bit positions | ROM verified | Stops terminate on zero, nonascending physical position, more than 32 stops, or a position past the right margin. After an early termination that is not zero, the handler consumes bytes until zero or a nonascending byte. |
| `ESC E` | Emphasized on. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `E -> 0x3A60` | ROM dispatch | Renderer maps to bold pass. |
| `ESC F` | Emphasized off. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `F -> 0x3A6B` | ROM dispatch |  |
| `ESC G` | Double-strike on. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `G -> 0x3A79`; handler sets raw `$8001` bit `0x10` and calls resolver `0x3AF0` | ROM verified | Renderer style approximates double-strike through impact rendering state. |
| `ESC H` | Double-strike off. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `H -> 0x3A7D` | ROM dispatch |  |
| `ESC I n` | Enables/disables printable low-control glyph slots. | Notes `Character sets and fonts`, `Escape commands` | Uppercase ESC table `0x09C7`: `I -> 0x0BB9` | ROM dispatch | Printable low-control set is modeled from notes. |
| `ESC J n` | Immediate forward feed by `n/216` inch without changing line spacing. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `J -> 0x10C7` | ROM dispatch | Marks page dirty in PDF output. |
| `ESC K n1 n2 data` | 60 dpi 8-pin graphics; may be reassigned by `ESC ?`. | Notes `Graphics modes` | Reassignment vectors at `$9739..$973F`; mode 0 setup `0x33DA` | ROM verified | Uses same raw-data quota as `ESC *`. |
| `ESC L n1 n2 data` | 120 dpi low-speed 8-pin graphics; may be reassigned by `ESC ?`. | Notes `Graphics modes` | Reassignment vectors; mode 1 setup `0x33FA` | ROM verified | Adjacent dots allowed. |
| `ESC M` | Elite pitch on. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `M -> 0x3A84`; handler sets raw `$8001` bit `0x01` and calls resolver `0x3AF0` | ROM verified | Elite masks Proportional, Emphasized, and Compressed effective pitch/weight flags while active. |
| `ESC N n` | Sets skip-over-perforation line count. | Notes `Escape commands`, forms | Uppercase ESC table `0x09C7`: `N -> 0x109A`; handler masks `n & 0x7F`, rejects zero, converts through current line spacing, requires converted distance to be less than form length `$889F`, and stores the remaining printable span at `$88A5/$88A7` | ROM verified | Dreamulator enforces the low-7-bit, nonzero, less-than-form-length validation. |
| `ESC O` | Cancels skip-over-perforation. | Notes `Escape commands`, forms | Uppercase ESC table `0x09C7`: `O -> 0x10C3` | ROM dispatch |  |
| `ESC P` | Elite pitch off. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `P -> 0x3A8F`; handler clears raw `$8001` bit `0x01` and calls resolver `0x3AF0` | ROM verified | If raw Proportional, Emphasized, or Compressed bits are set, they can become effective after Elite is cleared. |
| `ESC Q n` | Sets right margin in current pitch. | Notes `Escape commands`, margins | Uppercase ESC table `0x09C7`: `Q -> 0x2486`; handler multiplies parameter by current pitch width, requires result `< 0x1681` and at least `$8010 + 0x90`, then stores `$800E` and calls cancel path `0x23FE` | ROM verified | Dreamulator validates the physical bounds and cancels pending buffered text only when the new margin is accepted. |
| `ESC R n` | Selects international character set. | Notes `International character sets` | Uppercase ESC table `0x09C7`: `R -> 0x0ABE`; handler stores `n & 0x7F` only when the value is `<= 10`; international remap table is `0x0AF7..0x0B7A` | ROM verified | Dreamulator accepts low-7-bit values `0..10` and ignores larger values. Sets `9` and `10` remain unnamed for glyph-label documentation. |
| `ESC S n` | Enables superscript for `0` and subscript for `1`. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `S -> 0x3A9D`; handler uses on/off helper convention, sets/clears `$8007` bit `0x20` for subscript selection, sets raw `$8001` bit `0x80`, then calls resolver `0x3AF0` | ROM verified | Script forces the double-strike/script pass; it does not clear the raw Proportional bit. |
| `ESC T` | Cancels superscript/subscript. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `T -> 0x3AAF` | ROM dispatch |  |
| `ESC U n` | Continuous unidirectional off/on from low bit. | Notes `Escape commands`, direction notes | Uppercase ESC table `0x09C7`: `U -> 0x3AB3` | ROM dispatch | Same convention as FX/LQ; blank-feed interaction still needs handler trace. |
| `ESC W n` | Continuous expanded off/on from low bit. | Notes `Escape commands` | Uppercase ESC table `0x09C7`: `W -> 0x3AC1` | ROM dispatch | Not canceled by `DC4`. |
| `ESC Y n1 n2 data` | 120 dpi high-speed graphics with adjacent-dot suppression; may be reassigned. | Notes `Graphics modes` | Reassignment vectors; mode 2 setup `0x341C` | ROM verified |  |
| `ESC Z n1 n2 data` | 240 dpi graphics with adjacent-dot suppression; may be reassigned. | Notes `Graphics modes` | Reassignment vectors; mode 3 setup `0x343E` | ROM verified |  |
| `ESC ^ d n1 n2 data` | 9-pin graphics; documented `d=0` 60 dpi and `d=1` 120 dpi; two bytes per column. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x5E -> 0x351D`; handler accepts `d=0..3`, reads `n1,n2`, doubles `$8053`, then enters the shared graphics engine with 9-pin flag `$8006` bit `0x20` set | ROM verified | `d=2` uses the same constants as `ESC *` mode 2 and `d=3` uses the same constants as mode 3, including adjacent-dot suppression. Invalid `d` still consumes `n1,n2` through the width reader and exits. |
| `ESC b ch n...0` | Sets vertical tabs for channel `(ch & 0x7F)` when it is `< 8`. | Notes `Escape commands`, tabs | Explicit ESC dispatch `0x09FD`: `0x62 -> 0x1170`; valid channels are cleared through `0x1157` before the shared vertical-tab list parser | ROM verified | If the channel is invalid, the handler consumes only `ch` and returns; it does not consume a tab list. Valid-channel list rules match `ESC B`. |
| `ESC i n` | Consumed as FX immediate-print mode. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x69 -> 0x08B3` | Approx | ROM dispatch exists; PDF renderer has no delayed print buffer, so no visible effect. |
| `ESC j n` | Immediate reverse feed by `n/216` inch, clamped at top margin. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x6A -> 0x1126` | ROM dispatch | Physical reverse-feed limits need ROM/service confirmation. |
| `ESC l n` | Sets left margin in current pitch. | Notes `Escape commands`, margins | Explicit ESC dispatch `0x09FD`: `0x6C -> 0x24B9`; handler multiplies parameter by current pitch width, requires result below `$800E - 0x90`, stores `$8010`, clears a state bit, and calls cancel path `0x23FE` | ROM verified | Dreamulator validates against the right margin, stores accepted values immediately, and cancels pending buffered text only when the new margin is accepted. |
| `ESC p n` | Proportional off/on from low bit. | Notes `Escape commands`, ROM glyph table | Explicit ESC dispatch `0x09FD`: `0x70 -> 0x3AD5`; uses on/off helper `0x0A6F`; handler toggles raw `$8001` bit `0x02` and calls resolver `0x3AF0`; glyph prefix format at `0x17A3`/`0x1DA3` | ROM verified | Effective Proportional is masked by Elite, masks plain Emphasized/Compressed, and always sets effective Emphasized. Lower-priority raw bits are not cleared. |
| `ESC s n` | Consumed as half-speed mode. | Notes `Escape commands` | Explicit ESC dispatch `0x09FD`: `0x73 -> 0x2679` | Approx | ROM dispatch exists; timing/head-speed has no visible PDF effect. |
| `ESC x n` | ROM-specific print-quality/download-font select. | LQ comparison; explicit ESC table | Explicit ESC dispatch `0x09FD`: `0x78 -> 0x29A7`; uses on/off helper `0x0A6F`. `1`/`'1'` calls RAM probe/setup `0x29D9`; `0`/`'0'` sets `$805C` bit `0x01`, clears `$805D` bit `0x04`, calls `0x28A0`, clears `$805D` bit `0x04` again, calls `0x2E42`, then clears `$805C` bit `0x01`; invalid parameters are ignored except literal `'8'`, which sets `$805C` bit `0x10`. | ROM verified | This is not a normal documented FX-80 feature. Treat as a Version 2.00/shared-code path unless a target model explicitly supports print-quality or external/download font behavior. |

## Current high-priority verification gaps

1. Keep FX-family `ESC &` on the documented 12-byte format unless a ROM-version
   option is added. The Version 2.00 dispatch path is LQ-style, but the manuals,
   ROM glyph table, and adjacent 12-byte parser all support the classic FX
   format as the expected model behavior.
2. Trace `ESC <`, `ESC U`, `LF`, `CR`, `VT`, and `ESC j` further only if a
   byte-for-byte firmware line-buffer model is needed. The current logical
   pending-line buffer captures the visible blank-feed behavior used by the
   emulator.
3. Trace `ESC 8`, `ESC 9`, `DC1`, and `DC3` far enough to model paper-out,
   select/deselect, ACK/BUSY, and DIP-gated input behavior if parallel-port
   fidelity becomes a goal.
