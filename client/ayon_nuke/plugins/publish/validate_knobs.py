import json

import nuke
import six
import pyblish.api

from ayon_core.pipeline.publish import (
    RepairContextAction,
    PublishXmlValidationError,
)


class ValidateKnobs(pyblish.api.ContextPlugin):
    """Ensure knobs are consistent.

    Knobs to validate and their values comes from the

    Controlled by plugin settings that require json in following structure:
        "ValidateKnobs": {
            "enabled": true,
            "knobs": {
                "family": {
                    "knob_name": knob_value
                    }
                }
            }
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Knobs"
    hosts = ["nuke"]
    actions = [RepairContextAction]
    optional = True

    settings_category = "nuke"

    knobs = "{}"

    def process(self, context):
        invalid = self.get_invalid(context, compute=True)
        if invalid:
            invalid_items = [
                (
                    "Node __{node_name}__ with knob _{label}_ "
                    "expecting _{expected}_, "
                    "but is set to _{current}_"
                ).format(**i)
                for i in invalid
            ]
            raise PublishXmlValidationError(
                self,
                "Found knobs with invalid values:\n{}".format(invalid),
                formatting_data={
                    "invalid_items": "\n".join(invalid_items)}
            )

    @classmethod
    def get_invalid(cls, context, compute=False):
        invalid = context.data.get("invalid_knobs", [])
        if compute:
            invalid = cls.get_invalid_knobs(context)

        return invalid

    @classmethod
    def get_invalid_knobs(cls, context):
        invalid_knobs = []

        for instance in context:
            # Load fresh knobs data for each instance
            settings_knobs = json.loads(cls.knobs)

            # Filter families.
            families = [instance.data["productType"]]
            families += instance.data.get("families", [])

            # Get all knobs to validate.
            knobs = {}
            for family in families:
                # check if dot in family
                if "." in family:
                    family = family.split(".")[0]

                # avoid families not in settings
                if family not in settings_knobs:
                    continue

                # get presets of knobs
                for preset in settings_knobs[family]:
                    knobs[preset] = settings_knobs[family][preset]

            # Get invalid knobs.
            nodes = []

            for node in nuke.allNodes():
                nodes.append(node)
                if node.Class() == "Group":
                    node.begin()
                    nodes.extend(iter(nuke.allNodes()))
                    node.end()

            for node in nodes:
                for knob in node.knobs():
                    if knob not in knobs.keys():
                        continue

                    expected = knobs[knob]
                    if node[knob].value() != expected:
                        invalid_knobs.append(
                            {
                                "node_name": node.name(),
                                "knob": node[knob],
                                "name": node[knob].name(),
                                "label": node[knob].label(),
                                "expected": expected,
                                "current": node[knob].value()
                            }
                        )

        context.data["invalid_knobs"] = invalid_knobs
        return invalid_knobs

    @classmethod
    def repair(cls, instance):
        invalid = cls.get_invalid(instance)
        for data in invalid:
            # TODO: will need to improve type definitions
            # with the new settings for knob types
            if isinstance(data["expected"], six.text_type):
                data["knob"].setValue(str(data["expected"]))
                continue

            data["knob"].setValue(data["expected"])
