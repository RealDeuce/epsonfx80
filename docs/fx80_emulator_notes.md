# Epson FX-80 emulator notes

These notes summarize the local FX-80/FX-100 manuals, service document, and ROM dumps for emulator implementation. They are written so an implementer should not need to reopen the PDFs for command behavior.

The notes are FX-80 focused. FX-100 differences are included where the manuals give different line widths or paper width behavior.

## Source inventory

| File | Use | SHA-256 |
| --- | --- | --- |
| `fx80__uv.pdf` | Tutorial volume, examples and behavioral explanations | `9fe120d39c0d5b78d9cb3145eb9c4d2bdf4298c6fed777d21a14aff70f858576` |
| `fx80__u1.pdf` | Reference volume, appendices A-K | `32d9469d3cb854002fd6b8a7fc61d836d0596e340b4c47b43fa6cd8225ba1556` |
| `fx80__sl.pdf` | One-page specification sheet | `d3c4b46622b7a90783eced7d9b34e95d8fc42cd4b97218e84387ebff10c35818` |
| `Sams_Computerfacts_Epson_FX-80_Printer_1985_Howard_Sams_text.pdf` | Service data, board and fault details | `60e7ec221b19ccfa26989ef5beb3489474af5cc477b7e854b1571b336f022d91` |
| `epson_8426k9_m1206ba029_read_as_27c128.bin` | 16 KiB firmware ROM, includes Version 2.00 string and character glyph table | `76f44e1c9fe34090a568b39a0fd995308d81bf5f1bf36f6fb6833eb1a2d51a17` |
| `epson_fx_c42040kb_8042ah.bin` | 2 KiB 8042-family controller/slave ROM dump | `1475e4136887a9453ff49ecaa8a77d024e1094eb13bc76d39d1a585efae015ff` |

## Hardware model

Printing is serial impact dot matrix. Text is normally bidirectional with logic seeking. Bit-image graphics, superscript/subscript, one-line unidirectional, and continuous unidirectional modes print left-to-right.

The print head has 9 pins at 1/72 inch vertical pitch. Standard graphics bytes fire the top eight pins. Seven-bit hosts can only control the middle seven pins unless host-side high-bit handling is worked around. 9-pin graphics uses two bytes per column: byte 1 fires the top eight pins normally, and only bit 7 of byte 2 fires the ninth/bottom pin.

Horizontal position is tracked by the firmware in 720 units per inch. The carriage motor appears to be a 6-wire unipolar stepper: the service document gives four 9.1-ohm winding checks, from CN4 center taps to the four phase ends. The strongest ROM/service correlation is:

| Quantity | Distance | 720-unit coordinate |
| --- | --- | --- |
| Half step / finest native motor substep | 1/240 inch | 3 units |
| Full motor step | 1/120 inch | 6 units |
| Single-density graphics column | 1/60 inch | 12 units |
| PTS sensor cycle / 4 full steps | about 1/30 inch | 24 units |

The PTS check is independent: the service adjustment sets the Position Timing Signal cycle to 2.1 ms during self-test. At 160 cps in 10 cpi pica, carriage speed is 16 inches/second, so 2.1 ms is 0.0336 inch, effectively 1/30 inch. That equals four inferred 1/120-inch full steps. The ROM's default FX-80 right margin is `0x1680` internal units, exactly 5760 units or 8 inches.

Nominal print speed is 160 cps. Half-speed mode is 80 cps. Paper feed is about 150 ms per 1/6-inch line. Standard buffer is 2 KiB, but DIP switch 1-4 chooses whether that RAM is used as a text buffer or as user-defined character RAM.

## Reset and defaults

Power-on, `INIT`, and `ESC @` reset the controller to the power-up state and clear the print buffer. `ESC @` also resets top-of-form to the current paper position.

Factory defaults:

| State | Factory value |
| --- | --- |
| Printer selected/active | Active |
| Typeface | Roman |
| Pitch | Pica, 10 cpi |
| Margins | Left 0, right 80 on FX-80, right 136 on FX-100 |
| Line spacing | 12-dot, 1/6 inch |
| Form length | 66 lines, 11 inches at default spacing |
| Vertical tabs | Every 2 lines |
| Vertical tab channel | 0 |
| Horizontal tabs | Every 8 spaces |
| International set | USA |
| User RAM | 2K available for user-defined characters |
| Paper-out sensor | On |
| Zero glyph | Non-slashed zero |
| CR behavior | CR only, no automatic LF |
| Head direction | Bidirectional |
| Skip-over-perforation | Off |
| Beeper | On |

## DIP switches

Switch settings are sampled at power-up. Change them only while power is off.

| Switch | ON | OFF, factory unless noted |
| --- | --- | --- |
| 1-1 | Compressed default pitch | Pica default pitch |
| 1-2 | Slashed zero | Non-slashed zero |
| 1-3 | Paper-out sensor inactive | Paper-out sensor active |
| 1-4 | 2K RAM used as text buffer | 2K RAM used for user-defined characters |
| 1-5 | Emphasized default weight | Single-strike default weight |
| 1-6 | International set bit | International set bit |
| 1-7 | International set bit | International set bit |
| 1-8 | International set bit | International set bit |
| 2-1 | Printer active/select enabled | Printer inactive |
| 2-2 | Beeper sounds | Beeper mute |
| 2-3 | Skip-over-perforation on | Skip-over-perforation off |
| 2-4 | CR adds LF | CR only |

International DIP encoding:

