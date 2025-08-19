import nuke
import ast


from PySide2 import QtWidgets, QtCore  # type: ignore


COLORSPACE_LIST = ["Output - Rec.709", "Output - sRGB", "scene_linear", "Utility - Raw"]


class Render_submission_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None, saved_data=None, kroger_node=None):
        super().__init__(parent)
        self.saved_data = saved_data or {}
        self.kroger_node = kroger_node
        self.setup_ui()
        self.populate_view_table()
        self.load_saved_data()

    def setup_ui(self):
        self.setWindowTitle("Render Submission")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Global settings section
        global_group = QtWidgets.QGroupBox("Global Settings")
        global_layout = QtWidgets.QFormLayout(global_group)

        # Global frame range - use script globals
        first_frame = int(nuke.root().firstFrame())
        last_frame = int(nuke.root().lastFrame())
        default_range = f"{first_frame}-{last_frame}"

        self.global_range_edit = QtWidgets.QLineEdit(default_range)
        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(self.global_range_edit)

        self.apply_global_btn = QtWidgets.QPushButton("Apply to All")
        self.apply_global_btn.clicked.connect(self.apply_global_range)
        range_layout.addWidget(self.apply_global_btn)

        global_layout.addRow("Global Range:", range_layout)

        # Global Priority with Apply button
        self.global_priority_spin = QtWidgets.QSpinBox()
        self.global_priority_spin.setRange(1, 100)
        self.global_priority_spin.setValue(95)
        priority_layout = QtWidgets.QHBoxLayout()
        priority_layout.addWidget(self.global_priority_spin)

        self.apply_priority_btn = QtWidgets.QPushButton("Apply to All")
        self.apply_priority_btn.clicked.connect(self.apply_global_priority)
        priority_layout.addWidget(self.apply_priority_btn)

        global_layout.addRow("Global Priority:", priority_layout)

        # Chunk Size
        self.chunk_size_spin = QtWidgets.QSpinBox()
        self.chunk_size_spin.setRange(1, 1000)
        self.chunk_size_spin.setValue(1)
        global_layout.addRow("Chunk Size:", self.chunk_size_spin)

        # Concurrent Tasks
        self.concurrent_tasks_spin = QtWidgets.QSpinBox()
        self.concurrent_tasks_spin.setRange(1, 100)
        self.concurrent_tasks_spin.setValue(2)
        global_layout.addRow("Concurrent Tasks:", self.concurrent_tasks_spin)

        # Pool
        self.pool_edit = QtWidgets.QLineEdit("local")
        global_layout.addRow("Pool:", self.pool_edit)

        # Group
        self.group_edit = QtWidgets.QLineEdit("nuke")
        global_layout.addRow("Group:", self.group_edit)

        # File Format
        self.file_format_combo = QtWidgets.QComboBox()
        self.file_format_combo.addItems(["dpx", "exr"])
        self.file_format_combo.setCurrentText("dpx")
        global_layout.addRow("File Format:", self.file_format_combo)

        # Colorspace
        self.colorspace_combo = QtWidgets.QComboBox()
        self.colorspace_combo.addItems(COLORSPACE_LIST)
        self.colorspace_combo.setCurrentText("rec709")
        global_layout.addRow("Colorspace:", self.colorspace_combo)

        layout.addWidget(global_group)

        # Views table section
        table_group = QtWidgets.QGroupBox("View Selection")
        table_layout = QtWidgets.QVBoxLayout(table_group)

        # Selection buttons
        selection_buttons = QtWidgets.QHBoxLayout()

        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_views)
        selection_buttons.addWidget(self.select_all_btn)

        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_none_views)
        selection_buttons.addWidget(self.select_none_btn)

        selection_buttons.addStretch()
        table_layout.addLayout(selection_buttons)

        # Create the table
        self.view_table = QtWidgets.QTableWidget()
        self.view_table.setColumnCount(4)
        self.view_table.setHorizontalHeaderLabels(
            ["View Name", "Frame Range", "Priority", "Render"]
        )

        # Table settings
        self.view_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view_table.setAlternatingRowColors(True)
        self.view_table.verticalHeader().setVisible(False)

        # Resize columns
        header = self.view_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.Fixed
        )  # View Name - fixed width
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)  # Frame Range
        header.setSectionResizeMode(
            2, QtWidgets.QHeaderView.Fixed
        )  # Priority - fixed width
        header.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeToContents
        )  # Render checkbox

        # Set specific column widths
        self.view_table.setColumnWidth(0, 120)  # View Name - wider
        self.view_table.setColumnWidth(2, 70)  # Priority - narrower

        table_layout.addWidget(self.view_table)

        layout.addWidget(table_group)

        # Test button for applying settings
        test_layout = QtWidgets.QHBoxLayout()
        self.apply_settings_btn = QtWidgets.QPushButton("Apply Settings to nodes")
        self.apply_settings_btn.clicked.connect(lambda: self.apply_settings(debug=True))
        test_layout.addWidget(self.apply_settings_btn)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Dialog buttons - Submit and Cancel side by side
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        # Change the OK button text to Submit
        submit_button = button_box.button(QtWidgets.QDialogButtonBox.Ok)
        submit_button.setText("Submit")

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_view_table(self):
        """Populate the table with current script views"""

        views = nuke.views()
        self.view_table.setRowCount(len(views))

        # Get default frame range
        first_frame = int(nuke.root().firstFrame())
        last_frame = int(nuke.root().lastFrame())
        default_range = f"{first_frame}-{last_frame}"

        for row, view_name in enumerate(views):
            # Column 0: View Name (read-only)
            name_item = QtWidgets.QTableWidgetItem(view_name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            # Remove the gray background - keep default
            self.view_table.setItem(row, 0, name_item)

            # Column 1: Frame Range (editable)
            range_item = QtWidgets.QTableWidgetItem(default_range)
            self.view_table.setItem(row, 1, range_item)

            # Column 2: Priority (spin box)
            priority_spin = QtWidgets.QSpinBox()
            priority_spin.setRange(1, 100)
            priority_spin.setValue(95)
            priority_spin.setAlignment(QtCore.Qt.AlignCenter)
            self.view_table.setCellWidget(row, 2, priority_spin)

            # Column 3: Render checkbox
            checkbox = QtWidgets.QCheckBox()
            # Default "main" views to unchecked, others to checked
            default_checked = view_name.lower() != "main"
            checkbox.setChecked(default_checked)

            # Center the checkbox in the cell
            checkbox_widget = QtWidgets.QWidget()
            checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(QtCore.Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)

            self.view_table.setCellWidget(row, 3, checkbox_widget)

        # Auto-resize rows to content
        self.view_table.resizeRowsToContents()

    def load_saved_data(self):
        """Load previously saved data into the dialog"""
        if not self.saved_data:
            return

        # Load global frame range
        if "global_frame_range" in self.saved_data:
            self.global_range_edit.setText(self.saved_data["global_frame_range"])

        # Load global render settings
        if "global_priority" in self.saved_data:
            self.global_priority_spin.setValue(self.saved_data["global_priority"])

        if "chunk_size" in self.saved_data:
            self.chunk_size_spin.setValue(self.saved_data["chunk_size"])

        if "concurrent_tasks" in self.saved_data:
            self.concurrent_tasks_spin.setValue(self.saved_data["concurrent_tasks"])

        if "pool" in self.saved_data:
            self.pool_edit.setText(self.saved_data["pool"])

        if "group" in self.saved_data:
            self.group_edit.setText(self.saved_data["group"])

        if "file_format" in self.saved_data:
            self.file_format_combo.setCurrentText(self.saved_data["file_format"])

        if "colorspace" in self.saved_data:
            self.colorspace_combo.setCurrentText(self.saved_data["colorspace"])

        # Load view-specific data
        if "view_data" in self.saved_data:
            view_data = self.saved_data["view_data"]
            selected_views = self.saved_data.get("selected_views", [])

            for row in range(self.view_table.rowCount()):
                view_name = self.view_table.item(row, 0).text()

                if view_name in view_data:
                    # Set frame range
                    frame_range = view_data[view_name].get("frame_range", "")
                    if frame_range:
                        range_item = self.view_table.item(row, 1)
                        if range_item:
                            range_item.setText(frame_range)

                    # Set priority
                    priority = view_data[view_name].get("priority", 95)
                    priority_widget = self.view_table.cellWidget(row, 2)
                    if priority_widget:
                        priority_widget.setValue(priority)

                # Set checkbox state
                checkbox = self.get_checkbox_from_row(row)
                if checkbox:
                    checkbox.setChecked(view_name in selected_views)

    def get_checkbox_from_row(self, row):
        """Get the checkbox widget from a specific row"""
        checkbox_widget = self.view_table.cellWidget(row, 3)
        if checkbox_widget:
            return checkbox_widget.layout().itemAt(0).widget()
        return None

    def get_priority_from_row(self, row):
        """Get the priority spinbox value from a specific row"""
        priority_widget = self.view_table.cellWidget(row, 2)
        if priority_widget:
            return priority_widget.value()
        return 95

    def select_all_views(self):
        """Check all render checkboxes"""
        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_row(row)
            if checkbox:
                checkbox.setChecked(True)

    def select_none_views(self):
        """Uncheck all render checkboxes"""
        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_row(row)
            if checkbox:
                checkbox.setChecked(False)

    def apply_global_range(self):
        """Apply global frame range to all view rows"""
        global_range = self.global_range_edit.text().strip()

        for row in range(self.view_table.rowCount()):
            range_item = self.view_table.item(row, 1)
            if range_item:
                range_item.setText(global_range)

    def apply_global_priority(self):
        """Apply global priority to all view rows"""
        global_priority = self.global_priority_spin.value()

        for row in range(self.view_table.rowCount()):
            priority_widget = self.view_table.cellWidget(row, 2)
            if priority_widget:
                priority_widget.setValue(global_priority)

    def get_selected_data(self):
        """Extract user selections from the dialog"""

        # Get job name from script
        script_name = (
            nuke.root().name().split("/")[-1].replace(".nk", "") or "UntitledScript"
        )
        global_range = self.global_range_edit.text().strip()

        # Get global render settings
        global_priority = self.global_priority_spin.value()
        chunk_size = self.chunk_size_spin.value()
        concurrent_tasks = self.concurrent_tasks_spin.value()
        pool = self.pool_edit.text().strip()
        group = self.group_edit.text().strip()
        file_format = self.file_format_combo.currentText()
        colorspace = self.colorspace_combo.currentText()

        selected_views = []
        view_data = {}

        for row in range(self.view_table.rowCount()):
            view_name = self.view_table.item(row, 0).text()
            frame_range = self.view_table.item(row, 1).text().strip()
            priority = self.get_priority_from_row(row)

            # Get checkbox state
            checkbox = self.get_checkbox_from_row(row)
            is_checked = checkbox.isChecked() if checkbox else False

            if is_checked:
                selected_views.append(view_name)

            # Store all view data regardless of checkbox state
            view_data[view_name] = {"frame_range": frame_range, "priority": priority}

        return {
            "job_name": script_name,
            "global_frame_range": global_range,
            "global_priority": global_priority,
            "chunk_size": chunk_size,
            "concurrent_tasks": concurrent_tasks,
            "pool": pool,
            "group": group,
            "file_format": file_format,
            "colorspace": colorspace,
            "selected_views": selected_views,
            "view_data": view_data,
        }

    def validate_data(self):
        """Validate user input"""

        data = self.get_selected_data()

        # Job name is automatically determined from script, so no need to check

        # Check at least one view selected
        if not data["selected_views"]:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please select at least one view to render."
            )
            return False

        # Validate frame ranges for selected views only
        for view_name in data["selected_views"]:
            view_info = data["view_data"][view_name]
            frame_range = view_info["frame_range"]

            if not frame_range:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Please enter a frame range for view '{view_name}'.",
                )
                return False

            # Basic frame range validation
            if "-" not in frame_range and not frame_range.isdigit():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Invalid frame range for '{view_name}': {frame_range}\n"
                    "Use format: 1001-1100 or single frame: 1001",
                )
                return False

        return True

    def apply_settings(self, debug=False):
        """Test applying settings to nodes without submitting"""
        if not self.validate_data():
            return

        data = self.get_selected_data()
        selected_views = data["selected_views"]
        view_data = data["view_data"]

        if debug:
            if not selected_views:
                QtWidgets.QMessageBox.warning(self, "Test Apply", "No views selected!")
                return

            if not self.kroger_node:
                QtWidgets.QMessageBox.warning(
                    self, "Test Apply", "No kroger write node reference!"
                )
                return

        try:
            # Find the generated nodes inside the kroger write group
            with self.kroger_node:
                all_nodes = nuke.allNodes()
                generated_nodes = [
                    node for node in all_nodes if node.Class() != "Input"
                ]
                print(f"found {len(generated_nodes)} generated nodes")

                # Create a mapping of view names to nodes
                view_to_node = {}
                for node in generated_nodes:
                    view_name_knob = node.knob("view_name_knob")
                    if view_name_knob:
                        view_name = view_name_knob.getValue()
                        view_to_node[view_name] = node
                        print(f"  mapped view '{view_name}' to node {node.name()}")
                    else:
                        print(f"  node {node.name()} has no view_name_knob")

                print(f"final view_to_node mapping: {list(view_to_node.keys())}")

            results = []
            print(f"applying settings to {len(selected_views)} selected views...")

            # Apply settings to each selected view
            for view_name in selected_views:
                if view_name not in view_to_node:
                    results.append(f"❌ {view_name}: Node not found")
                    continue

                node = view_to_node[view_name]
                node_results = []

                try:
                    # Get frame range for this specific view
                    frame_range = view_data[view_name]["frame_range"]
                    view_priority = view_data[view_name]["priority"]

                    # Parse frame range
                    if "-" in frame_range:
                        start_frame, end_frame = frame_range.split("-", 1)
                        start_frame = start_frame.strip()
                        end_frame = end_frame.strip()
                    else:
                        # Single frame
                        start_frame = end_frame = frame_range.strip()

                    # Check if view_name_knob still exists before setting values
                    print(
                        f"before setting values: view_name_knob exists = {node.knob('view_name_knob') is not None}"
                    )

                    # Test applying each setting and report results
                    knob_tests = [
                        ("file_type", data["file_format"]),
                        ("Render Start", int(start_frame)),
                        ("Render End", int(end_frame)),
                        ("deadlinePriority", view_priority),
                        ("concurrentTasks", data["concurrent_tasks"]),  # Fixed spelling
                        ("deadlineChunkSize", data["chunk_size"]),
                        ("deadlinePool", data["pool"]),
                        ("deadlineGroup", data["group"]),
                        ("colorspace", data["colorspace"]),
                    ]

                    for knob_name, value in knob_tests:
                        if node.knob(knob_name):
                            try:
                                node[knob_name].setValue(value)
                                node_results.append(f"✅ {knob_name}: {value}")
                                print(f"  ✅ {view_name}.{knob_name}: {value}")
                            except Exception as e:
                                node_results.append(
                                    f"❌ {knob_name}: Failed to set ({e})"
                                )
                                print(
                                    f"  ❌ {view_name}.{knob_name}: Failed to set ({e})"
                                )
                        else:
                            node_results.append(f"⚠️ {knob_name}: Knob not found")
                            print(f"  ⚠️ {view_name}.{knob_name}: Knob not found")

                    # Check if view_name_knob still exists after setting values
                    knob_exists_after = node.knob("view_name_knob") is not None
                    print(
                        f"after setting values: view_name_knob exists = {knob_exists_after}"
                    )

                    # Re-add the view_name_knob if it was removed
                    if not knob_exists_after:
                        print(f"re-adding view_name_knob for {view_name}")
                        view_name_knob = nuke.String_Knob(
                            "view_name_knob", "Render View"
                        )
                        view_name_knob.setValue(view_name)
                        node.addKnob(view_name_knob)
                        print(
                            f"re-added view_name_knob: {node.knob('view_name_knob') is not None}"
                        )

                    results.append(f"📁 {view_name}:")
                    results.extend([f"   {result}" for result in node_results])

                except Exception as e:
                    results.append(f"❌ {view_name}: Error - {str(e)}")

            # Print results to console
            if debug and results:
                print("\n=== Apply Settings Test Results ===")
                for result_line in results:
                    print(result_line)
                print("=== Test Complete ===\n")

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Test Apply Error", f"An error occurred:\n{str(e)}"
            )

    def accept(self):
        """Override accept to validate and confirm before closing"""
        if self.validate_data():
            # Get the data to check how many renders will be submitted
            data = self.get_selected_data()
            num_renders = len(data["selected_views"])

            # Show confirmation dialog
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Submission",
                f"About to submit {num_renders} render{'s' if num_renders != 1 else ''}, continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,  # Default to No for safety
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self.apply_settings()
                super().accept()

            # If No, do nothing and keep dialog open


