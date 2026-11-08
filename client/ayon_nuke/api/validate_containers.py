"""Nuke specific validation of outdated loaded containers."""

import pyblish.api

from ayon_core.pipeline import PublishXmlValidationError
from ayon_core.pipeline.load import get_outdated_containers
from ayon_core.plugins.publish.validate_containers import (
    ValidateOutdatedContainers as CoreValidateOutdatedContainers,
)

from .lib import get_used_nodes, is_node_used

# Instances can list loaded containers that should not be reported, e.g. a
# studio addon collector can fill this up. Items are container node names.
IGNORE_CONTAINERS_KEY = "validateOutdatedIgnoreContainers"


class ValidateOutdatedContainers(CoreValidateOutdatedContainers):
    """Validate outdated containers that are used by the script.

    Nuke artists often load an older version of a product only for
    comparison. Such containers are not connected to the render graph or
    shown in a Viewer, so they are not reported as outdated.

    Instances can add container node names to
    `instance.data[IGNORE_CONTAINERS_KEY]` to skip specific containers.
    """

    def process(self, context):
        if not self.is_active(context.data):
            return

        outdated_containers = get_outdated_containers()
        if not outdated_containers:
            return

        used_nodes = get_used_nodes()
        ignored_names = _get_ignored_names(context)
        reported = [
            container for container in outdated_containers
            if _is_reported(container, used_nodes, ignored_names)
        ]
        if not reported:
            return

        names = ", ".join(sorted(
            container.get("name", "?") for container in reported
        ))
        msg = "Outdated containers used in the scene: {}".format(names)
        raise PublishXmlValidationError(self, msg)


def _is_reported(container, used_nodes, ignored_names):
    """Return whether an outdated container should be reported.

    Args:
        container (dict): Container data from the scene.
        used_nodes (set[nuke.Node]): Nodes used by the script.
        ignored_names (set[str]): Container node names to ignore.

    Returns:
        bool: True when the container should be reported as outdated.
    """
    node = container.get("node")
    if node is None:
        # Container without a node cannot be inspected, report it.
        return True

    if node.name() in ignored_names:
        return False

    return is_node_used(node, used_nodes)


def _get_ignored_names(context):
    """Get container node names ignored by the published instances."""
    ignored_names = set()
    for instance in context:
        for item in instance.data.get(IGNORE_CONTAINERS_KEY, []):
            name = _get_node_name(item)
            if name:
                ignored_names.add(name)

    return ignored_names


def _get_node_name(item):
    """Get a node name from a string, container dict or node."""
    if isinstance(item, str):
        return item

    if isinstance(item, dict):
        item = item.get("node")
        if item is None:
            return None

    name = getattr(item, "name", None)
    if callable(name):
        return name()

    return None


def _replace_outdated_validator(plugins):
    """Replace the core validator with the Nuke implementation."""
    for index, plugin in enumerate(plugins):
        if plugin is ValidateOutdatedContainers:
            continue
        if getattr(plugin, "__name__", None) != "ValidateOutdatedContainers":
            continue
        plugins[index] = ValidateOutdatedContainers


def install_outdated_containers_override():
    """Make pyblish use the Nuke validation of outdated containers."""
    try:
        registered_filters = pyblish.api.registered_discovery_filters()
        register_filter = pyblish.api.register_discovery_filter
    except AttributeError:
        # Older pyblish does not support discovery filters.
        return

    for filter_ in registered_filters:
        if getattr(filter_, "__name__", None) == (
            "_replace_outdated_validator"
        ):
            return

    register_filter(_replace_outdated_validator)
