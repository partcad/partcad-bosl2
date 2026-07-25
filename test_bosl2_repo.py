#
# partcad-bosl2, 2026
#
# Licensed under Apache License, Version 2.0.
#
"""Unit tests for the BOSL2 repository plugin's pure logic (no network, no CAD).

The signature parser and part synthesizer are exercised directly; the key/value
dispatch is tested on the paths that do not require downloading BOSL2. A single
end-to-end test that does download is guarded and skipped when offline.
"""

import importlib.util
import os

import pytest

_here = os.path.dirname(__file__)
_spec = importlib.util.spec_from_file_location("bosl2_repo", os.path.join(_here, "bosl2_repo.py"))
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)


# --- signature parsing -----------------------------------------------------


def test_find_modules_captures_multiline_signatures():
    text = plugin.strip_comments(
        "module foo(a, b=2) { cube(); }\n"
        "module bar(\n  x,  // the width\n  y=[1,2]\n) { sphere(); }\n"
        "function nope(a) = a;\n"
    )
    mods = dict(plugin.find_modules(text))
    assert set(mods) == {"foo", "bar"}  # functions are not modules
    assert "x" in mods["bar"] and "y=[1,2]" in mods["bar"]


def test_split_args_respects_brackets_and_quotes():
    assert plugin.split_args('a, b=[1, 2, 3], c="x,y", d') == ["a", "b=[1, 2, 3]", 'c="x,y"', "d"]


def test_split_name_default_first_equals_only():
    assert plugin.split_name_default("size=[1,2]") == ("size", "[1,2]")
    assert plugin.split_name_default("bare") == ("bare", None)


def test_classify_scalar_types():
    assert plugin.classify_scalar("true") == ("bool", True)
    assert plugin.classify_scalar("-3") == ("int", -3)
    assert plugin.classify_scalar("2.5") == ("float", 2.5)
    assert plugin.classify_scalar('"hex"') == ("string", "hex")
    # vectors, identifiers, expressions and undef are not exposed
    for non_scalar in ("[1,2,3]", "EDGES_ALL", "get_slop()", "undef", None):
        assert plugin.classify_scalar(non_scalar) is None


# --- dimension resolution --------------------------------------------------


def test_resolve_dimensions_picks_one_alias_per_family():
    # cyl-like: many aliases; only one length and one radius should be chosen.
    chosen, skip = plugin.resolve_dimensions({"h", "l", "length", "r", "r1", "r2", "d"})
    assert set(chosen) == {"h", "r"}
    assert {"l", "length", "d", "r1", "r2"} <= skip


def test_resolve_dimensions_cone_uses_r1_r2():
    chosen, _ = plugin.resolve_dimensions({"h", "r1", "r2", "d1", "d2"})
    assert set(chosen) == {"h", "r1", "r2"}


# --- part synthesis --------------------------------------------------------


def _synth(name, sig):
    return plugin.synth_part(name, sig, "shapes3d", "_bosl2_shapes3d.scad")


def test_synth_primitive_with_defaulted_and_dimension_args():
    cfg = _synth("cuboid", "size, chamfer, rounding, trimcorners=true, anchor=CENTER, spin=0")
    assert cfg["type"] == "scad" and cfg["method"] == "cuboid"
    assert cfg["path"] == "_bosl2_shapes3d.scad"
    assert cfg["parameters"]["size"] == {"type": "float", "default": 20.0}
    assert cfg["parameters"]["trimcorners"] == {"type": "bool", "default": True}
    assert "anchor" not in cfg["parameters"]  # attachable args are excluded


def test_synth_seed_supplies_domain_args_and_overrides_resolver():
    cfg = plugin.synth_part("threaded_rod", "d, l, pitch, h, bevel=false", "threading", "_bosl2_threading.scad")
    # seed wins for the length family; `h` must not also be set (would assert).
    assert cfg["parameters"]["l"] == {"type": "float", "default": 30.0}
    assert "h" not in cfg["parameters"]
    assert cfg["parameters"]["pitch"] == {"type": "float", "default": 2.0}


def test_synth_skips_helpers_masks_and_2d():
    assert _synth("_private", "a") is None
    assert _synth("living_hinge_mask", "size") is None
    assert _synth("spur_gear2d", "teeth, circ_pitch") is None
    assert _synth("text3d", "text") is None  # blocklisted


def test_synth_skips_module_with_unfillable_required_arg():
    # No geometry set and a bare (required-looking) non-dimension input remains.
    assert _synth("needs_input", "profile") is None


# --- key/value dispatch (offline paths) ------------------------------------


def test_dispatch_offline_paths():
    assert plugin.get("shapes3d/deps") == []
    assert "desc" in plugin.get("shapes3d/meta")
    assert plugin.get("shapes3d/objects/sketch") == {}
    assert plugin.get("unknown_category/objects/part") is None
    assert plugin.get("meta") is None  # top-level: nothing served here


def test_requested_ref_defaults(monkeypatch):
    monkeypatch.setattr(plugin, "request", {}, raising=False)
    assert plugin._requested_ref() == plugin.DEFAULT_REF
    monkeypatch.setattr(plugin, "request", {"parameters": {"ref": "v9.9.9"}}, raising=False)
    assert plugin._requested_ref() == "v9.9.9"


# --- end-to-end catalog (requires network; skipped offline) -----------------


@pytest.mark.slow
def test_catalog_downloads_and_generates_renderable_parts():
    try:
        cache = plugin.ensure_bosl2(plugin.DEFAULT_REF)
    except Exception as e:  # offline / rate-limited
        pytest.skip("BOSL2 could not be fetched: %s" % e)
    parts = plugin.catalog_for("shapes3d", cache)
    assert "cuboid" in parts and parts["cuboid"]["method"] == "cuboid"
    # The wrapper is a valid absolute-include of the cached std.scad.
    wrapper = plugin.wrapper_scad(cache, "shapes3d")
    assert os.path.join(cache, "std.scad") in wrapper
