from __future__ import annotations

import pyblish.api
from ayon_core.pipeline.publish import (
    OptionalPyblishPluginMixin,
    PublishValidationError,
    RepairAction,
)


class ValidateFrameRange(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validate the Write node renders the frame range of its context.

    Each instance renders the range of its Write node: its own range when
    `use_limit` is on, otherwise the workfile range. The expected range is
    the frame range including handles of the task the instance publishes to,
    or of its folder when it has no task.

    Repair enables the frame range limit on the Write node and sets it to
    the expected range.
    """

    order = pyblish.api.ValidatorOrder
    families = ["render", "prerender"]
    label = "Validate Frame Range"
    hosts = ["nuke"]
    optional = True
    actions = [RepairAction]

    settings_category = "nuke"

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        if "frameStartHandle" not in instance.data:
            self.log.debug(
                "Skipping instance without a collected frame range."
            )
            return

        expected = self.get_expected_frame_range(instance)
        current = (
            int(instance.data["frameStartHandle"]),
            int(instance.data["frameEndHandle"]),
        )
        if current == expected:
            return

        task_entity = instance.data.get("taskEntity")
        folder_path = instance.data["folderPath"]
        if task_entity:
            context_label = (
                f"task '{task_entity['name']}' of folder '{folder_path}'"
            )
        else:
            context_label = f"folder '{folder_path}'"

        raise PublishValidationError(
            f"Write node renders frames {current[0]}-{current[1]} but "
            f"{context_label} expects {expected[0]}-{expected[1]}.",
            title="Frame range incorrect",
            description=(
                "## Frame range does not match the context\n\n"
                f"The Write node renders frames **{current[0]}-{current[1]}**"
                f" but {context_label} has frame range "
                f"**{expected[0]}-{expected[1]}** (including handles).\n\n"
                "### How to repair?\n\n"
                "Use **Repair** to limit the Write node to the expected "
                "frame range, or set the frame range on the Write node "
                "yourself. If the range is intended, disable this "
                "validation for the instance."
            ),
        )

    @staticmethod
    def get_expected_frame_range(instance) -> tuple[int, int]:
        entity = (
            instance.data.get("taskEntity") or instance.data["folderEntity"]
        )
        attrib = entity["attrib"]
        return (
            int(attrib["frameStart"]) - int(attrib["handleStart"]),
            int(attrib["frameEnd"]) + int(attrib["handleEnd"]),
        )

    @classmethod
    def repair(cls, instance):
        first_frame, last_frame = cls.get_expected_frame_range(instance)
        write_node = instance.data["transientData"]["writeNode"]
        write_node["use_limit"].setValue(True)
        write_node["first"].setValue(first_frame)
        write_node["last"].setValue(last_frame)
        cls.log.info(
            f"Limited '{write_node.fullName()}' to frames "
            f"{first_frame}-{last_frame}."
        )
