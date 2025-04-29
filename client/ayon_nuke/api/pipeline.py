import nuke

import os
import importlib
from collections import OrderedDict, defaultdict

import pyblish.api

from ayon_core.host import (
    HostBase,
    IWorkfileHost,
    ILoadHost,
    IPublishHost
)
from ayon_core.settings import get_current_project_settings
from ayon_core.lib import register_event_callback, Logger
from ayon_core.pipeline import (
    register_loader_plugin_path,
    register_creator_plugin_path,
    register_inventory_action_path,
    register_workfile_build_plugin_path,
    AYON_INSTANCE_ID,
    AVALON_INSTANCE_ID,
    AVALON_CONTAINER_ID,
    get_current_folder_path,
    get_current_task_name,
    registered_host,
)
from ayon_core.pipeline.workfile import BuildWorkfile
from ayon_core.tools.utils import host_tools
from ayon_nuke import NUKE_ROOT_DIR
from ayon_core.tools.workfile_template_build import open_template_ui

from .lib import (
    Context,
    ROOT_DATA_KNOB,
    INSTANCE_DATA_KNOB,
    get_main_window,
    WorkfileSettings,
    start_workfile_template_builder,
    launch_workfiles_app,
    check_inventory_versions,
    set_avalon_knob_data,
    read_avalon_data,
    on_script_load,
    dirmap_file_name_filter,
    add_scripts_menu,
    add_scripts_gizmo,
    get_node_data,
    set_node_data,
    MENU_LABEL,
)
from .workfile_template_builder import (
    build_workfile_template,
    create_placeholder,
    update_placeholder,
    NukeTemplateBuilder,
)
from .workio import (
    open_file,
    save_file,
    file_extensions,
    has_unsaved_changes,
    work_root,
    current_file
)
from .constants import ASSIST
from . import push_to_project

log = Logger.get_logger(__name__)

