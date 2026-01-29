import nuke
import re
import os
import copy
import pathlib
import random
import string
from collections import defaultdict

import ayon_api
from ayon_core.settings import get_current_project_settings
from ayon_core.lib import (
    BoolDef,
    EnumDef
)
from ayon_core.lib import StringTemplate
from ayon_core.pipeline import (
    LoaderPlugin,
    CreatorError,
    Creator as NewCreator,
    CreatedInstance,
    get_current_task_name,
    AYON_INSTANCE_ID,
    AVALON_INSTANCE_ID,
)
from ayon_core.pipeline.colorspace import (
    get_display_view_colorspace_name,
    get_colorspace_settings_from_publish_context,
    set_colorspace_data_to_representation
)
from ayon_core.lib.transcoding import (
    VIDEO_EXTENSIONS
)
from .lib import (
    INSTANCE_DATA_KNOB,
    Knobby,
    create_backdrop,
    maintained_selection,
    get_avalon_knob_data,
    set_node_knobs_from_settings,
    set_node_data,
    get_node_data,
    get_view_process_node,
    get_filenames_without_hash,
    get_work_default_directory,
    link_knobs,
    get_version_from_path,
)
from .pipeline import (
    list_instances,
    remove_instance,
    containerise,
    update_container,
)
from .command import viewer_update_and_undo_stop
from .colorspace import (
    get_formatted_display_and_view_as_dict,
    get_formatted_colorspace
)


def _collect_and_cache_nodes(creator):
    key = "ayon.nuke.nodes"
    if key not in creator.collection_shared_data:
        instances_by_identifier = defaultdict(list)
        for item in list_instances():
            _, instance_data = item
            identifier = instance_data["creator_identifier"]
            instances_by_identifier[identifier].append(item)
        creator.collection_shared_data[key] = instances_by_identifier
    return creator.collection_shared_data[key]


class NukeCreatorError(CreatorError):
    pass


class NukeCreator(NewCreator):
    node_class_name = None

    def _pass_pre_attributes_to_instance(
        self,
        instance_data,
        pre_create_data,
        keys=None
    ):
        if keys is None:
            keys = pre_create_data.keys()
        creator_attrs = instance_data["creator_attributes"] = {}

        creator_attrs.update({
            key: value
            for key, value in pre_create_data.items()
            if key in keys
        })

    def check_existing_product(self, product_name):
        """Make sure product name is unique.

        It search within all nodes recursively
        and checks if product name is found in
        any node having instance data knob.

        Arguments:
            product_name (str): Product name
        """

        for node in nuke.allNodes(recurseGroups=True):
            # make sure testing node is having instance knob
            if INSTANCE_DATA_KNOB not in node.knobs().keys():
                continue
            node_data = get_node_data(node, INSTANCE_DATA_KNOB)

            if not node_data:
                # a node has no instance data
                continue

            # test if product name is matching
            if node_data.get("productType") == product_name:
                raise NukeCreatorError(
                    (
                        "A publish instance for '{}' already exists "
                        "in nodes! Please change the variant "
                        "name to ensure unique output."
                    ).format(product_name)
                )

    def create_instance_node(
        self,
        node_name,
        knobs=None,
        parent=None,
        node_type=None,
        node_selection=None,
    ):
        """Create node representing instance.

        Arguments:
            node_name (str): Name of the new node.
            knobs (OrderedDict): node knobs name and values
            parent (str): Name of the parent node.
            node_type (str, optional): Nuke node Class.
            node_selection (Optional[list[nuke.Node]]): The node selection.

        Returns:
            nuke.Node: Newly created instance node.

        """
        node_type = node_type or "NoOp"

        node_knobs = knobs or {}

        # set parent node
        parent_node = nuke.root()
        if parent:
            parent_node = nuke.toNode(parent)

        try:
            with parent_node:
                created_node = nuke.createNode(node_type)
                created_node["name"].setValue(node_name)

                for key, values in node_knobs.items():
                    if key in created_node.knobs():
                        created_node["key"].setValue(values)
        except Exception as _err:
            raise NukeCreatorError("Creating have failed: {}".format(_err))

        return created_node

    def _get_current_selected_nodes(
        self,
        pre_create_data,
        class_name: str = None,
    ):
        """ Get current node selection.

        Arguments:
            pre_create_data (dict): The creator initial data.
            class_name (Optional[str]): Filter on a class name.

        Returns:
            list[nuke.Node]: node selection.
        """
        class_name = class_name or self.node_class_name
        use_selection = pre_create_data.get("use_selection")

        if use_selection:
            selected_nodes = nuke.selectedNodes()
        else:
            selected_nodes = nuke.allNodes()

        if class_name:
            # Allow class name implicit last versions of class names like
            # `Camera` to match any of its explicit versions, e.g.
            # `Camera3` or `Camera4`.
            if not class_name[-1].isdigit():
                # Match name with any digit
                pattern = rf"^{class_name}\d*$"
            else:
                pattern = class_name
            regex = re.compile(pattern)
            selected_nodes = [
                node
                for node in selected_nodes
                if regex.match(node.Class())
            ]

        if class_name and use_selection and not selected_nodes:
            raise NukeCreatorError(f"Select a {class_name} node.")

        return selected_nodes

    def create(self, product_name, instance_data, pre_create_data):

        # make sure selected nodes are detected early on.
        # we do not want any further Nuke operation to change the selection.
        node_selection = self._get_current_selected_nodes(pre_create_data)

        # make sure product name is unique
        self.check_existing_product(product_name)

        try:
            instance_node = self.create_instance_node(
                product_name,
                node_type=instance_data.pop("node_type", None),
                node_selection=node_selection,
            )
            instance = CreatedInstance(
                self.product_type,
                product_name,
                instance_data,
                self
            )

            self.apply_staging_dir(instance)
            instance.transient_data["node"] = instance_node

            self._add_instance_to_context(instance)

            set_node_data(
                instance_node, INSTANCE_DATA_KNOB, instance.data_to_store())

            return instance

        except Exception as exc:
            raise NukeCreatorError(f"Creator error: {exc}") from exc

    def collect_instances(self):
        cached_instances = _collect_and_cache_nodes(self)
        attr_def_keys = {
            attr_def.key
            for attr_def in self.get_instance_attr_defs()
        }
        attr_def_keys.discard(None)

        for (node, data) in cached_instances[self.identifier]:
            created_instance = CreatedInstance.from_existing(
                data, self
            )

            self.apply_staging_dir(created_instance)
            created_instance.transient_data["node"] = node
            self._add_instance_to_context(created_instance)

            for key in (
                set(created_instance["creator_attributes"].keys())
                - attr_def_keys
            ):
                created_instance["creator_attributes"].pop(key)

    def update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = created_inst.transient_data["node"]

            # in case node is not existing anymore (user erased it manually)
            try:
                instance_node.fullName()
            except ValueError:
                self._remove_instance_from_context(created_inst)
                continue

            # update instance node name if product name changed
            if "productName" in changes.changed_keys:
                instance_node["name"].setValue(
                    changes["productName"].new_value
                )

            set_node_data(
                instance_node,
                INSTANCE_DATA_KNOB,
                created_inst.data_to_store()
            )

    def remove_instances(self, instances):
        for instance in instances:
            remove_instance(instance)
            self._remove_instance_from_context(instance)

    def get_pre_create_attr_defs(self):
        return [
            BoolDef(
                "use_selection",
                default=not self.create_context.headless,
                label="Use selection"
            )
        ]

    def get_creator_settings(self, project_settings, settings_key=None):
        if not settings_key:
            settings_key = self.__class__.__name__
        return project_settings["nuke"]["create"][settings_key]


