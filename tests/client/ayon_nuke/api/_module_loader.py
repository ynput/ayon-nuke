"""Load `ayon_nuke` modules without importing the whole package.

`ayon_nuke.api` package imports Nuke and Qt related modules, so tested
modules are loaded directly from their files with `nuke` mocked and
other `ayon_nuke` modules replaced by stubs.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Optional
from unittest import mock

CLIENT_PATH = Path(__file__).resolve().parents[4] / "client" / "ayon_nuke"
API_PATH = CLIENT_PATH / "api"
LOAD_PLUGINS_PATH = CLIENT_PATH / "plugins" / "load"

_counter = 0


def _exec_module(path: Path, patched_modules: dict):
    global _counter
    _counter += 1
    module_name = f"_under_test_{path.stem}_{_counter}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, patched_modules):
        # dataclasses need the module registered while it is executed
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module


def load_api_module(
    name: str,
    blocked_modules: Optional[list[str]] = None,
):
    """Load module from `ayon_nuke/api`.

    Args:
        name (str): Module name (file name without extension).
        blocked_modules (Optional[list[str]]): Modules which raise
            ImportError on import, e.g. to simulate older ayon-core.

    """
    patched_modules = {"nuke": mock.MagicMock()}
    for blocked in blocked_modules or []:
        # None in 'sys.modules' makes import raise ImportError
        patched_modules[blocked] = None
    return _exec_module(API_PATH / f"{name}.py", patched_modules)


def _stub(name: str, **attributes) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_load_plugin_module(name: str, load_traits_module):
    """Load loader plugin module with stubbed Nuke and `ayon_nuke.api`.

    Args:
        name (str): Plugin module name (file name without extension).
        load_traits_module: Loaded `ayon_nuke.api.load_traits` module.

    """
    from ayon_core.pipeline import load

    nuke_module = mock.MagicMock()
    nuke_module.root.return_value.__getitem__.return_value.value.return_value = 1001  # noqa: E501
    api = _stub(
        "ayon_nuke.api",
        containerise=mock.MagicMock(),
        update_container=mock.MagicMock(),
        colorspace_exists_on_node=mock.MagicMock(),
        load_traits=load_traits_module,
    )
    patched_modules = {
        "nuke": nuke_module,
        "ayon_nuke": _stub("ayon_nuke", api=api),
        "ayon_nuke.api": api,
        "ayon_nuke.api.lib": _stub(
            "ayon_nuke.api.lib", maintained_selection=mock.MagicMock()),
        "ayon_nuke.api.command": _stub(
            "ayon_nuke.api.command",
            undo_chunk=lambda *_args, **_kwargs: (lambda func: func),
        ),
        "ayon_nuke.api.plugin": _stub(
            "ayon_nuke.api.plugin",
            NukeLoader=type("NukeLoader", (load.LoaderPlugin,), {}),
        ),
        "ayon_nuke.api.load_traits": load_traits_module,
        "ayon_nuke.api.load_utils": _stub(
            "ayon_nuke.api.load_utils",
            set_read_colorspace=mock.MagicMock(),
        ),
    }
    return _exec_module(LOAD_PLUGINS_PATH / f"{name}.py", patched_modules)
