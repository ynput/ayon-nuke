import nuke
from ayon_nuke.api import (
    containerise,
    plugin,
    update_container,
)
from ayon_nuke.api.command import undo_chunk
from ayon_nuke.api.lib import color_to_int, maintained_selection
from pxr import Usd, UsdGeom


class UsdCameraLoader(plugin.NukeLoader):
    """
    This will load usd camera into script.
    """

    label = "Load USD Camera"
    icon = "camera"
    color = "orange"
    order = 2

    extensions = {"usd", "usda", "usdc"}
    # There are essentially no 'camera' product type USD publishers available
    # in the majority of integrations, so we allow loading any usd
    # file. This way also USD Shots with cameras can be loaded.
    product_base_types = {"*"}
    product_types = product_base_types
    representations = {"*"}

    node_color_latest   = color_to_int(52, 105, 255)   # 0x3469ffff
    node_color_outdated = color_to_int(216, 132, 103)  # 0xd88467ff

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

        container = containerise(
            node=camera_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )
        self.update_node_color(camera_node)  # after containerise
        return container

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

        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )

        container = update_container(camera_node, {
            "representation": context["representation"]["id"]
        })
        self.update_node_color(camera_node)  # after update_container
        return container

    def switch(self, container, context):
        self.update(container, context)

    @undo_chunk("Remove USD Camera")
    def remove(self, container):
        node = container["node"]
        nuke.delete(node)

    def set_usd_camera_prim_path(self, camera_node):
        """Set the camera prim path on the Camera4 node.

        If already set and valid, does nothing. Otherwise, finds the first
        camera prim in the USD file and sets it.
        """
        # Get the USD file path from the node
        usd_path = camera_node["file"].value()
        if not usd_path:
            self.log.error("No USD file set on Camera4 node")
            return

        # Open USD stage
        stage = Usd.Stage.Open(usd_path)
        if not stage:
            self.log.error("Failed to open USD stage")
            return

        # If prim path is already set (e.g. on update) and the prim
        # is an existing camera in the stage, do nothing.
        existing_prim_path = camera_node["import_prim_path"].value()
        if existing_prim_path:
            prim = stage.GetPrimAtPath(existing_prim_path)
            if prim and prim.IsA(UsdGeom.Camera):
                self.log.info(
                    f"Camera prim path already set to: {existing_prim_path}"
                )
                return

        # Find first camera prim
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Camera):
                prim_path = prim.GetPath().pathString

                # Set Import Prim Path
                camera_node["import_prim_path"].setValue(prim_path)

                self.log.info(f"Set camera to: {prim_path}")
                return

        self.log.error("No camera found in USD file")