class Batch_publish_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None, kroger_node=None):
        super().__init__(parent)
        self.kroger_node = kroger_node
        self.setup_ui()
        self.populate_view_table()

    def setup_ui(self):
        self.setWindowTitle("Batch Publish")
        self.setMinimumSize(400, 300)
        self.resize(500, 400)

        
        layout = QtWidgets.QVBoxLayout(self)

        
        table_group = QtWidgets.QGroupBox("Select Views to Publish")
        table_layout = QtWidgets.QVBoxLayout(table_group)

   
        selection_buttons = QtWidgets.QHBoxLayout()

        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_views)
        selection_buttons.addWidget(self.select_all_btn)

        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_none_views)
        selection_buttons.addWidget(self.select_none_btn)

        selection_buttons.addStretch()
        table_layout.addLayout(selection_buttons)


        self.view_table = QtWidgets.QTableWidget()
        self.view_table.setColumnCount(2)
        self.view_table.setHorizontalHeaderLabels(["View Name", "Publish"])


        self.view_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view_table.setAlternatingRowColors(True)
        self.view_table.verticalHeader().setVisible(False)


        header = self.view_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)  # View Name
        header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents
        )  # Publish checkbox

        table_layout.addWidget(self.view_table)
        layout.addWidget(table_group)


        warning_label = QtWidgets.QLabel(
            "Warning: Submitting a large number of publishes can take several minutes"
        )
        warning_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(warning_label)

        warning_label2 = QtWidgets.QLabel("If you get failures check the external nuke shell window for errors.\nIf you try to publish a version that already exists, it will fail.")
        warning_label2.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(warning_label2)


        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )

        publish_button = button_box.button(QtWidgets.QDialogButtonBox.Ok)
        publish_button.setText("Publish")

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def populate_view_table(self):
        """Populate the table with available views from kroger write nodes"""
        if not self.kroger_node:
            return

        views = []
        try:
            # Get views from the generated nodes inside the kroger write group
            with self.kroger_node:
                all_nodes = nuke.allNodes()
                generated_nodes = [
                    node
                    for node in all_nodes
                    if node.Class() != "Input" and node.knob("view_name_knob")
                ]

                for node in generated_nodes:
                    view_name_knob = node.knob("view_name_knob")
                    if view_name_knob:
                        view_name = view_name_knob.getValue()
                        if view_name not in views:
                            views.append(view_name)
        except Exception as e:
            print(f"Error getting views: {e}")
            return

        self.view_table.setRowCount(len(views))

        for row, view_name in enumerate(views):
            # Column 0: View Name (read-only)
            name_item = QtWidgets.QTableWidgetItem(view_name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.view_table.setItem(row, 0, name_item)

            # Column 1: Publish checkbox
            checkbox = QtWidgets.QCheckBox()
            # Default all views to checked
            checkbox.setChecked(True)

            # Center the checkbox in the cell
            checkbox_widget = QtWidgets.QWidget()
            checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(QtCore.Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)

            self.view_table.setCellWidget(row, 1, checkbox_widget)


        self.view_table.resizeRowsToContents()

    def get_checkbox_from_row(self, row):
        """Get the checkbox widget from a specific row"""
        checkbox_widget = self.view_table.cellWidget(row, 1)
        if checkbox_widget:
            return checkbox_widget.layout().itemAt(0).widget()
        return None

    def select_all_views(self):
        """Check all publish checkboxes"""
        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_row(row)
            if checkbox:
                checkbox.setChecked(True)

    def select_none_views(self):
        """Uncheck all publish checkboxes"""
        for row in range(self.view_table.rowCount()):
            checkbox = self.get_checkbox_from_row(row)
            if checkbox:
                checkbox.setChecked(False)

    def get_selected_views(self):
        """Get list of selected view names"""
        selected_views = []
        for row in range(self.view_table.rowCount()):
            view_name = self.view_table.item(row, 0).text()
            checkbox = self.get_checkbox_from_row(row)
            if checkbox and checkbox.isChecked():
                selected_views.append(view_name)
        return selected_views

    def validate_data(self):
        """Validate that at least one view is selected"""
        selected_views = self.get_selected_views()
        if not selected_views:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Please select at least one view to publish."
            )
            return False
        return True

    def accept(self):
        """Override accept to validate and confirm before closing"""
        if self.validate_data():
            selected_views = self.get_selected_views()
            num_views = len(selected_views)

            # Show confirmation dialog
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Batch Publish",
                f"About to batch publish {num_views} view{'s' if num_views != 1 else ''}, continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,  # Default to No for safety
            )

            if reply == QtWidgets.QMessageBox.Yes:
                super().accept()


