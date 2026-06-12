"""
Tests for qa.py

Covers:
- _build_where_clause() filter construction logic
  (the pure function we can test without ChromaDB or Groq)
"""

import sys
import types
import pytest

# Stub out heavy dependencies so qa.py can be imported without
# Streamlit, ChromaDB, or a live Groq key in the test environment.
for mod in ["streamlit", "chromadb", "chromadb.utils", "chromadb.utils.embedding_functions"]:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

# Stub indexer.get_collection so qa module-level import doesn't fail
indexer_stub = types.ModuleType("indexer")
indexer_stub.get_collection = lambda: None
sys.modules["indexer"] = indexer_stub

from qa import _build_where_clause


class TestBuildWhereClause:

    def test_no_filters_returns_none(self):
        assert _build_where_clause() is None
        assert _build_where_clause(author=None, start_date=None, end_date=None) is None

    def test_empty_author_string_returns_none(self):
        assert _build_where_clause(author="") is None
        assert _build_where_clause(author="   ") is None

    def test_author_only(self):
        result = _build_where_clause(author="Armin Ronacher")
        assert result == {"author": {"$eq": "Armin Ronacher"}}

    def test_author_is_stripped(self):
        result = _build_where_clause(author="  kartik  ")
        assert result == {"author": {"$eq": "kartik"}}

    def test_start_date_only(self):
        result = _build_where_clause(start_date="2023-01-01")
        assert "timestamp" in result
        assert "$gte" in result["timestamp"]
        assert isinstance(result["timestamp"]["$gte"], int)

    def test_end_date_only(self):
        result = _build_where_clause(end_date="2023-12-31")
        assert "timestamp" in result
        assert "$lte" in result["timestamp"]
        assert isinstance(result["timestamp"]["$lte"], int)

    def test_end_date_appends_end_of_day(self):
        from datetime import datetime
        result = _build_where_clause(end_date="2024-06-15")
        expected_ts = int(datetime.strptime("2024-06-15 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp())
        assert result["timestamp"]["$lte"] == expected_ts

    def test_date_range_only_uses_and(self):
        result = _build_where_clause(start_date="2023-01-01", end_date="2023-12-31")
        assert "$and" in result
        conditions = result["$and"]
        assert len(conditions) == 2
        keys = [list(c.keys())[0] for c in conditions]
        assert "timestamp" in keys

    def test_all_three_filters_uses_and_with_three_conditions(self):
        result = _build_where_clause(
            author="kartik",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        assert "$and" in result
        assert len(result["$and"]) == 3

    def test_all_three_contains_author_condition(self):
        result = _build_where_clause(
            author="kartik",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        assert {"author": {"$eq": "kartik"}} in result["$and"]

    def test_single_condition_not_wrapped_in_and(self):
        """Single filter should be a plain dict, not wrapped in $and."""
        result = _build_where_clause(author="kartik")
        assert "$and" not in result

    def test_two_conditions_wrapped_in_and(self):
        result = _build_where_clause(author="kartik", start_date="2023-01-01")
        assert "$and" in result
        assert len(result["$and"]) == 2