# Opening nodes — implementation history, approaches & failure reasons

Purpose: a consolidated history of the approaches tried to implement the
`opening_surface`, `opening_cut_surface`, and `opening_volume` nodes, with the
ideas (user vs assistant) and the reasons each approach failed or was
abandoned.

---

## Node 1: `opening_surface`

**Goal:** retrieve the planar faces of an opening (void) that lie in the plane of
the host surface (wall/roof/slab), cached as generated geometry for downstream
measurement/collision nodes.

### Approach v1 — planar-group cap classification (initial, not a full success)
- Group the cached `IfcOpeningElement` Body-mesh faces into planar surfaces
  (normals within ~1°, coplanar ≤ 0.01, mirroring the reference
  `LightExposureRule.java` `groupTriangles`).
- The **two largest groups with opposing normals (≥170°)** = the two cap faces
  (front + back); the reveal band is dropped. Every face joins exactly one group
  (fixing a reference quirk where a triangle could join two groups).
- Geometry source = the **cached** opening mesh; openings without one get an
  error entry (`"no cached geometry"`). No on-demand tessellation.
- **User decisions:** `gen:` key prefix (not `inter:`); self-contained approach
  (don't pull in the `LightEntryModel` generator); both caps as one mesh; no
  host-type filter; `area` = single larger cap face.
- **Partial success + failure:** it worked for short/normal openings (315 runner
  tests; real-world model 117/117 openings without error) but was **not a success
  for overlong openings** — the two-largest-opposing face-group heuristic picked
  cap faces that **were not located at the wall plane**, so the retrieved
  surfaces were wrong for those cases.

### Approach v2 — curved-host branch (added, then found wrong, 2026-11-09)
Added `_surface_regions` / `_region_is_curved` / `_bbox_overlap` /
`_curved_host_caps`, making the algorithm three-branch:
1. `_cap_groups` (default): largest planar group + its largest opposing group.
2. `_curved_host_caps`: when the cutter overlaps a curved host region, use the
   cutter's own two largest congruent, roughly-opposing chord caps **directly**
   (no clipping).
3. `_clip_parallel_caps`: clip the cutter to the host's dominant surface-pair
   slab, then take the parallel caps; fallback to the two-largest heuristic.

**Failure:** on real curved walls the surfaces came out **perpendicular to the
wall and oversized**. Root cause (user's note): a curved-wall opening has **only
one face in the plane of the wall**; the cutter projects to a **triangle-like
cross-section**, so the chord caps are perpendicular to the wall and too big —
they are not the hole in the wall surface.

**Insight (open / unresolved by decision):** the surface should **follow the
curve** — combine the strip faces across the curve (not one flat chord cap), with
area ≈ the filling `IfcWindow`/`IfcDoor` area (via `IfcRelFillsElement`), and a
sub-question of a narrow fix vs re-architecting the cap output. *Left unresolved.*

Related: `opening_surface_ifc_generator` writes each cap as an independent
`IfcBuildingElementProxy`.

---

## Node 2: `opening_cut_surface`

**Goal:** extract the **host's own faces** that bound the opening void (the
reveal band), cache them as closed geometry per opening. Output geometry-only
(no area / width / height / depth).

### v0 — cap-driven selection (abandoned)
Reused `opening_surface`'s cap classification to locate the hole plane + footprint,
then selected host faces inside it.
**Failure:** mis-fired on curved hosts and on an oversized real-world cutter — it
reported the raw opening cutter. Replaced by plane-coincidence +
footprint-containment selection.

### Geometry-library root-cause fix (2026-11-11)
- Ruled out cache corruption — direct `ifcopenshell.geom` tessellation was
  **byte-identical** to the cache.
- **Real root cause:** the default library **`hybrid-cgal-simple-opencascade`
  fans the concave bore to a single centroid vertex**, so the reveal faces are
  degenerate slivers **never coplanar** with the cutter's lateral planes → only
  the two horizontal caps survive (window 24 faces / 0.81 m²; no vertical
  reveals). `cgal` triangulates the bore as **clean planar strips** exactly
  coplanar → vertical + horizontal reveals recovered (window 53 / 2.22 m²;
  door 38 / 2.36 m²).
- **Fix (user decision — node-local, not global):** re-tessellate **just the host**
  with `cgal` via `_reveal_host_mesh(...)`, memoized per `ExecutionContext`,
  falling back to the cached host. Not switching the global default (that
  re-tessellates every element of every node; ~3× on the Complex model).
- The `contains()`-in-cutter criterion was **tried and rejected** (it re-selects
  the fan-to-centroid slivers).

### v1 — bespoke watertight closure (round-wall-correct, no door closure)
`_close_bore`: `_weld_rim` (grid-weld coincident tessellation corners within 1 mm,
only tube-referenced vertices — **not** `merge_vertices(digits_vertex=3)`, which
over-merged and broke the mesh) → `_boundary_loops` (walk boundary edges as
**cycles following real face edges**, not DFS, which created phantom edges) →
`_cap_loops` (centroid fan per loop, wound opposite across the shared boundary
edge, then re-oriented to positive volume). Accepted only when `_is_watertight`
(watertight + winding-consistent + volume > 0). All 36 openings closed watertight.
**Failure:** floor-reaching **doors** were capped by a single centroid fan, which
**skews the cap** and gives wrong volumes on real doors.

### v2 — edge-topology / floor-seam door closure (removed as "incorrect")
- `_close_door_ring`, `_close_door_ring_grouped`, `_close_door_ring_fallback`,
  `_cap_floor_and_panels`, `_door_ring_groups`, `_door_bottom_vertices`.
- Topologically elegant rationale: header = the reveal sharing boundary edges
  with both jambs; sill derived from the jambs' free-end edges; min-height
  floor-seam fallback for fragmented curved doors. It also introduced per-plane
  cap decomposition (`_loop_cap_groups`) to split a non-planar rim into one flat
  cap per host plane.
**Failure:** still **wrong volumes/shapes on real doors**, couldn't close real
door 94737 (non-manifold tube) nor the curved host's doors. Removed in v3;
snapshotted as `opening_cut_surface_version2-door-openings-incorrect.py`.

### v3 — open rings (current)
- **User decision:** openings whose cut surface doesn't form a closed ring (any
  **non-planar boundary loop** = a floor-reaching door) are **not** closed
  watertight; only their two cap surfaces are added via `_close_open_ring`,
  open at the sill.
