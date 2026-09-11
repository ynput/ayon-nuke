import os

import nuke
import ayon_api

from ayon_core.pipeline import load
from ayon_nuke.api import (
    containerise,
    parse_container,
    update_container,
)
from ayon_nuke.api.command import undo_chunk
from ayon_nuke.api.lib import maintained_selection

try:
    from pxr import Usd, UsdGeom
except ImportError:  # USD is available only in compatible Nuke runtimes.
    Usd = None
    UsdGeom = None


def _require_usd():
    if Usd is None or UsdGeom is None:
        raise RuntimeError(
            "USD support is unavailable in this Nuke runtime. "
            "Use a Nuke build with USD Python support."
        )


def _camera_prim_path(usd_path, existing_path=None):
    """Return a valid camera prim path from a USD file."""
    _require_usd()

    if not usd_path or not os.path.exists(usd_path):
        raise RuntimeError(f"USD camera file does not exist: {usd_path}")

    stage = Usd.Stage.Open(usd_path)
    if not stage:
        raise RuntimeError(f"Could not open USD camera file: {usd_path}")

    if existing_path:
        prim = stage.GetPrimAtPath(existing_path)
        if prim and prim.IsA(UsdGeom.Camera):
            return existing_path

    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Camera):
            return prim.GetPath().pathString

    raise RuntimeError(f"No camera prim found in USD file: {usd_path}")


def _create_usd_camera_node(object_name, usd_path):
    """Create the newest available Camera-family USD import node."""
    last_error = None
    for node_class in ("Camera4", "Camera3"):
        try:
            node = nuke.createNode(
                node_class,
                "name {} file {} import_enabled True".format(
                    object_name, usd_path
                ),
                inpanel=False,
            )
        except (RuntimeError, NameError) as exc:
            last_error = exc
            continue

        required_knobs = (
            "file",
            "frame_rate",
            "import_enabled",
            "import_prim_path",
        )
        missing = [name for name in required_knobs if name not in node.knobs()]
        if missing:
            nuke.delete(node)
            last_error = RuntimeError(
                f"{node_class} is missing USD knobs: {', '.join(missing)}"
            )
            continue
        return node

    raise RuntimeError(
        "This Nuke runtime has no USD-capable Camera-family node."
    ) from last_error


def _version_imprint(context):
    version = context["version"]
    attributes = version.get("attrib") or {}
    imprint = {
        "representation": context["representation"]["id"],
        "version": version.get("version"),
        "frameStart": attributes.get("frameStart"),
        "frameEnd": attributes.get("frameEnd"),
        "source": attributes.get("source"),
        "fps": attributes.get("fps"),
    }
    return imprint, attributes.get("fps") or nuke.root()["fps"].value()


def _node_values(node):
    values = {}
    for knob_name in (
        "file",
        "frame_rate",
        "import_enabled",
        "import_prim_path",
        "tile_color",
    ):
        if knob_name in node.knobs():
            values[knob_name] = node[knob_name].value()
    return values


def _restore_node_values(node, values):
    for knob_name, value in values.items():
        if knob_name in node.knobs():
            node[knob_name].setValue(value)


