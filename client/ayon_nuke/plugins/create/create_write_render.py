import nuke

from ayon_nuke import api as napi


class CreateWriteRender(napi.NukeWriteCreator):

    settings_category = "nuke"

    identifier = "create_write_render"
    label = "Render (write)"
    product_type = "render"
    icon = "sign-out"

    instance_attributes = [
        "reviewable"
    ]
    default_variants = [
        "Main",
        "Mask"
    ]

    def create_instance_node(
            self, product_name, instance_data, staging_dir=None, node_selection=None):
        settings = self.project_settings["nuke"]["create"]["CreateWriteRender"]

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

        self.log.debug(">>>>>>> : {}".format(self.instance_attributes))
        self.log.debug(">>>>>>> : {}".format(self.get_linked_knobs()))

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

        self.integrate_links(node_selection, created_node, outputs=False)

        return created_node
