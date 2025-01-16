from pathlib import Path
import nuke 
import os


PROJECT_NAME = os.environ["AYON_PROJECT_NAME"]
PROJECT_FOLDER = Path(os.environ['AYON_PROJECT_ROOT_WORK'] + "/" + os.environ['AYON_PROJECT_NAME'])

class NodeHolder:
    def __init__(self, path):
        self.path = path

    def paste(self):
        nuke.nodePaste(str(self.path))

    @property
    def name(self):
        return Path(self.path).stem
    
class NodeLoader:

    def __init__(self):
        self.node_dir = PROJECT_FOLDER / "assets/nuke_nodes/groups"
        self.toolset_dir =  PROJECT_FOLDER / "assets/nuke_nodes/toolsets"

        if not self.node_dir.exists():
            self.node_dir.mkdir(parents=True, exist_ok=True)

        if not self.toolset_dir.exists():
            self.toolset_dir.mkdir(parents=True, exist_ok=True)

        self.active_nodes = {}
        self.active_toolsets = {}
        self.project_name = PROJECT_NAME
        self.root_tb = nuke.toolbar("Nodes")
        self.node_menu_name = f"{self.project_name}/nodes"
        self.toolset_menu_name = f"{self.project_name}/toolsets"
        self.node_toolbar = self.root_tb.addMenu(self.node_menu_name)
        self.toolset_toolbar = self.root_tb.addMenu(self.toolset_menu_name)
        self.populate()


    @property 
    def node_location(self):
        return self.node_dir
    @property 
    def toolset_location(self):
        return self.toolset_dir
    
    def add_selected_nodes(self):
        nodes = nuke.selectedNodes()
 
        gizmo_attempted = False

        for node in nodes:
            self._select_only(node)
            if(node.Class() == "Gizmo"):
                gizmo_attempted = True
                continue
            path = self.node_dir / (node.name() + ".nk")
            nuke.nodeCopy(str(path))
        
        if(gizmo_attempted):
            nuke.message("Gizmos not currently supported, use groups or nodes")

        self.populate()

    def add_toolset(self):
        if len(nuke.selectedNodes()) < 1:
            nuke.message("No nodes selected")
            return
        name = nuke.getInput("Toolset Name")
        path = self.toolset_dir / (name + ".nk")
        nuke.nodeCopy(str(path))

        self.populate()
                


    def populate(self):

        
        ### Nodes

        # remove existing menu items
        for node_name in self.active_nodes.keys():
            self._remove_node_from_menu(node_name)

        # collect new nodes
        self.new_node_holders = {
            node_file.stem: NodeHolder(node_file)
            for node_file in sorted(self.node_dir.glob("[!_]*.nk"))
            if(node_file).is_file
        }

        self.active_nodes = self.new_node_holders

        # add new menu items
        for node_name, group_holder in self.active_nodes.items():
            self._add_node_to_menu(name=node_name, command=group_holder.paste)


        ### Toolsets

        for toolset_name in self.active_toolsets.keys():
            self._remove_toolset_from_menu(toolset_name)

        # collect new toolsets
        self.new_toolset_holders = {
            toolset_file.stem: NodeHolder(toolset_file)
            for toolset_file in sorted(self.toolset_dir.glob("[!_]*.nk"))
            if(toolset_file).is_file
        }

        self.active_toolsets = self.new_toolset_holders

        # add new menu items
        for toolset_name, toolset_holder in self.active_toolsets.items():
            self._add_toolset_to_menu(name=toolset_name, command=toolset_holder.paste)
                

    def _remove_node_from_menu(self, name):

        # if we are removing the last entry, remove the whole menu
        # otherwise, nuke will crash
        if(len(self.active_nodes)==1):
            self.root_tb.removeItem(self.node_menu_name)

        # otherwise, remove the item
        else:
            self.node_toolbar.removeItem(name)

    def _add_node_to_menu(self, name, command):

        # if we removed the menu item, recreate it
        if not self.root_tb.findItem(self.node_menu_name):
            self.node_toolbar = self.root_tb.addMenu(self.node_menu_name)

        self.node_toolbar.addCommand(name=name, command=command)
        
    def _remove_toolset_from_menu(self, name):

        # if we are removing the last entry, remove the whole menu
        # otherwise, nuke will crash
        if(len(self.active_toolsets)==1):
            self.root_tb.removeItem(self.toolset_menu_name)

        # otherwise, remove the item
        else:
            self.toolset_toolbar.removeItem(name)

    def _add_toolset_to_menu(self, name, command):

        # if we removed the menu item, recreate it
        if not self.root_tb.findItem(self.toolset_menu_name):
            self.toolset_toolbar = self.root_tb.addMenu(self.toolset_menu_name)

        self.toolset_toolbar.addCommand(name=name, command=command)


    # def _create_node_menu(self):

    def _select_only(self, node):
        nuke.selectAll()
        nuke.invertSelection()
        node['selected'].setValue(True)