class NukeWriteCreator(NukeCreator):
    """Add Publishable Write node"""

    identifier = "create_write"
    label = "Create Write"
    product_type = "write"
    product_base_type = "write"
    icon = "sign-out"

    temp_rendering_path_template = (  # default to be applied if settings is missing
        "{work}/renders/nuke/{product[name]}/{product[name]}.{frame}.{ext}")

    render_target = "local"  # default to be applied if settings is missing

    def get_linked_knobs(self):
        linked_knobs = []
        if "channels" in self.instance_attributes:
            linked_knobs.append("channels")
        if "ordered" in self.instance_attributes:
            linked_knobs.append("render_order")
        if "use_range_limit" in self.instance_attributes:
            linked_knobs.extend(["___", "first", "last", "use_limit"])

        return linked_knobs

    def integrate_links(self, node_selection, node, outputs=True):
        # skip if no selection
        if not node_selection:  # selection should contain either 1 or no node.
            return

        # collect dependencies
        input_nodes = node_selection
        dependent_nodes = node_selection[0].dependent() if outputs else []

        # relinking to collected connections
        for i, input in enumerate(input_nodes):
            node.setInput(i, input)

        # make it nicer in graph
        node.autoplace()

        # relink also dependent nodes
        for dep_nodes in dependent_nodes:
            dep_nodes.setInput(0, node)

    def _get_current_selected_nodes(
        self,
        pre_create_data,
    ):
        """ Get current node selection.

        Arguments:
            pre_create_data (dict): The creator initial data.
            class_name (Optional[str]): Filter on a class name.

        Returns:
            list[nuke.Node]: node selection.

        Raises:
            NukeCreatorError. When the selection contains more than 1 Write node.
        """
        if not pre_create_data.get("use_selection"):
            return []

        selected_nodes = super()._get_current_selected_nodes(
            pre_create_data,
            class_name=None,
        )

        if not selected_nodes:
            raise NukeCreatorError("No active selection")

        elif len(selected_nodes) > 1:
            raise NukeCreatorError("Select only one node")

        return selected_nodes

    def update_instances(self, update_list):
        super().update_instances(update_list)
        for created_inst, changes in update_list:
            # ensure was not deleted by super()
            if self.create_context.get_instance_by_id(created_inst.id):
                self._update_write_node_filepath(created_inst, changes)

    def _update_write_node_filepath(self, created_inst, changes):
        """Update instance node on context changes.

        Whenever any of productName, folderPath, task or productType
        changes then update:
        - output filepath of the write node
        - instance node's name to the product name
        """
        keys = ("productName", "folderPath", "task", "productType")
        if not any(key in changes.changed_keys for key in keys):
            # No relevant changes, no need to update
            return

        data = created_inst.data_to_store()
        # Update values with new formatted path
        instance_node = created_inst.transient_data["node"]
        formatting_data = copy.deepcopy(data)
        write_node = nuke.allNodes(group=instance_node, filter="Write")[0]
        _, ext = os.path.splitext(write_node["file"].value())
        formatting_data.update({"ext": ext[1:]})

        # Retieve render template and staging directory.
        fpath_template = self.temp_rendering_path_template
        formatting_data["work"] = get_work_default_directory(formatting_data)
        fpath = StringTemplate(fpath_template).format_strict(formatting_data)

        staging_dir = self.apply_staging_dir(created_inst)
        if staging_dir:
            basename = os.path.basename(fpath)
            staging_path = pathlib.Path(staging_dir)/ basename
            fpath = staging_path.as_posix()

        write_node["file"].setValue(fpath)

    def get_pre_create_attr_defs(self):
        attrs_defs = super().get_pre_create_attr_defs()
        attrs_defs.append(self._get_render_target_enum())

        return attrs_defs

    def get_instance_attr_defs(self):
        attr_defs = [self._get_render_target_enum()]

        # add reviewable attribute
        if "reviewable" in self.instance_attributes:
            attr_defs.append(
                BoolDef(
                    "review",
                    default=True,
                    label="Review"
                )
            )

        return attr_defs

    def _get_render_target_enum(self):
        rendering_targets = {
            "local": "Local machine rendering",
            "frames": "Use existing frames"
        }

        if "farm_rendering" in self.instance_attributes:
            rendering_targets.update({
                "frames_farm": "Use existing frames - farm",
                "farm": "Farm rendering",
            })

        return EnumDef(
            "render_target",
            items=rendering_targets,
            default=self.render_target,
            label="Render target",
            tooltip="Define the render target."
        )

    def create(self, product_name, instance_data, pre_create_data):
        if not pre_create_data:
            # add no selection for headless
            pre_create_data = {
                "use_selection": False
            }

        # pass values from precreate to instance
        self._pass_pre_attributes_to_instance(
            instance_data,
            pre_create_data,
            [
                "active_frame",
                "render_target"
            ]
        )
        # make sure selected nodes are added
        node_selection = self._get_current_selected_nodes(pre_create_data)

        # make sure the product name is unique
        self.check_existing_product(product_name)

        try:
            instance = CreatedInstance(
                product_type=self.product_type,
                product_name=product_name,
                data=instance_data,
                creator=self,
            )

            staging_dir = self.apply_staging_dir(instance)
            instance_node = self.create_instance_node(
                product_name,
                instance_data,
                staging_dir=staging_dir,
                node_selection=node_selection,
            )

            instance.transient_data["node"] = instance_node

            self._add_instance_to_context(instance)

            set_node_data(
                instance_node,
                INSTANCE_DATA_KNOB,
                instance.data_to_store()
            )

            exposed_write_knobs(
                self.project_settings, self.__class__.__name__, instance_node
            )

            return instance

        except Exception as exc:
            raise NukeCreatorError(f"Creator error: {exc}") from exc

    def apply_settings(self, project_settings):
        """Method called on initialization of plugin to apply settings."""
        # plugin settings for particular creator
        super().apply_settings(project_settings)
        plugin_settings = self.get_creator_settings(project_settings)
        # enabled
        self.enabled: bool = plugin_settings.get("enabled", True)
        # order
        self.order: int = plugin_settings.get("order", 0)
        temp_rendering_path_template = (
            plugin_settings.get("temp_rendering_path_template")
            or self.temp_rendering_path_template
        )
        # TODO remove template key replacements
        temp_rendering_path_template = (
            temp_rendering_path_template
            .replace("{product[name]}", "{subset}")
            .replace("{product[type]}", "{family}")
            .replace("{task[name]}", "{task}")
            .replace("{folder[name]}", "{asset}")
        )
        # individual attributes
        self.instance_attributes = plugin_settings.get(
            "instance_attributes") or self.instance_attributes
        self.prenodes = plugin_settings["prenodes"]
        self.default_variants = plugin_settings.get(
            "default_variants") or self.default_variants
        self.render_target = plugin_settings.get(
            "render_target") or self.render_target
        self.temp_rendering_path_template = temp_rendering_path_template