def load_saved_data_from_node(kroger_node=None):
    """Load saved data from the node's hidden knob"""
    try:
        krogerWrite = kroger_node if kroger_node else nuke.thisNode()
        if krogerWrite.knob("dialog_data"):
            data_str = krogerWrite["dialog_data"].getValue()
            if data_str:
                # Safely evaluate the string as a Python dictionary
                return ast.literal_eval(data_str)
    except (ValueError, SyntaxError) as e:
        print(f"Error loading saved data: {e}")
    return {}


def save_data_to_node(data, kroger_node=None):
    """Save data to the node's hidden knob"""
    try:
        krogerWrite = kroger_node if kroger_node else nuke.thisNode()
        if krogerWrite.knob("dialog_data"):
            krogerWrite["dialog_data"].setValue(str(data))
    except Exception as e:
        print(f"Error saving data: {e}")


def submit_button_callback():
    """Callback function for the button"""
    
    kroger_node = nuke.thisNode()

    
    saved_data = load_saved_data_from_node(kroger_node)

    dialog = Render_submission_dialog(saved_data=saved_data, kroger_node=kroger_node)

    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        data = dialog.get_selected_data()
        print("Dialog accepted with data:")
        print(data)

    
        save_data_to_node(data, kroger_node)

    
        submit_renders(data, kroger_node)

    else:
        print("Dialog cancelled")
        
        data = dialog.get_selected_data()
        save_data_to_node(data, kroger_node)


