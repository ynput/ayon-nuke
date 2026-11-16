"""LoadEffects can expose knobs of the loaded nodes on its group node.

Covers ayon-nuke#416: the `exposed_knobs` setting, the links on the group,
the update of a loaded group and the settings a client or server without
the setting still sends. The loader shares its code with the
`attach_to_read_node` option of #425, tested in
`test_load_effects_options.py`.
"""

import nuke
import pytest

from ayon_nuke.plugins.load.load_effects import (
    LoadEffects,
    LoadEffectsInputProcess,
)

CONTEXT = {}


def _children(group):
    return [n for n in group.nodes() if n.Class() not in ("Input", "Output")]


def _timewarp(group):
    return next(n for n in group.nodes() if n.Class() == "TimeWarp")


def _is_link(group, name):
    knob = group.knobs().get(name)
    return knob is not None and knob.Class() == "Link_Knob"


def _tab_of(group, name):
    """Name of the tab the knob `name` of the group sits in."""
    tab = None
    for knob in group.allKnobs():
        if knob.Class() == "Tab_Knob":
            tab = knob.name()
        elif knob.name() == name:
            return tab
    return None


def _load(load_effects, group):
    load_effects.on_load(group, "ns", CONTEXT)


# -- On load ---------------------------------------------------------------


def test_nothing_exposed_by_default(loader, make_effect_file, new_group):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()
    knobs_before = set(group.knobs())

    _load(load_effects, group)

    assert LoadEffects.exposed_knobs == []
    assert set(group.knobs()) == knobs_before


def test_exposes_knob_from_child(loader, make_effect_file, new_group):
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)

    assert _is_link(group, "lookup")


def test_exposed_knob_drives_the_child(loader, make_effect_file, new_group):
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()
    _load(load_effects, group)

    group["lookup"].setValue(7.0)

    assert _timewarp(group)["lookup"].value() == 7.0


def test_exposes_several_knobs_from_different_children(
    loader, make_effect_file, new_group
):
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup", "multiply"]
    set_file(make_effect_file([("TimeWarp", {}), ("Grade", {})]))
    group = new_group()

    _load(load_effects, group)

    assert _is_link(group, "lookup")
    assert _is_link(group, "multiply")
    group["multiply"].setValue(2.5)
    grade = next(n for n in group.nodes() if n.Class() == "Grade")
    assert grade["multiply"].value() == 2.5


def test_knob_on_several_children_is_linked_once(
    loader, make_effect_file, new_group
):
    """Known limit (TODO in the plugin): only one child is exposed."""
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["multiply"]
    set_file(make_effect_file([("Grade", {}), ("Grade", {})]))
    group = new_group()

    _load(load_effects, group)

    assert _is_link(group, "multiply")
    group["multiply"].setValue(3.0)
    changed = [n for n in _children(group) if n["multiply"].value() == 3.0]
    assert len(changed) == 1


def test_unknown_knob_warns_and_loads(loader, make_effect_file, new_group):
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["no_such_knob", "lookup"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)

    assert "no_such_knob" not in group.knobs()
    assert any("no_such_knob" in w for w in LoadEffects.log.warnings)
    # The next knob of the list is still exposed.
    assert _is_link(group, "lookup")


def test_knobs_of_input_and_output_are_not_exposed(
    loader, make_effect_file, new_group
):
    load_effects, set_file = loader
    # `number` is a knob of the Input node only.
    LoadEffects.exposed_knobs = ["number"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)

    assert "number" not in group.knobs()
    assert any("number" in w for w in LoadEffects.log.warnings)


def test_a_real_knob_of_the_group_is_not_replaced(
    loader, make_effect_file, new_group
):
    load_effects, set_file = loader
    # Every node has a `label` knob of its own.
    LoadEffects.exposed_knobs = ["label"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)

    assert not _is_link(group, "label")
    assert any("label" in w for w in LoadEffects.log.warnings)


def test_input_process_loader_exposes_nothing(
    loader, make_effect_file, new_group, monkeypatch
):
    """`LoadEffectsInputProcess` inherits the setting, but does not use it."""
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup"]
    input_process = LoadEffectsInputProcess()
    monkeypatch.setattr(
        LoadEffectsInputProcess, "connect_active_viewer", lambda *a: True
    )
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    input_process.on_load(group, "ns", CONTEXT)

    assert "lookup" not in group.knobs()


# -- On update -------------------------------------------------------------


