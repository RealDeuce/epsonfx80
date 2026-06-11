#!/usr/bin/env python3
"""Generate a mixed uPD7810 disassembly for the FX-80 Version 2.00 ROM."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "epson_8426k9_m1206ba029_read_as_27c128.bin"
OUT = ROOT / "docs" / "fx80_upd7810_disassembly.lst"
UNIDASM = ROOT.parent / "mame" / "unidasm"

GLYPH_BASE = 0x17A3
GLYPH_SIZE = 12
GLYPH_COUNT = 256
GLYPH_END = GLYPH_BASE + GLYPH_SIZE * GLYPH_COUNT
FILL_START = 0x3FB6

DATA_REGIONS = [
    (0x0871, 0x08B3, "version/copyright text; terminator byte at 08B3 is shared with code"),
    (0x0970, 0x099D, "low-control dispatch table, 15 three-byte entries"),
    (0x09C7, 0x09FD, "uppercase ESC compact table, 27 two-byte entries"),
    (0x09FD, 0x0A6F, "explicit ESC dispatch table, 38 three-byte entries"),
    (0x0AF7, 0x0B7B, "international character remap table"),
    (GLYPH_BASE, GLYPH_END, "ROM glyph records, 256 12-byte entries"),
    (0x33F6, 0x33FA, "graphics phase table for mode 0"),
    (0x3416, 0x341C, "graphics phase table for mode 1"),
    (0x3438, 0x343E, "graphics phase table for mode 2"),
    (0x345A, 0x3464, "graphics phase table for mode 3"),
    (0x3480, 0x348A, "graphics phase table for mode 4"),
    (0x34A6, 0x34B4, "graphics phase table for mode 5"),
    (0x34D0, 0x34D8, "graphics phase table for mode 6"),
    (0x34F4, 0x350E, "graphics phase table for mode 7"),
    (0x38FF, 0x390F, "ESC ? graphics reassignment pointer table, 8 two-byte entries"),
    (0x3D6C, 0x3D82, "default/configuration jump table, 11 two-byte entries"),
    (0x3E00, 0x3E16, "default/configuration jump table, 11 two-byte entries"),
    (FILL_START, 0x4000, "0xFF fill"),
]


def disassemble(skip: int, count: int) -> str:
    proc = subprocess.run(
        [
            str(UNIDASM),
            str(ROM),
            "-arch",
            "upd7810",
            "-basepc",
            hex(skip),
            "-skip",
            str(skip),
            "-count",
            str(count),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


def write_data(out, rom: bytes, start: int, end: int, description: str) -> None:
    out.write(f"\n; ---- DATA {start:04X}-{end - 1:04X}: {description} ----\n")
    if start == GLYPH_BASE and end == GLYPH_END:
        for code in range(GLYPH_COUNT):
            addr = GLYPH_BASE + code * GLYPH_SIZE
            entry = rom[addr : addr + GLYPH_SIZE]
            hex_bytes = " ".join(f"{byte:02x}" for byte in entry)
            out.write(f"{addr:04x}: {hex_bytes:<35} ; glyph {code:02x}\n")
        return

    for addr in range(start, end, 16):
        chunk = rom[addr : min(addr + 16, end)]
        hex_bytes = " ".join(f"{byte:02x}" for byte in chunk)
        out.write(f"{addr:04x}: {hex_bytes}\n")


def main() -> None:
    rom = ROM.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()

    with OUT.open("w", encoding="ascii", newline="\n") as out:
        out.write("; Epson FX-80 Version 2.00 main ROM mixed disassembly\n")
        out.write(f"; Source: {ROM.name}\n")
        out.write(f"; SHA256: {digest}\n")
        out.write("; CPU: NEC uPD7810, disassembler: MAME unidasm\n")
        out.write(";\n")
        out.write("; Confirmed regions:\n")
        out.write(";   0000-0870  code\n")
        out.write(";   0871-08B2  version/copyright text\n")
        out.write(";   08B3-096F  code\n")
        out.write(";   0970-099C  low-control dispatch table\n")
        out.write(";   099D-09C6  code\n")
        out.write(";   09C7-09FC  uppercase ESC compact table\n")
        out.write(";   09FD-0A6E  explicit ESC dispatch table\n")
        out.write(";   0A6F-0AF6  code\n")
        out.write(";   0AF7-0B7A  international character remap table\n")
        out.write(";   0B7B-17A2  code\n")
        out.write(";   17A3-23A2  256 12-byte ROM glyph records\n")
        out.write(";   23A3-33F5  code and inline tables\n")
        out.write(";   33F6-350D  graphics phase tables interleaved with setup code\n")
        out.write(";   350E-38FE  code and inline tables\n")
        out.write(";   38FF-390E  ESC ? graphics reassignment pointer table\n")
        out.write(";   390F-3D6B  code and inline tables\n")
        out.write(";   3D6C-3D81  default/configuration jump table\n")
        out.write(";   3D82-3DFF  code and inline tables\n")
        out.write(";   3E00-3E15  default/configuration jump table\n")
        out.write(";   3E16-3FB5  code and inline tables\n")
        out.write(";   3FB6-3FFF  0xFF fill\n")
        out.write(";\n")
        out.write("; The byte at 08B3 is both the printable '@' terminator for the\n")
        out.write("; version/copyright text and the opcode byte for CALL $00D3.\n")
        out.write("; It is emitted as code so the ESC i entry stays synchronized.\n")

        pos = 0
        for start, end, description in DATA_REGIONS:
            if pos < start:
                out.write(f"\n; ---- CODE {pos:04X}-{start - 1:04X} ----\n")
                out.write(disassemble(pos, start - pos))
            write_data(out, rom, start, end, description)
            pos = end

        if pos < len(rom):
            out.write(f"\n; ---- CODE {pos:04X}-{len(rom) - 1:04X} ----\n")
            out.write(disassemble(pos, len(rom) - pos))


if __name__ == "__main__":
    main()
