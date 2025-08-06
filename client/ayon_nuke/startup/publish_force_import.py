import importlib.util
import sys

"""
Deadline nuke instances launched from staging are failing to import the modules.
It appears that they don't inherit the new ayon_nuke environment.
"""

print("Loading modules...")
print(f"Python path: {sys.path}")

# First try normal imports
try:
    import hornet_deadline_utils
    import hornet_publish_review_media
    import file_sequence

    hornet_publish_review_media.hornet_publish_configurate()
    print("Normal imports successful.")

except ImportError as import_error:
    print(f"Normal imports failed ({import_error}), using force import...")

    try:
        # File paths
        hdu_loc = "P:/dev/alexh_dev/ayon_v2/hornet/ayon-nuke/client/ayon_nuke/startup/hornet_deadline_utils.py"
        dprm_loc = "P:/dev/alexh_dev/ayon_v2/hornet/ayon-nuke/client/ayon_nuke/startup/hornet_publish_review_media.py"
        fs_loc = "P:/dev/alexh_dev/ayon_v2/hornet/ayon-nuke/client/ayon_nuke/startup/file_sequence/file_sequence.py"

        # Create specs
        spec1 = importlib.util.spec_from_file_location(
            "hornet_deadline_utils", hdu_loc
        )
        spec2 = importlib.util.spec_from_file_location(
            "hornet_publish_review_media", dprm_loc
        )
        spec3 = importlib.util.spec_from_file_location("file_sequence", fs_loc)

        if not spec1 or not spec2 or not spec3:
            raise ImportError("Could not create module specs")

        # Create modules
        module1 = importlib.util.module_from_spec(spec1)
        module2 = importlib.util.module_from_spec(spec2)
        module3 = importlib.util.module_from_spec(spec3)

        # Add to sys.modules before executing (for cross-imports)
        sys.modules["hornet_deadline_utils"] = module1
        sys.modules["hornet_publish_review_media"] = module2
        sys.modules["file_sequence"] = module3

        # Execute in correct order: file_sequence first
        if spec3.loader:
            spec3.loader.exec_module(module3)
        if spec1.loader:
            spec1.loader.exec_module(module1)
        if spec2.loader:
            spec2.loader.exec_module(module2)

        # Assign to variables
        hornet_deadline_utils = module1
        hornet_publish_review_media = module2
        file_sequence = module3

        # Call the function
        hornet_publish_review_media.hornet_publish_configurate()

        print("Force import successful.")

    except Exception as e:
        print(f"Error with force import: {e}")
        raise
