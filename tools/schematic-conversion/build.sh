#!/usr/bin/env bash
# Convert the Altium .SchDoc sheets of kit_18v_amp_hat_ma2304 into KiCad 10
# schematics with real symbols, a real hierarchical netlist and a de-branded
# title block.
#
#   ./build.sh [OUTDIR]          default OUTDIR: this repo's root
#
# It drives KiCad's OWN Altium importer (`kicad-cli sch import --format altium`).
# That subcommand exists only in the KiCad 10.99 nightly, so KICAD_CLI must point
# at a nightly `kicad-cli` (see README.md). The nightly writes a 10.99-format
# file; `sch downgrade --target "KiCad 10.0"` brings it back to the format the
# rest of this project (and the installed 10.0.7 Konnect toolchain) uses.
#
# Stages
#   1. import the Altium root sheet; the importer pulls in the child amp sheet
#      and builds the two-channel hierarchy (AMP_CH1 / AMP_CH2) for you
#   2. downgrade to the KiCad 10.0 format
#   3. restore the per-instance channel references the downgrade flattened
#      (X on the AMP_CH1 path -> X_1, on AMP_CH2 -> X_2, matching the board)
#   4. rename the child sheet to the name the board already records, de-brand
#      both title blocks and drop the vendor logo bitmap
#   5. export the netlist and compare every board net against the schematic
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$(realpath -m "${1:-$REPO}")"
ALT="${ALT_SOURCES:-}"          # set to the folder holding the Altium .SchDoc files
BOARD="${BOARD:-$REPO/kit_18v_amp_hat_ma2304.kicad_pcb}"
[ -n "$ALT" ] || {
    echo "set ALT_SOURCES to the folder with the Altium .SchDoc / .PrjPcb files" >&2
    exit 1; }

ROOT_NAME="kit_18v_amp_hat_ma2304"
CHILD_SRC="MA2304XX_AMP.kicad_sch"            # name the importer gives the child
CHILD_NAME="${ROOT_NAME}_amp.kicad_sch"       # name the board already records
ROOT_TITLE="kit_18v_amp_hat_ma2304 - Raspberry Pi HAT, MA2304 amplifiers"
CHILD_TITLE="kit_18v_amp_hat_ma2304 - Amplifier (MA2304)"

# --- locate a kicad-cli that can import Altium schematics -------------------
find_cli() {
    local c
    for c in "${KICAD_CLI:-}" "$(command -v kicad-cli 2>/dev/null)"; do
        [ -n "$c" ] && [ -x "$c" ] || continue
        if "$c" sch import --help >/dev/null 2>&1; then printf '%s\n' "$c"; return 0; fi
    done
    return 1
}
KICAD_CLI="$(find_cli || true)"
[ -n "$KICAD_CLI" ] || {
    echo "no kicad-cli with 'sch import': set KICAD_CLI to a KiCad 10.99 nightly" >&2
    exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- 1. import --------------------------------------------------------------
echo "== stage 1: KiCad Altium import ($("$KICAD_CLI" --version))"
"$KICAD_CLI" sch import --format altium \
    -o "$WORK/$ROOT_NAME.kicad_sch" "$ALT/KIT_18V_AMP_HAT_MA2304_Main.SchDoc"

# --- 2. downgrade to KiCad 10.0 ---------------------------------------------
echo "== stage 2: downgrade to KiCad 10.0"
"$KICAD_CLI" sch downgrade --target "KiCad 10.0" -o "$WORK/dg" \
    "$WORK/$ROOT_NAME.kicad_sch"

# --- 3. restore per-instance channel references -----------------------------
echo "== stage 3: restore per-instance references"
python3 "$HERE/restore_instances.py" "$WORK/dg/$ROOT_NAME.kicad_sch"

# --- 4. rename, de-brand ----------------------------------------------------
echo "== stage 4: rename child sheet and de-brand"
mv "$WORK/dg/$CHILD_SRC" "$WORK/dg/$CHILD_NAME"
python3 - "$WORK/dg/$ROOT_NAME.kicad_sch" "$CHILD_SRC" "$CHILD_NAME" <<'PY'
import sys
p, old, new = sys.argv[1:4]
s = open(p, encoding='utf-8').read()
open(p, 'w', encoding='utf-8').write(s.replace(
    f'(property "Sheetfile" "{old}"', f'(property "Sheetfile" "{new}"'))
print(f"  Sheetfile {old} -> {new}")
PY
python3 "$HERE/debrand_sch.py" "$WORK/dg/$ROOT_NAME.kicad_sch" "$ROOT_TITLE"
python3 "$HERE/debrand_sch.py" "$WORK/dg/$CHILD_NAME" "$CHILD_TITLE"

# --- 5. deliver and verify --------------------------------------------------
echo "== stage 5: install and verify"
install -m 644 "$WORK/dg/$ROOT_NAME.kicad_sch" "$OUT/$ROOT_NAME.kicad_sch"
install -m 644 "$WORK/dg/$CHILD_NAME" "$OUT/$CHILD_NAME"

"$KICAD_CLI" sch export netlist --format kicadxml -o "$WORK/$ROOT_NAME.netlist.xml" \
    "$OUT/$ROOT_NAME.kicad_sch" >/dev/null 2>&1 || true
BOARD="$BOARD" python3 "$HERE/verify.py" "$WORK/$ROOT_NAME.netlist.xml" "$OUT"

echo
echo "done -> $OUT/$ROOT_NAME.kicad_sch"
