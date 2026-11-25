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
