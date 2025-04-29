import nuke
import ayon_api

from ayon_core.pipeline import (
    load,
    get_representation_path,
)
from ayon_nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop
)
from ayon_nuke.api.lib import (
    maintained_selection
)


class AlembicCameraLoader(load.LoaderPlugin):
    """
    This will load a camera into script.
    """

    product_types = {"camera"}
    representations = {"*"}
    extensions = {"abc"}
    label = "Load Alembic Camera"
    enabled = True

    settings_category = "nuke"

    icon = "camera"
    color = "orange"
    node_color = "0x3469ffff"

    def load(self, context, name, namespace, data):
        # get main variables
        version_entity = context["version"]

        version_attributes = version_entity["attrib"]
        first = version_attributes.get("frameStart")
        last = version_attributes.get("frameEnd")
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        namespace = namespace or context["folder"]["name"]
        object_name = "{}_{}".format(name, namespace)

        # prepare data for imprinting
        # add additional metadata from the version to imprint to metadata knob
        data_imprint = {
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"],
        }
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # getting file path
        file = self.filepath_from_context(context).replace("\\", "/")

        with maintained_selection():

            try:
                camera_node = nuke.createNode(
                    "Camera3",
                    "name {} file {} read_from_file True".format(
                        object_name, file),
                    inpanel=False
                )
            except RuntimeError: # older nuke version
                camera_node = nuke.createNode(
                    "Camera2",
                    "name {} file {} read_from_file True".format(
                        object_name, file),
                    inpanel=False
                )                

            camera_node.forceValidate()
            camera_node["frame_rate"].setValue(float(fps))

            # workaround because nuke's bug is not adding
            # animation keys properly
            xpos = camera_node.xpos()
            ypos = camera_node.ypos()
            nuke.nodeCopy("%clipboard%")
            nuke.delete(camera_node)
            nuke.nodePaste("%clipboard%")
            camera_node = nuke.toNode(object_name)
            camera_node.setXYpos(xpos, ypos)

        # color node by correct color by actual version
        self.node_version_color(
            context["project"]["name"], version_entity, camera_node
        )

        return containerise(
            node=camera_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint)

    def update(self, container, context):
        """
            Called by Scene Inventory when look should be updated to current
            version.
            If any reference edits cannot be applied, eg. shader renamed and
            material not present, reference is unloaded and cleaned.
            All failed edits are highlighted to the user via message box.

        Args:
            container: object that has look to be updated
            representation: (dict): relationship data to get proper
                                    representation from DB and persisted
                                    data in .json
        Returns:
            None
        """
        # Get version from io
        version_entity = context["version"]
        repre_entity = context["representation"]

        # get main variables
        version_attributes = version_entity["attrib"]
        first = version_attributes.get("frameStart")
        last = version_attributes.get("frameEnd")
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        # prepare data for imprinting
        data_imprint = {
            "representation": repre_entity["id"],
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"]
        }

        # add attributes from the version to imprint to metadata knob
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # getting file path
        file = get_representation_path(repre_entity).replace("\\", "/")

        with maintained_selection():
            camera_node = container["node"]
            camera_node['selected'].setValue(True)

            # collect input output dependencies
            dependencies = camera_node.dependencies()
            dependent = camera_node.dependent()

            camera_node["frame_rate"].setValue(float(fps))
            camera_node["file"].setValue(file)

            # workaround because nuke's bug is
            # not adding animation keys properly
            xpos = camera_node.xpos()
            ypos = camera_node.ypos()
            nuke.nodeCopy("%clipboard%")
            camera_name = camera_node.name()
            nuke.delete(camera_node)
            nuke.nodePaste("%clipboard%")
            camera_node = nuke.toNode(camera_name)
            camera_node.setXYpos(xpos, ypos)

            # link to original input nodes
            for i, input in enumerate(dependencies):
                camera_node.setInput(i, input)
            # link to original output nodes
            for d in dependent:
                index = next((i for i, dpcy in enumerate(
                              d.dependencies())
                              if camera_node is dpcy), 0)
                d.setInput(index, camera_node)

        # color node by correct color by actual version
        self.node_version_color(
            context["project"]["name"], version_entity, camera_node
        )

        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )

        return update_container(camera_node, data_imprint)

    def node_version_color(self, project_name, version_entity, node):
        """ Coloring a node by correct color by actual version
        """
        # get all versions in list
        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        # change color of node
        if version_entity["id"] == last_version_entity["id"]:
            color_value = self.node_color
        else:
            color_value = "0xd88467ff"
        node["tile_color"].setValue(int(color_value, 16))

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = container["node"]
        with viewer_update_and_undo_stop():
            nuke.delete(node)


class FbxCameraLoader(AlembicCameraLoader):
    """
    This will load fbx camera into script.
    """
    extensions = {"fbx"}
    label = "Load FBX Camera"

    def load(self, context, name, namespace, data):
        fbx_camera_node = super().load(context, name, namespace,data)

        # Nuke forces 7 standard FBX cameras
        # Producer Perspective, Producer Top, Producer Bottom...
        # https://learn.foundry.com/nuke/11.1/content/comp_environment
        # /3d_compositing/importing_fbx_cameras.html
        # The following ensure the camera node is set to exported camera data.
        fbx_camera_node.forceValidate() 

        try:
            knob = fbx_camera_node["fbx_take_name"]
            knob.setValue(0)

        except NameError:
            # WARNING - Nuke 15: Camera3 validate does not play along
            # very well when mixing abc + fbx nodes in the same script.
            # They need to reloaded manually.
            #
            # Hopefully this will be fixed by upcoming Camera4            
            raise RuntimeError(
                "Could not load incoming FBX camera properly. "
                "This could be caused by a mix of abc and fbx "
                "into the script."
            )

        knob = fbx_camera_node["fbx_node_name"]
        knob.setValue(knob.values()[-1])

        return fbx_camera_node