PLUGINS_DIR = os.path.join(NUKE_ROOT_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")
WORKFILE_BUILD_PATH = os.path.join(PLUGINS_DIR, "workfile_build")

# registering pyblish gui regarding settings in presets
if os.getenv("PYBLISH_GUI", None):
    pyblish.api.register_gui(os.getenv("PYBLISH_GUI", None))


class NukeHost(
    HostBase, IWorkfileHost, ILoadHost, IPublishHost
):
    name = "nuke"

    def open_workfile(self, filepath):
        return open_file(filepath)

    def save_workfile(self, filepath=None):
        return save_file(filepath)

    def work_root(self, session):
        return work_root(session)

    def get_current_workfile(self):
        return current_file()

    def workfile_has_unsaved_changes(self):
        return has_unsaved_changes()

    def get_workfile_extensions(self):
        return file_extensions()

    def get_containers(self):
        return ls()

    def install(self):
        """Installing all requirements for Nuke host"""

        pyblish.api.register_host("nuke")

        self.log.info("Registering Nuke plug-ins..")
        pyblish.api.register_plugin_path(PUBLISH_PATH)
        register_loader_plugin_path(LOAD_PATH)
        register_creator_plugin_path(CREATE_PATH)
        register_inventory_action_path(INVENTORY_PATH)
        register_workfile_build_plugin_path(WORKFILE_BUILD_PATH)

        # Register AYON event for workfiles loading.
        register_event_callback("workio.open_file", check_inventory_versions)
        register_event_callback("taskChanged", change_context_label)

        _install_menu()

        # add script menu
        add_scripts_menu()
        add_scripts_gizmo()

        add_nuke_callbacks()

        launch_workfiles_app()

    def get_context_data(self):
        root_node = nuke.root()
        return get_node_data(root_node, ROOT_DATA_KNOB)

    def update_context_data(self, data, changes):
        root_node = nuke.root()
        set_node_data(root_node, ROOT_DATA_KNOB, data)


def add_nuke_callbacks():
    """ Adding all available nuke callbacks
    """
    nuke_settings = get_current_project_settings()["nuke"]
    workfile_settings = WorkfileSettings()

    # Set context settings.
    nuke.addOnCreate(
        workfile_settings.set_context_settings, nodeClass="Root")

    # adding favorites to file browser
    nuke.addOnCreate(workfile_settings.set_favorites, nodeClass="Root")

    # template builder callbacks
    nuke.addOnCreate(start_workfile_template_builder, nodeClass="Root")

    # fix ffmpeg settings on script
    nuke.addOnScriptLoad(on_script_load)

    # set checker for last versions on loaded containers
    nuke.addOnScriptLoad(check_inventory_versions)
    nuke.addOnScriptSave(check_inventory_versions)

    # set apply all workfile settings on script load and save
    #nuke.addOnScriptLoad(WorkfileSettings().set_context_settings)
    nuke.addOnScriptLoad(WorkfileSettings().set_colorspace)

    if nuke_settings["dirmap"]["enabled"]:
        log.info("Added Nuke's dir-mapping callback ...")
        # Add dirmap for file paths.
        nuke.addFilenameFilter(dirmap_file_name_filter)

    log.info("Added Nuke callbacks ...")


def reload_config():
    """Attempt to reload pipeline at run-time.

    CAUTION: This is primarily for development and debugging purposes.

    """

    for module in (
        "ayon_nuke.api.actions",
        "ayon_nuke.api.menu",
        "ayon_nuke.api.plugin",
        "ayon_nuke.api.lib",
    ):
        log.info("Reloading module: {}...".format(module))

        module = importlib.import_module(module)

        try:
            importlib.reload(module)
        except AttributeError as e:
            from importlib import reload
            log.warning("Cannot reload module: {}".format(e))
            reload(module)


def _show_workfiles():
    # Make sure parent is not set
    # - this makes Workfiles tool as separated window which
    #   avoid issues with reopening
    # - it is possible to explicitly change on top flag of the tool
    host_tools.show_workfiles(parent=None, on_top=False)


def get_context_label():
    return "{0}, {1}".format(
        get_current_folder_path(),
        get_current_task_name()
    )


def _install_menu():
    """Install AYON menu into Nuke's main menu bar."""

    # uninstall original AYON menu
    main_window = get_main_window()
    menubar = nuke.menu("Nuke")
    menu = menubar.addMenu(MENU_LABEL)

    if not ASSIST:
        label = get_context_label()
        context_action_item = menu.addCommand("Context")
        context_action_item.setEnabled(False)

        Context.context_action_item = context_action_item

        context_action = context_action_item.action()
        context_action.setText(label)

        # add separator after context label
        menu.addSeparator()

    menu.addCommand(
        "Work Files...",
        _show_workfiles
    )

    menu.addSeparator()
    if not ASSIST:
        # only add parent if nuke version is 14 or higher
        # known issue with no solution yet
        menu.addCommand(
            "Create...",
            lambda: host_tools.show_publisher(
                parent=main_window,
                tab="create"
            )
        )
        # only add parent if nuke version is 14 or higher
        # known issue with no solution yet
        menu.addCommand(
            "Publish...",
            lambda: host_tools.show_publisher(
                parent=main_window,
                tab="publish"
            )
        )

    menu.addCommand(
        "Load...",
        lambda: host_tools.show_loader(
            parent=main_window,
            use_context=True
        )
    )
    menu.addCommand(
        "Manage...",
        lambda: host_tools.show_scene_inventory(parent=main_window)
    )
    menu.addSeparator()
    menu.addCommand(
        "Library...",
        lambda: host_tools.show_library_loader(
            parent=main_window
        )
    )
    menu.addSeparator()
    menu.addCommand(
        "Set Resolution",
        lambda: WorkfileSettings().reset_resolution()
    )
    menu.addCommand(
        "Set Frame Range",
        lambda: WorkfileSettings().reset_frame_range_handles()
    )
    menu.addCommand(
        "Set Colorspace",
        lambda: WorkfileSettings().set_colorspace()
    )
    menu.addCommand(
        "Apply All Settings",
        lambda: WorkfileSettings().set_context_settings()
    )

    menu.addSeparator()
    menu.addCommand(
        "Build Workfile",
        lambda: BuildWorkfile().process()
    )

    menu_template = menu.addMenu("Template Builder")
    menu_template.addCommand(
        "Build Workfile from template",
        lambda: build_workfile_template()
    )

    if not ASSIST:
        menu_template.addSeparator()
        menu_template.addCommand(
            "Open template",
            lambda: open_template_ui(
                NukeTemplateBuilder(registered_host()), get_main_window()
            )
        )
        menu_template.addCommand(
            "Create Place Holder",
            lambda: create_placeholder()
        )
        menu_template.addCommand(
            "Update Place Holder",
            lambda: update_placeholder()
        )

    menu.addCommand(
        "Push to Project",
        lambda: push_to_project.main()
    )

    menu.addSeparator()
    menu.addCommand(
        "Experimental tools...",
        lambda: host_tools.show_experimental_tools_dialog(parent=main_window)
    )
    menu.addSeparator()
    # add reload pipeline only in debug mode
    if bool(os.getenv("NUKE_DEBUG")):
        menu.addSeparator()
        menu.addCommand("Reload Pipeline", reload_config)

    # adding shortcuts
    add_shortcuts_from_presets()


def change_context_label():
    if ASSIST:
        return

    context_action_item = Context.context_action_item
    if context_action_item is None:
        return
    context_action = context_action_item.action()

    old_label = context_action.text()
    new_label = get_context_label()

    context_action.setText(new_label)

    log.info("Task label changed from `{}` to `{}`".format(
        old_label, new_label))


def add_shortcuts_from_presets():
    menubar = nuke.menu("Nuke")
    nuke_presets = get_current_project_settings()["nuke"]["general"]

    if nuke_presets.get("menu"):
        menu_label_mapping = {
            "create": "Create...",
            "manage": "Manage...",
            "load": "Load...",
            "build_workfile": "Build Workfile",
            "publish": "Publish..."
        }

        for command_name, shortcut_str in nuke_presets.get("menu").items():
            log.info("menu_name `{}` | menu_label `{}`".format(
                command_name, MENU_LABEL
            ))
            log.info("Adding Shortcut `{}` to `{}`".format(
                shortcut_str, command_name
            ))
            try:
                menu = menubar.findItem(MENU_LABEL)
                item_label = menu_label_mapping[command_name]
                menuitem = menu.findItem(item_label)
                menuitem.setShortcut(shortcut_str)
            except (AttributeError, KeyError) as e:
                log.error(e)


def containerise(node,
                 name,
                 namespace,
                 context,
                 loader=None,
                 data=None):
    """Bundle `node` into an assembly and imprint it with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        node (nuke.Node): Nuke's node object to imprint as container
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        context (dict): Asset information
        loader (str, optional): Name of node used to produce this container.

    Returns:
        node (nuke.Node): containerised nuke's node object

    """
    data = OrderedDict(
        [
            ("schema", "openpype:container-2.0"),
            ("id", AVALON_CONTAINER_ID),
            ("name", name),
            ("namespace", namespace),
            ("loader", str(loader)),
            ("representation", context["representation"]["id"]),
        ],

        **data or dict()
    )

    set_avalon_knob_data(node, data)

    # set tab to first native
    node.setTab(0)

    return node


def parse_container(node):
    """Returns containerised data of a node

    Reads the imprinted data from `containerise`.

    Arguments:
        node (nuke.Node): Nuke's node object to read imprinted data

    Returns:
        dict: The container schema data for this container node.

    """
    data = read_avalon_data(node)

    # If not all required data return the empty container
    required = ["schema", "id", "name",
                "namespace", "loader", "representation"]
    if not all(key in data for key in required):
        return

    # Store the node's name
    data.update({
        "objectName": node.fullName(),
        "node": node,
    })

    return data


def update_container(node, keys=None):
    """Returns node with updateted containder data

    Arguments:
        node (nuke.Node): The node in Nuke to imprint as container,
        keys (dict, optional): data which should be updated

    Returns:
        node (nuke.Node): nuke node with updated container data

    Raises:
        TypeError on given an invalid container node

    """
    keys = keys or dict()

    container = parse_container(node)
    if not container:
        raise TypeError("Not a valid container node.")

    container.update(keys)
    node = set_avalon_knob_data(node, container)

    return node


def ls():
    """List available containers.

    This function is used by the Container Manager in Nuke. You'll
    need to implement a for-loop that then *yields* one Container at
    a time.
    """
    all_nodes = nuke.allNodes(recurseGroups=False)

    nodes = [n for n in all_nodes]

    for n in nodes:
        container = parse_container(n)
        if container:
            yield container


def list_instances(creator_id=None):
    """List all created instances to publish from current workfile.

    For SubsetManager

    Args:
        creator_id (Optional[str]): creator identifier

    Returns:
        (list) of dictionaries matching instances format
    """
    instances_by_order = defaultdict(list)
    product_instances = []
    instance_ids = set()

    for node in nuke.allNodes(recurseGroups=True):

        if node.Class() in ["Viewer", "Dot"]:
            continue

        try:
            if node["disable"].value():
                continue
        except NameError:
            # pass if disable knob doesn't exist
            pass

        # get data from avalon knob
        instance_data = get_node_data(
            node, INSTANCE_DATA_KNOB)

        if not instance_data:
            continue

        if instance_data["id"] not in {
            AYON_INSTANCE_ID, AVALON_INSTANCE_ID
        }:
            continue

        if creator_id and instance_data["creator_identifier"] != creator_id:
            continue

        instance_id = instance_data.get("instance_id")
        if not instance_id:
            pass
        elif instance_id in instance_ids:
            instance_data.pop("instance_id")
        else:
            instance_ids.add(instance_id)

        # node name could change, so update product name data
        _update_product_name_data(instance_data, node)

        if "render_order" not in node.knobs():
            product_instances.append((node, instance_data))
            continue

        order = int(node["render_order"].value())
        instances_by_order[order].append((node, instance_data))

    # Sort instances based on order attribute or product name.
    # TODO: remove in future Publisher enhanced with sorting
    ordered_instances = []
    for key in sorted(instances_by_order.keys()):
        instances_by_product = defaultdict(list)
        for node, data_ in instances_by_order[key]:
            product_name = data_.get("productName")
            if product_name is None:
                product_name = data_.get("subset")
            instances_by_product[product_name].append((node, data_))
        for subkey in sorted(instances_by_product.keys()):
            ordered_instances.extend(instances_by_product[subkey])

    instances_by_product = defaultdict(list)
    for node, data_ in product_instances:
        product_name = data_.get("productName")
        if product_name is None:
            product_name = data_.get("subset")
        instances_by_product[product_name].append((node, data_))
    for key in sorted(instances_by_product.keys()):
        ordered_instances.extend(instances_by_product[key])

    return ordered_instances


def _update_product_name_data(instance_data, node):
    """Update product name data in instance data.

    Args:
        instance_data (dict): instance creator data
        node (nuke.Node): nuke node
    """
    # make sure node name is product name
    old_product_name = instance_data.get("productName")
    if old_product_name is None:
        old_product_name = instance_data.get("subset")
    old_variant = instance_data["variant"]
    product_name_root = old_product_name.replace(old_variant, "")

    new_product_name = node.name()
    new_variant = new_product_name.replace(product_name_root, "")

    instance_data["productName"] = new_product_name
    instance_data["variant"] = new_variant


def remove_instance(instance):
    """Remove instance from current workfile metadata.

    For SubsetManager

    Args:
        instance (dict): instance representation from subsetmanager model
    """
    instance_node = instance.transient_data["node"]
    instance_knob = instance_node.knobs()[INSTANCE_DATA_KNOB]
    instance_node.removeKnob(instance_knob)
    nuke.delete(instance_node)


def select_instance(instance):
    """
        Select instance in Node View

        Args:
            instance (dict): instance representation from subsetmanager model
    """
    instance_node = instance.transient_data["node"]
    instance_node["selected"].setValue(True)