def batch_publish_button_callback():
    """Callback function for the batch publish button"""
    
    kroger_node = nuke.thisNode()
    # print(kroger_node.name())

    dialog = Batch_publish_dialog(kroger_node=kroger_node)

    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        selected_views = dialog.get_selected_views()
        print(f"Batch publishing selected views: {selected_views}")
        print(kroger_node.name())

        
        batch_publish(selected_views=selected_views, kroger_node=kroger_node)
    else:
        print("Batch publish dialog cancelled")


def submit_renders(data, krogerWrite):
    print("submitting renders with data:")
    """Submit the selected renders to the farm"""
    import os
    from datetime import datetime

    try:
        import hornet_deadline_utils
    except ImportError:
        nuke.message("Error: hornet_deadline_utils module not found!")
        return

    print("krogerWrite node found:", krogerWrite.name())
    selected_views = data["selected_views"]
    view_data = data["view_data"]

    if not selected_views:
        nuke.message("No views selected for rendering!")
        return

    succeeded = 0
    failed = 0
    script = os.path.basename(nuke.toNode("root").name()).split(".")[0]
    now = datetime.now().strftime("%H-%M-%S")
    batch_name = f"{script}_{now}"


    with krogerWrite:
        all_nodes = nuke.allNodes()
        generated_nodes = [
            node
            for node in all_nodes
            if node.Class() != "Input" and "view_name_knob" in node.knobs()
        ]

        if generated_nodes.count == 0:
            nuke.message("No generated nodes found in kroger write group!")
            return

        
        view_to_node = {}
        for node in generated_nodes:
            view_name_knob = node.knob("view_name_knob")
            if view_name_knob:
                view_name = view_name_knob.getValue()
                view_to_node[view_name] = node

        print("View to node mapping:")
        print(view_to_node)

    
    for view_name in selected_views:
        if view_name not in view_to_node:
            print(f"Warning: No node found for view '{view_name}', skipping...")
            failed += 1
            continue

        node = view_to_node[view_name]
        print(node.fullName())
        try:
            
            with node.begin():
                hornet_deadline_utils.deadlineNetworkSubmit(
                    # deadlineNetworkSubmit(
                    batch=batch_name,
                    silent=True,
                    node=node,
                )

            succeeded += 1
            print(f"Successfully submitted: {view_name}")

        except Exception as e:
            print(f"Failed to submit view '{view_name}': {str(e)}")
            failed += 1

    # Show results
    if succeeded > 0:
        if failed > 0:
            nuke.message(
                f"Submitted {succeeded} render{'s' if succeeded != 1 else ''} to farm.\n{failed} submission{'s' if failed != 1 else ''} failed."
            )
        else:
            nuke.message(
                f"Successfully submitted {succeeded} render{'s' if succeeded != 1 else ''} to farm!"
            )
    else:
        nuke.message("No renders were submitted successfully.")

    print(f"Submission complete: {succeeded} succeeded, {failed} failed")


