"""
Tests for accent-insensitive pattern matching utilities.
"""

import pytest
from tokki_sdk.tools.accent_utils import (
    normalize_unicode,
    remove_accents,
    expand_pattern_for_accents,
    make_pattern_accent_insensitive,
)


class TestAccentNormalization:
    def test_remove_accents_spanish(self):
        assert remove_accents("niño") == "nino"
        assert remove_accents("café") == "cafe"
        assert remove_accents("señor") == "senor"
        assert remove_accents("José") == "Jose"

    def test_remove_accents_french(self):
        assert remove_accents("été") == "ete"
        assert remove_accents("français") == "francais"
        assert remove_accents("château") == "chateau"
        assert remove_accents("crème") == "creme"

    def test_remove_accents_mixed(self):
        assert remove_accents("São Paulo") == "Sao Paulo"
        assert remove_accents("Zürich") == "Zurich"
        assert remove_accents("naïve") == "naive"

    def test_remove_accents_no_change(self):
        assert remove_accents("hello") == "hello"
        assert remove_accents("test123") == "test123"
        assert remove_accents("") == ""


class TestPatternExpansion:
    def test_expand_simple_vowels(self):
        result = expand_pattern_for_accents("cafe")
        # Check that characters are expanded to character classes
        assert result.startswith("[c")  # c is expanded
        assert "ç" in result  # contains accented variant
        assert "á" in result or "\xe1" in result  # contains accented a
        assert "é" in result or "\xe9" in result  # contains accented e

    def test_expand_preserves_regex_syntax(self):
        # Should preserve quantifiers
        result = expand_pattern_for_accents("ca+fe*")
        assert "+" in result
        assert "*" in result

        # Should preserve anchors
        result = expand_pattern_for_accents("^cafe$")
        assert result.startswith("^")
        assert result.endswith("$")

    def test_expand_preserves_character_classes(self):
        # Should not expand inside existing character classes
        result = expand_pattern_for_accents("[abc]def")
        assert "[abc]" in result
        # But should expand d, e, f outside the class
        assert "[eéèêë" in result

    def test_expand_preserves_escaped_chars(self):
        result = expand_pattern_for_accents(r"cafe\.")
        assert r"\." in result

    def test_expand_spanish_characters(self):
        result = expand_pattern_for_accents("niño")
        # Check that ñ appears in the pattern (as literal or unicode escape)
        assert "ñ" in result or "\xf1" in result

    def test_expand_french_characters(self):
        result = expand_pattern_for_accents("francais")
        # Check that ç appears in the pattern
        assert "ç" in result or "\xe7" in result


class TestMakePatternAccentInsensitive:
    def test_expand_method(self):
        pattern, suggestion = make_pattern_accent_insensitive("cafe", method="expand")
        # Verify character classes are created
        assert "[" in pattern and "]" in pattern
        # Verify accented characters are included
        assert "ç" in pattern or "\xe7" in pattern
        assert "á" in pattern or "\xe1" in pattern
        assert suggestion is None

    def test_normalize_method(self):
        pattern, suggestion = make_pattern_accent_insensitive("café", method="normalize")
        assert pattern == "cafe"
        assert suggestion is not None
        assert "normalized" in suggestion.lower()

    def test_default_method_is_expand(self):
        pattern, _ = make_pattern_accent_insensitive("test")
        # Default should expand
        assert "[" in pattern  # Character classes from expansion


class TestRealWorldExamples:
    def test_spanish_sentences(self):
        """Test real Spanish text patterns"""
        pattern = expand_pattern_for_accents("donde esta")
        assert "[oóòôö" in pattern
        assert "[aáàâä" in pattern
        assert "[eéèêë" in pattern

    def test_french_words(self):
        """Test real French word patterns"""
        pattern = expand_pattern_for_accents("ecole")
        # Should expand e to include é, è, ê, ë
        assert "[eéèêë" in pattern

    def test_mixed_language(self):
        """Test patterns that work across languages"""
        # Search for "Jose" should match "José" in Spanish
        pattern = expand_pattern_for_accents("Jose")
        assert "[eéèêë" in pattern
        # Search for "role" should match "rôle" in French
        pattern = expand_pattern_for_accents("role")
        assert "[oóòôö" in pattern
