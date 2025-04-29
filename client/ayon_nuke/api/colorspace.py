"""
Nuke Colorspace related methods
"""

import re

from ayon_core.lib import (
    Logger,
    StringTemplate,
)

from .constants import COLOR_VALUE_SEPARATOR

import nuke

log = Logger.get_logger(__name__)


_DISPLAY_AND_VIEW_COLORSPACES_CACHE = {}
_COLORSPACES_CACHE = {}


def get_display_and_view_colorspaces(root_node):
    """Get all possible display and view colorspaces

    This is stored in class variable to avoid multiple calls.

    Args:
        root_node (nuke.Node): root node

    Returns:
        list: all possible display and view colorspaces
    """
    script_name = nuke.root().name()
    if _DISPLAY_AND_VIEW_COLORSPACES_CACHE.get(script_name) is None:
        colorspace_knob = root_node["monitorLut"]
        colorspaces = nuke.getColorspaceList(colorspace_knob)
        _DISPLAY_AND_VIEW_COLORSPACES_CACHE[script_name] = colorspaces

    return _DISPLAY_AND_VIEW_COLORSPACES_CACHE[script_name]


def get_colorspace_list(colorspace_knob, node=None):
    """Get available colorspace profile names

    Args:
        colorspace_knob (nuke.Knob): nuke knob object
        node (Optional[nuke.Node]): nuke node for caching differentiation

    Returns:
        list: list of strings names of profiles
    """
    results = []

    # making sure any node is provided
    node = node or nuke.root()
    # unique script based identifier
    script_name = nuke.root().name()
    node_name = node.fullName()
    identifier_key = f"{script_name}_{node_name}"

    if _COLORSPACES_CACHE.get(identifier_key) is None:
        # This pattern is to match with roles which uses an indentation and
        # parentheses with original colorspace. The value returned from the
        # colorspace is the string before the indentation, so we'll need to
        # convert the values to match with value returned from the knob,
        # ei. knob.value().
        pattern = r".*\t.* \(.*\)"
        for colorspace in nuke.getColorspaceList(colorspace_knob):
            match = re.search(pattern, colorspace)
            if match:
                results.append(colorspace.split("\t", 1)[0])
            else:
                results.append(colorspace)

        _COLORSPACES_CACHE[identifier_key] = results

    return _COLORSPACES_CACHE[identifier_key]


def colorspace_exists_on_node(node, colorspace_name):
    """ Check if colorspace exists on node

    Look through all options in the colorspace knob, and see if we have an
    exact match to one of the items.

    Args:
        node (nuke.Node): nuke node object
        colorspace_name (str): color profile name

    Returns:
        bool: True if exists
    """
    node_knob_keys = node.knobs().keys()

    if "colorspace" in node_knob_keys:
        colorspace_knob = node["colorspace"]
    elif "floatLut" in node_knob_keys:
        colorspace_knob = node["floatLut"]
    else:
        log.warning(f"Node '{node.name()}' does not have colorspace knob")
        return False

    return colorspace_name in get_colorspace_list(colorspace_knob, node)


def create_viewer_profile_string(viewer, display=None, path_like=False):
    """Convert viewer and display to string

    Args:
        viewer (str): viewer name
        display (Optional[str]): display name
        path_like (Optional[bool]): if True, return path like string

    Returns:
        str: viewer config string
    """
    if not display:
        return viewer

    if path_like:
        return "{}/{}".format(display, viewer)
    return "{} ({})".format(viewer, display)


def get_formatted_display_and_view(
        view_profile, formatting_data, root_node=None):
    """Format display and view profile into string.

    This method is formatting a display and view profile. It is iterating
    over all possible combinations of display and view colorspaces. Those
    could be separated by COLOR_VALUE_SEPARATOR defined in constants.

    If Anatomy template tokens are used but formatting data is not provided,
    it will try any other available variants in next position of the separator.

    This method also validate that the formatted display and view profile is
    available in currently run nuke session ocio config.

    Example:
        >>> from ayon_nuke.api.colorspace import get_formatted_display_and_view
        >>> view_profile = {
        ...     "view": "{context};sRGB",
        ...     "display": "{project_code};ACES"
        ... }
        >>> formatting_data = {
        ...    "context": "01sh010",
        ...    "project_code": "proj01"
        ...}
        >>> display_and_view = get_formatted_display_and_view(
        ...    view_profile, formatting_data)
        >>> print(display_and_view)
        "01sh010 (proj01)"


    Args:
        view_profile (dict): view and display profile
        formatting_data (dict): formatting data
        root_node (Optional[nuke.Node]): root node

    Returns:
        str: formatted display and view profile string
            ex: "sRGB (ACES)"
    """
    if not root_node:
        root_node = nuke.root()

    views = view_profile["view"].split(COLOR_VALUE_SEPARATOR)

    # display could be optional in case nuke_default ocio config is used
    displays = []
    if view_profile["display"]:
        displays = view_profile["display"].split(COLOR_VALUE_SEPARATOR)

    # generate all possible combination of display/view
    display_views = []
    for view in views:
        # display could be optional in case nuke_default ocio config is used
        if not displays:
            display_views.append(view.strip())
            continue

        for display in displays:
            display_views.append(
                create_viewer_profile_string(
                    view.strip(), display.strip(), path_like=False
                )
            )

    for dv_item in display_views:
        # format any template tokens used in the string
        dv_item_resolved = StringTemplate(dv_item).format_strict(
            formatting_data)
        log.debug("Resolved display and view: `{}`".format(dv_item_resolved))

        # making sure formatted colorspace exists in running session
        if dv_item_resolved in get_display_and_view_colorspaces(root_node):
            return dv_item_resolved


