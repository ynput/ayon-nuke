"""Loaded and created nodes get a valid Nuke node name.

Folder and product names may have `.` and `-` (`sh010.v2`), which a Nuke
node name can't have: `setName` raises "illegal name" and
`createNode(cls, "name ...")` makes a node `nuke.toNode` can't find.
"""

import json

import nuke
import pytest

import ayon_api
from ayon_nuke.api import lib, plugin
from ayon_nuke.plugins.load import (
    load_backdrop,
    load_camera,
    load_camera_usd,
    load_clip,
    load_gizmo,
    load_image,
    load_model,
    load_ociolook,
    load_script_precomp,
    load_usd,
)

FOLDER = "sh010.v2"
PRODUCT = "matteShapes.main"
NODE_NAME = "matteShapes_main_sh010_v2"

USD_CAMERA = """#usda 1.0
def Xform "root"
{
    def Camera "cam"
    {
    }
}
"""


@pytest.mark.parametrize(
    "name, expected",
    [
        ("renderMain_sh010", "renderMain_sh010"),
        ("renderMain_sh010.v2", "renderMain_sh010_v2"),
        ("plate-main_sh010", "plate_main_sh010"),
        ("010_plate", "_010_plate"),
    ],
)
def test_sanitize_node_name(name, expected):
    assert lib.sanitize_node_name(name) == expected

    node = nuke.createNode("NoOp", inpanel=False)
    node.setName(expected)
    assert node.name() == expected


@pytest.fixture
def context():
    return {
        "project": {"name": "test"},
        "folder": {"name": FOLDER},
        "product": {"name": PRODUCT, "productType": "matteShapes"},
        "version": {
            "id": "version-id",
            "productId": "product-id",
            "version": 1,
            "attrib": {
                "frameStart": 1001,
                "frameEnd": 1010,
                "handleStart": 0,
                "handleEnd": 0,
                "fps": 25.0,
                "source": "",
                "colorSpace": None,
            },
        },
        "representation": {
            "id": "representation-id",
            "name": "nk",
            "context": {"representation": "nk"},
        },
    }


@pytest.fixture(autouse=True)
def no_server(monkeypatch):
    monkeypatch.setattr(
        ayon_api, "version_is_latest", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        ayon_api,
        "get_last_version_by_product_id",
        lambda *args, **kwargs: {"id": "version-id"},
    )


def _load(monkeypatch, loader_cls, path, context):
    monkeypatch.setattr(
        loader_cls,
        "filepath_from_context",
        classmethod(lambda cls, _context: str(path).replace("\\", "/")),
    )
    nuke.endGroup()
    return loader_cls().load(context, PRODUCT, None, {})


def _assert_valid_name(node):
    assert node.name() == NODE_NAME
    assert nuke.toNode(NODE_NAME) is node


def _nk_file(tmp_path, *node_classes):
    for node_class in node_classes:
        nuke.createNode(node_class, inpanel=False)
    path = tmp_path / "nodes.nk"
    nuke.selectAll()
    nuke.nodeCopy(str(path).replace("\\", "/"))
    nuke.scriptClear()
    return path


def test_backdrop_keeps_the_folder_name_in_the_label(
    monkeypatch, tmp_path, context
):
    path = _nk_file(tmp_path, "Blur")

    node = _load(monkeypatch, load_backdrop.LoadBackdropNodes, path, context)

    _assert_valid_name(node)
    assert f"{PRODUCT}_{FOLDER}" in node["label"].value()


def test_gizmo(monkeypatch, tmp_path, context):
    path = _nk_file(tmp_path, "Group")

    node = _load(monkeypatch, load_gizmo.LoadGizmo, path, context)

    _assert_valid_name(node)


def test_group_loader(monkeypatch, context):
    node = _load(monkeypatch, plugin.NukeGroupLoader, "", context)

    assert node.name() == f"{NODE_NAME}_1"


def test_precomp(monkeypatch, tmp_path, context):
    path = _nk_file(tmp_path, "Blur")

    node = _load(
        monkeypatch, load_script_precomp.LinkAsGroup, path, context
    )

    _assert_valid_name(node)


def test_ocio_look(monkeypatch, tmp_path, context):
    path = tmp_path / "look.json"
    working_space = {
        "name": nuke.root()["workingSpaceLUT"].value(),
        "type": "colorspaces",
    }
    path.write_text(json.dumps({
        "version": 1,
        "data": {
            "ocioLookWorkingSpace": working_space,
            "ocioLookItems": [],
        },
    }))

    node = _load(
        monkeypatch, load_ociolook.LoadOcioLookNodes, path, context
    )

    _assert_valid_name(node)


@pytest.mark.parametrize(
    "loader_cls, node_class",
    [
        (load_camera.AlembicCameraLoader, "Camera3"),
        (load_camera_usd.UsdCameraLoader, "Camera4"),
        (load_model.AlembicModelLoader, "ReadGeo2"),
        (load_usd.GeoImportLoader, "GeoImport"),
        (load_usd.GeoReferenceLoader, "GeoReference"),
    ],
)
def test_3d_loaders(monkeypatch, tmp_path, context, loader_cls, node_class):
    try:
        nuke.delete(nuke.createNode(node_class, inpanel=False))
    except RuntimeError:
        pytest.skip(f"No {node_class} node in this Nuke")
    # Copies through the clipboard, which terminal mode doesn't have.
    monkeypatch.setattr(
        load_model.AlembicModelLoader,
        "_fix_scene_view_contents",
        lambda self, node: node,
    )
    path = tmp_path / "camera.usda"
    path.write_text(USD_CAMERA)

    node = _load(monkeypatch, loader_cls, path, context)

    _assert_valid_name(node)


@pytest.mark.parametrize(
    "loader_cls", [load_clip.LoadClip, load_image.LoadImage]
)
def test_read_node_name_template(monkeypatch, context, loader_cls):
    monkeypatch.setattr(
        loader_cls, "node_name_template", "{product[name]}_{folder[name]}"
    )

    assert loader_cls()._get_node_name(context) == NODE_NAME
