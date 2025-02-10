# Copyright (c) 2024 Alex Harding (alexharding.ooo)
# This file is part of PySequitur which is released under MIT license.
# See file LICENSE for full license details.

# PySequitur v0.1.0
# https://github.com/arcadeperfect/pysequitur

from enum import Enum, auto

import re
import os
import shutil
import logging
from enum import Flag
from typing import Dict, Optional, Tuple, List, Any, TypedDict, Union
from pathlib import Path
from dataclasses import dataclass
from collections import Counter, defaultdict
from operator import attrgetter

logging.basicConfig(
    level=logging.INFO,  # Set default level to INFO
    format="%(levelname)s: %(message)s",  # Simple format
)

logger = logging.getLogger("pysequitur")

class SequenceExistence(Enum):

    FALSE = auto()
    PARTIAL = auto()
    TRUE = auto()



@dataclass
class Components:
    """Configuration class for naming operations on Items and FileSequences.

    Provides a flexible way to specify components of a filename during renaming
    or parsing operations.

    Any component left as None will retain its original value.

    Attributes:
        prefix (str, optional): New base name
        delimiter (str, optional): New delimiter between name and frame number
        padding (int, optional): New frame number padding length
        suffix (str, optional): New suffix after frame number
        extension (str, optional): New file extension

    Example:
        Renamer(prefix="new_name", padding=4) would change:
        "old_001.exr" to "new_name_0001.exr"

    """

    prefix: Optional[str] = None
    delimiter: Optional[str] = None
    padding: Optional[int] = None
    suffix: Optional[str] = None
    extension: Optional[str] = None
    frame_number: Optional[int] = None

    def with_frame_number(self, frame_number: int) -> "Components":
        return Components(
            prefix=self.prefix,
            delimiter=self.delimiter,
            padding=max(self.padding or 0, len(str(frame_number))),
            suffix=self.suffix,
            extension=self.extension,
            frame_number=frame_number,
        )


