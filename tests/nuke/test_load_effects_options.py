"""LoadEffects `attach_to_read_node` option (ayon-nuke#389, #425).

#389 added the option, #425 continued it on `develop` and keeps what
worked before it: loads and updates without options still attach, and
loaders with the old three argument `on_load` still load.
"""

import inspect

import nuke
import pytest

from ayon_nuke.api import plugin
from ayon_nuke.plugins.load import load_effects
from ayon_nuke.plugins.load.load_effects import (
    LoadEffects,
    LoadEffectsInputProcess,
)

CONTEXT = {}


@pytest.fixture
def read_node():
    # `connect_read_node` looks for "<namespace>_<assignTo>" in the path.
    return nuke.nodes.Read(file="/tmp/ns_plateMain.####.exr")


@pytest.fixture
def effect(loader, make_effect_file, new_group):
    load_effects_, set_file = loader
    set_file(make_effect_file([("TimeWarp", {})]))
    return load_effects_, new_group()


def test_attaches_when_option_is_on(effect, read_node):
    loader_, group = effect

    loader_.on_load(group, "ns", CONTEXT, {"attach_to_read_node": True})

    assert group.input(0) == read_node


def test_does_not_attach_when_option_is_off(effect, read_node):
    loader_, group = effect

    loader_.on_load(group, "ns", CONTEXT, {"attach_to_read_node": False})

    assert group.input(0) is None


def test_load_without_options_attaches_like_before(effect, read_node):
    """Before the option, every load attached to the read node.

    Loads without options (workfile builder, scripts) and the setting
    `attach_to_read_node: true` should keep that behaviour.
    """
    loader_, group = effect

    loader_.on_load(group, "ns", CONTEXT)

    assert group.input(0) == read_node


def test_update_attaches_like_before(effect, read_node):
    loader_, group = effect

    loader_.on_update(group, "ns", CONTEXT)

    assert group.input(0) == read_node


def test_option_default_follows_the_setting(monkeypatch):
    monkeypatch.setattr(LoadEffects, "attach_to_read_node", False)

    (option,) = LoadEffects.get_options()

    assert option.key == "attach_to_read_node"
    assert option.default is False


def test_old_style_group_loader_still_loads(monkeypatch):
    """A subclass of NukeGroupLoader from another addon, 3 arguments."""
    calls = []

    class LegacyLoader(plugin.NukeGroupLoader):
        def on_load(self, group_node, namespace, context):
            calls.append(namespace)

    monkeypatch.setattr(plugin, "containerise", lambda **kwargs: "container")
    monkeypatch.setattr(LegacyLoader, "_set_node_color", lambda *a: None)
    monkeypatch.setattr(LegacyLoader, "_get_imprint_data", lambda *a: {})
    context = {"folder": {"name": "ns"}}

    LegacyLoader().load(context, name="n", namespace="ns")

    assert calls == ["ns"]


def test_new_style_group_loader_gets_the_options(monkeypatch):
    """`load` passes the options to an `on_load` that takes them."""
    received = []

    class NewLoader(plugin.NukeGroupLoader):
        def on_load(self, group_node, namespace, context, options=None):
            received.append(options)

    monkeypatch.setattr(plugin, "containerise", lambda **kwargs: "container")
    monkeypatch.setattr(NewLoader, "_set_node_color", lambda *a: None)
    monkeypatch.setattr(NewLoader, "_get_imprint_data", lambda *a: {})
    context = {"folder": {"name": "ns"}}

    NewLoader().load(
        context, name="n", namespace="ns", options={"attach": True}
    )

    assert received == [{"attach": True}]


def test_input_process_loader_loads(loader, make_effect_file, new_group):
    _, set_file = loader
    set_file(make_effect_file([("TimeWarp", {})]))
    group = new_group()
    input_process = LoadEffectsInputProcess()
    input_process.connect_active_viewer = lambda group_node: True

    input_process.on_load(group, "ns", CONTEXT, None)

    assert any(n.Class() == "TimeWarp" for n in group.nodes())


def test_base_class_is_not_a_loader_of_its_own():
    """Plugin discovery skips abstract classes, so no duplicate loader."""
    assert inspect.isabstract(load_effects._BaseEffectsLoader)
    assert not inspect.isabstract(LoadEffects)
    assert not inspect.isabstract(LoadEffectsInputProcess)
