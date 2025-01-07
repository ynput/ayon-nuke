import nuke

from ayon_nuke import api as napi


class CreateWritePrerender(napi.NukeWriteCreator):

    settings_category = "nuke"

    identifier = "create_write_prerender"
    label = "Prerender (write)"
    product_type = "prerender"
    icon = "sign-out"

    instance_attributes = [
        "use_range_limit"
    ]
    default_variants = [
        "Key01",
        "Bg01",
        "Fg01",
        "Branch01",
        "Part01"
    ]

    # Before write node render.
    order = 90

    def create_instance_node(
            self, product_name, instance_data, staging_dir=None, node_selection=None):
        settings = self.project_settings["nuke"]["create"]
        settings = settings["CreateWritePrerender"]

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

        # get width and height
        if node_selection:  # contains 1 Write node or nothing
            selected_node = node_selection[0]
            width, height = (
                selected_node.width(), selected_node.height())
        else:
            actual_format = nuke.root().knob('format').value()
            width, height = (actual_format.width(), actual_format.height())
            selected_node = None

        created_node = napi.create_write_node(
            product_name,
            write_data,
            input=selected_node,
            prenodes=self.prenodes,
            linked_knobs=self.get_linked_knobs(),
            **{
                "width": width,
                "height": height
            }
        )

        self._add_frame_range_limit(created_node)

        self.integrate_links(node_selection, created_node, outputs=True)

        return created_node

    def _add_frame_range_limit(self, write_node):
        if "use_range_limit" not in self.instance_attributes:
            return

        write_node.begin()
        for n in nuke.allNodes():
            # get write node
            if n.Class() in "Write":
                w_node = n
        write_node.end()

        w_node["use_limit"].setValue(True)
        w_node["first"].setValue(nuke.root()["first_frame"].value())
        w_node["last"].setValue(nuke.root()["last_frame"].value())

        return write_node