@dataclass
class Item:

    prefix: str
    frame_string: str
    extension: str
    delimiter: Optional[str] = None
    suffix: Optional[str] = None
    directory: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.suffix is not None and any(char.isdigit() for char in self.suffix):
            raise ValueError("suffix cannot contain digits")

    @staticmethod
    def from_path(
        path: Path,
    ) -> Union["Item", None]:
        """
        Creates an Item object from a Path object

        Args:
            path (Path): Path object or string representing the file name
            directory (Path): Directory to use if path is a string (optional)
        """
        
        if path.name is None:
            raise ValueError("Path object must have a name")
        
        return ItemParser.item_from_filename(path.name, path.parent)
        
    @staticmethod
    def from_file_name(
        file_name: str,
        directory: Optional[Path] = None
    ) -> Union["Item", None]:
        
        return ItemParser.item_from_filename(file_name, directory)

    @staticmethod
    def from_components(    
        components: Components, frame: int, directory: Optional[Path] = None
    ) -> "Item":
        return ItemParser.item_from_components(components, frame, directory)

    @property
    def path(self) -> Path:
        return Path(self.absolute_path)

    @property
    def filename(self) -> str:
        """Returns the filename of the item as a string."""
        s = self.delimiter if self.delimiter else ""
        p = self.suffix if self.suffix else ""
        e = f".{self.extension}" if self.extension else ""

        return f"{self.prefix}{s}{self.frame_string}{p}{e}"

    @property
    def absolute_path(self) -> Path:
        """Returns the absolute path of the item as a Path object."""

        if self.directory is None:
            return Path(self.filename)

        return Path(self.directory) / self.filename

    @property
    def padding(self) -> int:
        """Returns the padding of the frame number as an integer."""
        return len(self.frame_string)

    @padding.setter
    def padding(self, value: int) -> None:
        """Sets the padding of the frame number.

        Args:
            value (int): New padding
        """

        padding = max(value, len(str(self.frame_number)))
        # self.frame_string = f"{self.frame_number:0{padding}d}"
        self.rename_to(Components(padding=padding))

    @property
    def stem(self) -> str:
        """Returns the stem of the item as a string."""
        return self.path.stem

    @property
    def frame_number(self) -> int:
        """Returns the frame number as an integer."""
        return int(self.frame_string)

    def update_frame_number(
        self, new_frame_number: int, padding: Optional[int] = None
    ) -> "Item":
        """Sets the frame number of the item.

        Args:
            new_frame_number (int): New frame number
            padding (int, optional): New frame number padding

        Raises:
            ValueError: If new_frame_number is negative

        """

        if new_frame_number == self.frame_number and padding == self.padding:
            return self

        if new_frame_number < 0:
            raise ValueError("new_frame_number cannot be negative")

        if padding is None:
            padding = self.padding

        new_padding = max(padding, len(str(new_frame_number)))

        self.rename_to(Components(frame_number=new_frame_number, padding=new_padding))

        return self

    def move_to(self, new_directory: Path) -> "Item":
        """Moves the item to a new directory.

        # Args:
        #     new_directory (str): New directory

        #"""

        # logger.info("Moving %s to %s", self.filename, new_directory)

        if self.check_move(new_directory)[2]:
            raise FileExistsError(
                f"File {self.filename} already exists in {new_directory}"
            )

        if self.path.exists():
            new_path = Path(new_directory) / self.filename
            self.path.rename(new_path)
            self.directory = new_directory

        else:
            raise FileNotFoundError()

        return self

    def check_move(self, new_directory: Path) -> Tuple[Path, Path, bool]:
        """Checks if the item can be moved to the given directory.

        Args:
            new_directory: The directory to check

        Returns:
            A tuple containing the current absolute path, the path that the item would be moved to,
            and a boolean indicating whether the path already exists.
        """
        new_path = Path(new_directory) / self.filename
        return (self.absolute_path, new_path, new_path.exists())  # TODO test this

    def rename_to(self, new_name: Components) -> "Item":
        """Renames the item.

        Any component that is None will not be changed.

        Can be used with an empty Components object to force the Path object to be renamed to the
        computed file name value from the components.

        # Args:
        #     new_name (str | Components, optional): New name

        #"""

        # logger.info("Renaming %s to %s", self.filename, new_name)

        old_path = Path(str(self.path))

        if new_name is None:
            new_name = Components()

        if isinstance(new_name, str):
            raise TypeError("strings are not supported in rename operatiosn")

        new_name = self._complete_components(new_name)

        # Update internal state
        self.prefix = new_name.prefix or ""
        self.delimiter = new_name.delimiter
        self.suffix = new_name.suffix
        self.extension = new_name.extension or ""
        new_padding = max(new_name.padding or 0, len(str(new_name.frame_number)))
        self.frame_string = f"{new_name.frame_number:0{new_padding}d}"

        if old_path.exists():
            old_path.rename(old_path.with_name(self.filename))
        else:
            # logger.warning("Renaming %s which does not exist", self.filename)
            pass

        return self

    def check_rename(self, new_name: Components) -> Tuple[Path, Path, bool]:
        """
        Checks if renaming the item to the new name would cause any conflicts.

        Args:
            new_name (Components): The new name to check for conflicts.

        Returns:
            Tuple[Path, Path, bool]: A tuple containing the current absolute path,
            the potential new absolute path, and a boolean indicating if the
            new name already exists.
        """

        new_name = self._complete_components(new_name)
        potential_item = Item.from_components(
            new_name, self.frame_number, self.directory
        )

        return (self.absolute_path, potential_item.absolute_path, potential_item.exists)

    def _complete_components(self, components: Components) -> Components:

        if components.prefix is None:
            components.prefix = self.prefix

        if components.delimiter is None:
            components.delimiter = self.delimiter

        if components.padding is None:
            components.padding = self.padding

        if components.suffix is None:
            components.suffix = self.suffix

        if components.extension is None:
            components.extension = self.extension

        if components.frame_number is None:
            components.frame_number = self.frame_number

        return components

    def copy_to(
        self,
        new_name: Optional[Components] = None,
        new_directory: Optional[Path] = None,
    ) -> "Item":
        """Copies the item.

        Args:
            new_name (str): New name
            new_directory (str, optional): New directory

        # Returns:
        #     Item: New item
        #"""

        # logger.info("Copying %s to %s", self.filename, new_name)

        if isinstance(new_name, str):
            raise TypeError("new_name must be a Components object")

        if new_name is None:
            new_name = Components()

        new_name = self._complete_components(new_name)

        if isinstance(new_name, str):
            raise TypeError("new_name must be a Components object")

        if new_directory is None:
            new_directory = self.directory

        new_item = Item.from_components(new_name, self.frame_number, new_directory)

        if new_item.absolute_path == self.absolute_path:
            new_item.prefix = (new_name.prefix or "") + "_copy"

        if new_item.exists:
            raise FileExistsError()

        if self.exists:
            shutil.copy2(self.absolute_path, new_item.absolute_path)

        else:
            # logger.warning("Copying %s which does not exist", self.filename)
            pass

        return new_item

    def check_copy(
        self,
        new_name: Optional[Components] = None,
        new_directory: Optional[Path] = None,
    ) -> Tuple[Path, Path, bool]:
        """
        Checks if copying the item to a new name and/or directory would cause any conflicts.

        Args:
            new_name (Optional[Components]): The new name to check for conflicts.
            new_directory (Optional[Path]): The new directory to check for conflicts.

        Returns:
            Tuple[Path, Path, bool]: A tuple containing the current absolute path,
            the potential new absolute path, and a boolean indicating if the
            new name already exists.
        """

        if isinstance(new_name, str):
            raise TypeError("new_name must be a Components object")

        if new_name is None:
            new_name = Components(prefix=self.prefix)

        if new_directory is None:
            new_directory = self.directory

        new_components = self._complete_components(new_name)

        new_item = Item.from_components(
            new_components, self.frame_number, new_directory
        )

        if new_item.absolute_path == self.absolute_path:
            new_components = self._complete_components(
                Components(prefix=new_name.prefix or "" + "_copy")
            )
            new_item = Item.from_components(
                new_components, self.frame_number, new_directory
            )

        return (self.absolute_path, new_item.absolute_path, new_item.exists)

    def delete(self) -> "Item":
        """Deletes the associated file."""

        # logger.info("Deleting %s", self.filename)

        if self.path.exists():
            self.path.unlink()
        else:
            raise FileNotFoundError()

        return self

    @property
    def exists(self) -> bool:
        """Checks if the item exists.

        Returns:
            bool: True if the item exists

        """

        return self.path.exists()

    @property
    def _min_padding(self) -> int:
        """Computes the minimum padding required to represent the frame
        number."""
        return len(str(int(self.frame_string)))

    def _check_path(self) -> bool:
        """Checks if the path computed from the components matches the path
        object."""

        if not self.path.exists():
            raise FileNotFoundError()

        if not self.absolute_path == str(self.path):
            return False

        return True


