---
description: De-overlap and tidy one schematic sheet (readability pass)
argument-hint: "[sheet: root | amp — default: both, one at a time]"
---

Run a readability pass on **$ARGUMENTS** (if blank, every sheet, one at a
time). Follow the `schematic-readability` skill, then verify with
`schematic-verify`.

The two sheets are `kit_18v_amp_hat_ma2304.kicad_sch` (root) and
`kit_18v_amp_hat_ma2304_amp.kicad_sch` (the amplifier sheet, shown twice as
AMP_CH1 / AMP_CH2 — one edit fixes both channels).

Steps:

1. `load_toolset(["sch_analysis", "sch_components", "sch_wiring", "sch_batch", "sch_export"])`.
2. Checkpoint: `snapshot_project` and `set_visual_baseline` for the sheet.
3. Record the starting numbers: `check_schematic_overlaps`, `find_orphan_items`,
   `validate_wire_connections`, `run_erc`.
4. Diagnose: `check_schematic_overlaps`, an inline
   `render_schematic_png { width_px: 3200 }`, and an `export_schematic_svg` for
   text geometry.
5. Fix in the safe order — `reset_schematic_field_positions` first, then label
   rotation/offsets, then symbol moves only where there are no wires (or where
   you will re-wire). Never move a wired symbol without repairing wires. Keep
   the 1.27 mm grid.
6. Verify after each step with the `schematic-verify` checklist. Revert any step
   that regresses connectivity before continuing.
7. Report: per sheet, the overlap counts before/after, what you moved, any
   wiring you had to repair, and anything you left deliberately.
