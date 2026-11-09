"""Validate outdated loaded containers used by the publish instances.

The class has the same name as the core `ValidateOutdatedContainers` plugin,
so it replaces it: the Nuke publish plugin path is registered before the core
one and plugin discovery skips plugins with an already discovered name.

The core plugin is imported with a leading underscore, because pyblish
discovers all plugin classes in the module that do not start with one,
including imported ones. It would otherwise be discovered first from this
module, as `dir()` is sorted, and replace the Nuke plugin.
"""
from ayon_core.pipeline import PublishXmlValidationError
from ayon_core.pipeline.load import filter_containers
from ayon_core.plugins.publish.validate_containers import (
    ValidateOutdatedContainers as _CoreValidateOutdatedContainers,
)


class ValidateOutdatedContainers(_CoreValidateOutdatedContainers):
    """Containers used by the publish must be updated to latest version.

    Only the loaded containers that active instances use as input, collected
    by `CollectUpstreamInputs`, are validated. Other containers do not affect
    the published output, e.g. an older version loaded only for comparison.
    """

    def process(self, context):
        if not self.is_active(context.data):
            return

        # Containers used by active instances, by their node name
        containers = {}
        instances_by_container = {}
        for instance in context:
            if not instance.data.get("publish", True):
                continue

            transient_data = instance.data.get("transientData", {})
            for container in transient_data.get("inputContainers", []):
                object_name = container["objectName"]
                containers[object_name] = container
                instances_by_container.setdefault(object_name, []).append(
                    instance.data["name"]
                )

        if not containers:
            return

        outdated_containers = [
            container
            for container in filter_containers(
                containers.values(), context.data["projectName"]
            ).outdated
            # Match core, which ignores outdated containers with a locked
            # version
            if container.get("version_locked") is not True
        ]
        if not outdated_containers:
            return

        lines = []
        for container in outdated_containers:
            object_name = container["objectName"]
            instance_names = ", ".join(instances_by_container[object_name])
            lines.append(f"- **{object_name}** used by: {instance_names}")
        outdated = "\n".join(lines)

        msg = f"There are outdated containers used by the publish:\n{outdated}"
        raise PublishXmlValidationError(
            self, msg, formatting_data={"outdated": outdated}
        )