def update_write_nodes_list(kroger_node=None):
    """Update the list of write nodes and their views in the properties panel"""
    try:    
        krogerWrite = kroger_node if kroger_node else nuke.thisNode()
        views_list = []

        
        with krogerWrite:
            all_nodes = nuke.allNodes()
        
            generated_nodes = [node for node in all_nodes if node.Class() != "Input"]

            for generated_node in generated_nodes:
        
                view_name_knob = generated_node.knob("view_name_knob")
                if view_name_knob:
                    view_name = view_name_knob.getValue()
                    views_list.append(view_name)

        
        write_nodes_list_knob = krogerWrite.knob("write_nodes_list")
        if write_nodes_list_knob:
            if views_list:
        
                list_text = "\n".join(views_list)
        
                list_text += "\n\n\n"
                write_nodes_list_knob.setValue(list_text)
            else:
                write_nodes_list_knob.setValue("No views found\n\n\n")

    except Exception as e:
        print(f"Error updating write nodes list: {e}")


def regenerate_write_nodes():
    """Delete all existing generated nodes and recreate them based on current views"""
    try:
        krogerWrite = nuke.thisNode()
        print("regenerating write nodes...")

        with krogerWrite:
        
            all_nodes = nuke.allNodes()
            generated_nodes = [node for node in all_nodes if node.Class() != "Input"]
            print(f"deleting {len(generated_nodes)} existing nodes...")

            for generated_node in generated_nodes:
                nuke.delete(generated_node)

        
        import quick_write

        sub_write_node_generator = quick_write._quick_write_node

        
        create_write_nodes_for_views(krogerWrite, sub_write_node_generator)

        
        update_write_nodes_list(krogerWrite)
        print("nodes regenerated successfully")

    except Exception as e:
        print(f"error regenerating nodes: {e}")