| Default country | 1-6 | 1-7 | 1-8 |
| --- | --- | --- | --- |
| USA | On | On | On |
| France | On | On | Off |
| Germany | On | Off | On |
| United Kingdom | On | Off | Off |
| Denmark | Off | On | On |
| Sweden | Off | On | Off |
| Italy | Off | Off | On |
| Spain | Off | Off | Off |

Japan has no DIP combination. Select it with `ESC R 8`.

## Character sets and fonts

The ROM exposes these character regions:

| Codes | Meaning in normal text mode |
| --- | --- |
| 0-31 | Control codes, with Roman international glyphs stored behind them |
| 32-126 | Roman USA printable set |
| 127 | DEL control code |
| 128-159 | High-order control aliases, with Italic international glyphs stored behind them |
| 160-254 | Italic USA printable set |
| 255 | High-order DEL/control |

`ESC 4` selects Italic; `ESC 5` selects Roman. Codes 160-254 print Italic glyphs directly on 8-bit systems. `ESC 6` makes 128-159 and 255 printable as glyphs; `ESC 7` returns them to control-code behavior. `ESC I 1` makes printable glyphs available at 0-31 except for active control-code slots; `ESC I 0` restores control-code behavior. Some low controls cannot be printed directly even under `ESC I 1`: 7-15, 17-20, 24, and 27. They can be reached through the international remapping path.

### ROM glyph table

The 16 KiB firmware dump contains the complete 256-entry glyph table.

* File: `epson_8426k9_m1206ba029_read_as_27c128.bin`
* Table base: `0x17A3`
* Entry size: 12 bytes
* Entry offset: `0x17A3 + code * 12`
* Entry format: byte 0 is the attribute byte, bytes 1-11 are column data.
* Stored column data is inverted in ROM: use `active_column = stored_byte ^ 0xFF`.
* The active column bits use the normal graphics pin weights: bit 7/top pin is `0x80`, then `0x40`, `0x20`, `0x10`, `0x08`, `0x04`, `0x02`, `0x01` downward through the eight selected pins.

Attribute byte format matches user-defined characters:

| Bits | Meaning |
| --- | --- |
| 7 | `1` means use top 8 pins; `0` means use bottom 8 pins |
| 6-4 | Proportional start column, 0-7 |
| 3-0 | Proportional end column, 0-11 |

For fixed-pitch output, print all 11 columns and apply the current pitch advance. For proportional output, print only the attribute-selected start/end span. Proportional mode is always emphasized.

`docs/fx80_rom_glyphs.csv` is generated from this ROM table. It includes all 256 rows with ROM offset, attribute decode, stored inverted bytes, and active column bytes.

## International character sets

`ESC R n` selects the international set. Valid `n` values:

| n | Country |
| --- | --- |
| 0 | USA |
| 1 | France |
| 2 | Germany |
| 3 | United Kingdom |
| 4 | Denmark |
| 5 | Sweden |
| 6 | Italy |
| 7 | Spain |
| 8 | Japan |

Only these printable code positions are remapped by international sets:

`35, 36, 64, 91, 92, 93, 94, 96, 123, 124, 125, 126`

The manual's printed labels for those positions are:

| Country | 35 | 36 | 64 | 91 | 92 | 93 | 94 | 96 | 123 | 124 | 125 | 126 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USA | number-sign | dollar | at | left-bracket | backslash | right-bracket | caret | grave | left-brace | vertical-bar | right-brace | tilde |
| France | number-sign | dollar | a-grave | degree | c-cedilla | section | caret | grave | e-acute | u-grave | e-grave | diaeresis |
| Germany | number-sign | dollar | section | A-diaeresis | O-diaeresis | U-diaeresis | caret | grave | a-diaeresis | o-diaeresis | u-diaeresis | sharp-s |
| United Kingdom | pound | dollar | at | left-bracket | backslash | right-bracket | caret | grave | left-brace | vertical-bar | right-brace | tilde |
| Denmark | number-sign | dollar | at | AE | O-slash | A-ring | caret | grave | ae | o-slash | a-ring | tilde |
| Sweden | number-sign | currency | E-acute | A-diaeresis | O-diaeresis | A-ring | U-diaeresis | e-acute | a-diaeresis | o-diaeresis | a-ring | u-diaeresis |
| Italy | number-sign | dollar | at | degree | backslash | e-acute | caret | u-grave | a-grave | o-grave | e-grave | i-grave |
| Spain | peseta | dollar | at | inverted-exclamation | N-tilde | C-cedilla | caret | grave | diaeresis | n-tilde | right-brace | tilde |
| Japan | number-sign | dollar | at | left-bracket | yen | right-bracket | caret | grave | left-brace | vertical-bar | right-brace | tilde |

For rendering, do not rely on Unicode glyph substitution alone. The FX has its own dot patterns in the ROM table. The international remap maps the public code position to an internal glyph location in the low control-code area. Blank cells mean use the normal public code glyph.

| Public code | USA | France | Germany | UK | Denmark | Sweden | Italy | Spain | Japan |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 35 | | | | 6 | | | | 12 | |
| 36 | | | | | | 11 | | | |
| 64 | | 0 | 16 | | | 29 | | | |
| 91 | | 5 | 23 | | 18 | 23 | 5 | 7 | |
| 92 | | 15 | 24 | | 20 | 24 | | 9 | 31 |
| 93 | | 16 | 25 | | 13 | 13 | 30 | 8 | |
| 94 | | | | | | 25 | | | |
| 96 | | | | | | 30 | 2 | | |
| 123 | | 30 | 26 | | 19 | 26 | 0 | 22 | |
| 124 | | 2 | 27 | | 21 | 27 | 3 | 10 | |
| 125 | | 1 | 28 | | 14 | 14 | 1 | | |
| 126 | | 22 | 17 | | | 28 | 4 | | |

