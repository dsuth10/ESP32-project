# Enclosure dimension and feature reconciliation

25 October 2026. Source review only; no model, export or generator was changed.
The existing SolidCraft design remains a modelling pilot. This review does not
establish physical fit, print readiness or a completed enclosure migration.

## Evidence and coordinate basis

- **G:** [battery-only Blender generator](../../../generate_case_battery_only.py),
  especially constants and `build_case_bottom` / `build_case_top`. These are
  model inputs and cutter dimensions, not freshly measured hardware.
- **S:** [saved native pilot](ESP32-S3-enclosure-pilot.solidcraft), inspected
  read-only as a ZIP archive (`document.json`), and [build requests](pilot-build.json).
  The saved document agrees with the requests on its user parameters and seven
  features. [Earlier local CAD checks](README.md#verified-locally) are historical
  evidence; they were not rerun here.
- **D:** [manufacturer outline drawing](../ES3C28P_Size.pdf), revision V1.0,
  11 June 2025; visually checked against [the existing rendering](../drawing_300dpi.png).
- **P:** [manufacturer specification](../ES3C28P_Specification.pdf), V1.0,
  14 June 2025; relevant pages 6-7 and 13. Pages 7 and 13 were rendered and
  visually inspected during this review.
- **T:** [local manufacturer STEP assembly](../3d_model/ES3C28P_3D/ES3C28P_3D.step).
  Its header identifies an Open CASCADE STEP export dated 10 June 2025 and its
  units include millimetres. Product records include `PCB`, `Board`, `SD_CARD1`,
  `User_Library-USB-TYPE-C20` and `User_Library-MIC2716`. No CAD-kernel import,
  transformed component measurement or interference calculation was performed;
  this file has not independently validated the dimensions below.

G centres the PCB in X/Y with its underside at Z = 0 mm; its case floor is
Z = -15 mm. S starts its base at Z = 0 mm with an internal floor at 2 mm.
Front/back drawing views can reverse apparent left/right. Register the board
outline, hole centres and USB end before transferring connector coordinates.
Do not combine these coordinate systems without an explicit transform.

## Dimension and feature matrix

All dimensions are in millimetres. Cutter sizes describe modelling operations,
not guaranteed final aperture sizes.

| Item | Manufacturer / existing generator evidence | Saved SolidCraft pilot | Consequence / next evidence |
| --- | --- | --- | --- |
| PCB footprint and corners | D: 50 × 86, corner radius 3.5. G: 50 × 86 × 1.6. | `board_width=50`, `board_length=86`; no board reference body. | Footprint agrees. Check actual board revision and connector protrusions before accepting its envelope. |
| Mounting pattern | D: 42 × 78 centres, four holes diameter 3.2; G: centres (±21, ±39), model holes diameter 3.2. | No mounting holes/bosses. | Pattern agrees. Register it as construction geometry before adding supports. |
| Wall, clearance and footprint | G: wall 2, per-side clearance 0.4; cavity 50.8 × 86.8 and outside 54.8 × 90.8. | Same inputs and expressions; exterior radius 6, derived inner radius 4. | Pilot footprint agrees with generator. Clearance remains a design allowance until a printer/material fit coupon is checked. |
| Display stack and opening | D/P: glass/touch outline 50 × 69.2; active area 43.2 × 57.6; visible area 43.6 × 58.05. G: glass stack height 4.3 above PCB top; recess cutter 50.8 × 70; window cutter 44.5 × 59.5. | Flat 2 mm lid, no recess/window. | Transfer the display seat and window as separate features; preserve touch access and avoid screen compression. Confirm offsets and edge overlap against the actual assembly. |
| Board/module thickness | D side view: 1.6 PCB, 5.9 front stack datum and 4.7 maximum rear SMD, 10.6 total. P page 7 instead lists 5.60 module depth. | `base_height=18` is explicitly provisional. | Manufacturer table/drawing conflict: use an assembly envelope and physical measurement; do not size the cavity from the 5.60 table entry alone. |
| Overall case height | G: floor -15, PCB top 1.6, bottom height 16.6, top height 5: outer shell span 21.6. | Base 18, lid 2: nominal closed stack 20. Saved exploded lid is at Z = 30-32 because `preview_gap=12`. | Heights are different designs. The 12 mm display gap is not battery space or assembly clearance. Define the complete Z stack before choosing a replacement height. |
| USB access | G: receptacle model 9 × 7.5 × 3.2 at (0, -43, -1.6); bottom opening cutter 12.5 × 6 × 5.5 centred at (0, -45.4, -1.8). T contains a USB Type-C part. | No opening. | Need actual plug overmould, insertion clearance and cable bend envelope, beyond the socket model. |
| MicroSD access | G: socket model 15 × 14.5 × 1.8 at (23.5, 7.97, -0.9); side cutter 8 × 15.5 × 3.8 plus cylindrical finger relief. T contains an SD part. | No slot/relief. | Verify which edge is accessed after datum registration, card protrusion and finger travel; do not mirror coordinates from a back view by assumption. |
| Reset / boot access | G: X = -11.56 / 11.57, Y = -39.74; button-access cutters diameter 3.2. D provides corresponding offsets from the USB-end edge. | No access holes. | Check reach, actuator travel and access with the selected fastening layout. |
| Microphone access | G: lid cutter diameter 1.5 at (15, 38.5, 4.1). D labels MIC; T contains a microphone part. | No opening. | Verify position/orientation before transfer; acoustic performance needs a physical application test. |
| Battery envelope / restraint | G assumes a 30 × 49 × 6 cell and an 34 × 62 × 8 allocated pocket, with 5 component gap. The cell is represented, but no dedicated restraint feature is created. | No battery reference or restraint. | Measure the actual cell including protection board, lead exit, connector and bend space. Design retention that does not compress the cell; clearance alone does not restrain it. |
| Bosses and fastening | G: boss radius 5; through-hole diameter 3.4; lower round bore diameter 6.8; top bore diameter 6.2. | No bosses, holes, locating lip or fastening. | Choose actual screw/nut/insert and assembly method before copying bores. A round lower bore is not evidence of an anti-rotation nut trap. Check wall/boss intersections. |

## Missing physical measurements and decisions

Existing files already supply nominal PCB, display and hole-pattern dimensions.
The unresolved evidence is the actual board revision and assembled thickness;
connector/plug/card reach; battery-plus-wiring envelope; available fasteners;
and the chosen printer/material's fit allowance. Record measured values separately
from nominal drawing values, including the datum and measuring method.

The display window style, battery restraint and lid-fastening method are design
choices. They should be settled using the above envelopes before detailed cuts.
The generator's simplified electronics are reference geometry, not complete
component keep-outs or proof of thermal/acoustic performance.

## Next bounded CAD slices on a copied candidate

1. Preserve the current native pilot and exports. Create a separately named
   candidate and verify the active document before editing. The original
   [save/export sequence](pilot-check-save.json) uses fixed filenames and must
   not be replayed over edited work.
2. In the candidate, add named construction datums for the PCB, mounting pattern,
   display and battery envelope. Import/align the local STEP as reference if
   supported; measure its transformed components rather than raw STEP points.
   Resolve the 5.60 versus 10.60 thickness discrepancy and choose the Z stack.
3. Add only the display recess/window; inspect remaining material and regenerate
   after small parameter changes. Save/reopen and compare measured geometry.
4. Add USB and MicroSD openings as a separate slice after plug/card envelopes are
   known; then add button and microphone access. Verify connected wall sections.
5. Add supports, the agreed lid fastening and battery restraint separately.
   Recheck the full assembly for interference and usable access after each slice.

Each slice needs local feature/rebuild and geometry checks. A later fit coupon,
unpowered assembly trial, cable/card/button access check and user acceptance are
separate physical gates. Full printed fit, charging clearance/ventilation and
microphone performance remain open. Nothing in this review changes firmware,
board registration or the stable application reference.