def get_formatted_display_and_view_as_dict(
        view_profile, formatting_data, root_node=None):
    """Format display and view profile into dict.

    This method is formatting a display and view profile. It is iterating
    over all possible combinations of display and view colorspaces. Those
    could be separated by COLOR_VALUE_SEPARATOR defined in constants.

    If Anatomy template tokens are used but formatting data is not provided,
    it will try any other available variants in next position of the separator.

    This method also validate that the formatted display and view profile is
    available in currently run nuke session ocio config.

    Example:
        >>> from ayon_nuke.api.colorspace import get_formatted_display_and_view_as_dict  # noqa
        >>> view_profile = {
        ...     "view": "{context};sRGB",
        ...     "display": "{project_code};ACES"
        ... }
        >>> formatting_data = {
        ...    "context": "01sh010",
        ...    "project_code": "proj01"
        ...}
        >>> display_and_view = get_formatted_display_and_view_as_dict(
        ...    view_profile, formatting_data)
        >>> print(display_and_view)
        {"view": "01sh010", "display": "proj01"}


    Args:
        view_profile (dict): view and display profile
        formatting_data (dict): formatting data
        root_node (Optional[nuke.Node]): root node

    Returns:
        dict: formatted display and view profile in dict
            ex: {"view": "sRGB", "display": "ACES"}
    """
    if not root_node:
        root_node = nuke.root()

    views = view_profile["view"].split(COLOR_VALUE_SEPARATOR)

    # display could be optional in case nuke_default ocio config is used
    displays = []
    if view_profile["display"]:
        displays = view_profile["display"].split(COLOR_VALUE_SEPARATOR)

    # generate all possible combination of display/view
    display_views = []
    for view in views:
        # display could be optional in case nuke_default ocio config is used
        if not displays:
            display_views.append({"view": view.strip(), "display": None})
            continue

        for display in displays:
            display_views.append(
                {"view": view.strip(), "display": display.strip()})

    root_display_and_view = get_display_and_view_colorspaces(root_node)
    for dv_item in display_views:
        # format any template tokens used in the string
        view = StringTemplate.format_strict_template(
            dv_item["view"], formatting_data
        )
        # for config without displays - nuke_default
        test_string = view
        display = dv_item["display"]
        if display:
            display = StringTemplate.format_strict_template(
                display, formatting_data
            )
            test_string = create_viewer_profile_string(
                view, display, path_like=False
            )

        log.debug(f"Resolved View: '{view}' Display: '{display}'")

        # Make sure formatted colorspace exists in running ocio config session
        if test_string in root_display_and_view:
            return {
                "view": view,
                "display": display,
            }


def get_formatted_colorspace(
        colorspace_name, formatting_data, root_node=None):
    """Format colorspace profile name into string.

    This method is formatting colorspace profile name. It is iterating
    over all possible combinations of input string which could be separated
    by COLOR_VALUE_SEPARATOR defined in constants.

    If Anatomy template tokens are used but formatting data is not provided,
    it will try any other available variants in next position of the separator.

    This method also validate that the formatted colorspace profile name is
    available in currently run nuke session ocio config.

    Example:
        >>> from ayon_nuke.api.colorspace import get_formatted_colorspace
        >>> colorspace_name = "{project_code}_{context};ACES - ACEScg"
        >>> formatting_data = {
        ...    "context": "01sh010",
        ...    "project_code": "proj01"
        ...}
        >>> new_colorspace_name = get_formatted_colorspace(
        ...    colorspace_name, formatting_data)
        >>> print(new_colorspace_name)
        "proj01_01sh010"


    Args:
        colorspace_name (str): colorspace profile name
        formatting_data (dict): formatting data
        root_node (Optional[nuke.Node]): root node

    Returns:
        str: formatted colorspace profile string
            ex: "ACES - ACEScg"
    """
    if not root_node:
        root_node = nuke.root()

    colorspaces = colorspace_name.split(COLOR_VALUE_SEPARATOR)

    # iterate via all found colorspaces
    for citem in colorspaces:
        # format any template tokens used in the string
        citem_resolved = StringTemplate(citem.strip()).format_strict(
            formatting_data)
        log.debug("Resolved colorspace: `{}`".format(citem_resolved))

        # making sure formatted colorspace exists in running session
        if colorspace_exists_on_node(root_node, citem_resolved):
            return citem_resolved