def test_update_links_the_new_nodes(loader, make_effect_file, new_group):
    """The children are rebuilt on update, the link still drives them."""
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()
    _load(load_effects, group)

    set_file(make_effect_file([("TimeWarp", {})]))
    load_effects.on_update(group, "ns", CONTEXT)

    assert _is_link(group, "lookup")
    group["lookup"].setValue(4.0)
    assert _timewarp(group)["lookup"].value() == 4.0
    # Only one link, not one per load.
    assert [k for k in group.knobs() if k == "lookup"] == ["lookup"]


def test_update_drops_link_when_the_node_is_gone(
    loader, make_effect_file, new_group
):
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()
    _load(load_effects, group)

    # The new version of the effect has no TimeWarp any more.
    set_file(make_effect_file([("Grade", {})]))
    load_effects.on_update(group, "ns", CONTEXT)

    assert "lookup" not in group.knobs()
    assert any("lookup" in w for w in LoadEffects.log.warnings)


def test_update_keeps_the_links_in_their_tab(
    loader, make_effect_file, new_group
):
    """An update must not move the links to the last tab of the group.

    The links are made in the `User` tab. A tab the artist adds after them
    must not take them over when the effect is updated.
    """
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["lookup", "multiply"]
    set_file(make_effect_file([("TimeWarp", {}), ("Grade", {})]))
    group = new_group()
    _load(load_effects, group)
    group.addKnob(nuke.Tab_Knob("custom", "Custom"))
    group.addKnob(nuke.String_Knob("note", "note"))
    knobs_before = [k.name() for k in group.allKnobs()]
    assert _tab_of(group, "lookup") == "User"

    set_file(make_effect_file([("TimeWarp", {}), ("Grade", {})]))
    load_effects.on_update(group, "ns", CONTEXT)
    load_effects.on_update(group, "ns", CONTEXT)

    assert _tab_of(group, "lookup") == "User"
    assert _tab_of(group, "multiply") == "User"
    assert _tab_of(group, "note") == "custom"
    # Same knobs in the same order, nothing removed and added again.
    assert [k.name() for k in group.allKnobs()] == knobs_before
    group["lookup"].setValue(6.0)
    assert _timewarp(group)["lookup"].value() == 6.0


def test_update_relinks_when_another_node_owns_the_knob(
    loader, make_effect_file, new_group
):
    """The node behind the link is gone, the knob is on a new node."""
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["mix"]
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()
    _load(load_effects, group)
    group.addKnob(nuke.Tab_Knob("custom", "Custom"))

    set_file(make_effect_file([("Blur", {})]))
    load_effects.on_update(group, "ns", CONTEXT)

    assert _is_link(group, "mix")
    assert _tab_of(group, "mix") == "User"
    group["mix"].setValue(0.3)
    blur = next(n for n in group.nodes() if n.Class() == "Blur")
    assert blur["mix"].value() == 0.3


def test_group_knob_without_a_child_knob_is_not_removed(
    loader, make_effect_file, new_group
):
    """`export_as_gizmo` is a knob of the group, no child has it."""
    load_effects, set_file = loader
    LoadEffects.exposed_knobs = ["export_as_gizmo"]
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)
    load_effects.on_update(group, "ns", CONTEXT)

    assert "export_as_gizmo" in group.knobs()
    assert not _is_link(group, "export_as_gizmo")
    assert any("export_as_gizmo" in w for w in LoadEffects.log.warnings)


# -- Settings --------------------------------------------------------------


@pytest.fixture
def host_settings(monkeypatch):
    """Let `apply_settings` read the nuke settings, undo what it sets."""
    monkeypatch.setenv("AYON_HOST_NAME", "nuke")
    monkeypatch.setattr(LoadEffects, "exposed_knobs", [])
    monkeypatch.setattr(LoadEffects, "enabled", True, raising=False)


def test_settings_set_the_exposed_knobs(host_settings):
    LoadEffects.apply_settings(
        {"nuke": {"load": {"LoadEffects": {
            "enabled": True, "exposed_knobs": ["lookup"],
        }}}}
    )

    assert LoadEffects.exposed_knobs == ["lookup"]


def test_settings_from_before_the_option_still_work(host_settings):
    """A server without `exposed_knobs` sends only `enabled`."""
    LoadEffects.apply_settings(
        {"nuke": {"load": {"LoadEffects": {"enabled": True}}}}
    )

    assert LoadEffects.exposed_knobs == []
    assert LoadEffects.enabled is True


def test_empty_setting_exposes_nothing(
    host_settings, loader, make_effect_file, new_group
):
    load_effects, set_file = loader
    LoadEffects.apply_settings(
        {"nuke": {"load": {"LoadEffects": {
            "enabled": True, "exposed_knobs": [],
        }}}}
    )
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()

    _load(load_effects, group)

    assert "lookup" not in group.knobs()