When Italic is active, use the corresponding Italic internal location by adding 128 to the internal low-code glyph location.

## Text mode rendering

The base character matrix is 9 rows high by 11 columns wide: 6 main columns plus 5 intermediate columns. Most ROM characters use 7 rows and leave the last two columns blank for inter-character spacing. Descenders use the lower rows. User-defined characters may be up to 8 dots tall and 11 columns wide.

Pitch and nominal line capacity:

| Pitch | CPI | FX-80 columns | FX-100 columns |
| --- | --- | --- | --- |
| Pica | 10 | 80 | 136 |
| Expanded Pica | 5 | 40 | 68 |
| Elite | 12 | 96 | 163 |
| Expanded Elite | 6 | 48 | 81 |
| Compressed | 17.16 | 132 default, 137 with margin change | 233 |
| Expanded Compressed | 8.58 | 68 | 116 |

Mode priority for conflicting pitch/weight modes is computed by the ROM resolver at `0x3AF0`:

`Elite > Proportional > Emphasized > Compressed > Pica`

Lower-priority modes are masked, not cancelled. Example: if Elite and Compressed are both active, output is Elite; when Elite is turned off, Compressed becomes visible. Proportional characters are always effectively emphasized and mask plain Emphasized/Compressed for pitch-weight selection. Italic, Underline, and Expanded combine with those modes. Script and Double-Strike are resolved separately; Script forces the double-strike/script pass.

## Master Select

`ESC ! n` selects a bundled pitch/weight combination. The ROM clears the raw low mode bits, applies Expanded from bit `0x20`, then stores `n & 0x3D` into the raw mode byte before recomputing effective mode flags. FX ignores LQ Master Select proportional bit `0x02`, italic bit `0x40`, and parameter bit `0x80`. Underline is not part of FX Master Select; use `ESC -`. The manuals present convenient printable ASCII aliases.

| Combination | Decimal n | Printable alias |
| --- | --- | --- |
| Pica single | 0 or 64 | NUL or `@` |
| Pica emphasized | 8 or 72 | BS or `H` |
| Pica double-strike | 16 or 80 | DLE or `P` |
| Pica emphasized double-strike | 24 or 88 | CAN or `X` |
| Elite single | 1 or 65 | SOH or `A` |
| Elite double-strike | 17 or 81 | DC1 or `Q` |
| Compressed single | 4 or 68 | EOT or `D` |
| Compressed double-strike | 20 or 84 | DC4 or `T` |
| Expanded pica single | 32 | space |
| Expanded pica emphasized | 40 | `(` |
| Expanded pica double-strike | 48 | `0` |
| Expanded pica emphasized double-strike | 56 | `8` |
| Expanded elite single | 33 | `!` |
| Expanded elite double-strike | 49 | `1` |
| Expanded compressed single | 36 | `$` |
| Expanded compressed double-strike | 52 | `4` |

Invalid combinations in the manual: Elite plus Emphasized, Compressed plus Emphasized, Expanded Elite plus Emphasized, Expanded Compressed plus Emphasized, and the emphasized double-strike variants of Elite/Compressed.

## Control codes

Parser convention: `ESC` is byte `0x1B`. Commands that take parameters consume exactly the documented parameter count, or consume a terminated list until `NUL` or a nonascending tab stop. Graphics commands then consume the requested number of raw data bytes; those bytes are not parsed as commands.

### Single-byte controls

| Dec | Hex | Mnemonic | Behavior |
| --- | --- | --- | --- |
| 0 | 00 | NUL | Terminates horizontal and vertical tab setting lists. |
| 7 | 07 | BEL | Sounds beeper, if beeper enabled. |
| 8 | 08 | BS | Flushes buffer, then moves print head left one current-pitch space. |
| 9 | 09 | HT | Flushes buffer, then moves to next horizontal tab stop. High-order alias 137 also tabs. |
| 10 | 0A | LF | Flushes buffer, advances paper by current line spacing, resets buffer character count. |
| 11 | 0B | VT | Flushes buffer, advances to next vertical tab stop in current channel. |
| 12 | 0C | FF | Flushes buffer, advances to next logical top-of-form. |
| 13 | 0D | CR | Prints buffer, resets buffer character count, returns to left margin. Adds LF only if DIP 2-4 or AUTO FEED XT requests it. |
| 14 | 0E | SO | One-line Expanded on until line end, `DC4`, or `ESC W 0`. |
| 15 | 0F | SI | Flushes buffer and turns Compressed on. |
| 17 | 11 | DC1 | Selects/enables printer when DIP 2-1 allows DC1/DC3 control. |
| 18 | 12 | DC2 | Turns Compressed off. |
| 19 | 13 | DC3 | Deselects printer when DIP 2-1 allows DC1/DC3 control. |
| 20 | 14 | DC4 | Turns one-line Expanded off. Does not cancel continuous `ESC W 1`. |
| 24 | 18 | CAN | Cancels all text in print buffer. |
| 27 | 1B | ESC | Starts an escape sequence. |
| 127 | 7F | DEL | Deletes most recent text character in print buffer. |

High-order aliases exist for many controls when high-bit handling is neutral, for example 137 for HT. `ESC #` accepts the host high bit, `ESC =` forces the high bit clear, and `ESC >` forces the high bit set. The ROM dispatches ESC commands after masking the command byte to 7-bit, so these high-bit modes do not change escape-command recognition.

### Escape commands by byte