- `_prune_flaps` drops the smallest face on each over-used edge (>2 uses) to
  restore manifoldness (required because a non-manifold tessellation flap can
  never be capped; found on real door 94737, host 93771, edge (7,24) with 3 faces).
- **Result:** windows byte-identical to v2 (watertight); door/roof-light rings =
  tube + cap surfaces, open at sill. Real model 27/117 watertight (windows);
  ~90 doors intentionally open.
- **Documented limitation:** heavily fragmented curved-band residuals
  (6313/6320, 6306/6299 on host 9461) remain degenerate slivers, identical to v2.

---

## Node 3: `opening_volume`

**Goal:** a watertight volume per opening, emitted as one of three methods:
- `closed_cut_surface` — the host cut-surface tube closed watertight;
- `lofted_caps` — a solid lofted between the two cap faces (single-cap /
  open-ring / degenerate case);
- `caps_only` — no watertight volume (degraded fallback).

**Architecture:** reads the cutter and host meshes from the **geometry cache**
(built by `util/geometry.py` `build_geometry_cache`) — it does **not** tessellate
the IFC directly — and writes its result back under a `gen:` key, reusing the
cut-surface tube/closure helpers and the cap-classification helpers from the
other two nodes.

The closing logic went through several distinct "does this ring deserve
`closed_cut_surface`?" gates, each with its own failure case:

### A. Folded-roof **skylight** regression (0.405 → 2.360; 0.071 → 0.539)
- Skylights sit on a folded roof; the rim crosses the ridge → **two boundary
  loops, one non-planar**.
- v3 `_close_bore` sent **any** non-planar loop to `_close_open_ring` (cap-only,
  not watertight) → tube stayed open, wrong sign/magnitude volume, reported as
  `lofted_caps`.