def create_write_nodes_for_views(krogerWrite, sub_write_node_generator):
    """Create generated nodes for all current views"""
    with krogerWrite:

        input_nodes = [node for node in nuke.allNodes() if node.Class() == "Input"]
        if not input_nodes:
            print("Warning: No Input node found")
            return

        source_node = input_nodes[0]
        init_position = [
            int(source_node["xpos"].getValue()),
            int(source_node["ypos"].getValue()),
        ]
        xOffset = 100
        yOffset = 100
        init_position[1] += yOffset


        aspect_value = ""
        if krogerWrite.knob("aspect"):
            aspect_value = krogerWrite["aspect"].getValue().strip()

            if aspect_value and not aspect_value.isspace():
                aspect_value = aspect_value.replace(" ", "_")
            else:
                aspect_value = ""


        for view in nuke.views():

            if aspect_value:
                variant_name = f"{view}_{aspect_value}"
                print(
                    f"creating node for view '{view}' with aspect '{aspect_value}' -> variant: '{variant_name}'"
                )
            else:
                variant_name = view
                print(f"creating node for view '{view}' (no aspect)")


            oneview = nuke.createNode("OneView", inpanel=False)
            oneview["view"].setValue(view)
            oneview.setInput(0, source_node)
            oneview.setXYpos(init_position[0], init_position[1])
            oneview.hideControlPanel()

            init_position[1] += yOffset


            generated_node = sub_write_node_generator(variant_name, inpanel=False)


            if generated_node.knob("views"):
                generated_node["views"].setValue(view)
                print(f"  set quick_write views to '{view}'")

            view_name_knob = nuke.String_Knob("view_name_knob", "Render View")
            view_name_knob.setValue(view)
            generated_node.addKnob(view_name_knob)
            generated_node.setInput(
                0, oneview
            )  # Connect to OneView instead of source_node
            generated_node.setXYpos(init_position[0], init_position[1])
            init_position[1] += yOffset  # Move position for next pair of nodes
            generated_node.hideControlPanel()


