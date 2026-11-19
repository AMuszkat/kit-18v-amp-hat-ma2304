# kit_18v_amp_hat_ma2304 — working notes

KiCad 10 project for a **Raspberry Pi HAT** carrying two **MA2304** Class-D
amplifiers (`MA2304_1`, `MA2304_2`) and an **MP3428** boost converter (`U1`,
`L1`, `Q1`). It plugs onto the Pi through a bottom-mounted 40-way socket (`P1`)
and the amplifier outputs leave on two 4-way terminal blocks (`Jout1`,
`Jout2`). Hierarchical schematic: a root sheet plus one **amplifier sheet used
twice** (channels `AMP_CH1` / `AMP_CH2`).

## Hard rule: never hand-edit KiCad files

`.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_prl`, `.kicad_sym`,
`.kicad_mod` and the library tables are serialized object graphs with UUIDs and
cross-references. A text edit corrupts them.

**Every change goes through the Konnect MCP server** (registered in `.mcp.json`;
`.claude/settings.json` also denies `Edit` on those paths as a backstop). See the
global `konnect` skill for the full operating rules. Reads for analysis are fine
(exported netlist / PDF / SVG, or `kicad-cli`); editing is not.

## Headless from the command line

The whole workflow runs without a GUI:

- schematic editing is **file-based** in Konnect (no `eeschema` needed);
- exports and checks go through `kicad-cli` (`sch export svg|pdf|netlist`, `sch erc`);
- the MCP server is `konnect` over stdio (`.mcp.json`, and `opencode.json` for
  the OpenCode CLI).

Check the wiring with `konnect --version` and `konnect status`.

## Project layout

| Path | What |
|---|---|
| `kit_18v_amp_hat_ma2304.kicad_sch` | Root sheet — Pi header `P1`, boost converter (`U1`/`L1`/`Q1`), the channel series resistors and the two sheet symbols |
| `kit_18v_amp_hat_ma2304_amp.kicad_sch` | Sub-sheet **AMP_CH1 / AMP_CH2** — one MA2304 and its output filter + decoupling, instantiated twice |
| `kit_18v_amp_hat_ma2304.kicad_pcb` | Board, 4 layers (the connectivity ground truth) |
| `3dmodels/` | STEP models, referenced as `${KIPRJMOD}/3dmodels/…` |
| `tools/schematic-conversion/` | Turns the Altium `.SchDoc` sheets into these two `.kicad_sch` files (`build.sh`) |
| `render/pipeline/` | Blender/3D hero-render pipeline |

## Current focus: schematic readability

The sheets are electrically complete — the netlist matches the board on
**109/109 nets** and designator parity is exact (137/137) — but they are **not
pleasant to read**. The native Altium import puts field text where the original
put it: References and Values pile up, symbol bodies crowd their neighbours, and
a couple of wire ends dangle.

Use the **`schematic-readability`** skill to diagnose and fix this and the
**`schematic-verify`** skill after every pass. `/tidy-schematic` runs the whole
loop on one sheet.

Measured starting point (Konnect `check_schematic_overlaps`, symbol-body level;
`find_orphan_items` / `validate_wire_connections`):

| Sheet | Symbol overlaps | Dangling wire ends |
|---|---|---|
| root | 5 | 2 |
| AMP_CH1/CH2 (`…_amp`) | 7 | 0 |

## Every session

1. `load_toolset` the schematic toolsets you need — `list_toolboxes` first.
2. Take a checkpoint before a batch of edits: `snapshot_project` and
   `set_visual_baseline`.
3. Look at the sheet — `render_schematic_png` with `inline: true` — before and
   after. Geometry checks do not catch text collisions.
4. Never move a **wired** symbol casually: `move_schematic_component` moves the
   symbol and leaves its wires behind. Prefer field/label moves, or re-verify
   connectivity afterwards.

## Conventions

- **1.27 mm grid**, always — off-grid pins break wire connections silently.
- Rails as **power symbols** (`add_power_symbol`), named signals as **net labels**.
- Label rotation follows the pin's `orientation_degrees` (from
  `get_schematic_pin_locations`) or the text reads back over the symbol.
- Keep changes scoped to one sheet and verify before moving on.
- The two channels are separate nets (`…_1` / `…_2`); never join a signal across
  `AMP_CH1` and `AMP_CH2` — the board keeps them distinct.
