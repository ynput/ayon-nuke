"""Workfile colorspace of the root node, `WorkfileSettings.set_colorspace`.

Nuke appends a value missing in its menu with only a console warning, so a
native OCIO config this Nuke does not ship (Nuke 17 has no `aces_1.2`, the
settings default) silently left the script on `nuke-default`.
"""

import ast
import copy
import os

import nuke
import pytest

from ayon_nuke.api import colorspace, lib

SETTINGS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "server", "settings", "imageio.py"
)
# not shipped with any Nuke the addon supports
MISSING_CONFIG = "aces_0.1.1"
# workfile colorspaces present in the OCIO v2 configs Nuke ships
ROLE_COLORSPACES = {
    "working_space": "scene_linear",
    "monitor_lut": "sRGB - Display/ACES 1.0 - SDR Video",
    "monitor_out_lut": "sRGB - Display/ACES 1.0 - SDR Video",
    "int_8_lut": "matte_paint",
    "int_16_lut": "texture_paint",
    "log_lut": "compositing_log",
    "float_lut": "scene_linear",
}
LUT_KNOBS = ("workingSpaceLUT", "int8Lut", "int16Lut", "logLut", "floatLut")


def _default_imageio_settings():
    """`DEFAULT_IMAGEIO_SETTINGS` of the server, without the server."""
    with open(SETTINGS_FILE) as stream:
        tree = ast.parse(stream.read())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None)
            == "DEFAULT_IMAGEIO_SETTINGS"
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("DEFAULT_IMAGEIO_SETTINGS not found")


def _menu_names(knob_name):
    return [item.split("\t")[0] for item in nuke.root()[knob_name].values()]


def _shipped_studio_config():
    for name in _menu_names("OCIO_config"):
        if name.startswith("fn-nuke_studio-config"):
            return name
    pytest.skip("this Nuke ships no fn-nuke studio config")


def _shipped_studio_config_file():
    """Path of a studio config file of this Nuke's install."""
    exe_dir = os.path.dirname(nuke.EXE_PATH)
    for configs_dir in (
        os.path.join(exe_dir, "plugins", "OCIOConfigs", "configs"),
        os.path.join(exe_dir, "..", "Resources", "OCIOConfigs", "configs"),
    ):
        if not os.path.isdir(configs_dir):
            continue
        for name in sorted(os.listdir(configs_dir)):
            if name.startswith("fn-nuke_studio-config"):
                return os.path.normpath(configs_dir), name
    pytest.skip("no fn-nuke studio config file found in the Nuke install")


class Recorder:
    """Stands in for the module's `log`, keeps warnings and errors."""

    def __init__(self):
        self.warnings = []
        self.errors = []

    def warning(self, message, *args):
        self.warnings.append(message % args if args else message)

    def error(self, message, *args):
        self.errors.append(message % args if args else message)

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass


@pytest.fixture
def workfile(monkeypatch):
    """`WorkfileSettings` on the server's default imageio settings.

    Global color management is off (no config preset), so the native
    config of the settings is used. Returns `(settings, imageio, report)`:
    `imageio` is the settings dict to change before `set_colorspace()`,
    `report` has the `messages` shown and the `log`.
    """
    colorspace._DISPLAY_AND_VIEW_COLORSPACES_CACHE.clear()
    colorspace._COLORSPACES_CACHE.clear()
    monkeypatch.setattr(
        lib,
        "get_current_context_imageio_config_preset",
        lambda **kwargs: None,
    )
    messages = []
    monkeypatch.setattr(nuke, "message", lambda text: messages.append(text))
    log = Recorder()
    monkeypatch.setattr(lib, "log", log)
    # a new Nuke session: nothing shown to the artist yet
    monkeypatch.setattr(
        lib.WorkfileSettings, "_reported_native_ocio_configs", set()
    )

    imageio = copy.deepcopy(_default_imageio_settings())
    settings = object.__new__(lib.WorkfileSettings)
    settings._project_name = "test"
    settings._root_node = nuke.root()
    settings.formatting_data = {}
    settings._project_setting = {"nuke": {"imageio": imageio}}

    report = type("Report", (), {})()
    report.messages = messages
    report.log = log
    yield settings, imageio, report
    colorspace._DISPLAY_AND_VIEW_COLORSPACES_CACHE.clear()
    colorspace._COLORSPACES_CACHE.clear()