def kroger_write_node(sub_write_node_generator=None):
    if sub_write_node_generator is None:
        import quick_write

        sub_write_node_generator = quick_write._quick_write_node

    krogerWrite = nuke.createNode("Group")

    # Use Nuke's built-in unique naming - this automatically appends numbers if name exists
    krogerWrite.setName("kroger_write")

    # Add aspect ratio text input at the top
    aspect_knob = nuke.String_Knob("aspect", "Aspect")
    aspect_knob.setValue("16x9")  # Default aspect ratio
    krogerWrite.addKnob(aspect_knob)


    divider1 = nuke.Text_Knob("divider1", "")
    krogerWrite.addKnob(divider1)


    regenerate_knob = nuke.PyScript_Knob("regenerate_writes", "refresh nodes")
    regenerate_knob.setValue("kroger_write.regenerate_write_nodes()")
    krogerWrite.addKnob(regenerate_knob)


    write_nodes_knob = nuke.Multiline_Eval_String_Knob("write_nodes_list", "Views")
    write_nodes_knob.setFlag(nuke.READ_ONLY)
    krogerWrite.addKnob(write_nodes_knob)


    divider_submit = nuke.Text_Knob("divider_submit", "")
    krogerWrite.addKnob(divider_submit)


    button_knob = nuke.PyScript_Knob("render_dialog_button", "Configure and Submit")
    button_knob.setValue("kroger_write.submit_button_callback()")
    krogerWrite.addKnob(button_knob)


    batch_publish_knob = nuke.PyScript_Knob("batch_publish_button", "Batch Publish")
    batch_publish_knob.setValue("kroger_write.batch_publish_button_callback()")
    krogerWrite.addKnob(batch_publish_knob)


    divider2 = nuke.Text_Knob("divider2", "")
    krogerWrite.addKnob(divider2)


    data_knob = nuke.String_Knob("dialog_data", "Dialog Data")
    data_knob.setVisible(False)
    krogerWrite.addKnob(data_knob)


    with krogerWrite:
        source_node = nuke.createNode("Input", inpanel=False)

    # Create write nodes for current views
    create_write_nodes_for_views(krogerWrite, sub_write_node_generator)

    # Auto-populate the write nodes list on creation
    update_write_nodes_list(krogerWrite)


    krogerWrite.showControlPanel()

    return krogerWrite