def get_instance_group_node_childs(instance):
    """Return list of instance group node children

    Args:
        instance (pyblish.Instance): pyblish instance

    Returns:
        list: [nuke.Node]
    """
    node = instance.data["transientData"]["node"]

    if node.Class() != "Group":
        return

    # collect child nodes
    child_nodes = []
    # iterate all nodes
    for node in nuke.allNodes(group=node):
        # add contained nodes to instance's node list
        child_nodes.append(node)

    return child_nodes


def get_colorspace_from_node(node):
    # Add version data to instance
    colorspace = node["colorspace"].value()

    # remove default part of the string
    if "default (" in colorspace:
        colorspace = re.sub(r"default.\(|\)", "", colorspace)

    return colorspace


def get_review_presets_config():
    settings = get_current_project_settings()
    review_profiles = (
        settings["core"]
        ["publish"]
        ["ExtractReview"]
        ["profiles"]
    )

    outputs = {}
    for profile in review_profiles:
        outputs.update(profile.get("outputs", {}))

    return [str(name) for name, _prop in outputs.items()]


def get_publish_config():
    settings = get_current_project_settings()
    return settings["nuke"].get("publish", {})


class NukeLoader(LoaderPlugin):
    container_id_knob = "containerId"
    container_id = None

    def reset_container_id(self):
        self.container_id = "".join(random.choice(
            string.ascii_uppercase + string.digits) for _ in range(10))

    def get_container_id(self, node):
        id_knob = node.knobs().get(self.container_id_knob)
        return id_knob.value() if id_knob else None

    def get_members(self, source):
        """Return nodes that has same "containerId" as `source`"""
        source_id = self.get_container_id(source)
        return [node for node in nuke.allNodes(recurseGroups=True)
                if self.get_container_id(node) == source_id
                and node is not source] if source_id else []

    def set_as_member(self, node):
        source_id = self.get_container_id(node)

        if source_id:
            node[self.container_id_knob].setValue(source_id)
        else:
            HIDEN_FLAG = 0x00040000
            _knob = Knobby(
                "String_Knob",
                self.container_id,
                flags=[
                    nuke.READ_ONLY,
                    HIDEN_FLAG
                ])
            knob = _knob.create(self.container_id_knob)
            node.addKnob(knob)

    def clear_members(self, parent_node):
        parent_class = parent_node.Class()
        members = self.get_members(parent_node)

        dependent_nodes = None
        for node in members:
            _depndc = [n for n in node.dependent() if n not in members]
            if not _depndc:
                continue

            dependent_nodes = _depndc
            break

        for member in members:
            if member.Class() == parent_class:
                continue
            self.log.info("removing node: `{}".format(member.name()))
            nuke.delete(member)

        return dependent_nodes