@dataclass
class FileSequence:
    """Manages a collection of related Items that form an image sequence.

    FileSequence provides methods for manipulating multiple related files as a single unit,
    including operations like renaming, moving, and frame number manipulation. It also
    provides validation and analysis of the sequence's health and consistency.

    Attributes:
        items (list[Item]): List of Item objects that make up the sequence

    Properties:
        existing_frames: List of frame numbers present in the sequence
        missing_frames: List of frame numbers missing from the sequence
        frame_count: Total number of frames including gaps
        first_frame: Lowest frame number in the sequence
        last_frame: Highest frame number in the sequence
        prefix: Common prefix shared by all items
        extension: Common file extension shared by all items
        padding: Number of digits used in frame numbers

    Example:
        A sequence might contain:
        - render_001.exr
        - render_002.exr
        - render_003.exr

    """
    class StringVariant(Enum):
        DEFAULT = auto()
        NUKE = auto()


    items: list[Item]

    def __str__(self) -> str:
        result = ""
        for item in self.items:
            result += str(item) + "\n"

        return result

    @staticmethod
    def find_sequences_in_filename_list(
        filename_list: List[str],
        directory: Optional[Path] = None,
    ) -> List["FileSequence"]:
        """
        Creates a list of detected FileSequence objects from a list of filenames.

        If no directory is supplied, the pathlib.Path objects cannot be verified
        and the sequence is considered virtual.

        Args:
            filename_list (List[str]): A list of filenames to be analyzed for sequences.
            directory (str, optional): The directory in which filenames are located.


        Returns:
            List[FileSequence]: A list of FileSequence objects representing the detected file sequences.

        """
        if not isinstance(filename_list, list):
            raise TypeError("filename_list must be a list")
            
        if directory is not None:
            if not isinstance(directory, Path):
                raise TypeError("directory must be a Path object")
        
        return SequenceParser.from_file_list(filename_list, directory)

    @staticmethod
    def find_sequences_in_path(directory: Path) -> List["FileSequence"]:
        """
        Creates a list of detected FileSequence objects from files found in a given directory.

        Args:
            directory (str | Path): The directory in which to search for sequences.

        Returns:
            FileSequence: A list of FileSequence objects representing the detected file sequences.
        """
        return SequenceParser.from_directory(directory)

    @staticmethod
    def match_components_in_filename_list(
        components: Components,
        filename_list: List[str],
        directory: Optional[Path] = None,
    ) -> List["FileSequence"]:
        """
        Matches components against a list of filenames and returns a list of detected
        sequences as FileSequence objects. If no components are specified, all
        possible sequences are returned. Otherwise only sequences that match the
        specified components are returned.

        If no directory is supplied, the pathlib.Path objects cannot be verified
        and the sequence is considered virtual.

        Examples:

        >>> FileSequence.from_components_in_filename_list(Components(prefix = "image), filename_list)
            Returns all sequences with prefix "image"

        >>> FileSequence.from_components_in_filename_list(Components(prefix = "image", extension = "exr"), filename_list)
            Returns all sequences with prefix "image" and extension "exr"

        Args:
            components (Components): Components to match
            directory (str): Directory that contains the files

        Returns:
            list[FileSequence]: List of Sequence objects

        """
        return SequenceParser.match_components_in_filename_list(
            components, filename_list, directory
        )

    @staticmethod
    def match_components_in_path(
        components: Components, directory: Path
    ) -> List["FileSequence"]:
        """
        Matches components against the contents of a directory and returns a list of detected
        sequences as FileSequence objects. If no components are specified, all
        possible sequences are returned. Otherwise only sequences that match the
        specified components are returned.


        Examples:

        >>> FileSequence.from_components_in_filename_list(Components(prefix = "image), filename_list)
            Returns all sequences with prefix "image"

        >>> FileSequence.from_components_in_filename_list(Components(prefix = "image", extension = "exr"), filename_list)
            Returns all sequences with prefix "image" and extension "exr"

        Args:
            components (Components): Components to match
            directory (str): Directory that contains the files

        Returns:
            list[FileSequence]: List of Sequence objects

        """
        return SequenceParser.filesequences_from_components_in_directory(components, directory)

    @staticmethod
    def match_sequence_string_in_filename_list(
        sequence_string: str, filename_list: List[str], directory: Optional[Path] = None
    ) -> Union["FileSequence", None]:
        """
        Matches a sequence string against a list of filenames and returns
        a detected sequence as a FileSequence object.

        Sequence strings take the form: <prefix><delimiter><####><suffix>.<extension>
        where the number of # symbols determines the padding.

        Supported Examples:

        image.####.exr
        render_###_revision.jpg
        plate_v1-#####.png

        Digits in the suffix are not supported.

        Args:
            sequencestring (str): Sequence String Pattern ie "image.####.exr"
            filename_list (list): List of filenames
            directory (str): Directory that contains the files (optional)
            pattern (str): Regex pattern for parsing frame-based filenames (optional)

        Returns:
            FileSequence: Sequence object

        """
        return SequenceParser.match_sequence_string_in_filename_list(
            sequence_string, filename_list, directory
        )

    @staticmethod
    def match_sequence_string_in_directory(
        filename: str, directory: Path
    ) -> Union["FileSequence", None]:
        """
        Matches a sequence string string against a list of files in a given directory
        and returns a detected sequence as a FileSequence object.

        Sequence strings take the form: <prefix><delimiter><####><suffix>.<extension>
        where the number of # symbols determines the padding.

        Supported Examples:

        image.####.exr
        render_###_revision.jpg
        plate_v1-#####.png

        Digits in the suffix are not supported.

        Args:
            filename (str): Sequence file name
            filename_list (list): List of filenames
            directory (str): Directory that contains the files (optional)
            pattern (str): Regex pattern for parsing frame-based filenames (optional)

        Returns:
            FileSequence: Sequence object

        """

        return SequenceParser.match_sequence_string_in_directory(
            filename, directory
        )


    @property
    def actual_frame_count(self) -> int:
        """Returns the total number of frames in the sequence, taking missing
        frames into account."""
        return len(self.items)

    @property
    def first_frame(self) -> int:
        """Returns the lowest frame number in the sequence."""
        return min(self.items, key=lambda item: item.frame_number).frame_number

    @property
    def last_frame(self) -> int:
        """Returns the highest frame number in the sequence."""
        return max(self.items, key=lambda item: item.frame_number).frame_number

    @property
    def prefix(self) -> str:
        """Returns the prefix Performs a check to ensure that prefix is
        consistent across all items."""

        return str(self._validate_property_consistency(prop_name="prefix"))

    @property
    def extension(self) -> str:
        """Returns the extension Performs a check to ensure that extension is
        consistent across all items."""
        return str(self._validate_property_consistency(prop_name="extension"))

    @property
    def delimiter(self) -> str:
        """Returns the delimiter Performs a check to ensure that delimiter is
        consistent across all items."""
        return str(self._validate_property_consistency(prop_name="delimiter"))

    @property
    def suffix(self) -> Union[str, None]:
        """Returns the suffix Performs a check to ensure that suffix is
        consistent across all items."""
        return str(self._validate_property_consistency(prop_name="suffix"))


    @property
    def directory(self) -> Path:
        """Returns the directory Performs a check to ensure that directory is
        consistent across all items."""

        directory = self._validate_property_consistency(prop_name="directory")

        if not isinstance(directory, Path):
            raise TypeError(f"{self.__class__.__name__} directory must be a Path")

        return directory

    @property
    def existing_frames(self) -> list[int]:
        """Returns a list of frame numbers which are present in the sequence.

        Frames are determined by parsing the filename of each item in the
        sequence.

        """
        return [item.frame_number for item in self.items]

    @property
    def missing_frames(self) -> List[int]:
        """Returns a set of frame numbers which are not present in the sequence.

        Frames are determined to be missing if they fall within the range of the
        first and last frame of the sequence (inclusive), but are not present in
        the sequence.

        """

        missing_frames = sorted(
            set(range(self.first_frame, self.last_frame + 1))
            - set(self.existing_frames)
        )

        if missing_frames:
            # logger.warning("Missing frames: %s", missing_frames)
            pass

        return missing_frames

    @property
    def frame_count(self) -> int:
        """Returns the number of frames in the sequence."""
        return self.last_frame + 1 - self.first_frame

    @property
    def padding(self) -> int:
        """Returns the padding.

        If padding is inconsistent, the most common padding is returned

        """

        if not self.items:
            raise ValueError("No items in sequence")
        padding_counts = Counter(item.padding for item in self.items)

        return padding_counts.most_common(1)[0][0]

    
    def sequence_string(self, variant = StringVariant.DEFAULT) -> str:
        """Returns the file name, computed from the components."""
       
        
        if variant == self.StringVariant.DEFAULT:
            padding = "#" * self.padding
            return f"{self.prefix}{self.delimiter}{padding}{self.suffix if self.suffix is not None else ''}.{self.extension}"
        
        if variant == self.StringVariant.NUKE:

            padding = f"%0{self.padding}d"

            return f"{self.prefix}{self.delimiter}{padding}{self.suffix if self.suffix is not None else ''}.{self.extension} {self.first_frame}-{self.last_frame}"

        raise ValueError(f"Invalid variant: {variant}")

    @property
    def absolute_file_name(self) -> str:
        """Returns the absolute file name."""
        return os.path.join(self.directory, self.sequence_string())
        
    @property
    def exists(self) -> SequenceExistence:
        """Returns True if the sequence exists on disk."""
        existing_count = sum(1 for item in self.items if item.exists)
        
        if existing_count == 0:
            return SequenceExistence.FALSE
        elif existing_count == len(self.items):
            return SequenceExistence.TRUE
        else:
            return SequenceExistence.PARTIAL


    @property
    def problems(self) -> "Problems":
        """Returns a flag containing all detected problems."""

        problems = Problems.check_sequence(self)

        if problems is not Problems.NONE:
            # logger.warning("Problems found: %s", problems)    
            pass

        return problems


    @staticmethod

    def rename_to(self, new_name: Components) -> "FileSequence":
        """Renames all items in the sequence.

        Args:
            new_name (str): The new name

        """
        if isinstance(new_name, str):
            raise ValueError("new_name must be a Components object, not a string")

        self._validate()

        new_name.frame_number = None

        conflicts = []

        for found in self.check_rename(new_name) or []:
            if found[2]:
                conflicts.append(found[1])

        if len(conflicts) > 0:
            raise ValueError(f"Conflicts detected: {str(conflicts)}")

        for item in self.items:
            item.rename_to(new_name.with_frame_number(item.frame_number))

        return self

    def check_rename(self, new_name: Components) -> List[Tuple[Path, Path, bool]]:
            """
            Checks if renaming the sequence to the new name would cause any conflicts.

            Args:
                new_name (Components): The new name to check for conflicts.

            Returns:
                List[Tuple[Path, Path, bool]]: List of tuples containing:
                    - Original path
                    - New path that would be created
                    - Whether a conflict exists at the new path
            """

            return [item.check_rename(new_name) for item in self.items]

    def move_to(self, new_directory: Path) -> "FileSequence":
        """Moves all items in the sequence to a new directory.

        Args:
            new_directory (str): The directory to move the sequence to.
        """

        if new_directory == self.directory:  # TODO test this
            return self

        conflicts = []

        for found in self.check_move(new_directory) or []:
            if found[2]:
                conflicts.append(found[1])

        if len(conflicts) > 0:
            raise FileExistsError(
                f"Conflicts detected: {str(conflicts)}"
            )  # TODO test this

        for item in self.items:
            item.move_to(new_directory)

        return self

    def check_move(self, new_directory: Path) -> List[Tuple[Path, Path, bool]]:
            """
            Checks if moving the sequence to the new directory would cause any conflicts.

            Args:
                new_directory (Path): The directory to check for conflicts.

            Returns:
                List[Tuple[Path, Path, bool]]: List of tuples containing:
                    - Original path
                    - New path that would be created
                    - Whether a conflict exists at the new path
            """

            # TODO test this

            return [item.check_move(new_directory) for item in self.items]

    def delete_files(self) -> "FileSequence":
        """Deletes all files in the sequence."""

        for item in self.items:
            item.delete()

        return self

    def copy_to(
        self, new_name: Optional[Components], new_directory: Optional[Path] = None
    ) -> "FileSequence":
        """Creates a copy of the sequence with a new name and optional new
        directory.

        Args:
            new_name (str): The new name
            new_directory (str, optional): The new directory. Defaults to None.

        Returns:
            FileSequence: A new FileSequence object representing the copied sequence

        """

        self.validate()

        if isinstance(new_name, str):
            raise TypeError("new_name must be a Components object, not a string")

        if isinstance(new_directory, str):
            raise TypeError("new_directory must be a Path object, not a string")

        new_items = []
        for item in self.items:
            new_item = item.copy_to(new_name, new_directory)
            new_items.append(new_item)

        new_sequence = FileSequence(new_items)

        return new_sequence

    def check_copy():
        # TODO implement this
        raise NotImplementedError

    def offset_frames(
        self, offset: int, padding: Optional[int] = None
    ) -> Union["FileSequence", None]:
        """Offsets all frames in the sequence by a given offset.

        If padding is not provided, the sequence's standard padding is used.

        Raises:
            ValueError: If the offset would result in a frame number below 0

        Args:
            offset (int): The offset to apply
            padding (int, optional): The padding to use. Defaults to None.

        """

        # TODO check if any of the new filesnames collide with existing files before proceeding

        if offset == 0:
            return

        if self.first_frame + offset < 0:
            raise ValueError("offset would yield negative frame numbers")

        if padding is None:
            padding = self.padding

        padding = max(padding, len(str(self.last_frame + offset)))

        for item in sorted(
            self.items, key=attrgetter("frame_number"), reverse=offset > 0
        ):

            target = item.frame_number + offset

            if any(item.frame_number == target for item in self.items):
                raise ValueError(f"Frame {target} already exists")

            item.update_frame_number(item.frame_number + offset, padding)

        return self  # TODO test chaining

    def set_padding(self, padding: int = 0) -> "FileSequence":
        """Sets the padding for all frames in the sequence.

        Defaults to minimum required padding to represent the last frame if a value below that is provided

        Args:
            padding (int, optional): The padding to set. Defaults to 0.

        """
        padding = max(padding, len(str(self.last_frame)))

        for item in self.items:
            item.padding = padding

        return self

    def find_duplicate_frames(self) -> Dict[int, Tuple[Item, ...]]:
        """Identifies frames that appear multiple times with different padding.
        For each set of duplicates, the first item in the tuple will be the one
        whose padding matches the sequence's standard padding.

        Returns:
            Dict[int, Tuple[Item, ...]]: Dictionary mapping frame numbers to tuples
            of Items representing duplicate frames. The first Item in each tuple
            has padding matching the sequence's standard padding.

        Example:
            If a sequence contains frame 1 as "001.ext", "01.ext", and "1.ext",
            and the sequence's padding is 3, the result would be:
            {1: (Item("001.ext"), Item("01.ext"), Item("1.ext"))}

        """
        # Group items by frame number
        frame_groups = defaultdict(list)
        for item in self.items:
            frame_groups[item.frame_number].append(item)

        # Filter for only the frame numbers that have duplicates
        duplicates = {
            frame: items for frame, items in frame_groups.items() if len(items) > 1
        }

        # Sort each group of duplicates
        sequence_padding = self.padding
        result = {}

        for frame_number, items in duplicates.items():
            # Sort items so that those matching sequence padding come first,
            # then by padding length, then by string representation for stability
            sorted_items = sorted(
                items,
                key=lambda x: (
                    x.padding != sequence_padding,  # False sorts before True
                    x.padding,
                    str(x),
                ),
            )
            result[frame_number] = tuple(sorted_items)

        return result

    def folderize(self, folder_name: str) -> None:
        """Moves all items in the sequence to a new directory.

        Args:
            folder_name (str): The directory to move the sequence to.

        """
        new_directory = self.directory / folder_name
        new_directory.mkdir(parents=True, exist_ok=True)

        for item in self.items:
            item.move_to(new_directory)  # TODO test this

    def _validate_property_consistency(self, prop_name: str) -> Any:
        """Checks if all items in the sequence have the same value for a given
        property.

        Args:
            prop_name (str): The name of the property to check.

        Returns:
            Any: The value of the property on the first item in the sequence.

        Raises:
            ValueError: If the sequence is empty.
            AnomalousItemDataError: If the values of the property are not consistent.

        """
        if not self.items:
            raise ValueError("Empty sequence")

        values = [getattr(item, prop_name) for item in self.items]

        first = values[0]
        if not all(v == first for v in values):
            raise AnomalousItemDataError(f"Inconsistent {prop_name} values")
        return first

    def validate(self) -> bool:
        """Checks that all items in the sequence have consistent values for the
        prefix, extension, delimiter, suffix, and directory properties.

        Raises:
            AnomalousItemDataError: If any of the properties have inconsistent
                values.

        """
        self._validate_property_consistency(prop_name="prefix")
        self._validate_property_consistency(prop_name="extension")
        self._validate_property_consistency(prop_name="delimiter")
        self._validate_property_consistency(prop_name="suffix")
        self._validate_property_consistency(prop_name="directory")

        return True

    def _check_padding(self) -> bool:
        """Checks that all items in the sequence have the same padding.

        # Returns:
        #     bool: True if padding is consistent, False otherwise.

        #"""
        if not all(item.padding == self.padding for item in self.items):
            # logger.warning("Inconsistent padding in sequence")
            return False
        return True