| Sequence | Parameters | Behavior |
| --- | --- | --- |
| `ESC ! n` | 1 | Master Select. See table above. |
| `ESC #` | none | Accept eighth bit as sent by host. |
| `ESC % n1 n2` | 2 | Select character source. `n1=0,n2=0` selects ROM. `n1=1,n2=0` selects RAM. Requires DIP 1-4 off. |
| `ESC & 0 c1 c2 ...` | variable | Define user characters from `c1` through `c2`. The FX manuals specify one attribute byte plus 11 column bytes per character and require DIP 1-4 off. The Version 2.00 ROM dispatch instead points to an LQ-style handler that consumes `d0,d1,d2` followed by three bytes per column; see `docs/fx80_command_rom_audit.md` before implementing this command. |
| `ESC * m n1 n2 data...` | 3 plus data | Variable-density graphics. Documented `m=0..6`; the Version 2.00 ROM also accepts `m=7`. Width is `n1 + 256*n2` columns; consume one data byte per column. |
| `ESC - n` | 1 | Underline off for `n=0`, on for `n=1`. |
| `ESC / n` | 1 | Select vertical tab channel `(n & 0x7F)` when it is `0..7`; values `8..127` after masking are ignored. |
| `ESC 0` | none | Set line spacing to 1/8 inch, 9 dots. |
| `ESC 1` | none | Set line spacing to 7/72 inch, 7 dots. |
| `ESC 2` | none | Set line spacing to 1/6 inch, 12 dots. |
| `ESC 3 n` | 1 | Set line spacing to `n/216` inch, `n=0..255`. |
| `ESC 4` | none | Italic on. |
| `ESC 5` | none | Italic off. |
| `ESC 6` | none | Print glyphs at 128-159 and 255 instead of treating them as controls. |
| `ESC 7` | none | Restore 128-159 and 255 to control-code behavior. |
| `ESC 8` | none | Disable paper-out sensor for BUSY/ERROR behavior. Pin 12 PE still reports paper out. |
| `ESC 9` | none | Enable paper-out sensor. |
| `ESC : n1 n2 n3` | 3 | Copy ROM character set to RAM. All three parameters are 0 in this model. Clears previous RAM definitions. |
| `ESC <` | none | One-line unidirectional mode; next line prints left-to-right. |
| `ESC =` | none | Force eighth bit to 0 for ordinary incoming data/control bytes. |
| `ESC >` | none | Force eighth bit to 1 for ordinary incoming data/control bytes. |
| `ESC ? s n` | 2 | Reassign alternate graphics command `s` (`K`, `L`, `Y`, or `Z`) to graphics density. Documented `n=0..6`; the Version 2.00 ROM accepts `n=0..7`. |
| `ESC @` | none | Reset to power-up defaults, clear print buffer, reset top-of-form. |
| `ESC A n` | 1 | Set line spacing to `(n & 0x7F)/72` inch when `(n & 0x7F) < 86`. Values whose low 7 bits are `86..127` are ignored. |
| `ESC B n...0` | list | Set up to 16 vertical tabs in current line spacing for channel 0. Later line-spacing changes do not move stored stops. Terminate with 0, a nonascending value, too many stops, or any converted stop not less than the current form length. After an early nonzero terminator, the ROM consumes bytes until 0 or a nonascending byte. |
| `ESC C n` | 1 | Set form length to `(n & 0x7F)` lines in current line spacing when nonzero; also clears vertical-tab storage, cancels skip-over-perforation, and resets top-of-form. |
| `ESC C 0 n` | 2 | Set form length to `(n & 0x7F)` inches when `1..22`; also clears vertical-tab storage, cancels skip-over-perforation, and resets top-of-form. |
| `ESC D n...0` | list | Set up to 32 horizontal tabs in current pitch. Stops are stored as absolute physical positions after adding the current left margin. Later pitch or margin changes do not move stored stops. Terminate with 0, a nonascending physical position, too many stops, or a position past the right margin. After an early nonzero terminator, the ROM consumes bytes until 0 or a nonascending byte. |
| `ESC E` | none | Emphasized on. Masked by Elite; masks Compressed. |
| `ESC F` | none | Emphasized off. |
| `ESC G` | none | Double-Strike on. |
| `ESC H` | none | Double-Strike off. |
| `ESC I n` | 1 | `n=1` enables printing glyphs at 0-31 where not active controls. `n=0` restores controls. |
| `ESC J n` | 1 | Immediate one-time forward feed of `n/216` inch without carriage return and without changing current line spacing. Flushes current buffer first. |
| `ESC K n1 n2 data...` | 2 plus data | Single-density graphics, 60 dpi, 480 dots per 8-inch line; one data byte per column. |
| `ESC L n1 n2 data...` | 2 plus data | Low-speed double-density graphics, 120 dpi, 960 dots per 8-inch line; one data byte per column. |
| `ESC M` | none | Elite on, 12 cpi. |
| `ESC N n` | 1 | Skip-over-perforation on for `(n & 0x7F)` lines. Zero is ignored; values whose converted distance is not less than the current form length are ignored. |
| `ESC O` | none | Skip-over-perforation off. |
| `ESC P` | none | Elite off. Returns to Pica unless Compressed is active. |
| `ESC Q n` | 1 | Set right margin in current pitch and cancel buffered text. FX-80 ranges: Pica 2-80, Elite 3-96, Compressed 4-137. FX-100: Pica 2-136, Elite 3-163, Compressed 4-233. Invalid settings are ignored. |
| `ESC R n` | 1 | Select international set. The Version 2.00 ROM accepts `(n & 0x7F) <= 10` and ignores larger values. Manuals document sets `0..8`; sets `9` and `10` need glyph-name confirmation. |
| `ESC S n` | 1 | Script on. `n=0` superscript, `n=1` subscript. Script forces the double-strike/script pass. |
| `ESC T` | none | Script off. |
| `ESC U n` | 1 | Continuous unidirectional off for `n=0`, on for `n=1`. |
| `ESC W n` | 1 | Continuous Expanded off for `n=0`, on for `n=1`. Not cancelled by `DC4`. |
| `ESC Y n1 n2 data...` | 2 plus data | High-speed double-density graphics, 120 dpi, 960 dots per 8-inch line, but suppresses adjacent dots in the same row. |
| `ESC Z n1 n2 data...` | 2 plus data | Quadruple-density graphics, 240 dpi, 1920 dots per 8-inch line, suppresses adjacent dots in the same row. |
| `ESC ^ d n1 n2 data...` | 3 plus data | 9-pin graphics. Manuals document `d=0` single-density 60 dpi and `d=1` double-density 120 dpi. The Version 2.00 ROM also accepts `d=2` and `d=3`, matching the high-speed 120 dpi and 240 dpi timing/adjacent-dot rules from `ESC *` modes 2 and 3. Width is `n1 + 256*n2` columns; consume two data bytes per column. Invalid `d` consumes `n1,n2` and no graphics data. |
| `ESC b ch n...0` | list | Set vertical tabs for channel `(ch & 0x7F)` when it is `0..7`; channel 0 is equivalent to `ESC B`. If the channel is invalid, only `ch` is consumed and the following bytes are parsed normally. Valid-channel list rules match `ESC B`. |
| `ESC i n` | 1 | FX-80 only. Immediate print mode off for `n=0`, on for `n=1`; each character prints as received. |
| `ESC j n` | 1 | FX-80 only. Immediate one-time reverse feed of `n/216` inch without carriage return. |
| `ESC l n` | 1 | Lowercase ell. Set left margin in current pitch. FX-80 ranges: Pica 0-78, Elite 0-93, Compressed 0-133. FX-100: Pica 0-134, Elite 0-160, Compressed 0-229. Invalid settings are ignored. The ROM stores the new margin immediately after validation and cancels buffered output. |
| `ESC p n` | 1 | Proportional off for `n=0`, on for `n=1`. Effective Proportional is masked by Elite, masks plain Emphasized/Compressed, and is always emphasized. |
| `ESC s n` | 1 | Half-speed off for `n=0`, on for `n=1`. |
| `ESC x n` | 1 | Version 2.00 ROM-specific print-quality/download-font select. `1`/`'1'` calls the alternate RAM/font setup path, `0`/`'0'` returns to the normal path, invalid values are ignored except literal `'8'`, which sets an internal quality/timing flag. Do not expose this as normal FX-80 behavior unless the target model explicitly supports it. |

