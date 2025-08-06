import importlib.util
import sys
import traceback

print("=== Testing file_sequence import in isolation ===")

fs_loc = "P:/dev/alexh_dev/ayon_v2/hornet/ayon-nuke/client/ayon_nuke/startup/file_sequence/file_sequence.py"

try:
    print(f"Creating spec from: {fs_loc}")
    spec = importlib.util.spec_from_file_location("file_sequence", fs_loc)
    
    if spec is None:
        print("✗ Failed to create spec")
        exit(1)
    
    print("✓ Spec created successfully")
    
    print("Creating module from spec...")
    module = importlib.util.module_from_spec(spec)
    print("✓ Module created successfully")
    
    print("Adding to sys.modules...")
    sys.modules["file_sequence"] = module
    print("✓ Added to sys.modules")
    
    print("Executing module...")
    if spec.loader is not None:
        spec.loader.exec_module(module)
    else:
        print("✗ No loader available")
        exit(1)
    
    print("✓ Module executed successfully")
    
    print("\n=== Module Analysis ===")
    print(f"Module type: {type(module)}")
    print(f"Module file: {getattr(module, '__file__', 'No __file__ attribute')}")
    
    # Check all available attributes
    all_attrs = dir(module)
    public_attrs = [attr for attr in all_attrs if not attr.startswith('_')]
    
    print(f"\nTotal attributes: {len(all_attrs)}")
    print(f"Public attributes: {len(public_attrs)}")
    
    print("\nAll public attributes:")
    for attr in sorted(public_attrs):
        attr_type = type(getattr(module, attr, None)).__name__
        print(f"  - {attr} ({attr_type})")
    
    # Specifically check for SequenceFactory
    print(f"\n=== SequenceFactory Check ===")
    if hasattr(module, 'SequenceFactory'):
        print("✓ SequenceFactory is available!")
        factory = getattr(module, 'SequenceFactory')
        print(f"  Type: {type(factory)}")
        print(f"  Methods: {[m for m in dir(factory) if not m.startswith('_')]}")
    else:
        print("✗ SequenceFactory is NOT available")
        
        # Check if there are any syntax or import errors that might prevent the class from being defined
        print("\nChecking if the class name exists in the file...")
        try:
            with open(fs_loc, 'r') as f:
                content = f.read()
                if 'class SequenceFactory' in content:
                    print("✓ 'class SequenceFactory' found in file")
                    # Find the line number
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'class SequenceFactory' in line:
                            print(f"  Found at line {i+1}: {line.strip()}")
                            break
                else:
                    print("✗ 'class SequenceFactory' NOT found in file")
        except Exception as e:
            print(f"✗ Error reading file: {e}")
    
    # Test a simple import
    print(f"\n=== Test Direct Access ===")
    try:
        from file_sequence import SequenceFactory
        print("✓ Direct import of SequenceFactory successful!")
    except ImportError as e:
        print(f"✗ Direct import failed: {e}")
    except Exception as e:
        print(f"✗ Other error during direct import: {e}")
        
except Exception as e:
    print(f"✗ Error during module loading: {e}")
    traceback.print_exc()

print("\n=== Test Complete ===") 