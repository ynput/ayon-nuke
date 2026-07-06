import re
from ayon_nuke.api import NukeUtility

class ReadFromWrite(NukeUtility):
    """Handle reading rendered output from Write nodes."""

    def get_read_path(self, write_node):
        """Construct read path from Write node, fixing padding for single frames."""
        file_path = write_node['file'].value()
        frame_start = write_node['first'].value()
        frame_end = write_node['last'].value()
        frame_inc = write_node['use_limit'].value() and write_node['limit'].value() or 1

        # Determine if single frame
        if frame_start == frame_end:
            # Use frame number with correct padding from the file pattern
            file_pattern = self.get_file_pattern(file_path)
            if file_pattern:
                # Extract padding from format (e.g., %04d)
                pad_match = re.search(r'%0(\d+)d', file_pattern)
                if pad_match:
                    pad = int(pad_match.group(1))
                else:
                    pad = 4  # default
                frame_str = str(int(frame_start)).zfill(pad)
                # Replace hash or %0Xd with frame string
                # First handle Nuke's # format (e.g., filename.####.exr)
                new_path = re.sub(r'#+', frame_str, file_path)
                # Also handle printf-style %0Xd
                new_path = re.sub(r'%0\d+d', frame_str, new_path)
                return new_path
            else:
                # Fallback: just use the frame number without padding?
                # Better to keep original behavior? Assume it's a single file.
                return file_path.replace('#', str(int(frame_start)))
        else:
            # Multiple frames: keep original behavior
            return file_path

    def get_file_pattern(self, file_path):
        """Extract printf-style pattern from file path if present."""
        if '%0' in file_path:
            return file_path
        return None
