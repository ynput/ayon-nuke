import dataclasses
import importlib.util
import logging
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum, Flag, auto
from operator import attrgetter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union

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
        file_name: str, directory: Optional[Path] = None
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
        self,
        new_frame_number: int,
        padding: Optional[int] = None,
        virtual: bool = False,
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

        if virtual:
            return dataclasses.replace(
                self, frame_string=f"{new_frame_number:0{new_padding}d}"
            )

        self.rename_to(Components(frame_number=new_frame_number, padding=new_padding))

        return self

    def set_padding_to(self, padding: int, virtual: bool = False) -> "Item":
        if virtual:
            return dataclasses.replace(
                self, frame_string=f"{self.frame_number:0{padding}d}"
            )

        self.padding = padding

        return self

    def move_to(
        self, new_directory: Path, create_directory: bool = False, virtual: bool = False
    ) -> "Item":
        """Moves the item to a new directory.

        # Args:
        #     new_directory (str): New directory

        #"""

        logger.info("Moving %s to %s", self.filename, new_directory)

        if virtual:
            new_path = Path(new_directory) / self.filename
            return dataclasses.replace(self, directory=new_directory)

        if self.check_move(new_directory)[2]:
            raise FileExistsError(
                f"File {self.filename} already exists in {new_directory}"
            )

        if create_directory:
            if not new_directory.exists():
                new_directory.mkdir(parents=True)

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
            A tuple containing:
                - The current absolute path
                - The path that the item would be moved to
                - A boolean indicating whether the path already exists.
        """
        new_path = Path(new_directory) / self.filename
        return (self.absolute_path, new_path, new_path.exists())  # TODO test this

    def rename_to(self, new_name: Components, virtual: bool = False) -> "Item":
        """Renames the item.

        Any component that is None will not be changed.

        Empty Components forces renaming to match the current computed filename.

        # Args:
        #     new_name (str | Components, optional): New name

        #"""

        logger.info("Renaming %s to %s", self.filename, new_name)

        old_path = Path(str(self.path))

        if new_name is None:
            new_name = Components()

        if isinstance(new_name, str):
            raise TypeError("strings are not supported in rename operatiosn")

        new_name = self._complete_components(new_name)

        if virtual:
            return Item.from_components(new_name, self.frame_number, self.directory)

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
            logger.warning("Renaming %s which does not exist", self.filename)

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
        virtual: bool = False,
    ) -> "Item":
        """Copies the item.

        Args:
            new_name (str): New name
            new_directory (str, optional): New directory

        # Returns:
        #     Item: New item
        #"""

        logger.info("Copying %s to %s", self.filename, new_name)

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

        if virtual:
            return new_item

        if new_item.exists:
            raise FileExistsError()

        if self.exists:
            shutil.copy2(self.absolute_path, new_item.absolute_path)

        else:
            logger.warning("Copying %s which does not exist", self.filename)

        return new_item

    def check_copy(
        self,
        new_name: Optional[Components] = None,
        new_directory: Optional[Path] = None,
    ) -> Tuple[Path, Path, bool]:
        """
        Checks if copying the item to a new name and/or directory would cause any
        conflicts.

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

        logger.info("Deleting %s", self.filename)

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

    FileSequence provides methods for manipulating multiple related files as a single
    unit, including operations like renaming, moving, and frame number manipulation.
    It also provides validation and analysis of the sequence's health and consistency.

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

    # Re-introducing StringVariant for compatibility
    class StringVariant(Enum):
        DEFAULT = auto()
        NUKE = auto()

    items: list[Item]

    def __repr__(self) -> str:
        # return "no" # Old __repr__
        # Delegate to the sequence_string method for a more informative representation
        return self.sequence_string(variant=self.StringVariant.DEFAULT) + f" {self.first_frame}-{self.last_frame}"


    # Old __str__ method, using __repr__ for simplicity now
    # def __str__(self) -> str:
    #     result = ""
    #     for item in self.items:
    #         result += str(item) + "\n"
    #     return result

    @staticmethod
    def find_sequences_in_filename_list(
        filename_list: List[str],
        directory: Optional[Path] = None,
        min_frames: int = 2, # min_frames was not in old signature
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
        logger.warning(
            "FileSequence.find_sequences_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames instead."
        )
        print(
            "FileSequence.find_sequences_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames instead."
        )
        print("")
        if not isinstance(filename_list, list):
            raise TypeError("filename_list must be a list")

        if directory is not None:
            if not isinstance(directory, Path):
                raise TypeError("directory must be a Path object")

        # Delegate to the new SequenceFactory
        return SequenceFactory.from_filenames(filename_list, min_frames, directory)

    @staticmethod
    def find_sequences_in_path(directory: Path, min_frames: int = 2) -> List["FileSequence"]:
        """
        Creates a list of detected FileSequence objects from files found in a given directory.

        Args:
            directory (str | Path): The directory in which to search for sequences.

        Returns:
            FileSequence: A list of FileSequence objects representing the detected file sequences.
        """
        logger.warning(
            "FileSequence.find_sequences_in_path is deprecated. "
            "Please use SequenceFactory.from_directory instead."
        )
        print(
            "FileSequence.find_sequences_in_path is deprecated. "
            "Please use SequenceFactory.from_directory instead."
        )
        # Delegate to the new SequenceFactory
        return SequenceFactory.from_directory(directory, min_frames)

    @staticmethod
    def match_components_in_filename_list(
        components: Components,
        filename_list: List[str],
        directory: Optional[Path] = None,
        min_frames: int = 2, # min_frames was not in old signature
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
        logger.warning(
            "FileSequence.match_components_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames_with_components instead."
        )
        print(
            "FileSequence.match_components_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames_with_components instead."
        )
        # Delegate to the new SequenceFactory
        return SequenceFactory.from_filenames_with_components(
            components, filename_list, directory, min_frames
        )

    @staticmethod
    def match_components_in_path(
        components: Components, directory: Path, min_frames: int = 2 # min_frames was not in old signature
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
        logger.warning(
            "FileSequence.match_components_in_path is deprecated. "
            "Please use SequenceFactory.from_directory_with_components instead."
        )
        print(
            "FileSequence.match_components_in_path is deprecated. "
            "Please use SequenceFactory.from_directory_with_components instead."
        )
        # Delegate to the new SequenceFactory
        return SequenceFactory.from_directory_with_components(components, directory, min_frames)

    @staticmethod
    def match_sequence_string_in_filename_list(
        sequence_string: str, filename_list: List[str], directory: Optional[Path] = None,
        min_frames: int = 2, # min_frames was not in old signature
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
        logger.warning(
            "FileSequence.match_sequence_string_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames_with_sequence_string instead."
        )
        print(
            "FileSequence.match_sequence_string_in_filename_list is deprecated. "
            "Please use SequenceFactory.from_filenames_with_sequence_string instead."
        )
        # Delegate to the new SequenceFactory
        return SequenceFactory.from_filenames_with_sequence_string(
            sequence_string, filename_list, directory, min_frames
        )

    @staticmethod
    def match_sequence_string_in_directory(
        filename: str, directory: Path, min_frames: int = 2 # min_frames was not in old signature
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
        logger.warning(
            "FileSequence.match_sequence_string_in_directory is deprecated. "
            "Please use SequenceFactory.from_directory_with_sequence_string instead."
        )
        print(
            "FileSequence.match_sequence_string_in_directory is deprecated. "
            "Please use SequenceFactory.from_directory_with_sequence_string instead."
        )
        # Delegate to the new SequenceFactory
        return SequenceFactory.from_directory_with_sequence_string(
            filename, directory, min_frames
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
            logger.warning("Missing frames: %s", missing_frames)

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

    def sequence_string(self, variant: StringVariant = StringVariant.DEFAULT) -> str:
        """Returns the file name, computed from the components."""
        padding_str: str
        if variant == self.StringVariant.DEFAULT:
            padding_str = "#" * self.padding
            suffix_part = self.suffix if self.suffix is not None else ""
            return f"{self.prefix}{self.delimiter}{padding_str}{suffix_part}.{self.extension}"
        elif variant == self.StringVariant.NUKE:
            padding_str = f"%0{self.padding}d"
            suffix_part = self.suffix if self.suffix is not None else ""
            return f"{self.prefix}{self.delimiter}{padding_str}{suffix_part}.{self.extension} {self.first_frame}-{self.last_frame}"
        else:
            raise ValueError(f"Invalid variant: {variant}")


    @property
    def absolute_file_name(self) -> str:
        """Returns the absolute file name."""
        return os.path.join(self.directory, self.sequence_string(variant=self.StringVariant.DEFAULT)) # Ensure default variant is used

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

        # TODO write tests for this

        problems = Problems.check_sequence(self)

        if problems is not Problems.NONE:
            logger.warning("Problems found: %s", problems)

        return problems

    # Renaming this to _rename_to as it was a static method in the old code
    # but operated on 'self' which is an instance method behavior.
    # The new API for FileSequence rename_to is an instance method.
    def _rename_to_old_static_api(self, new_name: Components) -> "FileSequence":
        """Renames all items in the sequence. This is a compatibility shim."""
        logger.warning(
            "FileSequence.rename_to (old static method API) is deprecated. "
            "Please use the instance method .rename_to() or SequenceFactory methods instead."
        )
        print(
            "FileSequence.rename_to (old static method API) is deprecated. "
            "Please use the instance method .rename_to() or SequenceFactory methods instead."
        )
        if isinstance(new_name, str):
            raise ValueError("new_name must be a Components object, not a string")

        self.validate() # Ensure consistency before renaming

        # This method in the old code did not account for 'virtual' operations.
        # Assuming it performs actual file operations.
        new_name.frame_number = None # Ensure frame number is not part of sequence rename components

        conflicts = []
        for found in self.check_rename(new_name) or []:
            if found[2]:
                conflicts.append(found[1])

        if len(conflicts) > 0:
            raise ValueError(f"Conflicts detected: {str(conflicts)}")

        for item in self.items:
            # Need to pass the frame number to the item's rename_to for proper formatting
            item.rename_to(new_name.with_frame_number(item.frame_number))

        return self

    def rename_to(self, new_name: Components, virtual=False) -> "FileSequence":
        """Renames all items in the sequence.

        Args:
            new_name (str): The new name

        """

        # TODO: add test for virtual

        if isinstance(new_name, str):
            raise ValueError("new_name must be a Components object, not a string")

        if virtual:
            new_items = [item.rename_to(new_name, True) for item in self.items]
            return FileSequence(new_items)

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

    def move_to(
        self, new_directory: Path, create_directory: bool = False, virtual: bool = False
    ) -> "FileSequence":
        """Moves all items in the sequence to a new directory.

        Args:
            new_directory (str): The directory to move the sequence to.
            create_directory (bool, optional): Whether to create the directory if it
                doesn't exist. Defaults to False.
        """

        if new_directory == self.directory:  # TODO test this
            return self

        if virtual:
            virtual_items = [
                item.move_to(new_directory, create_directory, virtual=True)
                for item in self.items
            ]
            return FileSequence(virtual_items)

        conflicts = []

        for found in self.check_move(new_directory) or []:
            if found[2]:
                conflicts.append(found[1])

        if len(conflicts) > 0:
            raise FileExistsError(
                f"Conflicts detected: {str(conflicts)}"
            )  # TODO test this

        for item in self.items:
            item.move_to(new_directory, create_directory)

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
        self,
        new_name: Optional[Components] = None,
        new_directory: Optional[Path] = None,
        create_directory: bool = False,
        virtual: bool = False,
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

        if new_directory is not None and create_directory:
            new_directory.mkdir(parents=True, exist_ok=True)

        new_items = []
        for item in self.items:
            new_item = item.copy_to(new_name, new_directory, virtual)
            new_items.append(new_item)

        new_sequence = FileSequence(new_items)

        return new_sequence

    def check_copy(self):
        # TODO implement this
        raise NotImplementedError

    def offset_frames(
        self, offset: int, padding: Optional[int] = None, virtual: bool = False
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
            return self

        # Check for negative frame numbers in both virtual and non-virtual modes
        if self.first_frame + offset < 0:
            raise ValueError("offset would yield negative frame numbers")

        if padding is None:
            padding = self.padding

        padding = max(padding, len(str(self.last_frame + offset)))

        if virtual:
            virtual_items = [
                item.update_frame_number(
                    item.frame_number + offset, padding=padding, virtual=True
                )
                for item in self.items
            ]
            return FileSequence(virtual_items)

        for item in sorted(
            self.items, key=attrgetter("frame_number"), reverse=offset > 0
        ):
            target = item.frame_number + offset

            if any(item.frame_number == target for item in self.items):
                raise ValueError(f"Frame {target} already exists")

            item.update_frame_number(item.frame_number + offset, padding)

        return self

    def set_padding_to(self, padding: int = 0, virtual: bool = False) -> "FileSequence":
        """Sets the padding for all frames in the sequence.

        Defaults to minimum required padding to represent the last frame if a value
        below that is provided

        Args:
            padding (int, optional): The padding to set. Defaults to 0.

        """
        padding = max(padding, len(str(self.last_frame)))

        if virtual:
            virtual_items = [
                item.set_padding_to(padding, virtual=True) for item in self.items
            ]
            return FileSequence(virtual_items)

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

    def folderize(
        self, folder_name: str, virtual: bool = False
    ) -> Union["FileSequence", str]:
        """Moves all items in the sequence to a new directory.

        Args:
            folder_name (str): The directory to move the sequence to.
            virtual (bool, optional): If True, returns a new FileSequence with updated paths
                                    without performing actual file operations. Defaults to False.

        Returns:
            Union[FileSequence, str]: If virtual=True, returns a new FileSequence object.
                                    If virtual=False, returns the sequence string.
        """
        new_directory = self.directory / folder_name

        if virtual:
            # Create virtual items with the new directory without moving files
            virtual_items = [
                item.move_to(new_directory, create_directory=False, virtual=True)
                for item in self.items
            ]
            # Return a new FileSequence with the virtual items
            return FileSequence(virtual_items)

        # Original implementation for non-virtual mode
        new_directory.mkdir(parents=True, exist_ok=True)

        for item in self.items:
            item.move_to(new_directory)

        # The old version returned None, but the docstring said it returned the sequence string
        # I'm adjusting to return the new sequence string for consistency if not virtual
        return self.sequence_string(variant=self.StringVariant.DEFAULT)


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
            logger.warning("Inconsistent padding in sequence")
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
            Item object if parsing succeeds, None if the filename doesn't match
            the pattern
        """

        if len(Path(filename).parts) > 1:
            raise ValueError("first argument must be a name, not a path")

        # First split on dots and determine the extension
        parts = filename.split(".")
        if len(parts) <= 1:  # No extension
            name_part = filename
            extension = ""
        else:
            # Check for known compound extensions
            for i in range(len(parts) - 1):
                possible_ext = ".".join(parts[-(i + 1) :])
                if possible_ext in ItemParser.known_extensions:
                    name_part = ".".join(parts[: -(i + 1)])
                    extension = possible_ext
                    break
            else:
                # If no compound extension found, use the last part
                name_part = ".".join(parts[:-1])
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

        if components.prefix is None:
            raise ValueError("components must have a prefix")

        if components.extension is None:
            raise ValueError("components must have an extension")

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

        # TODO test this

        # Match %[0][padding]d pattern
        # Groups:
        # 1 - Optional 0 flag
        # 2 - Optional padding number
        # Followed by mandatory 'd'

        print("converting item to hashes")

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
    @dataclass
    class ParseResult:
        sequences: list[FileSequence]
        rogues: list[Path]

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
        min_frames: int = 2, # Added min_frames to new API
        allowed_extensions: Optional[set[str]] = None,
        # return_rogues = False # Removed as per new API design
    ) -> ParseResult: # Changed return type to ParseResult
        """
        Creates a list of detected FileSequence objects from a list of filenames.

        Args:
            filename_list (List[str]): A list of filenames to be analyzed for sequences.
            directory (str, optional): The directory in which filenames are located.

        Returns:
            List[FileSequence]: A list of FileSequence objects representing the detected
            file sequences.
        """
        sequence_dict: Dict[
            Tuple[str, str, str, str], SequenceParser.SequenceDictItem
        ] = {}

        rogues: list[Path] = [] # Added for new API

        if allowed_extensions: # Added for new API
            allowed_extensions = {ext.lower().lstrip(".") for ext in allowed_extensions}

        for file in filename_list:
            # TODO config file for this
            if file[0] == ".":
                continue

            if allowed_extensions: # Added for new API
                extension = Path(file).suffix.lower().lstrip(".")
                if extension not in allowed_extensions:
                    continue

            parsed_item = ItemParser.item_from_filename(file, directory)
            if not parsed_item:
                # if return_rogues: # Removed as per new API design
                if directory is None: # Added for new API
                    directory = Path("")
                rogues.append(directory / file) # Added for new API
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
            if len(seq["items"]) < min_frames: # Used min_frames from new API
                # If a sequence does not meet min_frames, its items become rogues
                if directory is None:
                    directory = Path("")
                for item in seq["items"]:
                    rogues.append(item.absolute_path)
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

            if len(main_sequence_items) >= 2: # Keep min_frames for sub-sequences too
                main_sequence = FileSequence(
                    sorted(main_sequence_items, key=lambda i: i.frame_number)
                )
                sequence_list.append(main_sequence)

            for _padding, items_list in anomalous_items.items():
                if len(items_list) >= 2: # Keep min_frames for sub-sequences too
                    anomalous_sequence = FileSequence(
                        sorted(items_list, key=lambda i: i.frame_number)
                    )
                    sequence_list.append(anomalous_sequence)

        logger.info(f"Parsed {len(sequence_list)} sequences in {directory}")

        return __class__.ParseResult(sequence_list, rogues) # Changed return value

    @staticmethod
    def filesequences_from_components_in_directory(
        components: Components, min_frames: int, directory: Path
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

        sequences = SequenceParser.from_directory(directory, min_frames).sequences

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

        logger.info("Found %d sequences matching %s", len(matches), str(components))

        return matches

    @staticmethod
    def match_sequence_string_in_filename_list(
        sequence_string: str,
        filename_list: List[str],
        min_frames: int, # Added min_frames to new API
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
        print(f"pre padding conversion: {sequence_string}") # Keep old print
        sequence_string = ItemParser.convert_padding_to_hashes(sequence_string)
        print(f"post padding conversion: {sequence_string}") # Keep old print

        sequences = SequenceParser.from_file_list(
            filename_list, directory, min_frames # Fixed parameter order
        ).sequences

        matched = []

        for sequence in sequences:
            if sequence.sequence_string(variant=FileSequence.StringVariant.DEFAULT) == sequence_string: # Use the method
                matched.append(sequence)

        if len(matched) > 1:
            raise ValueError(
                f"Multiple sequences match {sequence_string!r}: {matched!r}, should be only one"  # noqa: E501
            )

        if len(matched) == 0:
            return None

        logger.info("Found sequences matching %s", sequence_string)

        return matched[0]

    @staticmethod
    def match_sequence_string_absolute(
        path: str, min_frames: int # Added min_frames to new API
    ) -> Union[FileSequence, None]:
        """Matches a sequence path against a list of filenames and returns
        a detected sequence as a FileSequence object.
        """
        path_ = Path(path)

        return SequenceParser.match_sequence_string_in_directory(
            path_.name, min_frames, path_.parent # Used min_frames from new API
        )

    @staticmethod
    def match_sequence_string_in_directory(
        filename: str,
        min_frames: int, # Added min_frames to new API
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

        print(f"matching sequence string in directory: {filename}") # Keep old print

        files = os.listdir(str(directory))

        return SequenceParser.match_sequence_string_in_filename_list(
            filename, files, min_frames, directory # Used min_frames from new API
        )

    @staticmethod
    def from_directory(
        directory: Path,
        min_frames: int = 2, # Added min_frames to new API
        allowed_extensions: Optional[set[str]] = None, # Added for new API
    ) -> ParseResult: # Changed return type to ParseResult
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

        If a sequence is detected with inconsistent frame padding, the sequence will
        still be returned with the inconsistent padding accurately represented at the
        Item level, however the FileSequence object will return this as a Problem and
        attempt to guess the optimum padding value when queried at the FileSequence
        level.

        This can happen if a sequence exceeded expected duration during generation:

        frame_998.png
        frame_999.png
        frame_1000.png

        If duplicate frames exist with different padding, the sequence will consume the
        one that has the most appropriate padding, and any files with anomalous padding
        will be returned in a separate sequence:

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

        # files = os.listdir(str(directory)) # Old way
        files = [str(f.name) for f in directory.iterdir() if f.is_file()] # New way, using pathlib.Path.iterdir()

        if not isinstance(files, list):
            raise TypeError("files must be a list")

        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path object")

        # return None # Old return

        return SequenceParser.from_file_list(
            files, directory, min_frames, allowed_extensions # Used min_frames and allowed_extensions from new API
        )

    @staticmethod
    def match_components_in_filename_list(
        components: Components,
        filename_list: List[str],
        min_frames: int, # Added min_frames to new API
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

        sequences = SequenceParser.from_file_list(filename_list, directory, min_frames).sequences # Fixed parameter order

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

        logger.info("Found %d sequences matching %s", len(matches), str(components))

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

    """  # noqa: E501

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


class SequenceFactory:
    @staticmethod
    def from_directory(directory: Path, min_frames: int = 2) -> list[FileSequence]:
        return SequenceParser.from_directory(directory, min_frames).sequences

    @staticmethod
    def from_filenames(
        filenames: List[str], min_frames: int = 2, directory: Optional[Path] = None
    ) -> list[FileSequence]:
        """
        Creates a list of detected FileSequence objects from files
        found in a given directory.

        Args:
            filenames (List[str]): A list of file names to search for sequences.
            min_frames (int): The minimum number of frames required for a sequence.
            directory (str | Path): The directory in which to search for sequences.

        Returns:
            List[FileSequence]: A list of FileSequence objects representing
            the detected file sequences.
        """
        return SequenceParser.from_file_list(filenames, directory, min_frames).sequences

    @staticmethod
    def from_filenames_with_components(
        components: Components,
        filename_list: List[str],
        directory: Optional[Path] = None,
        min_frames: int = 2,
    ) -> list[FileSequence]:
        return SequenceParser.match_components_in_filename_list(
            components, filename_list, min_frames, directory
        )

    @staticmethod
    def from_directory_with_components(
        components: Components, directory: Path, min_frames: int = 2
    ) -> List["FileSequence"]:
        """
        Matches components against the contents of a directory and returns a list
        of detected sequences as FileSequence objects. If no components are specified,
        all possible sequences are returned. Otherwise only sequences that match the
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

        """  # noqa: E501
        return SequenceParser.filesequences_from_components_in_directory(
            components, min_frames, directory
        )

    @staticmethod
    def from_filenames_with_sequence_string(
        sequence_string: str,
        filename_list: List[str],
        directory: Optional[Path] = None,
        min_frames: int = 2,
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
            sequence_string, filename_list, min_frames, directory
        )

    @staticmethod
    def from_sequence_string_absolute(
        path: str, min_frames: int = 2
    ) -> Union["FileSequence", None]:
        """
        Parses a combined directory and sequence string as a single argument.

        Sequence strings take the form: <prefix><delimiter><####><suffix>.<extension>
        where the number of # symbols determines the padding.

        Returns:
            FileSequence | None
        """

        return SequenceParser.match_sequence_string_absolute(path, min_frames)

    @staticmethod
    def from_directory_with_sequence_string(
        filename: str, directory: Path, min_frames: int = 2
    ) -> Union["FileSequence", None]:
        """
        Matches a sequence string string against the contents of a given directory
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
            directory (str): Directory that contains the files (optional)

        Returns:
            FileSequence | None

        """

        return SequenceParser.match_sequence_string_in_directory(
            filename, min_frames, directory
        )

    @staticmethod
    def from_nuke_node(node) -> Union["FileSequence", None]:
        """
        Creates a FileSequence object from a Nuke node
        Can only be called from a Nuke environment

        Raises:
            ImportError: Nuke is not available

        Returns:
            FileSequence | None
        """
        if not importlib.util.find_spec("nuke"):
            raise ImportError("This method can only be called from a Nuke environment")

        # The old Nuke node reading implicitly assumes the path contains the sequence string.
        # This will need careful testing as Nuke's 'file' knob often contains the full sequence string.
        file_path_from_nuke = node["file"].getValue()
        try:
            # Attempt to parse as an absolute sequence string
            return SequenceFactory.from_sequence_string_absolute(file_path_from_nuke)
        except ValueError as e:
            # If it fails, log and return None or re-raise if strict
            logger.error(f"Failed to parse Nuke file path '{file_path_from_nuke}' as a sequence string: {e}")
            return None