## Graphics modes

All graphics commands reserve a fixed number of columns. After the command, the next bytes are graphics data until the quota is filled. Do not interpret bytes inside the quota as text or commands.

For all 8-pin graphics modes, each data byte maps directly to pins:

| Bit | Weight | Pin |
| --- | --- | --- |
| 7 | 128 | Top selected pin |
| 6 | 64 | Next pin |
| 5 | 32 | Next pin |
| 4 | 16 | Next pin |
| 3 | 8 | Next pin |
| 2 | 4 | Next pin |
| 1 | 2 | Next pin |
| 0 | 1 | Bottom selected pin |

Graphics density table:

| m | Alternate command | Density | FX-80 8-inch columns | FX-100 13.6-inch columns | Head speed | Adjacent dot rule |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `ESC K` | Single, 60 dpi | 480 | 816 | 16 in/s | Adjacent dots allowed |
| 1 | `ESC L` | Low-speed double, 120 dpi | 960 | 1632 | 8 in/s | Adjacent dots allowed |
| 2 | `ESC Y` | High-speed double, 120 dpi | 960 | 1632 | 16 in/s | No consecutive dots in same row |
| 3 | `ESC Z` | Quadruple, 240 dpi | 1920 | 3264 | 8 in/s | No consecutive dots in same row |
| 4 | none | Epson QX-10 screen, 80 dpi | 640 | 1088 | 8 in/s | Adjacent dots allowed |
| 5 | none | One-to-one plotter, 72 dpi | 576 | 979 | 12 in/s | Adjacent dots allowed |
| 6 | none | Other CRT screens, 90 dpi | 720 | 1224 | 8 in/s | Adjacent dots allowed |
| 7 | none | Undocumented ROM mode, 144 dpi | 1152 | 1958 | 12 in/s inferred | Adjacent dots allowed |

Width parameter is `n1 + 256*n2`. The manuals note FX-80 treats overlarge `n2` modulo 8 for 8-pin graphics, and FX-100 modulo 13, but practical visible line widths are limited by the selected density and paper width.

### ROM graphics density implementation

The Version 2.00 firmware was disassembled as NEC uPD7810 code. The bit-image handlers are at `0x3371..0x350D`. The command dispatch for `ESC *` compares `m` against `0..7`, not just the documented `0..6`, and jumps to the setup entries at `0x33DA`, `0x33FA`, `0x341C`, `0x343E`, `0x3464`, `0x348A`, `0x34B4`, and `0x34D8`.

Each setup entry starts with `CALL $33B5; RET;`. `$33B5` consumes `n1,n2` and stores the requested graphics column count at `$8053`. If the count is zero it returns normally and the local `RET` exits the command. If the count is nonzero it returns with the uPD7810 skip-return path, skipping the local `RET` and entering the setup body that follows.

The setup body writes these per-mode constants:

| m | Density | Entry | `VV:2C` | `720 / VV:2C` | `VV:31` | `VV:57` | `VV:2B` | `VV:52` bit 0 | Phase table copied to `$8032` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 60 dpi | `0x33DA` | 12 | 60 | 1 | 1 | `0x02` | clear | `1` |
| 1 | 120 dpi low-speed | `0x33FA` | 6 | 120 | 2 | 1 | `0x22` | clear | `1, 833` |
| 2 | 120 dpi high-speed | `0x341C` | 6 | 120 | 2 | 1 | `0x02` | set | `1, 416` |
| 3 | 240 dpi | `0x343E` | 3 | 240 | 4 | 1 | `0x22` | set | `1, 416, 833, 1250` |
| 4 | 80 dpi | `0x3464` | 9 | 80 | 4 | 3 | `0x22` | clear | `1, 1287, 858, 429` |
| 5 | 72 dpi | `0x348A` | 10 | 72 | 6 | 5 | `0x12` | clear | `1, 1000, 800, 600, 400, 200` |
| 6 | 90 dpi | `0x34B4` | 8 | 90 | 3 | 2 | `0x22` | clear | `1, 1100, 555` |
| 7 | 144 dpi, undocumented | `0x34D8` | 5 | 144 | 12 | 5 | `0x32` | clear | `1, 896, 1792, 538, 1433, 179, 1075, 1881, 717, 1613, 358, 1254` |

`VV:2C` is the most important density parameter. It is the number of internal horizontal units per input graphics column, with the firmware using a 720-units-per-inch coordinate grid. This is visible in the common graphics code at `0x36A2`, which clips the requested graphics length by computing `(right_margin - current_x) / VV:2C`, and in the fetch paths at `0x35BA` and `0x3631`, which advance `$8016` by `VV:2C` after consuming graphics data.

Therefore the 72, 80, and 90 dpi modes are generated as distinct spacings on the internal 720-unit grid:

| Density | Internal step | Emulator interpretation |
| --- | --- | --- |
| 72 dpi | 10/720 inch per input byte | exact 1/72-inch column spacing; not an alias for 60 or 120 dpi |
| 80 dpi | 9/720 inch per input byte | exact 1/80-inch column spacing; not an alias for 120 dpi |
| 90 dpi | 8/720 inch per input byte | exact 1/90-inch column spacing; not an alias for 120 dpi |

Using the inferred motor mapping, the native full-step grid is 120 dpi and the half-step grid is 240 dpi. The odd graphics densities are timed while the carriage is moving:

| Density | Step in 720 units | Step in full motor steps | Step in half steps |
| --- | --- | --- | --- |
| 60 dpi | 12 | 2 | 4 |
| 72 dpi | 10 | 5/3 | 10/3 |
| 80 dpi | 9 | 3/2 | 3 |
| 90 dpi | 8 | 4/3 | 8/3 |
| 120 dpi | 6 | 1 | 2 |
| 240 dpi | 3 | 1/2 | 1 |

This is why 80 dpi can land exactly on the half-step grid but 72 and 90 dpi cannot. The printer does not need to stop or step exactly at every dot column; it fires pins at timed positions during carriage motion, with the PTS sensor and the slave 8042-family controller maintaining phase/timing.

The ROM tables for the third-step modes are:

| Mode | Density | Table ROM offset | Raw little-endian words copied to `$8032` | Full-step phase sequence in 720-unit coordinates |
| --- | --- | --- | --- | --- |
| 5 | 72 dpi | `0x34A6` | `1, 1000, 800, 600, 400, 200` | `0, 4, 2, 0, ...` = full-step phases `0, 2/3, 1/3, 0, ...` |
| 6 | 90 dpi | `0x34D0` | `1, 1100, 555` | `0, 2, 4, 0, ...` = full-step phases `0, 1/3, 2/3, 0, ...` |

Those table values are definitely used by the graphics engine, but their exact physical unit is not fully decoded. The pattern and placement in the code make them timing/phase thresholds used by the buffered print path rather than host-visible dot coordinates. They do not look like empirical correction tables for stepper positional error: mode 5 is a straight `1000, 800, 600, 400, 200` progression, and mode 6 is approximately a two-threshold progression `1100, 555`. That regularity is consistent with divider/threshold scheduling and rounding, not with per-phase correction for `1/3` versus `2/3` full-step mechanical error.

The graphics modes use these carriage speeds and derived motor rates:

| Mode | Density | ROM speed selector | Carriage speed | Full-step rate at 1/120 inch | PTS-cycle rate at 4 full steps/cycle | Graphics byte rate |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 60 dpi | `VV:2B=0x02` | 16 in/s | 1920 full steps/s | 480 cycles/s | 960 bytes/s |
| 1 | 120 dpi low-speed | `VV:2B=0x22` | 8 in/s | 960 full steps/s | 240 cycles/s | 960 bytes/s |
| 2 | 120 dpi high-speed | `VV:2B=0x02` | 16 in/s | 1920 full steps/s | 480 cycles/s | 1920 bytes/s |
| 3 | 240 dpi | `VV:2B=0x22` | 8 in/s | 960 full steps/s | 240 cycles/s | 1920 bytes/s |
| 4 | 80 dpi | `VV:2B=0x22` | 8 in/s | 960 full steps/s | 240 cycles/s | 640 bytes/s |
| 5 | 72 dpi | `VV:2B=0x12` | 12 in/s | 1440 full steps/s | 360 cycles/s | 864 bytes/s |
| 6 | 90 dpi | `VV:2B=0x22` | 8 in/s | 960 full steps/s | 240 cycles/s | 720 bytes/s |
| 7 | 144 dpi, undocumented | `VV:2B=0x32` | 12 in/s inferred | 1440 full steps/s inferred | 360 cycles/s inferred | 1728 bytes/s inferred |