def test_missing_native_config_is_reported(workfile):
    settings, imageio, report = workfile
    imageio["workfile"]["native_ocio_config"] = MISSING_CONFIG
    root = nuke.root()
    configs = _menu_names("OCIO_config")
    luts = {knob: root[knob].value() for knob in LUT_KNOBS}
    lut_menus = {knob: _menu_names(knob) for knob in LUT_KNOBS}

    settings.set_colorspace()

    assert len(report.messages) == 1
    assert MISSING_CONFIG in report.messages[0]
    # also in the log; the viewer step then logs its own error
    assert report.log.errors[0] == report.messages[0]
    # nothing appended to the menus, the luts are left alone
    assert root["OCIO_config"].value() == "nuke-default"
    assert _menu_names("OCIO_config") == configs
    assert {knob: root[knob].value() for knob in LUT_KNOBS} == luts
    assert {knob: _menu_names(knob) for knob in LUT_KNOBS} == lut_menus


def test_missing_native_config_message_once_per_session(workfile):
    """It runs on every script open, the log keeps each time."""
    settings, imageio, report = workfile
    imageio["workfile"]["native_ocio_config"] = MISSING_CONFIG

    settings.set_colorspace()
    settings.set_colorspace()

    assert len(report.messages) == 1
    errors = [error for error in report.log.errors if MISSING_CONFIG in error]
    assert len(errors) == 2


def test_colorspace_label_is_not_accepted(workfile):
    """Nuke appends a menu item's label, it is not a value."""
    settings, imageio, report = workfile
    config = _shipped_studio_config()
    imageio["workfile"]["native_ocio_config"] = config
    imageio["workfile"].update(ROLE_COLORSPACES)
    settings.set_colorspace()
    # ex: "scene_linear (ACEScg)" of "scene_linear\tscene_linear (ACEScg)"
    label = next(
        item.split("\t")[1]
        for item in nuke.root()["workingSpaceLUT"].values()
        if item.startswith("scene_linear\t")
    )
    imageio["workfile"]["working_space"] = label

    settings.set_colorspace()

    assert label not in _menu_names("workingSpaceLUT")
    assert nuke.root()["workingSpaceLUT"].value() == "scene_linear"
    assert len(report.log.warnings) == 1
    assert label in report.log.warnings[0]


def test_default_native_config_on_this_nuke(workfile):
    """`aces_1.2` works where Nuke ships it and is reported where not."""
    settings, imageio, report = workfile
    shipped = "aces_1.2" in _menu_names("OCIO_config")

    settings.set_colorspace()

    root = nuke.root()
    if shipped:
        assert report.messages == []
        assert root["OCIO_config"].value() == "aces_1.2"
        assert root["workingSpaceLUT"].value() == "role_scene_linear"
        assert root["monitorLut"].value() == "sRGB (ACES)"
    else:
        # Nuke 17 and newer
        assert len(report.messages) == 1
        assert "aces_1.2" in report.messages[0]
        assert root["OCIO_config"].value() == "nuke-default"
        assert "aces_1.2" not in _menu_names("OCIO_config")
        assert "role_scene_linear" not in _menu_names("workingSpaceLUT")


