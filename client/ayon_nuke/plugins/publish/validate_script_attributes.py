from copy import deepcopy
import pyblish.api
from ayon_core.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)
from ayon_core.pipeline.publish import RepairAction
from ayon_nuke.api.lib import (
    WorkfileSettings
)


class ValidateScriptAttributes(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """ Validates file output. """

    order = pyblish.api.ValidatorOrder + 0.1
    families = ["workfile"]
    label = "Validate script attributes"
    hosts = ["nuke"]
    optional = True
    actions = [RepairAction]

    settings_category = "nuke"

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        script_data = deepcopy(instance.context.data["scriptData"])

        # Task may be optional for an instance
        task_entity = instance.data.get("taskEntity")
        if task_entity:
            src_attributes = task_entity["attrib"]
        else:
            src_attributes = instance.data["folderEntity"]["attrib"]

        # These attributes will be checked
        attributes = [
            "fps",
            "frameStart",
            "frameEnd",
            "resolutionWidth",
            "resolutionHeight",
            "handleStart",
            "handleEnd"
        ]

        # get only defined attributes from folder or task data
        check_attributes = {
            attr: src_attributes[attr]
            for attr in attributes
            if attr in src_attributes
        }
        # fix frame values to include handles
        check_attributes["fps"] = float("{0:.4f}".format(
            check_attributes["fps"]))
        script_data["fps"] = float("{0:.4f}".format(
            script_data["fps"]))

        # Compare folder's values Nukescript X Database
        not_matching = []
        for attr in attributes:
            self.log.debug(
                "Task vs Script attribute \"{}\": {}, {}".format(
                    attr,
                    check_attributes[attr],
                    script_data[attr]
                )
            )
            if check_attributes[attr] != script_data[attr]:
                not_matching.append({
                    "name": attr,
                    "expected": check_attributes[attr],
                    "actual": script_data[attr]
                })

        # Raise error if not matching
        if not_matching:
            msg = "Following attributes are not set correctly: \n{}"
            attrs_wrong_str = "\n".join([
                (
                    "`{0}` is set to `{1}`, "
                    "but should be set to `{2}`"
                ).format(at["name"], at["actual"], at["expected"])
                for at in not_matching
            ])
            attrs_wrong_html = "<br/>".join([
                (
                    "-- __{0}__ is set to __{1}__, "
                    "but should be set to __{2}__"
                ).format(at["name"], at["actual"], at["expected"])
                for at in not_matching
            ])
            raise PublishXmlValidationError(
                self, msg.format(attrs_wrong_str),
                formatting_data={
                    "failed_attributes": attrs_wrong_html
                }
            )

    @classmethod
    def repair(cls, instance):
        cls.log.debug("__ repairing instance: {}".format(instance))
        WorkfileSettings().set_context_settings()
