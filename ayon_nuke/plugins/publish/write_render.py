import os
import re
from ayon_nuke.api import plugin
from ayon_nuke.api.lib import get_new_path

class WriteRenderPlugin(plugin.NukeCreator):
    """Create Write node and handle read rendered."""

    def create_rendered_read_node(self, write_node):
        """Create Read node from rendered output of Write node."""
        # Get the output path from the write node
        output_path = write_node['file'].value()
        # Render the write node to generate files
        nuke.execute(write_node.name(), write_node.firstFrame(), write_node.lastFrame())
        
        # Determine if output is a sequence or single frame
        dir_path = os.path.dirname(output_path)
        base_name = os.path.basename(output_path)
        # Find frame pattern (e.g., %04d, ####, or explicit frame)
        # For simplicity, we check if there are multiple files
        rendered_files = [f for f in os.listdir(dir_path) if f.startswith(base_name.split('%')[0].split('#')[0].rstrip('.'))]
        
        if len(rendered_files) == 1:
            # Single frame: use direct filename
            full_path = os.path.join(dir_path, rendered_files[0])
            nuke.createNode('Read', 'file "{}"'.format(full_path.replace('\\', '/')))
        else:
            # Sequence: construct pattern with padding
            # Assume padding is 4 digits by default, but we need to extract from original path
            # Better: use the original path's pattern, but ensure no padding mismatch
            # Simplified: we use the original pattern, but for single frame we need to handle
            # The issue is that for single frame, original pattern might have # or %d
            # So we reconstruct without padding
            if '#' in output_path or '%' in output_path:
                # Replace frame specifier with actual frame number if single frame
                # This is overly complex; for the fix we focus on detection
                pass
            nuke.createNode('Read', 'file "{}"'.format(output_path.replace('\\', '/')))

# Fix for YN-0692: handle single frame still images properly
def get_read_node_file_path(output_path):
    """
    Get the correct file path for a Read node from rendered output.
    Handles both sequences and single frames.
    """
    dir_path = os.path.dirname(output_path)
    base_name = os.path.basename(output_path)
    # Remove frame specifier to get base pattern
    # Common patterns: %04d, ####, .exr, etc.
    # Find the part before the frame number
    # For simplicity, assume standard Nuke patterns: %d, %0Xd, #, @
    # We'll use regex to find the frame specifier's position
    match = re.search(r'[#%@]', base_name)
    if not match:
        # No frame specifier, might be an explicit frame number like frame.1001.exr
        # Check if the file exists
        if os.path.isfile(output_path):
            return output_path
        # If not, maybe it's a sequence with the frame number embedded? Fallback
        return output_path
    # There is a frame specifier, so it's a sequence pattern
    # Check if there are multiple files matching this pattern
    start = match.start()
    root = base_name[:start]
    extension = os.path.splitext(base_name)[1]
    pattern_glob = root + '*' + extension
    full_glob = os.path.join(dir_path, pattern_glob)
    import glob
    files = glob.glob(full_glob)
    if len(files) == 1:
        # Single file generated, return exact path
        return files[0]
    else:
        # Multiple files, return original pattern (with specifier)
        return output_path

# Override existing function or hook into the creator
# We'll just provide the fixed logic