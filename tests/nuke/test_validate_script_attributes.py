"""ValidateScriptAttributes checks the script root against the task.

It is a context plugin: it runs for every publish, whatever products are
published, and compares the Nuke root settings with the context's task.
"""

import nuke
import pyblish.api
import pyblish.plugin
import pyblish.util
import pytest

import ayon_nuke.api as napi
from ayon_core.pipeline import PublishXmlValidationError
from ayon_nuke.plugins.publish import (
    collect_context_data,
    validate_script_attributes,
)
from ayon_nuke.plugins.publish.collect_context_data import CollectContextData
from ayon_nuke.plugins.publish.validate_script_attributes import (
    ValidateScriptAttributes,
)

TASK_ATTRIB = {
    "fps": 25.0,
    "frameStart": 1001,
    "frameEnd": 1100,
    "handleStart": 10,
    "handleEnd": 10,
    "resolutionWidth": 1920,
    "resolutionHeight": 1080,
}


class FakeHost:
    def get_current_workfile(self):
        return "/work/sh010_compositing_v001.nk"


@pytest.fixture(autouse=True)
def host(monkeypatch):
    monkeypatch.setattr(
        collect_context_data, "registered_host", lambda: FakeHost()
    )


def set_root(fps=25, width=1920, height=1080, start=1001, end=1100,
             handle_start=10, handle_end=10):
    root = nuke.root()
    nuke.addFormat(f"{width} {height} 1.0 test_{width}x{height}")
    root["format"].setValue(f"test_{width}x{height}")
    root["fps"].setValue(fps)
    root["first_frame"].setValue(start - handle_start)
    root["last_frame"].setValue(end + handle_end)
    napi.set_node_data(
        root,
        napi.INSTANCE_DATA_KNOB,
        {"handleStart": handle_start, "handleEnd": handle_end},
    )


def publish(active=True, product_base_type="render"):
    """Collect and validate a context with one non-workfile instance."""
    context = pyblish.api.Context()
    context.data["taskEntity"] = {"attrib": dict(TASK_ATTRIB)}
    context.data["publish_attributes"] = {
        "ValidateScriptAttributes": {"active": active}
    }
    context.create_instance(
        "renderMain",
        productBaseType=product_base_type,
        family=product_base_type,
        families=[product_base_type],
    )
    pyblish.util.publish(
        context, plugins=[CollectContextData, ValidateScriptAttributes]
    )
    errors = [
        result["error"]
        for result in context.data["results"]
        if result["error"]
    ]
    return context, errors


def test_matching_script_passes():
    set_root()

    _, errors = publish()

    assert errors == []


def test_runs_without_a_workfile_instance():
    set_root(fps=24)

    _, errors = publish(product_base_type="render")

    assert len(errors) == 1
    assert isinstance(errors[0], PublishXmlValidationError)


def test_lists_every_wrong_attribute():
    set_root(fps=24, width=2048, end=1050)

    _, errors = publish()

    message = str(errors[0])
    assert "`fps` is set to `24.0`, but should be set to `25.0`" in message
    assert "`resolutionWidth` is set to `2048`" in message
    assert "`frameEnd` is set to `1050`" in message
    assert "resolutionHeight" not in message


def test_inactive_is_skipped():
    set_root(fps=24)

    _, errors = publish(active=False)

    assert errors == []


def test_repair_sets_context_settings(monkeypatch):
    calls = []

    class FakeWorkfileSettings:
        def set_context_settings(self):
            calls.append("set_context_settings")

    monkeypatch.setattr(
        validate_script_attributes, "WorkfileSettings", FakeWorkfileSettings
    )

    ValidateScriptAttributes.repair(pyblish.api.Context())

    assert calls == ["set_context_settings"]
