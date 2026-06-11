# Epson FX-80 ROM analysis

This repository contains working reverse-engineering notes, tools, and
reference documents for the Epson FX-80 printer firmware.

It exists to support FX-80 printer emulation in Dreamulator:

https://github.com/RealDeuce/Dreamulator/

The goal is not to create a generic printer reference.  The goal is to keep the
evidence needed to implement a ROM-derived FX-80 output path: resident fonts,
pitch selection, print effects, user-defined character behavior, graphics modes,
DIP switch behavior, and command dispatch details.

## Why this exists

Dreamulator already has printer output paths for other printers where the
rendering behavior is derived from the original device rather than from a
generic substitute font.  The FX-80 should follow the same model.

The FX-80 firmware ROM contains enough of the printer behavior to identify:

- the resident bitmap font data and glyph table layout;
- the dispatch tables and command parsers;
- 10 cpi, 12 cpi, condensed, and proportional pitch handling;
- the text-mode priority resolver (Elite > Proportional > Emphasized >
  Compressed > Pica);
- emphasized, double-strike, expanded, condensed, underline, superscript,
  subscript, italic, and slashed-zero behavior;
- user-defined character download and rendering, including the `ESC &` format
  split between the documented 12-byte FX format and the live LQ-style
  three-plane format in the Version 2.00 ROM;
- `ESC *` graphics mode dispatch and all eight density modes;
- `ESC ?` graphics command reassignment;
- international character set remapping;
- startup defaults, DIP switch sampling, and reset behavior;
- the 8042-family slave controller ROM.

Keeping the documents, disassembly, scripts, and trace notes together makes the
Dreamulator implementation reproducible.  The original ROM dumps are not
tracked in this public repository; keep any locally obtained dumps outside git
or under the ignored filenames listed below.  When the emulator needs a
behavioral detail, this repository should show whether that detail is already
known, where it came from, and which ROM offsets are useful for confirming it.

## Repository contents

| Path | Purpose |
| --- | --- |
| `docs/fx80_emulator_notes.md` | Detailed emulator implementation notes covering hardware model, reset defaults, DIP switches, all command behaviors, font layout, graphics modes, and pitch/effect interactions.  Summarized from the local manuals and ROM analysis so an implementer should not need to reopen the PDFs. |
| `docs/fx80_command_rom_audit.md` | Firmware-derived command dispatch inventory, decoded dispatch tables, ROM anchor addresses, and per-command verification status. |
| `docs/fx80_rom_glyphs.csv` | Decoded resident glyph table data extracted from the firmware ROM. |
| `docs/fx80_upd7810_disassembly.lst` | Disassembly listing of the main firmware ROM. |
| `fx80__uv.pdf` | FX-80 tutorial volume (examples and behavioral explanations). |
| `fx80__u1.pdf` | FX-80 reference volume (appendices A-K). |
| `fx80__sl.pdf` | FX-80 one-page specification sheet. |
| `Sams_Computerfacts_Epson_FX-80_Printer_1985_Howard_Sams_text.pdf` | Service data, board layout, and fault details. |
| `tools/generate_fx80_disassembly.py` | Script to generate the disassembly listing from the ROM dump. |

## ROM summary

The main firmware image used for this analysis was a 16 KiB dump read as a
27C128-class device.  It contains a Version 2.00 identification string.

The CPU is NEC uPD7810 family.  The disassembly listing was generated locally
from a locally supplied dump using:

```sh
python3 tools/generate_fx80_disassembly.py
```

For local regeneration, place the main firmware dump at the ignored path
`epson_8426k9_m1206ba029_read_as_27c128.bin`.  The companion ignored path
`epson_fx_c42040kb_8042ah.bin` is for the 2 KiB 8042-family slave controller
dump used for interface/keyboard handling.

## Key ROM structures

The resident glyph data lives at `0x17A3..0x23A2`, organized as 256 entries of
12 bytes each.  Byte 0 is an attribute/prefix byte; bytes 1-11 are inverted
column data.

The main command dispatch is at `0x095E..0x09C4`, with three dispatch tables:

- Low control codes: `0x0970`
- Explicit ESC commands: `0x09FD`
- Uppercase `ESC @..Z` compact table: `0x09C7`

The `ESC *` graphics mode dispatch is at `0x3371..0x339A`, with eight mode setup
entries covering all standard graphics densities.

The text-mode priority resolver at `0x3AF0..0x3B34` enforces the pitch/effect
precedence hierarchy documented in the FX-80 manuals.

## How this should be used by Dreamulator work

Use this repository as the evidence pack for the FX-80 implementation:

1. Use a locally supplied Version 2.00 firmware dump as the canonical firmware
   image when regenerating derived artifacts.
2. Use `docs/fx80_rom_glyphs.csv` and the glyph table offsets to validate
   decoded glyph shapes.
3. Use `docs/fx80_emulator_notes.md` for command behavior, hardware model,
   reset defaults, and pitch/effect interaction rules.
4. Use `docs/fx80_command_rom_audit.md` for dispatch addresses, per-command ROM
   verification status, and known handler traces.
5. When a new emulator behavior is unclear, add the new trace and derived output
   here first, then port the behavior into Dreamulator.
