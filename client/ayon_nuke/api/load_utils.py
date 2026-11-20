"""Nuke specific helpers shared by loaders of trait representations."""
from __future__ import annotations

from typing import Optional

from ayon_core.lib import Logger
from ayon_core.pipeline.colorspace import (
    get_current_context_imageio_config_preset,
    get_imageio_file_rules_colorspace_from_filepath,
)

from .colorspace import colorspace_exists_on_node
from .lib import get_imageio_input_colorspace

log = Logger.get_logger(__name__)


def get_read_colorspace(
    project_name: str,
    filepath: str,
    representation_colorspace: Optional[str] = None,
    logger=None,
) -> Optional[str]:
    """Colorspace for read node of a file.

    File rules have priority over colorspace of the representation.

    Args:
        project_name (str): Project name.
        filepath (str): File path.
        representation_colorspace (Optional[str]): Colorspace of the
            representation (`ColorManaged` trait).
        logger (Optional[Any]): Structured logger, e.g. `log` of loader.

    Returns:
        Optional[str]: Colorspace name.

    """
    logger = logger or log
    config_data = get_current_context_imageio_config_preset()
    file_rules_colorspace = get_imageio_file_rules_colorspace_from_filepath(
        filepath, "nuke", project_name, config_data=config_data
    )
    # colorspace from `project_settings/nuke/imageio/regexInputs`
    regex_colorspace = get_imageio_input_colorspace(filepath)
    logger.debug(
        "Colorspace candidates - file rules: {file_rules_colorspace},"
        " regex inputs: {regex_colorspace},"
        " representation: {representation_colorspace}",
        file_rules_colorspace=file_rules_colorspace,
        regex_colorspace=regex_colorspace,
        representation_colorspace=representation_colorspace,
        filepath=filepath,
    )

    return (
        file_rules_colorspace
        or regex_colorspace
        or representation_colorspace
    )


def set_read_colorspace(
    read_node,
    project_name: str,
    filepath: str,
    representation_colorspace: Optional[str] = None,
    logger=None,
) -> Optional[str]:
    """Set colorspace to read node if it is available on the node.

    Args:
        read_node (nuke.Node): Read node.
        project_name (str): Project name.
        filepath (str): File path.
        representation_colorspace (Optional[str]): Colorspace of the
            representation (`ColorManaged` trait).
        logger (Optional[Any]): Structured logger, e.g. `log` of loader.

    Returns:
        Optional[str]: Colorspace set to the node.

    """
    logger = logger or log
    colorspace = get_read_colorspace(
        project_name, filepath, representation_colorspace, logger
    )
    node_name = read_node.name()
    if colorspace and colorspace_exists_on_node(read_node, colorspace):
        logger.info(
            "Used colorspace {colorspace} on {node_name}",
            colorspace=colorspace,
            node_name=node_name,
        )
        read_node["colorspace"].setValue(colorspace)
        return colorspace

    if not colorspace:
        template = "Colorspace not set on {node_name}, no colorspace found"
    else:
        template = (
            "Colorspace not set on {node_name},"
            " {colorspace} is not available on the node"
        )
    logger.info(
        template,
        colorspace=colorspace,
        node_name=node_name,
    )
    return None
