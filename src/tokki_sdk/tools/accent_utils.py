"""
Utilities for accent-insensitive pattern matching.

Handles Spanish, French, and other Romance language accents.
"""

import re
import unicodedata
from typing import Optional


# Character class mappings for common accented characters
ACCENT_MAP = {
    "a": "[aáàâäãåāăą]",
    "A": "[AÁÀÂÄÃÅĀĂĄ]",
    "e": "[eéèêëēėę]",
    "E": "[EÉÈÊËĒĖĘ]",
    "i": "[iíìîïīįı]",
    "I": "[IÍÌÎÏĪĮ]",
    "o": "[oóòôöõøōő]",
    "O": "[OÓÒÔÖÕØŌŐ]",
    "u": "[uúùûüūůű]",
    "U": "[UÚÙÛÜŪŮŰ]",
    "c": "[cçćč]",
    "C": "[CÇĆČ]",
    "n": "[nñń]",
    "N": "[NÑŃ]",
    "y": "[yýÿ]",
    "Y": "[YÝŸ]",
    "s": "[sšß]",
    "S": "[SŠ]",
    "z": "[zžź]",
    "Z": "[ZŽŹ]",
    "l": "[lł]",
    "L": "[LŁ]",
}


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode text to NFD (decomposed) form.

    This separates base characters from combining diacritical marks.
    Example: "café" → "cafe" + combining accent marks
    """
    return unicodedata.normalize("NFD", text)


def remove_accents(text: str) -> str:
    """
    Remove all accents from text, keeping only base characters.

    Example: "café" → "cafe", "niño" → "nino"
    """
    nfd = normalize_unicode(text)
    # Remove combining characters (accents)
    return "".join(c for c in nfd if not unicodedata.combining(c))


def expand_pattern_for_accents(pattern: str) -> str:
    """
    Expand a regex pattern to match accented variants.

    Converts simple characters to character classes that include accents.
    Example: "cafe" → "[cç][aáàâä][fƒ][eéèêë]"

    This preserves existing regex syntax (brackets, quantifiers, etc.)
    """
    result = []
    i = 0
    while i < len(pattern):
        char = pattern[i]

        # Don't expand characters inside existing character classes
        if char == "[":
            # Find the closing bracket
            end = i + 1
            while end < len(pattern) and pattern[end] != "]":
                if pattern[end] == "\\":
                    end += 2  # Skip escaped character
                else:
                    end += 1
            if end < len(pattern):
                result.append(pattern[i : end + 1])
                i = end + 1
                continue

        # Don't expand escaped characters or special regex chars
        if char == "\\":
            if i + 1 < len(pattern):
                result.append(pattern[i : i + 2])
                i += 2
            else:
                result.append(char)
                i += 1
            continue

        # Don't expand regex special characters
        if char in r".*+?{}()|^$":
            result.append(char)
            i += 1
            continue

        # Expand if we have an accent mapping
        if char in ACCENT_MAP:
            result.append(ACCENT_MAP[char])
        else:
            result.append(char)

        i += 1

    return "".join(result)


def make_pattern_accent_insensitive(
    pattern: str, method: str = "expand"
) -> tuple[str, Optional[str]]:
    """
    Convert a pattern to be accent-insensitive.

    Args:
        pattern: The original regex pattern
        method: Either "expand" (default) or "normalize"
            - "expand": Expands characters to include accented variants
            - "normalize": Returns normalized pattern and suggests normalizing content

    Returns:
        Tuple of (new_pattern, suggestion)
        - new_pattern: The modified pattern
        - suggestion: Optional hint about how to use it (for normalize method)
    """
    if method == "normalize":
        # For normalize method, suggest using NFD normalization on both pattern and content
        normalized = remove_accents(pattern)
        suggestion = "Note: Content should also be normalized for matching"
        return normalized, suggestion
    else:
        # Default: expand pattern to include accented variants
        expanded = expand_pattern_for_accents(pattern)
        return expanded, None