class ItemParser:
    """Static utility class for parsing filenames and discovering sequences.

    Most functionality is available through convenience methods in the Parser class.

    Parser provides methods to analyze filenames, extract components, and group related
    files into sequences. It handles complex filename patterns and supports various
    file naming conventions commonly used in visual effects and animation pipelines.

    Class Attributes:
        pattern (str): Regex pattern for parsing frame-based filenames
        known_extensions (set): Set of compound file extensions (e.g., 'tar.gz')

    Methods:
        parse_filename: Parse a single filename into components
        find_sequences: Group multiple files into sequences
        scan_directory: Scan a directory for frame sequences

    Example:
        Parser can handle filenames like:
        - "render_001.exr"
        - "comp.001.exr"
        - "anim-0100.png"

    """

    # pattern = (
    #     r"^"
    #     # Name up to last frame number
    #     r"(?P<name>.*?(?=[^a-zA-Z\d]*\d+(?!.*\d+)))"
    #     # Separator before frame (optional)
    #     r"(?P<delimiter>[^a-zA-Z\d]*)"
    #     # Frame number (1 or more digits)
    #     r"(?P<frame>\d+)"
    #     # Negative lookahead for more digits
    #     r"(?!.*\d+)"
    #     # Non-greedy match up to extension
    #     r"(?P<suffix>.*?)"
    #     # Dot and extension (everything after last dot)
    #     r"(?:\.(?P<ext>.*))?$"
    # )



    # known_extensions = {"tar.gz", "tar.bz2", "log.gz"}

    # @staticmethod
    # def item_from_filename(
    #     filename: str,
    #     directory: Optional[Path] = None,
    #     pattern: Optional[str] = None,
    # ) -> Union[Item, None]:
     
    #     # if isinstance(filename, Path):
    #     #     directory = Path(str(filename.parent))
    #     #     filename = str(filename.name)

    #     if len(Path(filename).parts) > 1:
    #         raise ValueError("first argument must be a name, not a path")

    #     if not pattern:
    #         pattern = ItemParser.pattern

    #     match = re.match(pattern, filename)
    #     if not match:
    #         return None

    #     parsed_dict = match.groupdict()

    #     # Set default values if keys are missing
    #     parsed_dict.setdefault("frame", "")
    #     parsed_dict.setdefault("name", "")
    #     parsed_dict.setdefault("ext", "")
    #     parsed_dict.setdefault("delimiter", "")
    #     parsed_dict.setdefault("suffix", "")

    #     name = parsed_dict["name"]
    #     delimiter = parsed_dict["delimiter"]

    #     if len(delimiter) > 1:
    #         name += delimiter[0:-1]
    #         delimiter = delimiter[-1]

    #     if directory is None:
    #         directory = Path("")

    #     path = Path(directory) / filename

    #     if not path:
    #         raise ValueError("invalid filepath")

    #     ext = parsed_dict.get("ext", "")

    #     if parsed_dict["ext"]:
    #         # Split the extension by dots
    #         ext_parts = parsed_dict["ext"].split(".")
    #         # Check for known multi-part extensions
    #         for i in range(len(ext_parts)):
    #             possible_ext = ".".join(ext_parts[i:])
    #             if possible_ext in ItemParser.known_extensions:
    #                 # Adjust suffix
    #                 if ext_parts[:i]:
    #                     parsed_dict["suffix"] += "." + ".".join(ext_parts[:i])
    #                 ext = possible_ext
    #                 break
    #         else:
    #             # If no known multi-part extension is found, use the last part as the extension
    #             if len(ext_parts) > 1:
    #                 parsed_dict["suffix"] += "." + ".".join(ext_parts[:-1])
    #             ext = ext_parts[-1]
    #     else:
    #         ext = ""

    #     # Remove trailing dot from suffix if present
    #     if parsed_dict["suffix"].endswith("."):
    #         parsed_dict["suffix"] = parsed_dict["suffix"][:-1]

    #     return Item(
    #         prefix=name,
    #         frame_string=parsed_dict["frame"],
    #         extension=ext,
    #         delimiter=delimiter,
    #         suffix=parsed_dict["suffix"],
    #         directory=Path(directory),
    #     )

    pattern = (
        r"^"
        # Name up to last frame number
        r"(?P<name>.*?(?=[^a-zA-Z\d]*\d+(?!.*\d+)))"
        # Separator before frame (optional)
        r"(?P<delimiter>[^a-zA-Z\d]*)"
        # Frame number (1 or more digits)
        r"(?P<frame>\d+)"
        # Negative lookahead for more digits
        r"(?!.*\d+)"
        # Non-greedy match up to end
        r"(?P<suffix>.*?)$"
    )

    known_extensions = {"tar.gz", "tar.bz2", "log.gz"}

    @staticmethod
    def item_from_filename(
        filename: str,
        directory: Optional[Path] = None,
        pattern: Optional[str] = None,
    ) -> Union[Item, None]:
        """Parse a filename into an Item object.
        
        First identifies the extension using known compound extensions or the last dot,
        then parses the remainder for sequence components.

        Args:
            filename: The filename to parse
            directory: Optional directory Path
            pattern: Optional custom regex pattern

        Returns:
            Item object if parsing succeeds, None if the filename doesn't match the pattern
        """
     
        if len(Path(filename).parts) > 1:
            raise ValueError("first argument must be a name, not a path")

        # First split on dots and determine the extension
        parts = filename.split('.')
        if len(parts) <= 1:  # No extension
            name_part = filename
            extension = ""
        else:
            # Check for known compound extensions
            for i in range(len(parts)-1):
                possible_ext = '.'.join(parts[-(i+1):])
                if possible_ext in ItemParser.known_extensions:
                    name_part = '.'.join(parts[:-(i+1)])
                    extension = possible_ext
                    break
            else:
                # If no compound extension found, use the last part
                name_part = '.'.join(parts[:-1])
                extension = parts[-1]

        # Now parse the name part with the regex
        if not pattern:
            pattern = ItemParser.pattern

        match = re.match(pattern, name_part)
        if not match:
            return None

        parsed_dict = match.groupdict()

        # Set default values if keys are missing
        parsed_dict.setdefault("frame", "")
        parsed_dict.setdefault("name", "")
        parsed_dict.setdefault("delimiter", "")
        parsed_dict.setdefault("suffix", "")

        name = parsed_dict["name"]
        delimiter = parsed_dict["delimiter"]

        if len(delimiter) > 1:
            name += delimiter[0:-1]
            delimiter = delimiter[-1]

        if directory is None:
            directory = Path("")

        path = Path(directory) / filename

        if not path:
            raise ValueError("invalid filepath")

        return Item(
            prefix=name,
            frame_string=parsed_dict["frame"],
            extension=extension,
            delimiter=delimiter,
            suffix=parsed_dict["suffix"],
            directory=Path(directory),
        )



    @staticmethod
    def item_from_path(path: Path) -> Union[Item, None]:
        """Creates an Item object from a Path object.

        Args:
            path (Path): Path object representing the file.

        Returns:
            Item: Item object created from the Path.
        """
        return ItemParser.item_from_filename(path.name, path.parent)



    



 
    @staticmethod
    def item_from_components(
        components: Components, frame: int, directory: Optional[Path] = None
    ) -> Item:
        """Converts a Components object into an Item object.

        Args:
            components (Components): Components object

        Returns:
            Item: Item object

        """

        # TODO write a test for this

        if isinstance(components, str):
            raise TypeError("components must be a Components object")

        if components.padding is None:
            components.padding = len(str(frame))

        frame_string = str(frame).zfill(components.padding)

        item = Item(
            prefix=components.prefix,
            frame_string=frame_string,
            extension=components.extension,
            delimiter=components.delimiter,
            suffix=components.suffix,
            directory=directory,
        )

        return item

    @staticmethod
    def convert_padding_to_hashes(sequence_str: str) -> str:
        """Converts printf-style frame number patterns (%04d) to hash notation (####).

        Args:
            sequence_str (str): String containing printf-style pattern

        Returns:
            str: String with hash notation

        Example:
            >>> convert_printf_pattern("render_%04d.exr")
            'render_####.exr'
            >>> convert_printf_pattern("shot_%d.jpg")  # No padding specified
            'shot_#.jpg'
        """

        # Match %[0][padding]d pattern
        # Groups:
        # 1 - Optional 0 flag
        # 2 - Optional padding number
        # Followed by mandatory 'd'
        printf_pattern = r"%(?:(0)?(\d+))?d"

        def replace_match(match):
            padding = match.group(2)
            if padding:
                # If padding specified, use that many #'s
                return "#" * int(padding)
            else:
                # If no padding specified, use single #
                return "#"

        return re.sub(printf_pattern, replace_match, sequence_str)

