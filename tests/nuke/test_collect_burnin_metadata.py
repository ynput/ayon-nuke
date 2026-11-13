"""CollectBurninMetadata collects Nuke metadata as burnin keys (#405).

The metadata comes from a real Nuke stream: a camera with an animated
`focal` knob, a ModifyMetaData node that copies it into `camera/focal` and
a Write node. Edge cases that Nuke cannot produce (a key missing on some
frames, values that are not strings) use a stand-in for the Write node.
"""

import nuke
import pyblish.api
import pytest

from ayon_nuke.plugins.publish import collect_burnin_metadata
from ayon_nuke.plugins.publish.collect_burnin_metadata import (
    CollectBurninMetadata,
)

FIRST, LAST = 1001, 1100


class Log:
    """Keeps what the plugin logged at debug level."""

    def __init__(self):
        self.messages = []

    def debug(self, message, *args):
        self.messages.append(message % args if args else message)

    info = warning = error = debug


class FakeWrite:
    """A Write node whose metadata per frame is given."""

    def __init__(self, metadata_by_frame):
        self._metadata = metadata_by_frame

    def metadata(self, time):
        return dict(self._metadata(time))

    def fullName(self):
        return "FakeWrite"

    def Class(self):
        return "Write"


@pytest.fixture
def plugin(monkeypatch):
    monkeypatch.setattr(CollectBurninMetadata, "log", Log(), raising=False)
    monkeypatch.setattr(CollectBurninMetadata, "metadata_keys", ["camera/"])
    return CollectBurninMetadata()


@pytest.fixture
def scene():
    """Camera with `focal` 24 -> 50 over the frame range, into a Write."""
    nuke.root()["first_frame"].setValue(FIRST)
    nuke.root()["last_frame"].setValue(LAST)
    camera = nuke.nodes.Camera4()
    camera["focal"].setAnimated()
    camera["focal"].setValueAt(24, FIRST)
    camera["focal"].setValueAt(50, LAST)

    def build(extra_rows=""):
        source = nuke.nodes.CheckerBoard2()
        modify = nuke.nodes.ModifyMetaData(inputs=[source])
        modify["metadata"].fromScript(
            '{set camera/focal "[value %s.focal]"}\n'
            '{set camera/name "%s"}\n%s' % (camera.name(), camera.name(),
                                           extra_rows)
        )
        return nuke.nodes.Write(inputs=[modify], file="/tmp/burnin_####.exr")

    build.camera = camera
    return build


def make_instance(write_node, start=FIRST, end=LAST):
    context = pyblish.api.Context()
    instance = context.create_instance("renderMain")
    instance.data.update(
        {
            "frameStartHandle": start,
            "frameEndHandle": end,
            "transientData": {"writeNode": write_node},
        }
    )
    return instance


def collected(instance):
    return instance.data.get("burninDataMembers", {})


# -- Real Nuke metadata -----------------------------------------------------


def test_animated_key_is_one_value_per_frame(plugin, scene):
    write = scene()
    instance = make_instance(write, FIRST, FIRST + 49)

    plugin.process(instance)

    focal = collected(instance)["camera/focal"]
    assert isinstance(focal, list)
    assert len(focal) == 50
    camera = scene.camera
    for index in (0, 10, 49):
        expected = camera["focal"].getValueAt(FIRST + index)
        assert float(focal[index]) == pytest.approx(expected, abs=1e-3)


def test_values_are_in_frame_order(plugin, scene):
    instance = make_instance(scene(), FIRST, LAST)

    plugin.process(instance)

    focal = [float(v) for v in collected(instance)["camera/focal"]]
    assert focal == sorted(focal)
    assert focal[0] == 24.0 and focal[-1] == 50.0
    assert len(focal) == LAST - FIRST + 1


def test_constant_key_is_a_single_value(plugin, scene):
    instance = make_instance(scene(), FIRST, FIRST + 9)

    plugin.process(instance)

    assert collected(instance)["camera/name"] == "Camera1"


def test_nuke_metadata_values_are_strings(plugin, scene):
    """Nuke returns every ModifyMetaData value as text, so it is kept so."""
    instance = make_instance(scene(), FIRST, FIRST + 4)

    plugin.process(instance)

    assert all(isinstance(v, str) for v in collected(instance)["camera/focal"])


def test_prefix_collects_every_key_under_it(plugin, scene):
    # Keys outside the prefix, also one that only contains it.
    write = scene('{set other/value "x"}\n{set mycamera/value "y"}')
    instance = make_instance(write, FIRST, FIRST + 4)

    plugin.process(instance)

    assert set(collected(instance)) == {"camera/focal", "camera/name"}


def test_exact_key_collects_only_that_key(plugin, scene, monkeypatch):
    monkeypatch.setattr(
        CollectBurninMetadata, "metadata_keys", ["camera/name"]
    )
    instance = make_instance(scene(), FIRST, FIRST + 4)

    plugin.process(instance)

    assert collected(instance) == {"camera/name": "Camera1"}