class NukeGroupLoader(LoaderPlugin):
    """Loader with basic logic of managing load and updates to what should
    be encompassed on a Single Group node inside Nuke.

    Child classes usually override only `on_load` and `on_update` to adjust
    the behavior.

    Exposes 'helper' method `connect_active_viewer` for child classes.
    This is not used by default but can be used by child classes for easy
    access to them.
    """
    settings_category = "nuke"

    ignore_attr = ["useLifetime"]
    node_color = "0x3469ffff"

    def on_load(self, group_node: nuke.Node, namespace: str, context: dict):
        """Logic to be implemented on subclass to describe what to do on load.
        """
        # Override to do anything
        pass

    def on_update(
        self,
        group_node: nuke.Node,
        namespace: str,
        context: dict
    ) -> nuke.Node:
        """Logic to be implemented on subclass to describe what to do on load.

        Returns:
            nuke.Node: The group node. This can be a new group node if it is
                to replace the original group node.

        """
        # Override to do anything
        return group_node

    def _create_group(self, object_name: str, context: dict):
        """Create a group node with a unique name

        Arguments:
            object_name (str): name of the object to create.
            context (dict): context of version

        Returns:
            nuke.Node: created group node
        """
        return nuke.createNode(
            "Group",
            "name {}_1".format(object_name),
            inpanel=False
        )

    def load(self, context, name=None, namespace=None, options=None):
        """
        Loading function to get the soft effects to particular read node

        Arguments:
            context (dict): context of version
            name (str): name of the version
            namespace (str): namespace name
            options (dict): compulsory attribute > not used

        Returns:
            nuke.Node: containerised nuke node object
        """

        namespace = namespace or context["folder"]["name"]
        object_name = "{}_{}".format(name, namespace)

        group_node = self._create_group(object_name, context)
        self.on_load(group_node, namespace, context)
        # On load may have deleted the group node. If it did, then we stop here
        if not group_node:
            return

        self._set_node_color(group_node, context)

        self.log.info(
            "Loaded setup: `{}`".format(group_node["name"].value()))

        data_imprint = self._get_imprint_data(context)
        return containerise(
            node=group_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint)

    def update(self, container, context):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        group_node: nuke.Node = container["node"]  # Group node
        namespace: str = container["namespace"]

        # Trigger load logic on the created group
        group_node = self.on_update(group_node, namespace, context)

        # change color of node
        self._set_node_color(group_node, context)

        # Update the imprinted representation
        data_imprint = self._get_imprint_data(context)
        update_container(
            group_node,
            data_imprint
        )

        self.log.info(
            "updated to version: {}".format(context["version"]["version"])
        )

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = container["node"]
        with viewer_update_and_undo_stop():
            nuke.delete(node)

    def connect_active_viewer(self, group_node):
        """
        Finds Active viewer and
        place the node under it, also adds
        name of group into Input Process of the viewer

        Arguments:
            group_node (nuke node): nuke group node object

        """
        group_node_name = group_node["name"].value()

        viewer = [n for n in nuke.allNodes() if "Viewer1" in n["name"].value()]
        if len(viewer) > 0:
            viewer = viewer[0]
        else:
            msg = "Please create Viewer node before you run this action again"
            self.log.error(msg)
            nuke.message(msg)
            return None

        # get coordinates of Viewer1
        xpos = viewer["xpos"].value()
        ypos = viewer["ypos"].value()

        ypos += 150

        viewer["ypos"].setValue(ypos)

        # set coordinates to group node
        group_node["xpos"].setValue(xpos)
        group_node["ypos"].setValue(ypos + 50)

        # add group node name to Viewer Input Process
        viewer["input_process_node"].setValue(group_node_name)

        # put backdrop under
        create_backdrop(
            label="Input Process",
            layer=2,
            nodes=[viewer, group_node],
            color="0x7c7faaff")

        return True

    def _set_node_color(self, node, context):
        """Set node color based on whether version is latest"""
        is_latest = ayon_api.version_is_latest(
            context["project"]["name"], context["version"]["id"]
        )
        color_value = self.node_color if is_latest else "0xd84f20ff"
        node["tile_color"].setValue(int(color_value, 16))

    def _get_imprint_data(self, context: dict) -> dict:
        """Return data to be imprinted from version."""
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        data = {
            "version": version_entity["version"],
            "colorspaceInput": version_attributes.get("colorSpace"),
            # For updating
            "representation": context["representation"]["id"]
        }
        for k in [
            "frameStart",
            "frameEnd",
            "handleStart",
            "handleEnd",
            "source",
            "fps"
        ]:
            data[k] = version_attributes[k]

        for key, value in dict(**data).items():
            if value is None:
                self.log.warning(
                    f"Skipping imprinting of key with 'None' value` {key}")
                data.pop(key)

        return data


