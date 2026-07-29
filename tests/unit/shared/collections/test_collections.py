"""Tests for collections module.

Comprehensive tests for immutable collection types.
"""


from src.aip.shared.collections import (
    ImmutableDict,
    ImmutableList,
    ImmutableSet,
)


class TestImmutableList:
    """Tests for ImmutableList."""

    def test_immutable_list_creation_empty(self) -> None:
        """Test creating empty immutable list."""
        lst = ImmutableList()
        assert len(lst) == 0

    def test_immutable_list_creation_with_items(self) -> None:
        """Test creating immutable list with items."""
        lst = ImmutableList([1, 2, 3])
        assert len(lst) == 3
        assert lst[0] == 1

    def test_immutable_list_indexing(self) -> None:
        """Test indexing."""
        lst = ImmutableList([10, 20, 30])
        assert lst[0] == 10
        assert lst[1] == 20
        assert lst[-1] == 30

    def test_immutable_list_slicing(self) -> None:
        """Test slicing."""
        lst = ImmutableList([1, 2, 3, 4, 5])
        result = lst[1:3]

        assert isinstance(result, ImmutableList)
        assert len(result) == 2
        assert result[0] == 2

    def test_immutable_list_iteration(self) -> None:
        """Test iteration."""
        lst = ImmutableList([1, 2, 3])
        items = list(lst)

        assert items == [1, 2, 3]

    def test_immutable_list_contains(self) -> None:
        """Test contains check."""
        lst = ImmutableList([1, 2, 3])

        assert 2 in lst
        assert 5 not in lst

    def test_immutable_list_equality(self) -> None:
        """Test equality."""
        lst1 = ImmutableList([1, 2, 3])
        lst2 = ImmutableList([1, 2, 3])
        lst3 = ImmutableList([1, 2])

        assert lst1 == lst2
        assert lst1 != lst3

    def test_immutable_list_hash(self) -> None:
        """Test hashing."""
        lst1 = ImmutableList([1, 2, 3])
        lst2 = ImmutableList([1, 2, 3])

        assert hash(lst1) == hash(lst2)

    def test_immutable_list_concatenation(self) -> None:
        """Test concatenation."""
        lst1 = ImmutableList([1, 2])
        lst2 = ImmutableList([3, 4])

        result = lst1 + lst2

        assert isinstance(result, ImmutableList)
        assert len(result) == 4
        assert result[2] == 3

    def test_immutable_list_to_list(self) -> None:
        """Test conversion to mutable list."""
        lst = ImmutableList([1, 2, 3])
        mutable = lst.to_list()

        assert isinstance(mutable, list)
        assert mutable == [1, 2, 3]

    def test_immutable_list_map(self) -> None:
        """Test map function."""
        lst = ImmutableList([1, 2, 3])
        result = lst.map(lambda x: x * 2)

        assert isinstance(result, ImmutableList)
        assert result[0] == 2
        assert result[1] == 4

    def test_immutable_list_filter(self) -> None:
        """Test filter function."""
        lst = ImmutableList([1, 2, 3, 4, 5])
        result = lst.filter(lambda x: x > 2)

        assert isinstance(result, ImmutableList)
        assert len(result) == 3
        assert result[0] == 3

    def test_immutable_list_str_and_repr(self) -> None:
        """Test list string representations."""
        lst = ImmutableList([1, 2, 3])
        assert str(lst) == "[1, 2, 3]"
        assert "ImmutableList" in repr(lst)

    def test_immutable_list_equality_with_other_type(self) -> None:
        """Test list inequality with other types."""
        lst = ImmutableList([1, 2, 3])
        assert lst != [1, 2, 3]


class TestImmutableDict:
    """Tests for ImmutableDict."""

    def test_immutable_dict_creation_empty(self) -> None:
        """Test creating empty immutable dict."""
        d = ImmutableDict()
        assert len(d) == 0

    def test_immutable_dict_creation_with_items(self) -> None:
        """Test creating immutable dict with items."""
        d = ImmutableDict({"a": 1, "b": 2})
        assert len(d) == 2
        assert d["a"] == 1

    def test_immutable_dict_indexing(self) -> None:
        """Test indexing."""
        d = ImmutableDict({"a": 10, "b": 20})
        assert d["a"] == 10

    def test_immutable_dict_get(self) -> None:
        """Test get method."""
        d = ImmutableDict({"a": 10})

        assert d.get("a") == 10
        assert d.get("missing") is None
        assert d.get("missing", 99) == 99

    def test_immutable_dict_contains(self) -> None:
        """Test contains check."""
        d = ImmutableDict({"a": 1, "b": 2})

        assert "a" in d
        assert "c" not in d

    def test_immutable_dict_keys(self) -> None:
        """Test keys method."""
        d = ImmutableDict({"a": 1, "b": 2})
        keys = d.keys()

        assert isinstance(keys, set)
        assert "a" in keys

    def test_immutable_dict_values(self) -> None:
        """Test values method."""
        d = ImmutableDict({"a": 1, "b": 2})
        values = d.values()

        assert 1 in values
        assert 2 in values

    def test_immutable_dict_items(self) -> None:
        """Test items method."""
        d = ImmutableDict({"a": 1, "b": 2})
        items = d.items()

        assert ("a", 1) in items
        assert ("b", 2) in items

    def test_immutable_dict_iteration(self) -> None:
        """Test iteration over keys."""
        d = ImmutableDict({"a": 1, "b": 2})
        keys = list(d)

        assert "a" in keys
        assert "b" in keys

    def test_immutable_dict_equality(self) -> None:
        """Test equality."""
        d1 = ImmutableDict({"a": 1, "b": 2})
        d2 = ImmutableDict({"a": 1, "b": 2})
        d3 = ImmutableDict({"a": 1})

        assert d1 == d2
        assert d1 != d3

    def test_immutable_dict_hash(self) -> None:
        """Test hashing."""
        d1 = ImmutableDict({"a": 1})
        d2 = ImmutableDict({"a": 1})

        assert hash(d1) == hash(d2)

    def test_immutable_dict_to_dict(self) -> None:
        """Test conversion to mutable dict."""
        d = ImmutableDict({"a": 1, "b": 2})
        mutable = d.to_dict()

        assert isinstance(mutable, dict)
        assert mutable["a"] == 1

    def test_immutable_dict_str_and_repr(self) -> None:
        """Test dict string representations."""
        data = ImmutableDict({"a": 1})
        assert str(data) == "{'a': 1}"
        assert "ImmutableDict" in repr(data)

    def test_immutable_dict_equality_with_other_type(self) -> None:
        """Test dict inequality with other types."""
        data = ImmutableDict({"a": 1})
        assert data != {"a": 1}