def test_prefix_is_not_a_substring_match(plugin, scene, monkeypatch):
    monkeypatch.setattr(CollectBurninMetadata, "metadata_keys", ["camera"])
    instance = make_instance(scene(), FIRST, FIRST + 4)

    plugin.process(instance)

    # "camera" has no trailing "/": an exact key, matching nothing.
    assert collected(instance) == {}


def test_frames_outside_the_script_range_are_read(plugin, scene):
    """Frames outside the script range evaluate, no fallback needed."""
    instance = make_instance(scene(), 900, 904)

    plugin.process(instance)

    assert float(collected(instance)["camera/focal"]) == 24.0


def test_handles_are_part_of_the_range(plugin, scene):
    instance = make_instance(scene(), FIRST - 5, FIRST + 4)

    plugin.process(instance)

    assert len(collected(instance)["camera/focal"]) == 10


def test_collected_keys_do_not_replace_other_burnin_members(plugin, scene):
    instance = make_instance(scene(), FIRST, FIRST + 4)
    instance.data["burninDataMembers"] = {"focalLength": 35}

    plugin.process(instance)

    members = collected(instance)
    assert members["focalLength"] == 35
    assert "camera/name" in members


# -- Which instances are processed ----------------------------------------


def test_no_keys_configured_collects_nothing(plugin, scene, monkeypatch):
    monkeypatch.setattr(CollectBurninMetadata, "metadata_keys", [])
    instance = make_instance(scene(), FIRST, FIRST + 4)

    plugin.process(instance)

    assert "burninDataMembers" not in instance.data


def test_missing_exact_key_is_logged_not_collected(
    plugin, scene, monkeypatch
):
    monkeypatch.setattr(
        CollectBurninMetadata, "metadata_keys", ["camera/missing"]
    )
    instance = make_instance(scene(), FIRST, FIRST + 4)

    plugin.process(instance)

    assert "burninDataMembers" not in instance.data
    assert any("camera/missing" in m for m in plugin.log.messages)


def test_instance_without_write_node_is_skipped(plugin, monkeypatch):
    monkeypatch.setattr(
        collect_burnin_metadata.napi,
        "get_instance_group_node_children",
        lambda instance: [],
    )
    instance = make_instance(None)

    plugin.process(instance)

    assert "burninDataMembers" not in instance.data
    assert any("No Write node" in m for m in plugin.log.messages)


def test_write_node_is_found_in_the_instance_group(
    plugin, scene, monkeypatch
):
    write = scene()
    monkeypatch.setattr(
        collect_burnin_metadata.napi,
        "get_instance_group_node_children",
        lambda instance: [nuke.nodes.Grade(), write],
    )
    instance = make_instance(None, FIRST, FIRST + 4)

    plugin.process(instance)

    assert collected(instance)["camera/name"] == "Camera1"


def test_inactive_optional_plugin_is_skipped(plugin, scene, monkeypatch):
    monkeypatch.setattr(CollectBurninMetadata, "optional", True)
    instance = make_instance(scene(), FIRST, FIRST + 4)
    instance.data["publish_attributes"] = {
        "CollectBurninMetadata": {"active": False}
    }

    plugin.process(instance)

    assert "burninDataMembers" not in instance.data


# -- Values Nuke does not produce ------------------------------------------


def test_key_missing_on_some_frames_is_empty_there(plugin):
    def metadata(frame):
        return {"camera/focal": "24"} if frame >= 1003 else {}

    instance = make_instance(FakeWrite(metadata), 1001, 1005)

    plugin.process(instance)

    assert collected(instance)["camera/focal"] == ["", "", "24", "24", "24"]


def test_key_found_on_no_frame_is_not_collected(plugin):
    instance = make_instance(FakeWrite(lambda frame: {}), 1001, 1003)

    plugin.process(instance)

    assert "burninDataMembers" not in instance.data


def test_values_are_compared_by_type_and_value(plugin):
    """24 and 24.0 differ, the key is animated and not constant."""

    def metadata(frame):
        return {"camera/focal": 24 if frame == 1001 else 24.0}

    instance = make_instance(FakeWrite(metadata), 1001, 1002)

    plugin.process(instance)

    assert collected(instance)["camera/focal"] == [24, 24.0]


def test_other_value_types_become_text(plugin):
    class Color:
        def __str__(self):
            return "red"

    def metadata(frame):
        return {
            "camera/int": 3,
            "camera/float": 2.5,
            "camera/bool": True,
            "camera/none": None,
            "camera/other": Color(),
        }

    instance = make_instance(FakeWrite(metadata), 1001, 1002)

    plugin.process(instance)

    members = collected(instance)
    assert members["camera/int"] == 3
    assert members["camera/float"] == 2.5
    assert members["camera/bool"] is True
    assert members["camera/other"] == "red"
    # A key that is None on every frame has nothing to show.
    assert "camera/none" not in members


@pytest.mark.xfail(
    strict=True,
    reason="a number 0 on every frame is dropped: `not any(values)`",
)
def test_constant_zero_is_collected(plugin):
    instance = make_instance(
        FakeWrite(lambda frame: {"camera/tilt": 0}), 1001, 1003
    )

    plugin.process(instance)

    assert collected(instance) == {"camera/tilt": 0}