The motor drive does not look like analog sine-wave microstepping. The 8042-family slave ROM contains discrete phase/timing tables and emits table bytes to the motor-control ports with `movp3` lookups, `outl p2`, and timer waits (`strt t`, `jtf`). It also watches the PTS input to keep carriage timing aligned. The service document supports this model: the carriage motor is driven through transistor/driver circuitry, with four winding checks from center taps to phase ends, and the PTS board is adjusted for a square-ish timing pulse cycle.

For full-step-aligned graphics modes, dots line up with the motor timing grid, but the code still looks like continuous-motion timed firing, not stop-step-fire. Mode 0 fires every 2 full steps, modes 1 and 2 fire every full step, and mode 3 fires every half step. The nonaligned modes are handled by timed positions between those full-step events.

The per-mode phase tables are copied as little-endian 16-bit words to RAM at `$8032` by the loop at `0x350E`. The common graphics engine uses the table-managed buffered output path beginning at `0x3727`. For emulation, the practical model is to position each received graphics column at `x += 720 / density` internal units and render that byte's vertical pins at that column. Apply adjacent-dot suppression only for modes 2 and 3, matching the `VV:52` bit 0 setup. The firmware's phase tables are carriage/print-timing details; they are evidence that the odd densities are hardware-timed, but a raster emulator can reproduce placement from the 720-unit step values.

For gap-free graphics:

* 7-pin/8-pin graphics commonly use `ESC 1` (7/72 inch) or `ESC 3 20` (20/216 inch) depending on desired overlap.
* 9-pin graphics commonly use `ESC 0` (9/72 inch).

`ESC @` does not cancel graphics bytes already reserved by a graphics command; if it appears inside a graphics data quota it is consumed as graphics data.

## Forms, margins, and tabs

Top-of-form is set to the current physical paper position on power-up/reset or either form-length command. Default form length is 11 inches or 66 default-spaced lines.

Skip-over-perforation can be enabled by DIP 2-3 or `ESC N n`. `ESC N` sets a skip of `n` lines at the bottom of each form; `ESC O`, `ESC @`, and either `ESC C` form-length command cancel or reset it. DIP 2-3 uses a one-inch skip.

Margin settings are absolute physical positions based on the pitch active when set. Later pitch changes do not move the margins. The ROM stores a valid `ESC l` left-margin setting immediately and cancels buffered output. `ESC Q` also cancels buffered output after accepting a valid right margin.

Default horizontal tabs are every 8 spaces. Default vertical tabs are every 2 lines in channel 0. Horizontal tab stops are stored as physical positions using the pitch and left margin active when set. Vertical tab stops are stored in current line spacing units. Later pitch, margin, or line-spacing changes do not move already stored stops.

## Parallel interface

Connector is Centronics-compatible 8-bit parallel.

| Pin | Signal | Direction from printer | Behavior |
| --- | --- | --- | --- |
| 1 | STROBE | In | Pulse width more than 0.5 us; reads data. |
| 2-9 | DATA 1-8 | In | HIGH means logical 1, LOW means 0. |
| 10 | ACKNLG | Out | About 12 us LOW pulse after data received and printer ready for more. |
| 11 | BUSY | Out | HIGH during data entry, printing, off-line, or error. |
| 12 | PE | Out | HIGH when out of paper. Not disabled by `ESC 8`. |
| 14 | AUTO FEED XT | In | LOW adds one line feed after printing. DIP 2-4 can fix equivalent behavior. |
| 16 | 0V | Ground | Logic ground. |
| 17 | CHASSIS GND | Ground | Chassis ground, isolated from logic ground. |
| 19-30 | GND | Ground | Twisted-pair returns. |
| 31 | INIT | In | LOW for more than 50 us resets controller and clears buffer. |
| 32 | ERROR | Out | LOW on paper-end, off-line, or error. |
| 33 | GND | Ground | Same as 19-30. |
| 36 | SLCT IN | In | Data entry possible only when LOW; factory DIP 2-1 setting supports this. |

Pins 13 and 35 are pulled up to +5 V through 3.3K. Pins 15, 18, and 34 are unused.

Normal data entry requires ACKNLG observation or BUSY LOW. If the printer is online and `SLCT IN` is HIGH with `DC1`, data entry is enabled. If online and `DC3` has deselected the printer, data may still be acknowledged but input bytes are lost until `DC1`.

`ESC 8` disables paper-out contribution to BUSY and ERROR on pins 11 and 32, but pin 12 PE still indicates paper out, so hosts that monitor PE will still stop.

## Service and error behavior

Beeper/error patterns from Sams service data:

| Pattern | Meaning |
| --- | --- |
| Three short tones and one long tone | Overvoltage detection. |
| Three short tones repeated twice | Printhead malfunction, loose head cable, or head not seated. |
| Four long tones | One or more printhead driver transistors Q6-Q14 shorted, or damaged printhead. |
| Five short tones repeated five times | Paper empty signal. If paper is loaded, check PE sensor path. |

Main service components named in the service manual:

* FMBD board contains main microprocessor IC 3B.
* Slave microprocessor IC 9B is checked for carriage/paper-feed timing behavior.
* Main microprocessor clock is 10 MHz at IC 3B pins 30/31.
* Slave microprocessor clock is 11 MHz at IC 9B pins 2/3.
* Printhead solenoids should measure about 20 ohms.
* Printhead drive supply is 24 V at CN5 pins 14-16.
* Paper-feed motor drive check is 22.5 V at CN4 pins 11-12 while printing.

