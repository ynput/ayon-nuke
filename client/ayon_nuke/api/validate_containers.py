"""Nuke validation of outdated loaded containers."""
from ayon_core.pipeline import PublishXmlValidationError
from ayon_core.pipeline.load import get_outdated_containers
from ayon_core.plugins.publish.validate_containers import (
    ValidateOutdatedContainers as CoreValidateOutdatedContainers,
)

from .lib import get_used_nodes, is_node_used

# Instances can list loaded containers that should not be reported, e.g. a
# studio addon collector can fill this up. Items are container node names.
IGNORE_CONTAINERS_KEY = "validateOutdatedIgnoreContainers"


def _get_ignored_names(context) -> set[str]:
    """Get container node names ignored by the published instances.

    Args:
        context (Optional[pyblish.api.Context]): Publishing context used to
            get containers ignored by the instances.

    Returns:
        set[str]: Set of ignored container node names.
    """
    ignored_names = set()
    if context is None:
        return ignored_names

    for instance in context:
        for item in instance.data.get(IGNORE_CONTAINERS_KEY, []):
            name = _get_node_name(item)
            if name:
                ignored_names.add(name)

    return ignored_names


def _get_node_name(item)-> str | None:
    """Get a node name from a string, container dict or node.

    Args:
        item (str | dict | object): The item to extract the node name from.

    Returns:
        str | None: The node name if found, otherwise None.
    """
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


def any_outdated_containers(context=None):
    """Check if there are outdated containers used in the script.

    Nuke variant of 'ayon_core.pipeline.load.any_outdated_containers'. The
    only difference is that outdated containers which are not used in the
    script, e.g. older versions loaded only for comparison, are ignored.

    Args:
        context (Optional[pyblish.api.Context]): Publishing context used to
            get containers ignored by the instances.

    Returns:
        bool: True when an outdated container is used in the script.
    """
    outdated_containers = get_outdated_containers()
    if not outdated_containers:
        return False

    used_nodes = get_used_nodes()
    ignored_names = _get_ignored_names(context)
    for container in outdated_containers:
        node = container.get("node")
        if node is None:
            # Container without a node cannot be inspected, report it.
            return True

        if node.name() in ignored_names:
            continue

        if is_node_used(node, used_nodes):
            return True

    return False


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

        if any_outdated_containers(context):
            msg = "There are outdated containers in the scene."
            raise PublishXmlValidationError(self, msg)