class ExporterReview(object):
    """
    Base class object for generating review data from Nuke

    Args:
        klass (pyblish.plugin): pyblish plugin parent
        instance (pyblish.instance): instance of pyblish context

    """
    data = None
    publish_on_farm = False

    def __init__(self,
                 klass,
                 instance,
                 multiple_presets=True
                 ):

        self.log = klass.log
        self.instance = instance
        self.multiple_presets = multiple_presets
        self.path_in = self.instance.data.get("path", None)
        self.staging_dir = self.instance.data["stagingDir"]
        self.collection = self.instance.data.get("collection", None)
        self.data = {"representations": []}
        if self.instance.data.get("stagingDir_is_custom"):
            self.staging_dir = self._update_staging_dir(
                self.instance.context.data["currentFile"],
                self.staging_dir
            )

    def get_file_info(self):
        if self.collection:
            # get path
            self.fname = os.path.basename(
                self.collection.format("{head}{padding}{tail}")
            )
            self.fhead = self.collection.format("{head}")

            # get first and last frame
            self.first_frame = min(self.collection.indexes)
            self.last_frame = max(self.collection.indexes)

            # make sure slate frame is not included
            frame_start_handle = self.instance.data["frameStartHandle"]
            if frame_start_handle > self.first_frame:
                self.first_frame = frame_start_handle

        else:
            self.fname = os.path.basename(self.path_in)
            self.fhead = os.path.splitext(self.fname)[0] + "."
            self.first_frame = self.instance.data["frameStartHandle"]
            self.last_frame = self.instance.data["frameEndHandle"]

        if "#" in self.fhead:
            self.fhead = self.fhead.replace("#", "")[:-1]

    def get_representation_data(
        self,
        tags=None,
        range=False,
        custom_tags=None,
        colorspace=None,
    ):
        """ Add representation data to self.data

        Args:
            tags (list[str], optional): list of defined tags.
                                        Defaults to None.
            range (bool, optional): flag for adding ranges.
                                    Defaults to False.
            custom_tags (list[str], optional): user inputted custom tags.
                                               Defaults to None.
            colorspace (str, optional): colorspace name.
                                        Defaults to None.
        """
        add_tags = tags or []
        repre = {
            "name": self.name,
            "outputName": self.name,
            "ext": self.ext,
            "files": self.file,
            "stagingDir": self.staging_dir,
            "tags": [self.name.replace("_", "-")] + add_tags,
            "data": {
                # making sure that once intermediate file is published
                # as representation, we will be able to then identify it
                # from representation.data.isIntermediate
                "isIntermediate": True,
                "isMultiIntermediates": self.multiple_presets
            },
        }

        if custom_tags:
            repre["custom_tags"] = custom_tags

        if range:
            repre.update({
                "frameStart": self.first_frame,
                "frameEnd": self.last_frame,
            })
        if ".{}".format(self.ext) not in VIDEO_EXTENSIONS:
            filenames = get_filenames_without_hash(
                self.file, self.first_frame, self.last_frame)
            repre["files"] = filenames

        if self.publish_on_farm:
            repre["tags"].append("publish_on_farm")

        # add colorspace data to representation
        if colorspace:
            set_colorspace_data_to_representation(
                repre,
                self.instance.context.data,
                colorspace=colorspace,
                log=self.log
            )
        self.data["representations"].append(repre)

    def get_imageio_baking_profile(self):
        from . import lib as opnlib
        nuke_imageio = opnlib.get_nuke_imageio_settings()

        if nuke_imageio["baking_target"]["enabled"]:
            return nuke_imageio["baking_target"]
        else:
            # viewer is having display and view keys only and it is
            # display_view type
            return {
                "type": "display_view",
                "display_view": nuke_imageio["viewer"],
            }

    def _update_staging_dir(self, current_file, staging_dir):
        """Update staging dir with current file version.

        Staging dir is used as a place where intermediate review files should
        be stored. If render path contains version portion, which is replaced
        by version from workfile, it must be reflected even for baking scripts.
        """
        try:
            root_version = get_version_from_path(current_file)
            padding = len(root_version)
            root_version = int(root_version)
        except (TypeError, IndexError):
            self.log.warning(
                f"Current file '{current_file}' doesn't contain version number. "
                "No replacement necessary",
                exc_info=True)
            return staging_dir
        try:
            staging_dir_version = "v" + get_version_from_path(staging_dir)
        except (TypeError, IndexError):
            self.log.warning(
                f"Staging directory '{staging_dir}' doesn't contain version number. "
                "No replacement necessary",
                exc_info=True)
            return staging_dir

        new_version = "v" + str("{" + ":0>{}".format(padding) + "}").format(
            root_version
        )
        self.log.debug(
            f"Update version in staging dir from {staging_dir_version} "
            f"to {new_version}"
        )
        return staging_dir.replace(staging_dir_version, new_version)

