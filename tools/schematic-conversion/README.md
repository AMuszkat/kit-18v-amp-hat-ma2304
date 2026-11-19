# Schematic conversion tools

Turns the original Altium `.SchDoc` sheets of `kit_18v_amp_hat_ma2304` into
**KiCad 10 schematics with real symbols, a real hierarchical netlist and a
de-branded title block**.

    ./build.sh [OUTDIR]        # default OUTDIR: the repo root

Everything runs head-less from the command line; no KiCad GUI session is
touched.

## Requirements

- **KiCad 10.99 nightly** `kicad-cli`, for `sch import --format altium` and
  `sch downgrade`. The stable 10.0.7 `kicad-cli` has no `sch import`. Set
  `KICAD_CLI=/path/to/nightly/kicad-cli`; otherwise a `kicad-cli` on `PATH`
  that supports `sch import` is used.
- `python3`, and the stable `kicad-cli` 10.0.7 on `PATH` (for the verification
  netlist export).
- `ALT_SOURCES=/path/to/altium/schematics` — the folder holding the Altium
  `.SchDoc` / `.PrjPcb` files (the source is not part of this repository).

## What it does

1. **`kicad-cli sch import --format altium`** on the Altium root sheet. KiCad's
   own importer resolves the symbols, the supply rails (as named power symbols,
   so `PVDD`, `PVDD_MA`, `MP_AGND`, `GND`, … stay distinct) and the two-channel
   hierarchy: the amplifier sheet is instantiated twice as **AMP_CH1** /
   **AMP_CH2**, and its Altium ports become real hierarchical labels + sheet
   pins.

   This is deliberately *not* the `altium2kicad` route used for the other kit
   boards: on a sheet that is instantiated twice, that route emits the child
   ports as **global** labels, which shorts channel 1 to channel 2. KiCad's
   importer produces the correct per-channel nets.

2. **`sch downgrade --target "KiCad 10.0"`** to the format this project and the
   installed 10.0.7 tool-chain use.

3. **`restore_instances.py`** — the downgrade flattens the per-instance
   references (both channels would be called `CflyA0`). This restores the
   board's own channel suffixes: `X_1` for AMP_CH1, `X_2` for AMP_CH2.

4. **Rename + de-brand** — the child sheet is renamed to
   `kit_18v_amp_hat_ma2304_amp.kicad_sch` (the name the board already records in
   its sheet path), the title blocks are replaced with neutral ones
   (`debrand_sch.py`) and the embedded vendor logo bitmap and vendor fields are
   dropped.

5. **`verify.py`** — checks designator parity and the netlist against the board
   (net by net, by pad set) and scans the schematics for vendor text.

## The result

Against the board in this repo:

    designator parity: 137 / 137
    board nets with an identical schematic pad set: 109 / 109
    schematic multi-pad nets without a board match: none
    vendor text: none

## Files

    build.sh              the pipeline, one command
    restore_instances.py  re-annotate the two sheet instances
    debrand_sch.py        neutral title block, no vendor image/fields
    verify.py             board vs schematic, net by pad set