"""
        Args:
        write_nodes (list): List of nuke write group nodes to publish
        delay (float): Seconds to wait between publishes
        review (bool): Whether to generate review media at all
        review_farm (bool): Whether to generate review media on farm (True) or locally (False)
        integrate_farm (bool): Whether to use farm integration ("frames_farm") or local ("frames")
        burnin (bool): Whether to include burnins in review media
        silent (bool): Suppress individual success/failure popup messages (batch summary still shown)
"""


def batch_publish(
    selected_views=None,
    review=True,
    review_farm=True,
    integrate_farm=True,
    burnin=True,
    silent=True,
    kroger_node=None,
):
    try:
        import hornet_publish_utils  # noqa: F401

        print("[OK] Successfully imported hornet_publish_utils")
    except ImportError as e:
        error_msg = f"[ERROR] Error importing hornet_publish_utils: {e}"
        print(error_msg)
        nuke.message(error_msg)
        return

    try:
        # Get the current node
        krogerWrite = kroger_node if kroger_node else nuke.thisNode()
        print(f"Using kroger node: {krogerWrite.name()}")

        publis_nodes = []
        print(f"Looking for publish nodes in {krogerWrite.name()}...")
        print(f"Selected views filter: {selected_views}")

        with krogerWrite.begin():
            nodes = nuke.allNodes("Group")
            print(f"Found {len(nodes)} Group nodes inside kroger write")

            for node in nodes:
                node_name = node.name()
                print(f"  Checking node: {node_name}")

                # Check for required knobs
                has_publish_instance = "publish_instance" in node.knobs().keys()
                has_quick_publish = "quick_publish" in node.knobs().keys()
                print(
                    f"    publish_instance: {has_publish_instance}, quick_publish: {has_quick_publish}"
                )

                if not (has_publish_instance and has_quick_publish):
                    print(f"    [SKIP] Skipping {node_name} - missing required knobs")
                    continue

                # Check view filter
                if selected_views:
                    view_name_knob = node.knob("view_name_knob")
                    if view_name_knob:
                        view_name = view_name_knob.getValue()
                        print(f"    Node view: '{view_name}'")
                        if view_name not in selected_views:
                            print(
                                f"    [SKIP] Skipping {node_name} - view '{view_name}' not in selected views"
                            )
                            continue
                    else:
                        print(f"    [WARN] Node {node_name} has no view_name_knob")

                publis_nodes.append(node)
                print(f"    [OK] Added {node_name} to publish list")

        print(f"Final publish list: {len(publis_nodes)} nodes")
        for i, node in enumerate(publis_nodes):
            view_knob = node.knob("view_name_knob")
            view_name = view_knob.getValue() if view_knob else "unknown"
            print(f"  {i + 1}. {node.name()} (view: {view_name})")

        if not publis_nodes:
            error_msg = "[ERROR] No publish nodes found matching criteria"
            print(error_msg)
            nuke.message(error_msg)
            return

        print("Starting batch publish with hornet_publish_utils...")
        print(
            f"   Parameters: review={review}, review_farm={review_farm}, integrate_farm={integrate_farm}"
        )
        print(f"   Parameters: burnin={burnin}, silent={silent}")

        hornet_publish_utils.batch_publish_write_nodes(
            publis_nodes,
            delay=0.25,
            review=review,
            review_farm=review_farm,
            integrate_farm=integrate_farm,
            burnin=burnin,
            silent=silent,
        )

        print("[OK] Batch publish completed successfully")

    except Exception as e:
        error_msg = f"[ERROR] Batch publish error: {str(e)}"
        print(error_msg)
        print(f"   Error type: {type(e).__name__}")
        import traceback

        print("   Full traceback:")
        traceback.print_exc()
        nuke.message(error_msg)
        return