def test_shipped_native_config_is_set(workfile):
    settings, imageio, report = workfile
    config = _shipped_studio_config()
    imageio["workfile"]["native_ocio_config"] = config
    imageio["workfile"].update(ROLE_COLORSPACES)

    settings.set_colorspace()

    root = nuke.root()
    assert report.messages == []
    assert report.log.warnings == []
    assert root["OCIO_config"].value() == config
    assert root["workingSpaceLUT"].value() == "scene_linear"
    assert root["floatLut"].value() == "scene_linear"
    assert root["logLut"].value() == "compositing_log"
    assert (
        root["monitorLut"].value() == "ACES 1.0 - SDR Video (sRGB - Display)"
    )


def test_colorspace_missing_in_config_is_skipped(workfile):
    """`role_*` names of OCIO v1 configs are not in the OCIO v2 ones."""
    settings, imageio, report = workfile
    config = _shipped_studio_config()
    imageio["workfile"]["native_ocio_config"] = config
    imageio["workfile"].update(ROLE_COLORSPACES)
    imageio["workfile"]["working_space"] = "role_scene_linear"

    settings.set_colorspace()

    root = nuke.root()
    assert report.messages == []
    assert root["OCIO_config"].value() == config
    assert "role_scene_linear" not in _menu_names("workingSpaceLUT")
    assert root["workingSpaceLUT"].value() != "role_scene_linear"
    # the other colorspaces are still set
    assert root["floatLut"].value() == "scene_linear"
    assert len(report.log.warnings) == 1
    assert "workingSpaceLUT: 'role_scene_linear'" in report.log.warnings[0]


def test_colorspace_alias_is_accepted(workfile):
    settings, imageio, report = workfile
    config = _shipped_studio_config()
    imageio["workfile"]["native_ocio_config"] = config
    imageio["workfile"].update(ROLE_COLORSPACES)
    # an alias of `ACEScg` in the fn-nuke studio configs
    imageio["workfile"]["working_space"] = "ACES - ACEScg"

    settings.set_colorspace()

    assert report.log.warnings == []
    assert nuke.root()["workingSpaceLUT"].value() == "ACEScg"


def test_nuke_color_management_ignores_native_config(workfile):
    """The native config is used only by the OCIO workflow."""
    settings, imageio, report = workfile
    imageio["workfile"].update(
        {
            "color_management": "Nuke",
            "native_ocio_config": MISSING_CONFIG,
            "working_space": "linear",
            "monitor_lut": "sRGB",
            "monitor_out_lut": "rec709",
            "int_8_lut": "sRGB",
            "int_16_lut": "sRGB",
            "log_lut": "Cineon",
            "float_lut": "linear",
        }
    )

    settings.set_colorspace()

    root = nuke.root()
    assert report.messages == []
    assert root["colorManagement"].value() == "Nuke"
    assert MISSING_CONFIG not in _menu_names("OCIO_config")
    assert root["logLut"].value() == "Cineon"


def test_global_config_colorspaces_are_set(workfile, monkeypatch):
    """The config path is a `[getenv]` expression, the menus follow it."""
    settings, imageio, report = workfile
    configs_dir, file_name = _shipped_studio_config_file()
    path = os.path.join(configs_dir, file_name).replace("\\", "/")
    monkeypatch.setenv("BUILTIN_OCIO_ROOT", configs_dir)
    monkeypatch.setenv("OCIO", path)
    config_data = {
        "path": path,
        "template": "{BUILTIN_OCIO_ROOT}/" + file_name,
    }
    monkeypatch.setattr(
        lib,
        "get_current_context_imageio_config_preset",
        lambda **kwargs: config_data,
    )
    imageio["workfile"].update(ROLE_COLORSPACES)

    settings.set_colorspace()

    root = nuke.root()
    assert report.messages == []
    assert report.log.warnings == []
    assert root["OCIO_config"].value() == "custom"
    assert "[getenv BUILTIN_OCIO_ROOT]" in root["customOCIOConfigPath"].value()
    assert root["workingSpaceLUT"].value() == "scene_linear"
    assert root["floatLut"].value() == "scene_linear"