class TestImmutableSet:
    """Tests for ImmutableSet."""

    def test_immutable_set_creation_empty(self) -> None:
        """Test creating empty immutable set."""
        s = ImmutableSet()
        assert len(s) == 0

    def test_immutable_set_creation_with_items(self) -> None:
        """Test creating immutable set with items."""
        s = ImmutableSet([1, 2, 3])
        assert len(s) == 3

    def test_immutable_set_contains(self) -> None:
        """Test contains check."""
        s = ImmutableSet([1, 2, 3])

        assert 2 in s
        assert 5 not in s

    def test_immutable_set_iteration(self) -> None:
        """Test iteration."""
        s = ImmutableSet([1, 2, 3])
        items = set(s)

        assert items == {1, 2, 3}

    def test_immutable_set_equality(self) -> None:
        """Test equality."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([1, 2, 3])
        s3 = ImmutableSet([1, 2])

        assert s1 == s2
        assert s1 != s3

    def test_immutable_set_hash(self) -> None:
        """Test hashing."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([1, 2, 3])

        assert hash(s1) == hash(s2)

    def test_immutable_set_intersection(self) -> None:
        """Test intersection."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([2, 3, 4])

        result = s1 & s2

        assert isinstance(result, ImmutableSet)
        assert 2 in result
        assert 1 not in result

    def test_immutable_set_union(self) -> None:
        """Test union."""
        s1 = ImmutableSet([1, 2])
        s2 = ImmutableSet([2, 3])

        result = s1 | s2

        assert isinstance(result, ImmutableSet)
        assert 1 in result
        assert 3 in result

    def test_immutable_set_difference(self) -> None:
        """Test difference."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([2, 3])

        result = s1 - s2

        assert isinstance(result, ImmutableSet)
        assert 1 in result
        assert 2 not in result

    def test_immutable_set_to_set(self) -> None:
        """Test conversion to mutable set."""
        s = ImmutableSet([1, 2, 3])
        mutable = s.to_set()

        assert isinstance(mutable, set)
        assert mutable == {1, 2, 3}

    def test_immutable_set_is_subset_of(self) -> None:
        """Test subset check."""
        s1 = ImmutableSet([1, 2])
        s2 = ImmutableSet([1, 2, 3])
        s3 = ImmutableSet([4, 5])

        assert s1.is_subset_of(s2) is True
        assert s2.is_subset_of(s1) is False
        assert s3.is_subset_of(s1) is False

    def test_immutable_set_is_superset_of(self) -> None:
        """Test superset check."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([1, 2])
        s3 = ImmutableSet([4, 5])

        assert s1.is_superset_of(s2) is True
        assert s2.is_superset_of(s1) is False
        assert s1.is_superset_of(s3) is False

    def test_immutable_set_str_and_repr(self) -> None:
        """Test set string representations."""
        s = ImmutableSet([1, 2])
        assert str(s).startswith("{")
        assert "ImmutableSet" in repr(s)

    def test_immutable_set_equality_with_other_type(self) -> None:
        """Test set inequality with other types."""
        s = ImmutableSet([1, 2])
        assert s != {1, 2}

    def test_immutable_set_disjoint_sets(self) -> None:
        """Test disjoint sets."""
        s1 = ImmutableSet([1, 2, 3])
        s2 = ImmutableSet([4, 5, 6])

        intersection = s1 & s2
        assert len(intersection) == 0

    def test_immutable_set_single_element(self) -> None:
        """Test single element set."""
        s = ImmutableSet([42])
        assert 42 in s
        assert len(s) == 1

    def test_immutable_dict_empty_get(self) -> None:
        """Test get on empty dict."""
        d = ImmutableDict()
        assert d.get("missing") is None

    def test_immutable_list_negative_indexing(self) -> None:
        """Test negative indexing."""
        lst = ImmutableList([1, 2, 3, 4, 5])
        assert lst[-1] == 5
        assert lst[-2] == 4

    def test_immutable_list_empty_map(self) -> None:
        """Test map on empty list."""
        lst = ImmutableList()
        result = lst.map(lambda x: x * 2)
        assert len(result) == 0

    def test_immutable_list_empty_filter(self) -> None:
        """Test filter on empty list."""
        lst = ImmutableList()
        result = lst.filter(lambda x: x > 0)
        assert len(result) == 0