class UsdCameraLoader(load.LoaderPlugin):
    """Load a USD file containing a camera into Nuke.

    This legacy loader intentionally keeps its broad compatibility contract.
    Existing containers persist this class name and must continue to resolve.
    """

    label = "Load USD Camera"
    icon = "camera"
    color = "orange"
    order = 2

    extensions = {"usd", "usda", "usdc"}
    product_base_types = {"*"}
    product_types = product_base_types
    representations = {"*"}

    node_color = "0x3469ffff"
    settings_category = "nuke"

    @undo_chunk("Load USD Camera")
    def load(self, context, name, namespace, data):
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        namespace: str = namespace or context["folder"]["name"]
        object_name: str = "{}_{}".format(name, namespace)

        file = self.filepath_from_context(context).replace("\\", "/")

        with maintained_selection():
            camera_node = nuke.createNode(
                "Camera4",
                "name {} file {} import_enabled True".format(
                    object_name, file
                ),
                inpanel=False,
            )
            camera_node.forceValidate()
            camera_node["frame_rate"].setValue(float(fps))

        self.node_version_color(
            context["project"]["name"], version_entity, camera_node
        )

        self.set_usd_camera_prim_path(camera_node)

        return containerise(
            node=camera_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )

    @undo_chunk("Update USD Camera")
    def update(self, container, context):
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        file = self.filepath_from_context(context).replace("\\", "/")

        with maintained_selection():
            camera_node = container["node"]
            camera_node["frame_rate"].setValue(float(fps))
            camera_node["file"].setValue(file)

        self.set_usd_camera_prim_path(camera_node)
        self.node_version_color(
            context["project"]["name"], version_entity, camera_node
        )

        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )

        return update_container(
            camera_node, {"representation": context["representation"]["id"]}
        )

    def node_version_color(self, project_name, version_entity, node):
        """Colour a node according to the version's latest status."""
        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        if version_entity["id"] == last_version_entity["id"]:
            color_value = self.node_color
        else:
            color_value = "0xd88467ff"
        node["tile_color"].setValue(int(color_value, 16))

    def switch(self, container, context):
        self.update(container, context)

    @undo_chunk("Remove USD Camera")
    def remove(self, container):
        nuke.delete(container["node"])

    def set_usd_camera_prim_path(self, camera_node):
        """Set the first valid camera prim unless the current one is valid."""
        usd_path = camera_node["file"].value()
        prim_path = _camera_prim_path(
            usd_path, camera_node["import_prim_path"].value()
        )
        camera_node["import_prim_path"].setValue(prim_path)


class UsdCameraLoaderV2(UsdCameraLoader):
    """Load and update published USD camera products in place."""

    label = "Load USD Camera (V2)"
    order = 1
    product_base_types = {"camera"}
    product_types = product_base_types
    representations = {"usd"}

    @undo_chunk("Load USD Camera (V2)")
    def load(self, context, name, namespace, data):
        imprint, fps = _version_imprint(context)
        namespace = namespace or context["folder"]["name"]
        object_name = "{}_{}".format(name, namespace)
        usd_path = self.filepath_from_context(context).replace("\\", "/")

        camera_node = None
        try:
            prim_path = _camera_prim_path(usd_path)
            with maintained_selection():
                camera_node = _create_usd_camera_node(object_name, usd_path)
                camera_node.forceValidate()
                camera_node["frame_rate"].setValue(float(fps))
                camera_node["import_prim_path"].setValue(prim_path)
                camera_node.forceValidate()

            self.node_version_color(
                context["project"]["name"], context["version"], camera_node
            )
            return containerise(
                node=camera_node,
                name=name,
                namespace=namespace,
                context=context,
                loader=self.__class__.__name__,
                data=imprint,
            )
        except Exception:
            if camera_node is not None:
                nuke.delete(camera_node)
            raise

    @undo_chunk("Update USD Camera (V2)")
    def update(self, container, context):
        node = container["node"]
        previous_values = _node_values(node)
        previous_container = parse_container(node).copy()
        previous_container.pop("node", None)
        previous_container.pop("objectName", None)

        imprint, fps = _version_imprint(context)
        usd_path = self.filepath_from_context(context).replace("\\", "/")
        existing_path = previous_values.get("import_prim_path")

        try:
            prim_path = _camera_prim_path(usd_path, existing_path)
            with maintained_selection():
                node["file"].setValue(usd_path)
                node["frame_rate"].setValue(float(fps))
                node["import_enabled"].setValue(True)
                node["import_prim_path"].setValue(prim_path)
                node.forceValidate()

            self.node_version_color(
                context["project"]["name"], context["version"], node
            )
            result = update_container(node, imprint)
        except Exception:
            _restore_node_values(node, previous_values)
            node.forceValidate()
            update_container(node, previous_container)
            raise

        self.log.info(
            "updated to version: {}".format(context["version"]["version"])
        )
        return result

    def switch(self, container, context):
        return self.update(container, context)

    @undo_chunk("Remove USD Camera (V2)")
    def remove(self, container):
        nuke.delete(container["node"])
