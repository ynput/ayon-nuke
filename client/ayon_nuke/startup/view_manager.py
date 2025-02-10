from PySide2 import QtWidgets as qtw
from PySide2 import QtGui as qtg
from PySide2 import QtCore as qtc
import nuke

class View(qtw.QWidget):
    def __init__(self):
        super().__init__()
        self.setup()
        self.create_widgets()
        self.create_layout()
        self.create_connections()  # Add this line
        self._populate_view_table()

    def setup(self):
        self.setWindowTitle('View Manager')
        self.resize(400, 650)

    def create_widgets(self):
        # table of views
        self.view_table = qtw.QTableWidget()
        self.view_table.setColumnCount(1)
        self.view_table.setHorizontalHeaderLabels(['Active'])

        # buttons
        self.refresh_views_button = qtw.QPushButton("Refresh Views")
        self.select_all_button = qtw.QPushButton("Select All")
        self.select_none_button = qtw.QPushButton("Select None")
        self.invert_selection_button = qtw.QPushButton("Invert Selection")

        #set buttons
        self.set_all_nodes_to_render_button = qtw.QPushButton("Set all write nodes to the view 'render'")
        self.set_all_nodes_to_render_button.setToolTip('Sets all write nodes to the view "render", creates it if it does not exist')
        self.set_write_nodes_button = qtw.QPushButton("Set Node Views")
        self.set_write_nodes_button.setToolTip('Apply selection to selected write nodes')


        self.render_row_label = qtw.QLabel("Select a render node:")
        #render buttons
        self.local_render_button = qtw.QPushButton("Local Render")
        self.local_render_button.setToolTip('Render selected write node locally with selected views')
        self.farm_render_button = qtw.QPushButton("Farm Render")
        self.farm_render_button.setToolTip('Render selected write node on farm with selected views')

        #view management buttons
        self.add_views_button = qtw.QPushButton("Add Views")
        self.remove_views_button = qtw.QPushButton("Remove Views")


    def create_layout(self):
        self.layout_main = qtw.QVBoxLayout()
        

        self.layout_selection_buttons = qtw.QHBoxLayout()
        self.layout_selection_buttons.addWidget(self.select_all_button)
        self.layout_selection_buttons.addWidget(self.select_none_button)
        self.layout_selection_buttons.addWidget(self.invert_selection_button)

        self.set_all_buttons = qtw.QHBoxLayout()
        self.set_all_buttons.addWidget(self.set_all_nodes_to_render_button)

        self.layout_render_buttons = qtw.QHBoxLayout()
        self.layout_render_buttons.addWidget(self.set_write_nodes_button)
        self.layout_render_buttons.addWidget(self.local_render_button)
        self.layout_render_buttons.addWidget(self.farm_render_button)

        self.layout_manage_views_buttons = qtw.QHBoxLayout()
        self.layout_manage_views_buttons.addWidget(self.add_views_button)
        self.layout_manage_views_buttons.addWidget(self.remove_views_button)

        self.layout_main.addWidget(self.view_table)
        self.layout_main.addSpacing(10)
        self.layout_main.addLayout(self.layout_selection_buttons)
        self.layout_main.addLayout(self.layout_manage_views_buttons)
        self.layout_main.addSpacing(10)
        self.layout_main.addLayout(self.set_all_buttons)
        self.layout_main.addWidget(self.render_row_label)
        self.layout_main.addLayout(self.layout_render_buttons)

        self.setLayout(self.layout_main)

    def create_connections(self):
        # Connect buttons to their respective functions
        self.select_all_button.clicked.connect(self.select_all_views)
        self.select_none_button.clicked.connect(self.select_no_views)
        self.invert_selection_button.clicked.connect(self.invert_view_selection)
        self.set_write_nodes_button.clicked.connect(self.set_write_nodes_views)
        self.local_render_button.clicked.connect(self.render_write_node_locally)
        self.set_all_nodes_to_render_button.clicked.connect(self.set_all_writes_to_render_view)
        self.add_views_button.clicked.connect(self.get_views_from_user)
        self.remove_views_button.clicked.connect(self.delete_selected_views)

    def _populate_view_table(self):
        print("populate view table")
        view_count = len(nuke.views())
        self.view_table.setRowCount(view_count)
        self.view_table.setVerticalHeaderLabels(nuke.views())

        # Add checkboxes to each cell
        for row in range(view_count):
            checkbox = qtw.QCheckBox()
            checkbox.setChecked(True)

            cell_widget = qtw.QWidget()
            layout = qtw.QHBoxLayout(cell_widget)
            layout.addWidget(checkbox)
            layout.setAlignment(qtc.Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)

            self.view_table.setCellWidget(row, 0, cell_widget)

    def get_checkbox_from_cell(self, row):

        cell_widget = self.view_table.cellWidget(row, 0)
        return cell_widget.layout().itemAt(0).widget()

    def select_all_views(self):

        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_cell(row)
            checkbox.setChecked(True)

    def select_no_views(self):

        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_cell(row)
            checkbox.setChecked(False)

    def invert_view_selection(self):

        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_cell(row)
            checkbox.setChecked(not checkbox.isChecked())

    def set_write_nodes_views(self):

        for node in nuke.selectedNodes():
            # if(node.Class() != 'Write'):
            #     continue
            # if "views" not in [knob.lower for knob in node.knobs().keys()]:
            #     print("no views knob")
            #     return 

            if "views" not in [k.lower() for k in node.knobs().keys()]:
                print("no views knob")
                return 

            node['views'].setValue(self.get_selected_views_string())

    def set_all_writes_to_render_view(self):
        print("set all writes to render view")
        if "render" not in nuke.views():
            nuke.addView("render")
        
        for node in nuke.allNodes():
            if node.Class() not in ['Write', 'Group']:
                continue
            print(node.Class())
            if "views" not in [k.lower() for k in node.knobs().keys()]:
                continue

            node['views'].setValue("render")


    def render_write_node_locally(self):
        node = nuke.selectedNode()
        print(node.name())
        if (node.Class() != 'Write'):
            return
        print("afuhnawseio")
        first = int(node['first'].getValue())
        last = int(node['last'].getValue())
        nuke.render(node, first, last, views = self.get_selected_views_list())

    def get_views_from_user(self):
        view_string = qtw.QInputDialog.getText(self, 'Add Views', 'Enter a comma-separated list of views:')[0]
        self.add_views(view_string)
        self._populate_view_table()

    def add_views(self, view_string):
        views = [v.strip() for v in view_string.split(",")]
        for view in views:
            if view not in nuke.views():
                nuke.addView(view)

    def delete_selected_views(self):
        print("delete selected views")
        for view in self.get_selected_rows():
            print(view)
            nuke.deleteView(view)

        self._populate_view_table()
        
    def get_selected_views_string(self):
        selected_views = " ".join(self.view_table.verticalHeaderItem(row).text() 
                                  for row in range(self.view_table.rowCount())
                                  if self.get_checkbox_from_cell(row).isChecked())

        return selected_views or " "
    
    def get_selected_views_list(self):
        return [self.view_table.verticalHeaderItem(row).text() 
                for row in range(self.view_table.rowCount())
                if self.get_checkbox_from_cell(row).isChecked()]


    # def get_selected_rows(self):
    #     slected_rows = []
    #     print("selected rows", self.view_table.selectedItems())
    #     for item in self.view_table.selectedItems():
    #         print(item)
    #         row = item.row()
    #         label =  self.view_table.verticalHeaderItem(row).text()
    #         slected_rows.append(label)

    #     return slected_rows
    def get_selected_rows(self):
        selected_rows = []
        for selection_range in self.view_table.selectedRanges():
            for row in range(selection_range.topRow(), selection_range.bottomRow() + 1):
                label = self.view_table.verticalHeaderItem(row).text()
                selected_rows.append(label)
        return selected_rows
        


def show():
    global VIEW
    VIEW = View()
    # VIEW.raise_()
    VIEW.setWindowFlags(VIEW.windowFlags() | qtc.Qt.WindowStaysOnTopHint)
    VIEW.show()


