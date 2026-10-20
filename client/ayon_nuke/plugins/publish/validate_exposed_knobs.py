import pyblish.api

from ayon_core.pipeline.publish import get_errored_instances_from_context
from ayon_nuke.api.lib import link_knobs
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError
)


class RepairExposedKnobs(pyblish.api.Action):
    label = "Repair"
    on = "failed"
    icon = "wrench"

    def process(self, context, plugin):
        instances = get_errored_instances_from_context(context)

        for instance in instances:
            child_nodes = (
                instance.data.get("transientData", {}).get("childNodes")
                or instance
            )

            write_group_node = instance.data["transientData"]["node"]
            # get write node from inside of group
            write_node = None
            for x in child_nodes:
                if x.Class() == "Write":
                    write_node = x

            creator_identifier = instance.data["creator_identifier"]
            plugin_name = plugin.creator_settings_mapping[creator_identifier]
            nuke_settings = instance.context.data["project_settings"]["nuke"]
            create_settings = nuke_settings["create"][plugin_name]
            exposed_knobs = create_settings["exposed_knobs"]
            link_knobs(exposed_knobs, write_node, write_group_node)


class ValidateExposedKnobs(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validate write node exposed knobs.

    Compare exposed linked knobs to settings.
    """

    order = pyblish.api.ValidatorOrder
    optional = False
    families = ["render", "prerender", "image"]
    label = "Validate Exposed Knobs"
    actions = [RepairExposedKnobs]
    hosts = ["nuke"]

    settings_category = "nuke"

    creator_settings_mapping = {
        "create_write_render": "CreateWriteRender",
        "create_write_prerender": "CreateWritePrerender",
        "create_write_prerender_alpha": "CreateWritePrerenderAlpha",
        "create_write_image": "CreateWriteImage"
    }

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        creator_identifier = instance.data["creator_identifier"]
        plugin = self.creator_settings_mapping[creator_identifier]
        group_node = instance.data["transientData"]["node"]
        nuke_settings = instance.context.data["project_settings"]["nuke"]
        create_settings = nuke_settings["create"][plugin]
        exposed_knobs = create_settings.get("exposed_knobs", [])
        unexposed_knobs = []
        for knob in exposed_knobs:
            if knob not in group_node.knobs():
                unexposed_knobs.append(knob)

        if unexposed_knobs:
            raise PublishValidationError(
                "Missing exposed knobs: {}".format(unexposed_knobs)
            )