- **Fix:** a **single** non-planar loop = a floor-reaching door → stays open; a
  **multi-loop** non-planar rim = a bent skylight through-bore → falls through to
  per-plane watertight capping via `_loop_cap_groups`. Correct volumes 2.360 /
  0.539, `closed_cut_surface`. Verified: small model changes only the two
  skylights; simple/curved/real models unchanged (no accidental door closures).

### B. Sliver-based rejection gate (`_prefer_lofted_caps` / `_tube_is_degenerate` / `_SLIVER_EDGE_RATIO`)
Rejected a watertight tube when it was closed only by a degenerate centroid fan
(zero-width slivers from a non-planar rim), provided a healthy two-sided cap pair
+ adequate depth existed.
**Failure:** over-fired on **multi-layer walls** (a decomposed host exposes
several layer-interface planes), wrongly routing them to `lofted_caps`.

### C. Mid-wall-jog rejection gate (`_tube_has_mid_wall_jog`) — superseded B
Rejected any watertight tube containing a **cap-parallel face strictly between
the two cap planes** (≈ line 296 in `_opening_volume`).
**Failure:** over-fired on **multi-layer windows** — a legitimate layer-interface
plate sits at mid-depth (e.g. facet at offset −7.6249 between caps −7.83/−7.36).
Five windows (`1853/1871/2247/2041/2069`) were emitted `lofted_caps` (≈1.1276)
instead of `closed_cut_surface` (1.137). The reference model
(`opening_cut_surface_model_small-1117.ifc`) proves the stepped bore is correct
(1.63×1.565×0.265 + 1.5×1.5×0.205 ≈ 1.137).
**Fix:** drop the gate so **any watertight tube → `closed_cut_surface`**
("take the cut surface, then add the caps"). Note: the repo was briefly in a
broken intermediate state where tests still referenced the removed
`_prefer_lofted_caps`/`_tube_is_degenerate`/`_SLIVER_EDGE_RATIO`.

### D. Degenerate "two opposite cut surfaces" case (opening `#340917` "Tür-003", host `#340868`)
The tube is built from **only two opposite cut surfaces**; `_close_bore`
centroid-fan-caps the two rims into a 12-face shell that trimesh reports
`is_watertight=True` and `is_winding_consistent=True` but with **signed volume
`3.7e-17 m³`**. Because `_is_watertight` only requires `volume > 0`, the node
wrongly emitted a zero-volume `closed_cut_surface` — symptom "no volume is created."
**Fix (user choice: absolute floor):** added `_MIN_CLOSED_TUBE_VOLUME = 1e-6`,
rejecting zero-volume tubes so they fall through to `_loft_open_ring`, producing
a real `0.596 m³` (2.98 area × 0.2 depth).
**Alternatives considered and rejected:** fixing `_close_bore` to refuse
zero-volume closure (too invasive, affects `opening_cut_surface`); tightening the
shared `_is_watertight` (risky across nodes); a relative-to-caps guard (would
misclassify `411404/411479`: tube 0.38 vs cap-derived 0.052).

### E. Report-level "always created / surfaces-as-truth" test
Runs both `opening_surface` and `opening_volume` on `Testmodell-LightExposureSmall.ifc`,
asserting per opening: geometry **always created**, `method ∈ {closed_cut_surface,
lofted_caps}`, watertight + winding-consistent + volume > 0, and that the volume's
reported `area`/`width`/`height`/`depth` equal the `opening_surface` values
(`rel=1e-3`).
**Why report-level, not face-level (user decision):** `closed_cut_surface`
re-tessellates the caps, so the cap triangles are **not a face-subset of the
volume** (e.g. opening `1853`: surface 4 faces, volume 48) — a face-containment
check would be wrong. The `volume = area × depth` identity is also only exact for
axis-aligned through-bores; sloped skylight `679` gives `2.3598 ≠ 7.9971×0.35 = 2.799`.
Also required a **fresh `ExecutionContext`** because reusing the module-scoped
`real_context` collided on `cache_mesh` re-keying a `gen:opening_volume_main_*` key.

---

## Cross-cutting ideas / attribution

