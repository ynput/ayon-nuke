"""LoadEffects skips a retime the read node already carries (ayon-nuke#158).

Publishing a plate and its effects writes the same TimeWarp twice: into the
plate version's retime data and into the effect JSON. Loading the plate
re-creates the TimeWarp on the read node, loading the effects added a
second one, applying the retime twice.

The loader now skips the effect nodes whose class is in the setting
`skip_node_classes` when it attaches to a read node that already has a
retime. The setting is empty by default, so nothing is skipped until a
studio lists e.g. `TimeWarp`. Effects loaded without such a read node
still keep their own retime.
"""

import nuke
import pytest

from ayon_nuke.api import containerise
from ayon_nuke.api.plugin import NukeLoader

CONTEXT = {}

# What `NukeGroupLoader._get_imprint_data` reads from the context.
IMPRINT_CONTEXT = {
    "version": {"version": 1, "attrib": {}},
    "representation": {"id": "representation-id"},
}

READ_FILE = "/tmp/ns_plateMain.####.exr"


@pytest.fixture(autouse=True)
def skip_timewarp(loader, monkeypatch):
    """The setting lists TimeWarp, as for a studio that opted in."""
    load_effects, _ = loader
    monkeypatch.setattr(
        type(load_effects), "skip_node_classes", ["TimeWarp"])


@pytest.fixture
def read_node():
    # `_find_read_node` looks for "<namespace>_<assignTo>" in the path.
    return nuke.nodes.Read(file=READ_FILE)


def _containerise(read_node, data):
    """Imprint the container data `LoadClip` leaves on a loaded clip."""
    containerise(
        read_node,
        name="plateMain",
        namespace="ns",
        context={
            "representation": {"id": "representation-id"},
            "project": {"name": "project"},
        },
        loader="LoadClip",
        data=data,
    )
    return read_node


def _set_container_id(node, container_id="container-id"):
    """Add the container id `LoadClip.set_as_member` puts on its nodes."""
    knob = nuke.String_Knob(NukeLoader.container_id_knob)
    node.addKnob(knob)
    knob.setValue(container_id)


@pytest.fixture
def retimed_read(read_node):
    """Read node as `LoadClip` leaves it after re-creating a retime."""
    _containerise(read_node, {"addRetime": True})
    _set_container_id(read_node)
    timewarp = nuke.createNode("TimeWarp", inpanel=False)
    timewarp.setInput(0, read_node)
    _set_container_id(timewarp)
    return read_node


@pytest.fixture
def loaded_read(read_node):
    """Read node of a loaded clip whose version had no retime."""
    return _containerise(read_node, {})


def _containerise_group(load_effects, group):
    """Imprint the group as `NukeGroupLoader.load` does after `on_load`."""
    containerise(
        group,
        name="effectMain",
        namespace="ns",
        context={
            "representation": {"id": "representation-id"},
            "project": {"name": "project"},
        },
        loader="LoadEffects",
        data=load_effects._get_imprint_data(IMPRINT_CONTEXT),
    )


def _effect_timewarps(group):
    return [node for node in group.nodes() if node.Class() == "TimeWarp"]


def _script_timewarps():
    return nuke.allNodes(filter="TimeWarp", recurseGroups=True)


def _plate_timewarp():
    """The TimeWarp `LoadClip` made for the plate."""
    return nuke.allNodes(filter="TimeWarp")[0]


def _load(loader, group, options=None):
    load_effects, _ = loader
    if options is None:
        load_effects.on_load(group, "ns", CONTEXT)
    else:
        load_effects.on_load(group, "ns", CONTEXT, options)


def test_skips_timewarp_when_read_has_retime(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert not _effect_timewarps(group)
    assert any(n.Class() == "Grade" for n in group.nodes())
    # The effect was above the TimeWarp in the editor, so it runs after
    # the Read's retime to keep animated knobs on timeline frames.
    assert _plate_timewarp().input(0) == retimed_read
    assert group.input(0) == _plate_timewarp()
    # The plate's retime stays the only TimeWarp in the script.
    assert len(_script_timewarps()) == 1


def test_effect_without_the_read_retime_stays_under_read(
        loader, make_effect_file, new_group, retimed_read):
    """The setting lists TimeWarp, but the effect has none to skip."""
    load_effects, set_file = loader
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert group.input(0) == retimed_read
    assert _plate_timewarp().input(0) == group


def test_keeps_timewarp_when_setting_is_empty(
        loader, make_effect_file, new_group, retimed_read, monkeypatch):
    load_effects, set_file = loader
    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group)

    # Default settings keep the effect as it was published.
    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) == retimed_read


def test_keeps_classes_not_in_setting(
        loader, make_effect_file, new_group, retimed_read, monkeypatch):
    load_effects, set_file = loader
    monkeypatch.setattr(type(load_effects), "skip_node_classes", ["Grade"])
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert len(_effect_timewarps(group)) == 1
    assert not [n for n in group.nodes() if n.Class() == "Grade"]


def test_effect_still_connects_after_the_skipped_timewarp(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    output = next(n for n in group.nodes() if n.Class() == "Output")
    assert output.input(0).Class() == "Grade"


def test_keeps_timewarp_when_read_has_no_retime(
        loader, make_effect_file, new_group, read_node):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group)

    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) == read_node


def test_keeps_timewarp_when_read_version_had_no_retime(
        loader, make_effect_file, new_group, loaded_read):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group)

    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) == loaded_read


def test_keeps_timewarp_when_read_lost_its_retime(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    # A plate updated to a version without retime, or a retime deleted by
    # hand: `addRetime` stays imprinted, but the TimeWarp is gone.
    for node in nuke.allNodes(filter="TimeWarp"):
        nuke.delete(node)
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group)

    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) == retimed_read


def test_keeps_timewarp_when_not_attached(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group, {"attach_to_read_node": False})

    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) is None


def test_update_does_not_add_the_retime_again(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()
    load_effects.on_load(group, "ns", CONTEXT)

    load_effects.on_update(group, "ns", CONTEXT)

    assert not _effect_timewarps(group)
    assert group.input(0) == _plate_timewarp()
    assert _plate_timewarp().input(0) == retimed_read


def test_update_keeps_the_load_choice_not_to_attach(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()
    _load(loader, group, {"attach_to_read_node": False})
    _containerise_group(load_effects, group)

    # An update runs on a new loader instance, without load options.
    type(load_effects)().on_update(group, "ns", CONTEXT)

    assert len(_effect_timewarps(group)) == 1
    assert group.input(0) is None


def test_update_keeps_the_load_choice_to_attach(
        loader, make_effect_file, new_group, retimed_read, monkeypatch):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()
    _load(loader, group, {"attach_to_read_node": True})
    _containerise_group(load_effects, group)
    # The setting changed since the load.
    monkeypatch.setattr(type(load_effects), "attach_to_read_node", False)

    type(load_effects)().on_update(group, "ns", CONTEXT)

    assert not _effect_timewarps(group)
    assert group.input(0) == _plate_timewarp()


def test_warns_when_every_node_is_skipped(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file([("TimeWarp", {"lookup": 2.0})]))
    group = new_group()

    _load(loader, group)

    assert not _effect_timewarps(group)
    assert any(
        "All nodes of the effect are skipped" in warning
        for warning in load_effects.log.warnings
    )


def test_skips_every_timewarp_of_the_effect(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {}), ("Grade", {}), ("TimeWarp", {})]))
    group = new_group()

    _load(loader, group)

    assert not _effect_timewarps(group)