class ExporterReviewLut(ExporterReview):
    """
    Generator object for review lut from Nuke

    Args:
        klass (pyblish.plugin): pyblish plugin parent
        instance (pyblish.instance): instance of pyblish context


    """
    _temp_nodes = []

    def __init__(self,
                 klass,
                 instance,
                 name=None,
                 ext=None,
                 cube_size=None,
                 lut_size=None,
                 lut_style=None,
                 multiple_presets=True):
        # initialize parent class
        super(ExporterReviewLut, self).__init__(
            klass, instance, multiple_presets)

        # deal with now lut defined in viewer lut
        if hasattr(klass, "viewer_lut_raw"):
            self.viewer_lut_raw = klass.viewer_lut_raw
        else:
            self.viewer_lut_raw = False

        self.name = name or "baked_lut"
        self.ext = ext or "cube"
        self.cube_size = cube_size or 32
        self.lut_size = lut_size or 1024
        self.lut_style = lut_style or "linear"

        # set frame start / end and file name to self
        self.get_file_info()

        self.log.info("File info was set...")

        self.file = self.fhead + self.name + ".{}".format(self.ext)
        self.path = os.path.join(
            self.staging_dir, self.file).replace("\\", "/")

    def clean_nodes(self):
        for node in self._temp_nodes:
            nuke.delete(node)
        self._temp_nodes = []
        self.log.info("Deleted nodes...")

    def generate_lut(self, **kwargs):
        bake_viewer_process = kwargs["bake_viewer_process"]
        bake_viewer_input_process_node = kwargs[
            "bake_viewer_input_process"]

        # ---------- start nodes creation

        # CMSTestPattern
        cms_node = nuke.createNode("CMSTestPattern")
        cms_node["cube_size"].setValue(self.cube_size)
        # connect
        self._temp_nodes.append(cms_node)
        self.previous_node = cms_node

        if bake_viewer_process:
            # Node View Process
            if bake_viewer_input_process_node:
                ipn = get_view_process_node()
                if ipn is not None:
                    # connect
                    ipn.setInput(0, self.previous_node)
                    self._temp_nodes.append(ipn)
                    self.previous_node = ipn
                    self.log.debug(
                        "ViewProcess...   `{}`".format(self._temp_nodes))

            if not self.viewer_lut_raw:
                # OCIODisplay
                dag_node = nuke.createNode("OCIODisplay")
                # connect
                dag_node.setInput(0, self.previous_node)
                self._temp_nodes.append(dag_node)
                self.previous_node = dag_node
                self.log.debug(
                    "OCIODisplay...   `{}`".format(self._temp_nodes))

        # GenerateLUT
        gen_lut_node = nuke.createNode("GenerateLUT")
        gen_lut_node["file"].setValue(self.path)
        gen_lut_node["file_type"].setValue(".{}".format(self.ext))
        gen_lut_node["lut1d"].setValue(self.lut_size)
        gen_lut_node["style1d"].setValue(self.lut_style)
        # connect
        gen_lut_node.setInput(0, self.previous_node)
        self._temp_nodes.append(gen_lut_node)
        # ---------- end nodes creation

        # Export lut file
        nuke.execute(
            gen_lut_node.name(),
            int(self.first_frame),
            int(self.first_frame))

        self.log.info("Exported...")

        # ---------- generate representation data
        self.get_representation_data()

        # ---------- Clean up
        self.clean_nodes()

        return self.data