class SequenceParser:
    
    class SequenceDictItem(TypedDict):
        """TypedDict for storing sequence dictionary items."""

        name: str
        delimiter: str
        suffix: str
        frames: List[str]
        extension: str
        items: List[Item]
    
    
    
    @staticmethod
    def from_file_list(
        filename_list: List[str],
        directory: Optional[Path] = None,
    ) -> List[FileSequence]:
        """
        Creates a list of detected FileSequence objects from a list of filenames.

        Args:
            filename_list (List[str]): A list of filenames to be analyzed for sequences.
            directory (str, optional): The directory in which filenames are located.

        Returns:
            List[FileSequence]: A list of FileSequence objects representing the detected file sequences.
        """
        sequence_dict: Dict[Tuple[str, str, str, str], SequenceParser.SequenceDictItem] = {}

        for file in filename_list:
            
            parsed_item = ItemParser.item_from_filename(file, directory)
            if not parsed_item:
                continue

            # Include suffix in the key to separate sequences with different suffixes
            key = (
                parsed_item.prefix,
                parsed_item.delimiter or "",
                parsed_item.suffix or "",  # Add suffix to key
                parsed_item.extension or "",
            )

            if key not in sequence_dict:
                sequence_dict[key] = {
                    "name": parsed_item.prefix,
                    "delimiter": parsed_item.delimiter or "",
                    "suffix": parsed_item.suffix or "",
                    "frames": [],
                    "extension": parsed_item.extension or "",
                    "items": [],
                }

            sequence_dict[key]["items"].append(parsed_item)
            sequence_dict[key]["frames"].append(parsed_item.frame_string)

        sequence_list = []

        for seq in sequence_dict.values():
            if len(seq["items"]) < 2:
                continue

            temp_sequence = FileSequence(
                sorted(seq["items"], key=lambda i: i.frame_number)
            )

            duplicates = temp_sequence.find_duplicate_frames()

            if not duplicates:
                sequence_list.append(temp_sequence)
                continue

            padding_counts = Counter(item.padding for item in temp_sequence.items)
                
        
            nominal_padding = padding_counts.most_common(1)[0][0]

            main_sequence_items = []
            anomalous_items = defaultdict(list)
            processed_frames = set()

            for item in temp_sequence.items:
                if item.frame_number in processed_frames:
                    continue

                if item.frame_number in duplicates:
                    duplicate_items = duplicates[item.frame_number]
                    for dup_item in duplicate_items:
                        if dup_item.padding == nominal_padding:
                            main_sequence_items.append(dup_item)
                        else:
                            anomalous_items[dup_item.padding].append(dup_item)
                else:
                    main_sequence_items.append(item)

                processed_frames.add(item.frame_number)

            if len(main_sequence_items) >= 2:
                main_sequence = FileSequence(
                    sorted(main_sequence_items, key=lambda i: i.frame_number)
                )
                sequence_list.append(main_sequence)

            # for items in anomalous_items.items():
            #     if len(items) >= 2:
            #         anomalous_sequence = FileSequence(
            #             sorted(items, key=lambda i: i.frame_number)
            #         )
            #         sequence_list.append(anomalous_sequence)
            for padding, items_list in anomalous_items.items():
                if len(items_list) >= 2:
                    anomalous_sequence = FileSequence(
                        sorted(items_list, key=lambda i: i.frame_number)
                    )
                    sequence_list.append(anomalous_sequence)

        # logger.info("Parsed %d sequences", len(sequence_list))

        return sequence_list
        
    @staticmethod
    def filesequences_from_components_in_directory(
        components: Components, directory: Path
    ) -> List[FileSequence]:
        """Matches components against a directory and returns a list of detected
        sequences as FileSequence objects. If no components are specified, all
        sequences are returned. Otherwise only sequences that match the
        specified components are returned.
    
        Args:
            components (Components): Components to match
            directory (str): Directory that contains the files
    
        Returns:
            list[FileSequence]: List of Sequence objects
    
        """
    
        sequences = SequenceParser.from_directory(directory)
    
        matches = []
    
        for sequence in sequences:
    
            match = True
    
            if components.prefix is not None and components.prefix != sequence.prefix:
                match = False
    
            if (
                components.delimiter is not None
                and components.delimiter != sequence.delimiter
            ):
                match = False
    
            if (
                components.padding is not None
                and components.padding != sequence.padding
            ):
                match = False
    
            if components.suffix is not None and components.suffix != sequence.suffix:
                match = False
    
            if (
                components.extension is not None
                and components.extension != sequence.extension
            ):
                match = False
    
            if match:
                matches.append(sequence)
    
        # logger.info("Found %d sequences matching %s", len(matches), str(components))
    
        return matches

    @staticmethod
    def match_sequence_string_in_filename_list(
        sequence_string: str,
        filename_list: List[str],
        directory: Optional[Path] = None,
    ) -> Union[FileSequence, None]:
        """
        Matches a sequence string against a list of filenames and returns
        a detected sequence as a FileSequence object.
    
        Sequence strings take the form: prefix.####.suffix.extension where the
        number of # symbols determines the padding
    
        Examples:
    
        image.####.exr
        render_###_revision.jpg
        plate_v1-#####.png
    
        Args:
            filename (str): Sequence file name
            filename_list (list): List of filenames
            directory (str): Directory that contains the files (optional)
            pattern (str): Regex pattern for parsing frame-based filenames (optional)
    
        Returns:
            FileSequence: Sequence object
    
        """
    
        sequence_string = ItemParser.convert_padding_to_hashes(sequence_string)
    
        sequences = SequenceParser.from_file_list(filename_list, directory)
    
        matched = []
    
        for sequence in sequences:
    
            if sequence.sequence_string == sequence_string:
                matched.append(sequence)
    
        if len(matched) > 1:
            raise ValueError(
                f"Multiple sequences match {sequence_string!r}: {matched!r}, should be only one"
            )
    
        if len(matched) == 0:
            return None
    
        # logger.info("Found sequences matching %s", sequence_string)
    
        return matched[0]

    @staticmethod
    def match_sequence_string_in_directory(
        filename: str,
        directory: Path,
    ) -> Union[FileSequence, None]:
        """Matches a sequence string name against a directory and returns
        a detected sequence as a FileSequence object.
    
        Sequence filenames take the form: prefix.####.suffix.extension where the
        number of # symbols determines the padding
    
        Examples:
    
        image.####.exr
        render_###_revision.jpg
        plate_v1-#####.png
    
        Args:
            filename (str): Sequence file name
            filename_list (list): List of filenames
            directory (str): Directory that contains the files (optional)
            pattern (str): Regex pattern for parsing frame-based filenames (optional)
    
        Returns:
            FileSequence: Sequence object
    
        """
    
        files = os.listdir(str(directory))
    
        return SequenceParser.match_sequence_string_in_filename_list(filename, files, directory)
        
    @staticmethod
    def from_directory(directory: Path) -> List[FileSequence]:
        """Scans a directory and call Parser.detect_file_sequences to return a
        list of detected sequences as FileSequence objects.

        Sequence file names are parsed into the following component form:

        <prefix><delimiter><frame><suffix><extension>

        For example:
        render.0001.grade.exr will yield:

        prefix: render
        delimiter: .
        frame: 0001
        suffix: grade
        extension: exr

        If there are missing frames, the sequence will still be parsed.

        If a sequence is detected with inconsistent frame padding, the sequence will still be returned with the inconsistent
        padding accurately represented at the Item level, however the FileSequence object will return this as a Problem
        and attempt to guess the optimum padding value when queried at the FileSequence level.

        This can happen if a sequence exceeded expected duration during generation:

        frame_998.png
        frame_999.png
        frame_1000.png

        If duplicate frames exist with different padding, the sequence will consume the one that has the most appropriate padding,
        and any files with anomalous padding will be returned in a separate sequence:

        frame_001.png
        frame_002.png
        frame_02.png
        frame_003.png
        frame_004.png
        frame_04.png
        frame_005.png

        will yield two sequences:

        [frame_001.png
        frame_002.png
        frame_003.png
        frame_004.png
        frame_005.png]

        [frame_02.png
        frame_04.png]

        Args:
            directory (str): Directory to scan
            pattern (str): Regex pattern for parsing frame-based filenames

        Returns:
            list[FileSequence]: List of Sequence objects

        """
        
        files = os.listdir(str(directory))
        
        if not isinstance(files, list):
            raise TypeError("files must be a list")
            
        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path object")

        # return None

        return SequenceParser.from_file_list(
            files, directory
        )

    @staticmethod
    def match_components_in_filename_list(
        components: Components,
        filename_list: List[str],
        directory: Optional[Path] = None,
    ) -> List[FileSequence]:
        """Matches components against a list of filenames and returns a list of
        detected sequences as FileSequence objects. If no components are
        specified, all sequences are returned. Otherwise only sequences that
        match the specified components are returned.

        Args:
            components (Components): Components to match
            filename_list (list): List of filenames
            directory (str): Directory that contains the files (optional)
            pattern (str): Regex pattern for parsing frame-based filenames (optional)

        Returns:
            list[FileSequence]: List of Sequence objects

        """

        sequences = SequenceParser.from_file_list(filename_list, directory)

        matches = []

        for sequence in sequences:

            match = True

            if components.prefix is not None and components.prefix != sequence.prefix:
                match = False

            if (
                components.delimiter is not None
                and components.delimiter != sequence.delimiter
            ):
                match = False

            if (
                components.padding is not None
                and components.padding != sequence.padding
            ):
                match = False

            if components.suffix is not None and components.suffix != sequence.suffix:
                match = False

            if (
                components.extension is not None
                and components.extension != sequence.extension
            ):
                match = False

            if match:
                matches.append(sequence)

        # logger.info("Found %d sequences matching %s", len(matches), str(components))

        return matches


