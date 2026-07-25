# BOSL2 for PartCAD

Exposes [BOSL2](https://github.com/BelfrySCAD/BOSL2/) — the Belfry OpenSCAD
Library v2 — as a broad catalog of **parametric PartCAD parts**, ready to be
published in [partcad-index](https://github.com/partcad/partcad-index/) side by
side with [cqwarehouse](https://github.com/partcad/partcad-cqwarehouse/).

Unlike cqwarehouse (which enumerates every part in YAML), this package is served
by an **external repository plugin**: the parts are generated on demand by
parsing BOSL2 module signatures, and the BOSL2 source itself is downloaded the
first time a part is listed or built — nothing is vendored into this repo.

## What it stacks on

Two PartCAD capabilities are combined here:

1. **Parametric OpenSCAD parts.** Each part is a `scad` part with a `method`
   (the BOSL2 module) and typed `parameters`. PartCAD appends a
   `module(name=value, …)` call to a throwaway copy of an include-only wrapper
   and renders it, so a library module that defines geometry but renders nothing
   on its own becomes an instantiable part.

2. **External (plugin-backed) packages.** A `type: external` dependency is
   served by a repository plugin through a generic key/value protocol. Objects,
   files and metadata are fetched lazily, so a large library stays cheap to
   load. Here one plugin (`bosl2_repo.py`) serves twelve category sub-packages.

## Layout

| Path | Purpose |
| --- | --- |
| `partcad.yaml` | Declares the `bosl2` repository and one `external` sub-package per BOSL2 category. |
| `bosl2_repo.py` | The repository plugin: downloads BOSL2 on demand, parses signatures, serves parts + include wrappers. |
| `test_bosl2_repo.py` | Unit tests for the parser/synthesizer and the offline dispatch paths. |

## Usage

```shell
# List the whole generated catalog (downloads BOSL2 on first use).
pc list parts -r //pub/std/metric/bosl2

# Inspect a primitive.
pc inspect //pub/std/metric/bosl2/shapes3d:cuboid

# Override parameters (they flow through the generated module call).
pc inspect -p teeth=30 -p thickness=12 //pub/std/metric/bosl2/gears:spur_gear
```

The categories exposed are: `shapes3d`, `gears`, `threading`, `screws`,
`metric_screws`, `nema_steppers`, `ball_bearings`, `linear_bearings`, `joiners`,
`cubetruss`, `bottlecaps` and `walls` — roughly 70 parametric parts.

## How parts are generated

For each configured BOSL2 source file, `bosl2_repo.py`:

1. **Parses** every top-level `module NAME(args)` signature.
2. **Extracts parameters**: scalar-defaulted arguments (`bool`/`int`/`float`/
   `string`) become overridable PartCAD parameters at their BOSL2 defaults.
3. **Resolves dimensions**: BOSL2 exposes the same dimension through mutually
   exclusive aliases (`r`/`d`/`r1`+`r2`, `h`/`l`/`length`, `size`/`size1`+
   `size2`). The engine picks a single canonical spelling per family so calls
   never trip a "define exactly one of …" assertion.
4. **Seeds domain arguments** the geometry rules cannot infer (gear `teeth`,
   thread `pitch`, bearing `trade_size`, …) from a small data table.
5. **Filters** helpers (`_`-prefixed), 2D modules, masks, and a blocklist of
   modules that cannot render standalone.

The result is a catalog where every generated part renders out of the box; users
can then override any exposed parameter.

### Pinning the BOSL2 version

The BOSL2 release is the `ref` parameter of the `bosl2` repository in
`partcad.yaml` (default `v2.0.747`). The source is cached under
`~/.cache/partcad-bosl2/<ref>/` (override the location with
`PARTCAD_BOSL2_CACHE`).

## Publishing in partcad-index

This package declares `name: //pub/std/metric/bosl2`, so standalone development
uses the exact addresses consumers will see. To publish it, add an import next
to cqwarehouse in the index's `std/metric/partcad.yaml`:

```yaml
import:
  cqwarehouse:
    type: git
    url: https://github.com/partcad/partcad-cqwarehouse/
    relPath: metric.yaml
  bosl2:                                   # <-- new, side by side
    desc: Parametric BOSL2 shapes, gears, threading and hardware
    type: git
    url: https://github.com/partcad/partcad-bosl2/
```

Parts then resolve as `//pub/std/metric/bosl2/<category>:<module>`.

> **Note.** Because the plugin downloads BOSL2 at build time, a consumer needs
> network access on first use (subsequently it is cached). This is the
> deliberate "download-on-demand" design; a future revision could pin BOSL2 as a
> git submodule instead.

## Development

```shell
# Fast, offline unit tests of the generation logic:
pytest test_bosl2_repo.py -m "not slow"

# Print the generated catalog directly (downloads BOSL2):
python bosl2_repo.py
```

## Licensing

The code in this repository is Apache-2.0 (see `LICENSE`). BOSL2 is **not**
bundled here; it is fetched from upstream at build time and remains under its own
BSD 2-Clause license. See `NOTICE`.