**User's driving requirements** (the contract that shaped every node):
- `gen:` keys, cached-geometry source (no on-demand tessellation), hosted in both
  runner and web per the node-development workflow.
- For a **closed ring**: "take the cut surface, then add the caps"
  (`closed_cut_surface`, watertight).
- For an **open ring** (floor-reaching door): cap surfaces only, **not
  watertight**, open at the sill — never fabricate closed volumes for doors.
- Skylight = multi-loop non-planar rim → close per-plane; door = single
  non-planar loop → stay open.
- Node-local cgal override (not global); absolute-floor volume guard (over
  relative); report-level surfaces-as-truth test (over geometry/face-level).
- Provided the reference implementations / field reports / ground-truth models
  (`LightExposureRule.java`, `opening_cut_surface_model_small-1117.ifc`, the
  real-world model) that validated or disproved each hypothesis.

**Assistant/prior-agent ideas** (the algorithms): planar-group cap classification,
cap-driven selection (failed), cgal host re-tessellation, per-plane cap
decomposition (`_loop_cap_groups`), bespoke weld/loop/fan closure, flap pruning,
edge-topology door closure (failed), the three `_close_bore` gates
(sliver → mid-wall-jog → watertight-only), the loft/degenerate-wedge helpers, and
most of the test harnesses.

**Recurring failure theme:** the shared closure/cap logic is where all three
nodes' bugs lived (not the nodes' own intake) — tessellation-library
triangulation, non-planar rims (skylight / doors), multi-layer interface plates,
and "watertight but zero/sliver volume" corner cases. Several iterations were
abandoned precisely because a change was too invasive, too global, or risked
breaking the door contract.

---

## Open / unresolved items
- **`opening_surface` curved-wall** surface should follow the curve and report an
  area ≈ the filling `IfcWindow`/`IfcDoor`; the branch currently reports
  perpendicular chord caps. **Left unresolved by decision.**
- Fragmented curved-band residuals in `opening_cut_surface` (host 9461 openings
  6313/6320, 6306/6299) are documented degenerate slivers.

---

## 2026-11-25 — opening-volume bugfix round: curved-wall depth + degenerate rim slivers

Two field-reported bugs were fixed in the consolidated `opening_volume` node
(which absorbed the former `opening_surface` node):

1. **Complex curved-wall** openings (`3I1L5gPDWg0VT5GUKLWs9c`, `0K5s5uMUftzg$$04ovBEeF`,
   `05J0gpim0wV07a6UxCKwP_`, + siblings) came out "too thin" — the volume only
   reached a middle wall layer instead of filling the hole.
2. **Real-world doors** (`3GC7bRf2psnrst9ie8qFDX`, `3ndo_UUzohbPDx681yNH6S`) emitted
   a "strange form".

### Bug 1 (curved-wall depth) — `_host_band_depth`

**Root cause.** The curved (round) host is faceted into many thin strips, so the
host facets behind a hole span several offset bands along the cap normal rather
than two clean surfaces. The old code split the sorted offsets at the *single
largest gap* and took the mean of each half, which could land mid-wall between
two intermediate strips and under-measure the wall (≈0.24–0.35 instead of the
true ≈0.39–0.47 outer→inner span).

**Fix.** Return the full outer→inner span — the distance between the outermost
and innermost host-surface facet centroids behind the hole. For a genuine
two-band flat wall the outer and inner facet clusters are each tight, so this
equals the old single-gap split and flat / 2-band hosts do not regress. The
depth feeds the single-cap prism construction (`_tapered_prism` / `_extrude_ring`)
for these coarse single-cap openings, so a correct depth makes the void span the
whole wall. **Note:** the deprecated `opening_surface` depth expectations were
not carried over into the consolidated test suite (it asserts only structural
invariants — watertight, winding-consistent, positive volume, method — not
hard-coded depths), so no test-depth edits were needed.

### Bug 2 (degenerate rim slivers) — `_loft_caps_watertight`

**Root cause.** A door/window frame authored as a low-poly solid carries a
redundant near-coincident vertex on a nearly-straight run (a sliver bevel, ~0.03
units). When the two cap rims are counted this way, one cap can read as a
`6`-ring and the other as a `4`-ring even though the true polygon is a rectangle.
Resampling a `6`-ring that has a sliver (the old uneven-rim loft) or bridging a
`6`-ring with thin sliver quads produced the malformed "strange form".