class ExporterReviewMov(ExporterReview):
    """
    Metaclass for generating review mov files

    Args:
        klass (pyblish.plugin): pyblish plugin parent
        instance (pyblish.instance): instance of pyblish context

    """
    _temp_nodes = {}

    def __init__(self,
                 klass,
                 instance,
                 name=None,
                 ext=None,
                 multiple_presets=True
                 ):
        # initialize parent class
        super(ExporterReviewMov, self).__init__(
            klass, instance, multiple_presets)
        # passing presets for nodes to self
        self.nodes = klass.nodes if hasattr(klass, "nodes") else {}

        # deal with now lut defined in viewer lut
        self.viewer_lut_raw = klass.viewer_lut_raw
        self.write_colorspace = instance.data["colorspace"]
        self.color_channels = instance.data["color_channels"]
        self.formatting_data = instance.data["anatomyData"]

        self.name = name or "baked"
        self.ext = ext or "mov"

        # set frame start / end and file name to self
        self.get_file_info()

        self.log.info("File info was set...")

        if ".{}".format(self.ext) in VIDEO_EXTENSIONS:
            self.file = "{}{}.{}".format(
                self.fhead, self.name, self.ext)
        else:
            # Output is image (or image sequence)
            # When the file is an image it's possible it
            # has extra information after the `fhead` that
            # we want to preserve, e.g. like frame numbers
            # or frames hashes like `####`
            filename_no_ext = os.path.splitext(
                os.path.basename(self.path_in))[0]
            after_head = filename_no_ext[len(self.fhead):]
            self.file = "{}{}.{}.{}".format(
                self.fhead, self.name, after_head, self.ext)
        self.path = os.path.join(
            self.staging_dir, self.file).replace("\\", "/")

    def clean_nodes(self, node_name):
        for node in self._temp_nodes[node_name]:
            nuke.delete(node)
        self._temp_nodes[node_name] = []
        self.log.info("Deleted nodes...")

    def render(self, render_node_name):
        self.log.info("Rendering...  ")
        # Render Write node
        nuke.execute(
            render_node_name,
            int(self.first_frame),
            int(self.last_frame))

        self.log.info("Rendered...")

    def save_file(self):
        import shutil
        with maintained_selection():
            self.log.info("Saving nodes as file...  ")
            # create nk path
            path = f"{os.path.splitext(self.path)[0]}.nk"
            # save file to the path
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            shutil.copyfile(self.instance.context.data["currentFile"], path)

        self.log.info("Nodes exported...")
        return path

    def generate_mov(self, farm=False, delete=True, **kwargs):
        # colorspace data
        colorspace = self.write_colorspace

        # get colorspace settings
        # get colorspace data from context
        config_data, _ = get_colorspace_settings_from_publish_context(
            self.instance.context.data)

        add_tags = []
        self.publish_on_farm = farm
        read_raw = kwargs["read_raw"]
        bake_viewer_process = kwargs["bake_viewer_process"]
        bake_viewer_input_process_node = kwargs[
            "bake_viewer_input_process"]

        baking_colorspace = self.get_imageio_baking_profile()

        colorspace_override = kwargs["colorspace_override"]
        if colorspace_override["enabled"]:
            baking_colorspace = colorspace_override

        fps = self.instance.context.data["fps"]

        self.log.debug(f">> baking_view_profile   `{baking_colorspace}`")

        add_custom_tags = kwargs.get("add_custom_tags", [])

        self.log.info(f"__ add_custom_tags: `{add_custom_tags}`")

        product_name = self.instance.data["productName"]
        self._temp_nodes[product_name] = []

        # Read node
        r_node = nuke.createNode("Read")
        r_node["file"].setValue(self.path_in)
        r_node["first"].setValue(self.first_frame)
        r_node["origfirst"].setValue(self.first_frame)
        r_node["last"].setValue(self.last_frame)
        r_node["origlast"].setValue(self.last_frame)
        r_node["colorspace"].setValue(self.write_colorspace)
        r_node["on_error"].setValue(kwargs.get("fill_missing_frames", "0"))

        # do not rely on defaults, set explicitly
        # to be sure it is set correctly
        r_node["frame_mode"].setValue("expression")
        r_node["frame"].setValue("")

        if read_raw:
            r_node["raw"].setValue(1)

        # connect to Read node
        self._shift_to_previous_node_and_temp(
            product_name, r_node, "Read...   `{}`"
        )

        # only create colorspace baking if toggled on
        if bake_viewer_process:
            if bake_viewer_input_process_node:
                # View Process node
                ipn = get_view_process_node()
                if ipn is not None:
                    # connect to ViewProcess node
                    self._connect_to_above_nodes(
                        ipn, product_name, "ViewProcess...   `{}`"
                    )

            if not self.viewer_lut_raw:
                # OCIODisplay
                if baking_colorspace["type"] == "display_view":
                    display_view = baking_colorspace["display_view"]

                    display_view_f = get_formatted_display_and_view_as_dict(
                        display_view, self.formatting_data
                    )

                    if not display_view_f:
                        raise ValueError(
                            "Invalid display and view profile: "
                            f"'{display_view}'"
                        )

                    # assign display and view
                    display = display_view_f["display"]
                    view = display_view_f["view"]

                    message = "OCIODisplay...   '{}'"
                    node = nuke.createNode("OCIODisplay")

                    # display could not be set in nuke_default config
                    if display:
                        node["display"].setValue(display)

                    node["view"].setValue(view)

                    if config_data:
                        # convert display and view to colorspace
                        colorspace = get_display_view_colorspace_name(
                            config_path=config_data["path"],
                            display=display, view=view
                        )

                # OCIOColorSpace
                elif baking_colorspace["type"] == "colorspace":
                    baking_colorspace = baking_colorspace["colorspace"]
                    # format colorspace string with anatomy data
                    baking_colorspace = get_formatted_colorspace(
                        baking_colorspace, self.formatting_data
                    )
                    if not baking_colorspace:
                        raise ValueError(
                            f"Invalid baking color space: '{baking_colorspace}'"
                        )
                    node = nuke.createNode("OCIOColorSpace")
                    message = "OCIOColorSpace...   '{}'"
                    # no need to set input colorspace since it is driven by
                    # working colorspace
                    node["out_colorspace"].setValue(baking_colorspace)
                    colorspace = baking_colorspace

                else:
                    raise ValueError(
                        "Invalid baking color space type: "
                        f"{baking_colorspace['type']}"
                    )

                self._connect_to_above_nodes(
                    node, product_name, message
                )

        # add reformat node
        reformat_nodes_config = kwargs["reformat_nodes_config"]
        if reformat_nodes_config["enabled"]:
            reposition_nodes = reformat_nodes_config["reposition_nodes"]
            for reposition_node in reposition_nodes:
                node_class = reposition_node["node_class"]
                knobs = reposition_node["knobs"]
                node = nuke.createNode(node_class)
                set_node_knobs_from_settings(node, knobs)

                # connect in order
                self._connect_to_above_nodes(
                    node, product_name, "Reposition node...   `{}`"
                )
            # append reformatted tag
            add_tags.append("reformatted")

        # Write node
        write_node = nuke.createNode("Write")
        self.log.debug(f"Path: {self.path}")

        write_node["file"].setValue(str(self.path))
        write_node["file_type"].setValue(str(self.ext))
        write_node["channels"].setValue(str(self.color_channels))

        # Knobs `meta_codec` and `mov64_codec` are not available on centos.
        # TODO shouldn't this come from settings on outputs?
        try:
            write_node["meta_codec"].setValue("ap4h")
        except Exception:
            self.log.info("`meta_codec` knob was not found")

        try:
            write_node["mov64_codec"].setValue("ap4h")
            write_node["mov64_fps"].setValue(float(fps))
        except Exception:
            self.log.info("`mov64_codec` knob was not found")

        try:
            write_node["mov64_write_timecode"].setValue(1)
        except Exception:
            self.log.info("`mov64_write_timecode` knob was not found")

        write_node["raw"].setValue(1)

        # connect
        write_node.setInput(0, self.previous_node)
        self._temp_nodes[product_name].append(write_node)
        self.log.debug(f"Write...   `{self._temp_nodes[product_name]}`")
        # ---------- end nodes creation

        # ---------- render or save to nk
        if self.publish_on_farm:
            nuke.scriptSave()
            path_nk = self.save_file()
            self.data.update({
                "bakeScriptPath": path_nk,
                "bakeWriteNodeName": write_node.name(),
                "bakeRenderPath": self.path
            })
        else:
            self.render(write_node.name())

        # ---------- generate representation data
        tags = ["review", "need_thumbnail"]

        if delete:
            tags.append("delete")

        self.get_representation_data(
            tags=tags + add_tags,
            custom_tags=add_custom_tags,
            range=True,
            colorspace=colorspace,
        )

        self.log.debug(f"Representation...   `{self.data}`")

        self.clean_nodes(product_name)
        nuke.scriptSave()

        return self.data

    def _shift_to_previous_node_and_temp(self, product_name, node, message):
        self._temp_nodes[product_name].append(node)
        self.previous_node = node
        self.log.debug(message.format(self._temp_nodes[product_name]))

    def _connect_to_above_nodes(self, node, product_name, message):
        node.setInput(0, self.previous_node)
        self._shift_to_previous_node_and_temp(product_name, node, message)


