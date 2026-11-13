"""Fixtures shared by the in-Nuke tests."""

import json

import nuke
import pytest


@pytest.fixture(autouse=True)
def clean_script():
    """Every test starts and ends with an empty Nuke script."""
    nuke.scriptClear()
    yield
    nuke.scriptClear()


class RecordingLog:
    """Stands in for a loader's `log`, keeps what was logged."""

    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args if args else message)

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


@pytest.fixture
def make_effect_file(tmp_path):
    """Write an effect JSON like the one the Effect publish makes.

    `nodes` is a list of `(node class, knob values)`, in track order.
    Returns the path of the file.
    """
    counter = {"n": 0}

    def _make(nodes):
        counter["n"] += 1
        data = {"assignTo": "plateMain"}
        for index, (node_class, knobs) in enumerate(nodes):
            data[f"{node_class}{index}"] = {
                "class": node_class,
                "trackIndex": index,
                "subTrackIndex": 0,
                "node": knobs,
            }
        path = tmp_path / f"effect_{counter['n']}.json"
        path.write_text(json.dumps(data))
        return str(path)

    return _make


@pytest.fixture
def loader(monkeypatch):
    """Build a `LoadEffects` that reads the effect file given to `load`.

    Returns `(load_effects, set_file)`: the loader instance and a function
    that sets the JSON file the next load or update reads. The loader's log
    is a `RecordingLog`.
    """
    from ayon_nuke.plugins.load.load_effects import LoadEffects

    files = {}
    monkeypatch.setattr(
        LoadEffects,
        "filepath_from_context",
        classmethod(lambda cls, context: files["path"]),
    )
    log = RecordingLog()
    monkeypatch.setattr(LoadEffects, "log", log)
    # Whatever a test sets, the class attribute goes back afterwards.
    monkeypatch.setattr(LoadEffects, "exposed_knobs", [])
    return LoadEffects(), lambda path: files.update(path=path)


@pytest.fixture
def new_group():
    """Create an empty group node the way the loader does."""

    def _new():
        nuke.endGroup()
        return nuke.createNode("Group", "name Effect_1", inpanel=False)

    return _new
