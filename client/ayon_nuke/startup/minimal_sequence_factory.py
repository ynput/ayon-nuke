"""
Minimal SequenceFactory for farm environments where the full file_sequence module might have issues.
"""

import os
import re
import importlib.util
from pathlib import Path
from typing import List, Optional, Union

# Import the needed classes from file_sequence if possible
try:
    # Try to import the full module first
    fs_spec = importlib.util.spec_from_file_location(
        "file_sequence",
        "P:/dev/alexh_dev/ayon_v2/hornet/ayon-nuke/client/ayon_nuke/startup/file_sequence/file_sequence.py",
    )
    fs_module = importlib.util.module_from_spec(fs_spec)
    fs_spec.loader.exec_module(fs_module)

    # Extract the classes we need
    FileSequence = fs_module.FileSequence
    Components = fs_module.Components
    Item = fs_module.Item
    ItemParser = fs_module.ItemParser

    print("✓ Successfully imported from full file_sequence module")

except Exception as e:
    print(f"✗ Could not import from full module: {e}")
    print("Creating minimal fallback implementation...")

    # Minimal fallback implementation
    class Components:
        def __init__(
            self,
            prefix=None,
            delimiter=None,
            padding=None,
            suffix=None,
            extension=None,
            frame_number=None,
        ):
            self.prefix = prefix
            self.delimiter = delimiter
            self.padding = padding
            self.suffix = suffix
            self.extension = extension
            self.frame_number = frame_number

    class Item:
        def __init__(
            self,
            prefix,
            frame_string,
            extension,
            delimiter=None,
            suffix=None,
            directory=None,
        ):
            self.prefix = prefix
            self.frame_string = frame_string
            self.extension = extension
            self.delimiter = delimiter
            self.suffix = suffix
            self.directory = directory

        @property
        def frame_number(self):
            return int(self.frame_string)

        @property
        def filename(self):
            s = self.delimiter if self.delimiter else ""
            p = self.suffix if self.suffix else ""
            e = f".{self.extension}" if self.extension else ""
            return f"{self.prefix}{s}{self.frame_string}{p}{e}"

    class FileSequence:
        def __init__(self, items):
            self.items = items

        @property
        def first_frame(self):
            return min(item.frame_number for item in self.items)

        @property
        def last_frame(self):
            return max(item.frame_number for item in self.items)

    class ItemParser:
        pattern = r"^(?P<name>.*?(?=[^a-zA-Z\d]*\d+(?!.*\d+)))(?P<delimiter>[^a-zA-Z\d]*)(?P<frame>\d+)(?!.*\d+)(?P<suffix>.*?)$"

        @staticmethod
        def item_from_filename(filename, directory=None):
            # Simple parsing implementation
            parts = filename.split(".")
            if len(parts) <= 1:
                return None

            extension = parts[-1]
            name_part = ".".join(parts[:-1])

            match = re.match(ItemParser.pattern, name_part)
            if not match:
                return None

            parsed = match.groupdict()
            return Item(
                prefix=parsed.get("name", ""),
                frame_string=parsed.get("frame", ""),
                extension=extension,
                delimiter=parsed.get("delimiter"),
                suffix=parsed.get("suffix"),
                directory=Path(directory) if directory else None,
            )


# Now create the SequenceFactory class
class SequenceFactory:
    @staticmethod
    def from_directory(
        directory: Path, min_frames: int = 2
    ) -> List[FileSequence]:
        """Simple implementation for farm environments."""
        try:
            files = [f.name for f in directory.iterdir() if f.is_file()]
        except:
            files = os.listdir(str(directory))

        return SequenceFactory.from_filenames(files, min_frames, directory)

    @staticmethod
    def from_filenames(
        filenames: List[str],
        min_frames: int = 2,
        directory: Optional[Path] = None,
    ) -> List[FileSequence]:
        """Simple implementation for farm environments."""
        sequence_dict = {}

        for filename in filenames:
            if filename.startswith("."):
                continue

            item = ItemParser.item_from_filename(filename, directory)
            if not item:
                continue

            key = (
                item.prefix,
                item.delimiter or "",
                item.suffix or "",
                item.extension or "",
            )

            if key not in sequence_dict:
                sequence_dict[key] = []
            sequence_dict[key].append(item)

        sequences = []
        for items in sequence_dict.values():
            if len(items) >= min_frames:
                sorted_items = sorted(items, key=lambda x: x.frame_number)
                sequences.append(FileSequence(sorted_items))

        return sequences

    @staticmethod
    def from_sequence_string_absolute(
        path: str, min_frames: int = 2
    ) -> Union[FileSequence, None]:
        """Simple implementation for farm environments."""
        path_obj = Path(path)
        return SequenceFactory.from_directory_with_sequence_string(
            path_obj.name, path_obj.parent, min_frames
        )

    @staticmethod
    def from_directory_with_sequence_string(
        filename: str, directory: Path, min_frames: int = 2
    ) -> Union[FileSequence, None]:
        """Simple implementation for farm environments."""
        # Convert hash notation to regex
        pattern = filename.replace("#", r"\d")
        pattern = pattern.replace(".", r"\.")

        try:
            files = [f.name for f in directory.iterdir() if f.is_file()]
        except:
            files = os.listdir(str(directory))

        matching_files = [f for f in files if re.match(pattern, f)]

        if len(matching_files) < min_frames:
            return None

        sequences = SequenceFactory.from_filenames(
            matching_files, min_frames, directory
        )
        return sequences[0] if sequences else None


print("✓ SequenceFactory is now available")
print(
    f"Available methods: {[m for m in dir(SequenceFactory) if not m.startswith('_')]}"
)
