import nuke

from ayon_core.lib import (
    NumberDef,
    UISeparatorDef,
)
from ayon_nuke import api as napi


class CreateWriteImage(napi.NukeWriteCreator):

    settings_category = "nuke"

    identifier = "create_write_image"
    label = "Image (write)"
    product_base_type = "image"
    product_type = product_base_type
    icon = "sign-out"

    instance_attributes = [
        "use_range_limit"
    ]
    default_variants = [
        "StillFrame",
        "MPFrame",
        "LayoutFrame"
    ]

    def get_pre_create_attr_defs(self):
        attr_defs = super().get_pre_create_attr_defs()
        attr_defs.extend([
            UISeparatorDef(),
            NumberDef(
                "active_frame",
                label="Active frame",
                default=nuke.frame()
            ),
        ])
        return attr_defs

    def _get_render_target_enum(self):
        # Prevent farm rendering for still image (force local).
        if "farm_rendering" in self.instance_attributes:
            self.instance_attributes.remove("farm_rendering")

        return super()._get_render_target_enum()

    def create_instance_node(
            self, product_name, instance_data, staging_dir=None, node_selection=None):
        settings = self.project_settings["nuke"]["create"]["CreateWriteImage"]

        # add fpath_template
        write_data = {
            "creator": self.__class__.__name__,
            "productName": product_name,
            "fpath_template": self.temp_rendering_path_template,
            "staging_dir": staging_dir,
            "render_on_farm": (
                "render_on_farm" in settings["instance_attributes"]
            )
        }
        write_data.update(instance_data)

        if node_selection:
            selected_node = node_selection[0]
        else:
            selected_node = None

        created_node = napi.create_write_node(
            product_name,
            write_data,
            input=selected_node,
            prenodes=self.prenodes,
            linked_knobs=self.get_linked_knobs(),
            **{
                "frame": nuke.frame()
            }
        )

        self._add_frame_range_limit(created_node, instance_data)

        self.integrate_links(node_selection, created_node, outputs=True)

        return created_node

    def _add_frame_range_limit(self, write_node, instance_data):
        if "use_range_limit" not in self.instance_attributes:
            return

        active_frame = (
            instance_data["creator_attributes"].get("active_frame"))

        write_node.begin()
        for n in nuke.allNodes():
            # get write node
            if n.Class() in "Write":
                w_node = n
        write_node.end()

        w_node["use_limit"].setValue(True)
        w_node["first"].setValue(active_frame or nuke.frame())
        w_node["last"].setExpression("first")

        return write_node