**Fix.** When the two rims **start** with unequal vertex counts, collapse any
redundant near-collinear sliver first. `_clean_degenerate_ring` drops a ring
vertex only when BOTH hold: the two edges meeting at it are near-collinear (same
direction, `_COLLINEAR_COS`) AND one of them is a short stub
(`_SLIVER_EDGE_LEN`), so a genuine corner with an angle is never simplified. The
ring is then lofted with `_loft_polygons` from the cleaned rings, which re-fans
the caps (they were degenerate anyway) and bridges clean quads — so the collapsed
vertices do not survive as unshared boundary edges that would break watertightness.

**Gating (per user requirement).** The cleanup runs only when the *initial* rims
are unequal (`n != m`). A rim that already has matching counts is left completely
untouched even if it carries short, same-direction edges.

**Outcome.** `3GC7bRf` (initially `6`/`4`) collapses to a clean `4`/`4` prism;
`3ndo_UUz` (initially `6`/`6`) stays on the equal-rim direct-bridge path per the
gating rule. Both doors report watertight, winding-consistent, positive-volume
`lofted_caps` solids. The ~10 other real-world unequal-rim openings have genuine
different-direction polygon vertices, so `_clean_degenerate_ring` leaves them
(fall through to the existing resampling loft), and the LightExposure skylights
(679/703/etc.) take the `closed_cut_surface` path and are unaffected.

**Validation:** `app/runner` `test_opening_volume.py` — 24 passed; curved-volume
extents along the cap normal now match the host wall span (0.39 / 0.4711 / 0.469
vs the previous under-measured depths).

## 2026-11-26 — follow-up: proud-cap depth guard + equal-rim twist

### Follow-up A (curved-wall depth) — cap plane sits proud of the facet span

The 2026-11-25 `_host_band_depth` fix (return the full outer→inner facet span)
still left one opening visibly too thin: the door `3I1L5gPDWg0VT5GUKLWs9c`
("Tür-008") on the round wall `Wand-004` (`IfcWall` 7879) measured 0.39 instead
of ~0.52.

**Root cause.** The single-cap prism is extruded from the hole *cap plane*, and on
a faced round wall that cap plane can sit noticeably proud of the curved outer
facet centroids. So the outer→inner *facet* span under-reads the wall by exactly
that proud offset, and the generated void stops short of the far wall surface by
the same amount.

**Fix.** In `_host_band_depth`, keep the facet span, but when the cap plane is
more than `_CAP_PROUD_TOL` (0.08) beyond it, re-measure the depth from the cap
plane out to the innermost host surface (`cap_to_far`) and return that instead.
Added `_CAP_PROUD_TOL = 0.08` beside the other cap-facing constants.

**Scope (verified).** Only the door is under-filled and only it is boosted
(0.39 → 0.52; its volume now reaches the inner wall surface). The sibling window
`3Zhu2g0pTLQTxxN3bM$Bc_` on the same wall takes the `closed_cut_surface` path and
never reads this depth, so its rendered volume is unchanged. The flush host-9461
openings (`0K5s5...`, `05J0...`, `1N8iUS0...`, `3Io1y...`) have cap-proud deltas
≈0.05, below the threshold, so they stay put.

### Follow-up B (degenerate rim slivers) — equal-rim door is *left twisted*

The 2026-11-25 gating rule left `3ndo_UUzohbPDx681yNH6S` (`6`/`6`) on the
equal-rim direct-bridging path. Inspecting the generated solid shows it is
watertight but the side band is **twisted**: every bridge triangle is a long
diagonal.

**Root cause.** The two `6`-rings are not congruent — the rectangle's collinear
bevel-slivers sit on *different corners* in the two rims (front: top-left +
bottom-right; back: bottom-left + top-right), i.e. they are effectively mirror
images. `_ring_shift` only tries cyclic shifts, so it cannot bring them into
correspondence (the best shift still leaves 2 misaligned pairs, edges up to 2.27).
A cyclic offset (e.g. index `i` vs `i-1`) is worse (sum-of-squares 14.4 vs 2.2),
and even reversing one rim only reaches 6.1. The only alignment that works is to
drop the bevel slivers, leaving both rims as the same 4-corner rectangle.

