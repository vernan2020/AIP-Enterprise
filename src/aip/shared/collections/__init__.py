"""Immutable collections for AIP Enterprise.

This module provides immutable collection types for use in domain models,
ensuring data integrity and safe sharing across components.

Classes:
    ImmutableList: Immutable list wrapper.
    ImmutableDict: Immutable dictionary wrapper.
    ImmutableSet: Immutable set wrapper.
"""

from typing import Callable, Generic, Iterator, Mapping, Self, Sequence, Set, TypeVar, overload

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class ImmutableList(Generic[T]):
    """Immutable list wrapper.

    Provides list-like interface with guaranteed immutability.
    Attempts to modify raise errors.

    Attributes:
        items: The underlying list data.
    """

    def __init__(self, items: Sequence[T] | None = None) -> None:
        """Initialize immutable list.

        Args:
            items: Initial items (default: empty).
        """
        self._items = tuple(items) if items else ()

    def __str__(self) -> str:
        """String representation."""
        return str(list(self._items))

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"ImmutableList({list(self._items)})"

    def __len__(self) -> int:
        """Get length of list."""
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items."""
        return iter(self._items)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> Self: ...

    def __getitem__(self, index: int | slice) -> T | "ImmutableList[T]":
        """Get item by index or slice.

        Args:
            index: Index or slice.

        Returns:
            Item or new ImmutableList for slices.
        """
        if isinstance(index, slice):
            return ImmutableList(self._items[index])
        return self._items[index]

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, ImmutableList):
            return False
        return self._items == other._items

    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash(self._items)

    def __add__(self, other: Self) -> Self:
        """Concatenate lists.

        Args:
            other: List to concatenate.

        Returns:
            New ImmutableList.
        """
        return ImmutableList(list(self._items) + list(other._items))

    def __contains__(self, item: T) -> bool:
        """Check if item in list.

        Args:
            item: Item to find.

        Returns:
            True if item exists.
        """
        return item in self._items

    def to_list(self) -> list[T]:
        """Convert to mutable list.

        Returns:
            Mutable list copy.
        """
        return list(self._items)

    def map(self, func: Callable[[T], V]) -> "ImmutableList[V]":
        """Map function over items.

        Args:
            func: Function to apply.

        Returns:
            New ImmutableList with mapped items.
        """
        return ImmutableList([func(item) for item in self._items])

    def filter(self, predicate: Callable[[T], bool]) -> "ImmutableList[T]":
        """Filter items by predicate.

        Args:
            predicate: Function returning True to keep item.

        Returns:
            New ImmutableList with filtered items.
        """
        return ImmutableList([item for item in self._items if predicate(item)])


class ImmutableDict(Generic[K, V]):
    """Immutable dictionary wrapper.

    Provides dict-like interface with guaranteed immutability.
    Attempts to modify raise errors.

    Attributes:
        items: The underlying dict data.
    """

    def __init__(self, items: Mapping[K, V] | None = None) -> None:
        """Initialize immutable dict.

        Args:
            items: Initial items (default: empty).
        """
        self._items = dict(items) if items else {}
        self._frozen_items = dict(self._items)

    def __str__(self) -> str:
        """String representation."""
        return str(self._items)

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"ImmutableDict({self._items})"

    def __len__(self) -> int:
        """Get number of items."""
        return len(self._items)

    def __getitem__(self, key: K) -> V:
        """Get item by key.

        Args:
            key: Key to lookup.

        Returns:
            Value for key.

        Raises:
            KeyError: If key not found.
        """
        return self._items[key]

    def __contains__(self, key: K) -> bool:
        """Check if key in dict.

        Args:
            key: Key to find.

        Returns:
            True if key exists.
        """
        return key in self._items

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, ImmutableDict):
            return False
        return self._items == other._items

    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash(tuple(sorted(self._items.items())))

    def __iter__(self) -> Iterator[K]:
        """Iterate over keys."""
        return iter(self._items)

    def keys(self) -> set[K]:
        """Get all keys.

        Returns:
            Set of keys.
        """
        return set(self._items.keys())

    def values(self) -> list[V]:
        """Get all values.

        Returns:
            List of values.
        """
        return list(self._items.values())

    def items(self) -> list[tuple[K, V]]:
        """Get all key-value pairs.

        Returns:
            List of (key, value) tuples.
        """
        return list(self._items.items())

    def get(self, key: K, default: V | None = None) -> V | None:
        """Get item with default.

        Args:
            key: Key to lookup.
            default: Default value if key not found.

        Returns:
            Value for key or default.
        """
        return self._items.get(key, default)

    def to_dict(self) -> dict[K, V]:
        """Convert to mutable dict.

        Returns:
            Mutable dict copy.
        """
        return dict(self._items)


class ImmutableSet(Generic[T]):
    """Immutable set wrapper.

    Provides set-like interface with guaranteed immutability.
    Attempts to modify raise errors.

    Attributes:
        items: The underlying set data.
    """

    def __init__(self, items: Sequence[T] | Set[T] | None = None) -> None:
        """Initialize immutable set.

        Args:
            items: Initial items (default: empty).
        """
        self._items = frozenset(items) if items else frozenset()

    def __str__(self) -> str:
        """String representation."""
        return str(set(self._items))

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"ImmutableSet({set(self._items)})"

    def __len__(self) -> int:
        """Get number of items."""
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        """Iterate over items."""
        return iter(self._items)

    def __contains__(self, item: T) -> bool:
        """Check if item in set.

        Args:
            item: Item to find.

        Returns:
            True if item exists.
        """
        return item in self._items

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if not isinstance(other, ImmutableSet):
            return False
        return self._items == other._items

    def __hash__(self) -> int:
        """Hash for use in collections."""
        return hash(self._items)

    def __and__(self, other: Self) -> Self:
        """Intersection of sets.

        Args:
            other: Set to intersect with.

        Returns:
            New ImmutableSet with common items.
        """
        return ImmutableSet(self._items & other._items)

    def __or__(self, other: Self) -> Self:
        """Union of sets.

        Args:
            other: Set to union with.

        Returns:
            New ImmutableSet with combined items.
        """
        return ImmutableSet(self._items | other._items)

    def __sub__(self, other: Self) -> Self:
        """Difference of sets.

        Args:
            other: Set to subtract.

        Returns:
            New ImmutableSet with difference.
        """
        return ImmutableSet(self._items - other._items)

    def to_set(self) -> set[T]:
        """Convert to mutable set.

        Returns:
            Mutable set copy.
        """
        return set(self._items)

    def is_subset_of(self, other: Self) -> bool:
        """Check if subset of another set.

        Args:
            other: The set to check against.

        Returns:
            True if this is subset of other.
        """
        return self._items <= other._items

    def is_superset_of(self, other: Self) -> bool:
        """Check if superset of another set.

        Args:
            other: The set to check against.

        Returns:
            True if this is superset of other.
        """
        return self._items >= other._items