class Problems(Flag):
    """Enumeration of potential issues in frame sequences using Flag for bitwise
    operations.

    Provides a way to track and combine multiple issues that might exist in a sequence,
    such as missing frames or inconsistent padding. Uses Python's Flag class to allow
    multiple problems to be represented in a single value.

    Flags:
        NONE: No problems detected
        MISSING_FRAMES: Sequence has gaps between frame numbers
        INCONSISTENT_PADDING: Frame numbers have different padding lengths
        FILE_NAME_INCLUDES_SPACES: Filenames contain spaces
        DUPLICATE_FRAME_NUMBERS_WITH_INCONSISTENT_PADDING: Same frame appears with different padding

    Methods:
        check_sequence: Analyze a FileSequence and return all detected problems

    Example:
        problems = Problems.check_sequence(sequence)
        if problems & Problems.MISSING_FRAMES:
            print("Sequence has missing frames")

    """

    NONE = 0
    # Sequence has gaps between frame numbers
    MISSING_FRAMES = auto()
    # Frame numbers have different amounts of padding
    INCONSISTENT_PADDING = auto()
    # File names contain spaces
    FILE_NAME_INCLUDES_SPACES = auto()
    # Same frame number appears with different padding
    DUPLICATE_FRAME_NUMBERS_WITH_INCONSISTENT_PADDING = auto()

    @classmethod
    def check_sequence(cls, sequence: FileSequence) -> "Problems":
        """Analyze a FileSequence and return a Problems flag with all detected
        issues.

        Args:
            sequence (FileSequence): The sequence to check

        Returns:
            Problems: A flag containing all detected problems

        """
        problems = cls.NONE

        # Check for missing frames
        if sequence.missing_frames:
            problems |= cls.MISSING_FRAMES

        # Check for inconsistent padding
        if not sequence._check_padding():
            problems |= cls.INCONSISTENT_PADDING

        # Check for spaces in filenames
        if any(" " in item.filename for item in sequence.items):
            problems |= cls.FILE_NAME_INCLUDES_SPACES

        # Check for duplicate frames with different padding
        if sequence.find_duplicate_frames():
            problems |= cls.DUPLICATE_FRAME_NUMBERS_WITH_INCONSISTENT_PADDING

        return problems


class AnomalousItemDataError(Exception):
    """Raised when unacceptable inconsistent data is found in a FileSequence."""