**Consequence.** Cleaning both rims to `4`/`4` (letting the `n != m` cleanup also
run when `n == m`) produces a clean prism but changes the door's volume
0.445 → 0.280. So the equal-rim gating rule preserves the authored ring but at the
cost of a twisted side band. Left as an open decision (see below).

### Follow-up C (equal-count resampling) — `_loft_polygons` kept distorting caps

While re-examining the equal-rim path, a separate defect surfaced in the loft
itself. `_loft_polygons` unconditionally resampled *both* rings to a common
count with uniform arc length. For a non-regular polygon cap (e.g. a
non-square rectangle) that moves the two corner vertices onto edge midpoints,
so the emitted cap is no longer the authored rectangle.

**Symptom.** The door `3GC7bRf2psnrst9ie8qFDX` (host `IfcWall` 364003, `n = m =
4`) emitted cap z-values `8.66, 9.3475, 10.925, 10.2375` — two interpolated
mid-edge vertices — instead of the four true rectangle corners (`8.66`, `10.925`).
The resampled intermediate vertices (z `9.3475` / `10.2375`, and the apexes at
`9.7925`) all come from `_resample_closed` uniform-arc-length resampling of a
non-square rectangle to `count = 4`, moving 2 corners to edge midpoints and
adding 2 centroid apexes. Watertight but with the wrong, shrunken cap.

**Fix.** In `_loft_polygons`, when `n is None` and the two rings already have
equal counts, keep the original ring vertices (`a, b = a_pts, b_pts`); only run
`_resample_closed` when the counts actually differ (or an explicit `n` is
supplied). This preserves the authored cap geometry exactly, and leaves the
`n != m` degradation branch untouched.

**Outcome.** `3GC7bRf` now emits only the true corners — z `8.66 ×4` and
`10.925 ×4` plus the two `9.7925` cap apexes; the interpolated `9.3475` /
`10.2375` vertices are gone. Still watertight (0 boundary edges) with positive
volume, correcting 0.16883 → 0.21166 (the true prism). `3ndo_UUz` is unchanged
(0.4452, 12 verts) because it never calls `_loft_polygons` (it takes the
equal-rim direct-bridge path).

**Validation:** `app/runner` `test_opening_surface.py` — 23 passed; the single
failure (`test_simple_model_window_closes_door_becomes_watertight`) is a
pre-existing missing-fixture `FileNotFoundError` for
`Testmodel-WallOpenings-Simple.ifc`, unrelated to this change.

### Follow-up D (degenerate rim slivers) — equal-rim twist is detected and cleaned

Resolves Follow-up B. Per user decision, the equal-rim direct bridge is kept for
congruent rims, and rims that a cyclic shift cannot pair are routed through the
existing clean-and-resample path.

**Correction to Follow-up B's consequence.** The feared volume regression does
not reproduce: cleaning `3ndo_UUz`'s two `6`-rings to the true `4`/`4` rectangle
and lofting gives volume **0.4485** (was 0.4452 twisted) — essentially
unchanged, not 0.280. The clean prism is strictly better (straight side quads,
16 faces instead of 20 diagonal ones).

**Detection.** Equal counts do not imply congruent rims, so `_rings_twisted`
measures it: after the best cyclic shift (`_ring_shift`), a congruent rim pair
offsets every vertex purely along the cap normal (the wall depth), leaving ~0
displacement *inside the cap plane*. Instrumenting every `n == m` case on the
real-world model confirms a clean separation — genuine congruent rims measure an
in-plane displacement ≤ 0.022 of the rims' in-plane extent, while the degenerate
mirror-image rims measure 0.399 (`3ndo_UUz`, `6`/`6`) and 0.826 (the three
`Tür-001` doors on `Wand-012`, `7`/`7`). Threshold `_TWIST_INPLANE_RATIO = 0.15`
(fraction of in-plane extent, so the test is scale-free; a plain
max-distance/mean-distance ratio would miss a narrow door in a thick wall).

