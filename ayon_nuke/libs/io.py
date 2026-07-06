import re
from pathlib import Path

def get_file_pattern(file_paths):
    """
    Convert a list of file paths to a Nuke-compatible file pattern.
    Properly handles single-frame sequences (no padding).
    """
    if not file_paths:
        return ""

    # Convert to Path objects for easier manipulation
    paths = [Path(p) for p in file_paths]
    stems = [p.stem for p in paths]
    suffixes = [p.suffix for p in paths]

    # If all files have the same suffix, use it; otherwise handle as generic
    if len(set(suffixes)) == 1:
        suffix = suffixes[0]
    else:
        suffix = ""  # fallback: no suffix pattern

    # Try to detect frame number pattern in stems
    # Common pattern: some_name.#### or some_name.%04d or just a number at end
    # For single file, just return the file as is
    if len(file_paths) == 1:
        return str(paths[0])

    # For multiple files, try to find the pattern
    # Assume the frame number is the last numeric part of the stem
    # Used to extract the base name and padding
    # Use regex to find number at end of stem
    pattern = re.compile(r'(.*?)([0-9]+)$')
    bases = []
    frames = []
    for stem in stems:
        match = pattern.match(stem)
        if match:
            bases.append(match.group(1))
            frames.append(match.group(2))
        else:
            # No recognizable pattern, fallback: return first file (may not be a sequence)
            return str(paths[0])

    # Verify all bases are identical
    if len(set(bases)) != 1:
        # Different base names, not a proper sequence; return first file
        return str(paths[0])

    base = bases[0]
    # Determine padding from frame number length
    frame_numbers = [int(f) for f in frames]
    padding = len(frames[0])  # assume first frame length is padding

    # Check if frames are sequential
    sorted_frames = sorted(frame_numbers)
    if sorted_frames != list(range(sorted_frames[0], sorted_frames[-1]+1)):
        # Not sequential, return first file (or handle with explicit list?)
        return str(paths[0])

    # Construct pattern with padding: base + %0Xd + suffix
    if padding == 1 and len(frame_numbers) == 1:
        # Single frame with padding 1: treat as single file, no pattern
        return str(paths[0])

    if padding > 0:
        pattern_str = f"{base}%0{padding}d{suffix}"
    else:
        pattern_str = f"{base}%d{suffix}"

    # Create the full file path using the directory of the first file
    directory = paths[0].parent
    return str(directory / pattern_str)