These details are mostly useful if the emulator models diagnostics, audible errors, or low-level board behavior.

## Dreamulator audit notes

The command verification ledger is maintained in
`docs/fx80_command_rom_audit.md`. That file separates current Dreamulator
behavior from manual-derived behavior and ROM-disassembly-confirmed behavior.

Dreamulator's FX-80 path is in `../dreamulator/src/print/escp.cpp`,
`../dreamulator/src/print/dotrender.cpp`, `../dreamulator/src/print/printer.cpp`,
and `../dreamulator/src/print/fontfx80.cpp`.

Current Dreamulator state:

* It already has an Epson FX profile with a 720 dpi render grid and 120 dpi
  draft character grid, which matches the firmware's 720-units-per-inch
  horizontal coordinate system.
* `fontfx80.cpp` contains ROM-extracted Roman and Italic draft glyph tables
  from the uPD7810 ROM, plus the ROM prefix/attribute bytes.
* `ESC 4` and `ESC 5` select the ROM-extracted Italic and Roman glyph tables
  for FX-80 text rendering.
* `ESC p` proportional mode uses the ROM prefix byte's start/end columns for
  FX-80 glyph clipping and character advance. Proportional text uses 120 dpi
  horizontal units and is rendered as emphasized text.
* For the FX-80 model, `ESC !` Master Select maps the FX-80 pitch/weight bits
  directly: elite, compressed, emphasized, double-strike, and expanded. It
  does not treat `0x02` as proportional or `0x40` as Italic; LQ-family ESC/P
  models keep their separate Master Select meanings.
* 8-pin graphics treats bit 7 as the top pin and bit 0 as the bottom pin.
* 9-pin `ESC ^` graphics treats the first byte as pins 1-8 with bit 7 at the
  top, and the second byte's bit 7 as pin 9.
* `ESC *` supports modes 0-7; mode 7 is the ROM-supported 144 dpi mode.
* `ESC Y`, `ESC Z`, and `ESC *` modes 2 and 3 apply adjacent-dot suppression
  by suppressing dots whose same-row bit was present in the immediately
  previous input column.
* `ESC ? s n` graphics-command reassignment is implemented for `K`, `L`, `Y`,
  and `Z`, with reassignment targets 0-7.
* `ESC ^ d n1 n2` maps `d=0` to 60 dpi and `d=1` to 120 dpi. The ROM
  also accepts `d=2` and `d=3`, matching `ESC *` modes 2 and 3.
* `ESC <` sets one-line unidirectional left-to-right printing. The one-line
  flag is consumed at the next printed line boundary. Blank LF, reverse LF, and
  repeated vertical feeds before output do not consume it. `ESC U n` controls
  persistent unidirectional mode independently.
* Graphics output is marked as forced left-to-right and does not count as a
  right-to-left bidirectional text pass at the following carriage return.
* Text output uses a logical pending-line buffer. Text characters are positioned
  and stored with a style snapshot as they arrive, then rendered on CR, LF, FF,
  immediate feed, graphics output, or final flush. `CAN` discards the pending
  text line, `DEL` removes the most recent pending text character, and accepted
  margin changes cancel pending buffered text before changing the margin.
* `ESC 6`/`ESC 7`, `ESC I`, `ESC =`/`ESC >`/`ESC #`, `DC1`/`DC3`, `DEL`,
  vertical tabs, `ESC %`, and `ESC :` are modeled for the FX-80 path.
  `ESC &` currently follows the FX manual's 12-byte download-character format,
  but the Version 2.00 ROM dispatch points to an LQ-style variable-width
  handler; treat Dreamulator's current `ESC &` behavior as manual-faithful, not
  ROM-verified. For the generic LQ path, LQ-format download-character
  definitions are consumed for stream sync, but
  custom LQ glyph rendering is not yet implemented because the current LQ
  renderer is still generic.

Remaining known gaps:

* The FX-family `ESC &` implementation should stay on the documented 12-byte
  format by default. The Version 2.00 ROM dispatch anomaly is documented in
  `docs/fx80_command_rom_audit.md`.
* Paper/status behavior for `ESC 8`, `ESC 9`, `DC1`, and `DC3` is not modeled
  beyond stream-level command consumption.
* The text-line buffer is logical rather than a byte-for-byte model of the
  firmware RAM layout. That is enough for visible `CAN`, `DEL`, margin
  cancellation, and direction behavior, but not for low-level RAM diagnostics.
* The visual model currently uses ideal column placement plus random impact
  jitter. It does not model deterministic carriage phase error for the 72/80/90
  dpi third-step graphics modes. That is acceptable for a normal raster printer
  emulator, but not for a high-fidelity mechanical simulation.

## Implementation checklist

1. Byte stream parser with normal, ESC, parameter, tab-list, and graphics-data states.
2. Text state with pitch/weight/style booleans, priority masking, and Master Select reset behavior.
3. Page model with current x/y, top-of-form, form length, margins, skip-over-perf, tabs, CR/LF behavior, and paper-out state.
4. Font renderer using `docs/fx80_rom_glyphs.csv` or direct ROM extraction at `0x17A3`.
5. International remapping before glyph lookup, including Italic offset handling.
6. User-defined RAM character table using the same attribute plus 11-byte format as ROM glyphs.
7. Graphics renderer with density scaling, adjacent-dot suppression in modes 2 and 3, and two-byte 9-pin mode.
8. Parallel-port status model for BUSY, ACKNLG, PE, ERROR, INIT, SLCT IN, DC1/DC3, and `ESC 8/9`.
9. Optional service/error beeper model.