**Fix.** In `_loft_caps_watertight`, the clean-and-resample branch now also runs
when `n == m` but `_rings_twisted` fires, so the bevel slivers are collapsed
(`_clean_degenerate_ring`) and the caps re-lofted (`_loft_polygons`) instead of
bridged with a twisted band. Genuine congruent equal-rim prisms are untouched
(the detected cap faces stay verbatim, 12 faces, same volume).

**Outcome.** `3ndo_UUzohbPDx681yNH6S` (`Tür-017`, `Wand-003` 274017): 0.4452 →
0.4485, 16 faces, clean prism. The three `Tür-001` doors (`3texd0KTo...` 126420,
`0M03gUGW...` 183477, `32kjha0R...` 265558, each on its own `Wand-012`
instance): 0.2240 → 0.1709, 20 faces — their previous volumes were computed off
twisted bands. All ~100 other openings on the model are byte-identical in method,
volume and face count.

**Validation:** `app/runner` `test_opening_surface.py` —
`test_loft_equal_rims_mirror_slivers_loft_clean_prism` added (mirrored-sliver
`6`-rings loft to the exact rectangle prism, detector asserted both ways); full
suite passes except the pre-existing missing-fixture failure noted above.

### Follow-up E (degenerate rim slivers) — the `Tür-001` "twist" was benign

Follow-up D mis-routed the three `Tür-001` doors. Their 0.2240 → 0.1709 volume
change was a regression, not a fix: the user confirmed the *before* values were
correct (and 3ndo's reroute remains correct).

**Root cause.** The `Tür-001` rims are congruent rectangles offset purely along
the cap normal — but the collinear bevel slivers sit at *different heights on
the same edge* (front: stub pair near the bottom; back: stub pair near the top,
plus an isolated collinear vertex 0.19 up whose edges are all ≥ 0.19, no short
stub). No cyclic shift pairs the vertices by height, so the best shift leaves
two pairs off by 2.003 and `_rings_twisted` fires (ratio 0.827). The
mispairing is benign: every mispaired vertex lies on the two parallel edge
lines, which span a plane, so the direct bridge's side triangles stay inside
that plane — the direct-bridge solid is exact (0.9601 × 2.2225 × 0.1051 =
0.2243 ≈ 0.2240). Follow-up D then degraded it twice: cleanup collapsed the
front rim to the exact rectangle (`7`→`4`) but kept the back rim a pentagon
(`7`→`5`, the isolated stub-less vertex survives), and `_loft_polygons` resampled
the unequal `4`/`5` rings to 5 uniform-arc-length points, pushing corners off
the true rectangle → 0.1709 (24% low).

**Fix.** The two branches in `_loft_caps_watertight` are now split. `n != m`
keeps its behaviour byte-identical. For `n == m` with `_rings_twisted` firing,
cleanup runs but reroutes to `_loft_polygons` only when it *recovers congruent
rings* (equal counts and `_rings_twisted` False on the cleaned rings) — the
signature of the mirror-image case. Rims that stay non-congruent after cleanup
genuinely differ (slivers at different spots along one edge), so they fall
through to the direct bridge with the original rims and the detected cap faces
verbatim.

**Outcome.** `3ndo_UUzohbPDx681yNH6S` keeps its Follow-up D result (0.4485, 16
faces, clean prism — its slivers sit on different *corners*, cleanup recovers
congruent `4`/`4` rings). The three `Tür-001` doors (`3texd0KTo...` 126420,
`0M03gUGW...` 183477, `32kjha0R...` 265558) are back to their correct direct
bridge: 0.2240, 24 faces. All other openings unchanged (only these four doors
ever entered the twist branch among the model's 74 equal-rim cases).

**Validation:** `app/runner` `test_opening_surface.py` —
`test_loft_equal_rims_benign_sliver_offset_keeps_direct_bridge` added (congruent
rectangles with slivers at different heights on one edge keep the direct bridge:
detector fires, volume stays the exact prism, caps verbatim at 24 faces); full
suite 25 passed except the pre-existing missing-fixture failure noted above.
