"""LoadEffects skips a retime the read node already carries (ayon-nuke#158).

Publishing a plate and its effects writes the same TimeWarp twice: into the
plate version's retime data and into the effect JSON. Loading the plate
re-creates the TimeWarp on the read node, loading the effects added a
second one, applying the retime twice.

The loader now skips the retime nodes of the effect when it attaches to a
read node that already has one. Effects loaded without such a read node
still keep their own retime.
"""

import nuke
import pytest

from ayon_nuke.api import containerise

CONTEXT = {}

READ_FILE = "/tmp/ns_plateMain.####.exr"


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


@pytest.fixture
def retimed_read(read_node):
    """Read node as `LoadClip` leaves it after re-creating a retime."""
    _containerise(read_node, {"addRetime": True})
    timewarp = nuke.createNode("TimeWarp", inpanel=False)
    timewarp.setInput(0, read_node)
    return read_node


@pytest.fixture
def loaded_read(read_node):
    """Read node of a loaded clip whose version had no retime."""
    return _containerise(read_node, {})


def _effect_timewarps(group):
    return [node for node in group.nodes() if node.Class() == "TimeWarp"]


def _script_timewarps():
    return nuke.allNodes(filter="TimeWarp", recurseGroups=True)


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
    assert group.input(0) == retimed_read
    # The plate's retime stays the only TimeWarp in the script.
    assert len(_script_timewarps()) == 1


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
    assert group.input(0) == retimed_read


def test_skips_every_timewarp_of_the_effect(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {}), ("Grade", {}), ("TimeWarp", {})]))
    group = new_group()

    _load(loader, group)

    assert not _effect_timewarps(group)
