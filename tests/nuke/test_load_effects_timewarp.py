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


def _containerise(read_node, data, name="plateMain"):
    """Imprint the container data `LoadClip` leaves on a loaded clip."""
    containerise(
        read_node,
        name=name,
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


def test_finds_read_by_container_not_file_path(
        loader, make_effect_file, new_group, monkeypatch):
    """The Read is found by its container data, not by the file path."""
    load_effects, set_file = loader
    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    read = nuke.nodes.Read(file="/tmp/custom.####.exr")
    _containerise(read, {})
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert group.input(0) == read


def test_container_match_wins_over_path_match(
        loader, make_effect_file, new_group, monkeypatch):
    """A path that happens to match must not win over the loaded clip."""
    load_effects, set_file = loader
    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    decoy = nuke.nodes.Read(file="/tmp/ns_plateMain_decoy.####.exr")
    read = nuke.nodes.Read(file="/tmp/custom.####.exr")
    _containerise(read, {})
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert group.input(0) == read
    assert group.input(0) is not decoy


def test_warns_when_several_reads_loaded_for_product(
        loader, make_effect_file, new_group, monkeypatch):
    """Duplicate loads cannot be told apart; warn and pick by name."""
    load_effects, set_file = loader
    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    first = nuke.nodes.Read(file="/tmp/a.####.exr")
    _containerise(first, {})
    second = nuke.nodes.Read(file="/tmp/b.####.exr")
    _containerise(second, {})
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert group.input(0) == first
    assert any(
        "Several Read nodes were loaded" in warning
        for warning in load_effects.log.warnings
    )


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


def _downstream(node):
    """A node reading `node`, as the rest of an artist's script."""
    down = nuke.nodes.NoOp(name="Downstream")
    down.setInput(0, node)
    return down


def _chain(node):
    """Classes from `node` up its input 0 to the top of the chain."""
    classes = []
    while node is not None and len(classes) < 10:
        classes.append(node.Class())
        node = node.input(0)
    return classes


def test_update_after_timewarp_added_to_setting(
        loader, make_effect_file, new_group, retimed_read, monkeypatch):
    """Effects loaded with the default empty setting sit under the Read."""
    load_effects, set_file = loader
    down = _downstream(_plate_timewarp())
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()
    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    _load(loader, group)
    assert _chain(down) == ["NoOp", "TimeWarp", "Group", "Read"]

    monkeypatch.setattr(
        type(load_effects), "skip_node_classes", ["TimeWarp"])
    load_effects.on_update(group, "ns", CONTEXT)

    # The plate's retime stays in the chain, the group moves after it.
    assert _chain(down) == ["NoOp", "Group", "TimeWarp", "Read"]
    assert not _effect_timewarps(group)


def test_update_after_timewarp_removed_from_setting(
        loader, make_effect_file, new_group, retimed_read, monkeypatch):
    load_effects, set_file = loader
    down = _downstream(_plate_timewarp())
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()
    _load(loader, group)
    assert _chain(down) == ["NoOp", "Group", "TimeWarp", "Read"]

    monkeypatch.setattr(type(load_effects), "skip_node_classes", [])
    load_effects.on_update(group, "ns", CONTEXT)

    assert _chain(down) == ["NoOp", "TimeWarp", "Group", "Read"]
    assert len(_effect_timewarps(group)) == 1


def test_update_in_place_keeps_the_chain(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    down = _downstream(_plate_timewarp())
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()
    _load(loader, group)

    load_effects.on_update(group, "ns", CONTEXT)
    load_effects.on_update(group, "ns", CONTEXT)

    assert _chain(down) == ["NoOp", "Group", "TimeWarp", "Read"]


def test_merge_reading_the_retime_on_a_keeps_its_b(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    background = nuke.nodes.Constant()
    merge = nuke.nodes.Merge2()
    merge.setInput(0, background)
    merge.setInput(1, _plate_timewarp())
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert merge.input(0) == background
    assert merge.input(1) == group


def test_expression_link_is_not_rewired(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    linked = nuke.nodes.NoOp(name="Linked")
    knob = nuke.Double_Knob("offset")
    linked.addKnob(knob)
    knob.setExpression("{}.lookup".format(_plate_timewarp().name()))
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert linked.input(0) is None
    assert group.input(0) == _plate_timewarp()


def test_update_keeps_what_reads_an_unplugged_group(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()
    _load(loader, group)
    write = _downstream(group)
    group.setInput(0, None)

    load_effects.on_update(group, "ns", CONTEXT)

    assert write.input(0) == group
    assert group.input(0) == _plate_timewarp()


def test_warns_about_nodes_below_the_skipped_retime(
        loader, make_effect_file, new_group, retimed_read):
    """Nodes before the TimeWarp in the effect were below it in Hiero."""
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("Grade", {}), ("TimeWarp", {"lookup": 2.0}), ("Blur", {})]))
    group = new_group()

    _load(loader, group)

    warnings = [
        warning for warning in load_effects.log.warnings
        if "below 'TimeWarp1'" in warning
    ]
    assert len(warnings) == 1
    assert "Grade0" in warnings[0]
    assert "Blur2" not in warnings[0]


def test_no_warning_when_the_retime_is_first(
        loader, make_effect_file, new_group, retimed_read):
    load_effects, set_file = loader
    set_file(make_effect_file(
        [("TimeWarp", {"lookup": 2.0}), ("Grade", {})]))
    group = new_group()

    _load(loader, group)

    assert not [
        warning for warning in load_effects.log.warnings
        if "in the editor" in warning
    ]


def test_update_keeps_the_input_of_an_unattached_group(
        loader, make_effect_file, new_group, retimed_read):
    """Nuke 17 drops a group's input when its Input node is rebuilt."""
    load_effects, set_file = loader
    set_file(make_effect_file([("Grade", {})]))
    group = new_group()
    _load(loader, group, {"attach_to_read_node": False})
    source = nuke.nodes.Constant()
    group.setInput(0, source)
    _containerise_group(load_effects, group)

    type(load_effects)().on_update(group, "ns", CONTEXT)

    assert group.input(0) == source
