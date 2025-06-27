#!/usr/bin/env python

import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import extract_usernames_pytesseract, extract_usernames_easyocr


@pytest.fixture
def test_image_path():
    """Path to test image file."""
    return Path(__file__).parent / "test.png"


@pytest.fixture
def expected_usernames():
    """Expected usernames from test image based on known good results."""
    return {
        "@4ad",
        "@AYEON", 
        "@AbroadinJapan",
        "@TheAdamConover",
        "@aragusea",
        "@aiDotEngineer",
        "@albertatech",
        "@4ad_official"
    }


def test_pytesseract_extraction(test_image_path, expected_usernames):
    """Test that Pytesseract extracts expected usernames."""
    if not test_image_path.exists():
        pytest.skip("Test image not found")
    
    usernames = extract_usernames_pytesseract(str(test_image_path))
    username_set = set(usernames)
    
    # Should extract legitimate usernames
    assert len(usernames) > 0, "Should extract at least some usernames"
    
    # Should not contain email patterns
    for username in usernames:
        assert not any(domain in username.lower() for domain in [
            "gmail", "yahoo", "hotmail", "outlook", "gmall"
        ]), f"Should not contain email patterns: {username}"
    
    # Check that we get most of the expected usernames
    common_usernames = username_set.intersection(expected_usernames)
    assert len(common_usernames) >= 5, f"Should extract at least 5 expected usernames, got {common_usernames}"


def test_easyocr_extraction(test_image_path, expected_usernames):
    """Test that EasyOCR extracts expected usernames."""
    if not test_image_path.exists():
        pytest.skip("Test image not found")
    
    usernames = extract_usernames_easyocr(str(test_image_path))
    username_set = set(usernames)
    
    # Should extract legitimate usernames
    assert len(usernames) > 0, "Should extract at least some usernames"
    
    # Should not contain email patterns
    for username in usernames:
        assert not any(domain in username.lower() for domain in [
            "gmail", "yahoo", "hotmail", "outlook", "gmall"
        ]), f"Should not contain email patterns: {username}"
    
    # Check that we get most of the expected usernames
    common_usernames = username_set.intersection(expected_usernames)
    assert len(common_usernames) >= 5, f"Should extract at least 5 expected usernames, got {common_usernames}"


def test_no_email_addresses_extracted(test_image_path):
    """Test that no email addresses are extracted by either OCR engine."""
    if not test_image_path.exists():
        pytest.skip("Test image not found")
    
    pytesseract_usernames = extract_usernames_pytesseract(str(test_image_path))
    easyocr_usernames = extract_usernames_easyocr(str(test_image_path))
    
    all_usernames = pytesseract_usernames + easyocr_usernames
    
    # Check for common email patterns that should be excluded
    forbidden_patterns = ["@gmail", "@yahoo", "@hotmail", "@outlook", "@gmall", ".com", ".org", ".net"]
    
    for username in all_usernames:
        for pattern in forbidden_patterns:
            assert pattern not in username.lower(), f"Username '{username}' contains forbidden pattern '{pattern}'"


def test_combined_results_unique(test_image_path):
    """Test that combined results eliminate duplicates properly."""
    if not test_image_path.exists():
        pytest.skip("Test image not found")
    
    pytesseract_usernames = extract_usernames_pytesseract(str(test_image_path))
    easyocr_usernames = extract_usernames_easyocr(str(test_image_path))
    
    # Combine and deduplicate like main.py does
    combined = list(dict.fromkeys(pytesseract_usernames + easyocr_usernames))
    
    # Should have no duplicates
    assert len(combined) == len(set(combined)), "Combined results should have no duplicates"
    
    # Should contain usernames from both engines
    assert len(combined) >= max(len(pytesseract_usernames), len(easyocr_usernames)), "Combined should be at least as long as longest individual result"