def convert_to_valid_instaces():
    """ Check and convert to latest publisher instances

    Also save as new minor version of workfile.
    """
    def product_type_to_identifier(product_type):
        mapping = {
            "render": "create_write_render",
            "prerender": "create_write_prerender",
            "still": "create_write_image",
            "model": "create_model",
            "camera": "create_camera",
            "nukenodes": "create_backdrop",
            "gizmo": "create_gizmo",
            "source": "create_source"
        }
        return mapping[product_type]

    from ayon_nuke.api import workio

    task_name = get_current_task_name()

    # save into new workfile
    current_file = workio.current_file()

    # add file suffix if not
    if "_publisherConvert" not in current_file:
        new_workfile = (
            current_file[:-3]
            + "_publisherConvert"
            + current_file[-3:]
        )
    else:
        new_workfile = current_file

    path = new_workfile.replace("\\", "/")
    nuke.scriptSaveAs(new_workfile, overwrite=1)
    nuke.Root()["name"].setValue(path)
    nuke.Root()["project_directory"].setValue(os.path.dirname(path))
    nuke.Root().setModified(False)

    _remove_old_knobs(nuke.Root())

    # loop all nodes and convert
    for node in nuke.allNodes(recurseGroups=True):
        transfer_data = {
            "creator_attributes": {}
        }
        creator_attr = transfer_data["creator_attributes"]

        if node.Class() in ["Viewer", "Dot"]:
            continue

        if get_node_data(node, INSTANCE_DATA_KNOB):
            continue

        # get data from avalon knob
        avalon_knob_data = get_avalon_knob_data(
            node, ["avalon:", "ak:"])

        if not avalon_knob_data:
            continue

        if avalon_knob_data["id"] not in {
            AYON_INSTANCE_ID, AVALON_INSTANCE_ID
        }:
            continue

        transfer_data.update({
            k: v for k, v in avalon_knob_data.items()
            if k not in ["families", "creator"]
        })

        transfer_data["task"] = task_name

        product_type = avalon_knob_data.get("productType")
        if product_type is None:
            product_type = avalon_knob_data["family"]

        # establish families
        families_ak = avalon_knob_data.get("families", [])

        if "suspend_publish" in node.knobs():
            creator_attr["suspended_publish"] = (
                node["suspend_publish"].value())

        # get review knob value
        if "review" in node.knobs():
            creator_attr["review"] = (
                node["review"].value())

        if "publish" in node.knobs():
            transfer_data["active"] = (
                node["publish"].value())

        # add identifier
        transfer_data["creator_identifier"] = product_type_to_identifier(
            product_type
        )

        # Add all nodes in group instances.
        if node.Class() == "Group":
            # only alter families for render product type
            if families_ak and "write" in families_ak.lower():
                target = node["render"].value()
                if target == "Use existing frames":
                    creator_attr["render_target"] = "frames"
                elif target == "Local":
                    # Local rendering
                    creator_attr["render_target"] = "local"
                elif target == "On farm":
                    # Farm rendering
                    creator_attr["render_target"] = "farm"

                if "deadlinePriority" in node.knobs():
                    transfer_data["farm_priority"] = (
                        node["deadlinePriority"].value())
                if "deadlineChunkSize" in node.knobs():
                    creator_attr["farm_chunk"] = (
                        node["deadlineChunkSize"].value())
                if "deadlineConcurrentTasks" in node.knobs():
                    creator_attr["farm_concurrency"] = (
                        node["deadlineConcurrentTasks"].value())

        _remove_old_knobs(node)

        # add new instance knob with transfer data
        set_node_data(
            node, INSTANCE_DATA_KNOB, transfer_data)

    nuke.scriptSave()


def _remove_old_knobs(node):
    remove_knobs = [
        "review", "publish", "render", "suspend_publish", "warn", "divd",
        "deadlinePriority", "deadlineChunkSize", "deadlineConcurrentTasks",
        "Deadline"
    ]

    # remove all old knobs
    for knob in node.allKnobs():
        try:
            if knob.name() in remove_knobs:
                node.removeKnob(knob)
            elif "avalon" in knob.name():
                node.removeKnob(knob)
        except ValueError:
            pass


def exposed_write_knobs(settings, plugin_name, instance_node):
    exposed_knobs = settings["nuke"]["create"][plugin_name].get(
        "exposed_knobs", []
    )
    if exposed_knobs:
        instance_node.addKnob(nuke.Text_Knob('', 'Write Knobs'))
    write_node = nuke.allNodes(group=instance_node, filter="Write")[0]
    link_knobs(exposed_knobs, write_node, instance_node)
