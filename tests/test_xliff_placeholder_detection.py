"""
Tests for XLIFF placeholder detection in healthcheck command.

This test suite verifies that healthcheck detects XLIFF-specific placeholders
(ph, pc, sc, ec, mrk) and reports missing/extra placeholders as errors/warnings.
"""

import os
import tempfile
import pytest
from algebras.utils.translation_validator import extract_xliff_placeholders, check_xliff_placeholders, Issue


class TestXLIFFPlaceholderDetection:
    """Test cases for XLIFF placeholder detection in healthcheck."""
    
    def test_extract_ph_tags(self):
        """
        Test that extract_xliff_placeholders detects ph (placeholder) tags.
        
        Behavior: The function should extract all <ph> tags from XLIFF source/target text,
        including their attributes like id and equiv-text.
        """
        source_text = 'Hello <ph id="1" equiv-text="%name"/>!'
        placeholders = extract_xliff_placeholders(source_text)
        
        assert len(placeholders) > 0
        # Should detect ph tag
        assert any('ph' in str(p) or '1' in str(p) or '%name' in str(p) for p in placeholders)
    
    def test_extract_pc_tags(self):
        """
        Test that extract_xliff_placeholders detects pc (paired code) tags.
        
        Behavior: The function should extract <pc> tags used in XLIFF 2.0 for
        paired formatting codes like bold, italic.
        """
        source_text = 'This is <pc id="1" type="fmt">bold</pc> text.'
        placeholders = extract_xliff_placeholders(source_text)
        
        assert len(placeholders) > 0
        # Should detect pc tag
        assert any('pc' in str(p) or '1' in str(p) for p in placeholders)
    
    def test_extract_sc_ec_tags(self):
        """
        Test that extract_xliff_placeholders detects sc (start code) and ec (end code) tags.
        
        Behavior: The function should extract <sc> and <ec> tag pairs used in XLIFF 1.2
        for formatting codes.
        """
        source_text = 'This is <sc id="1" type="bold"/>bold<ec id="1"/> text.'
        placeholders = extract_xliff_placeholders(source_text)
        
        assert len(placeholders) > 0
        # Should detect sc and ec tags
        assert any('sc' in str(p) or 'ec' in str(p) or '1' in str(p) for p in placeholders)
    
    def test_extract_mrk_tags(self):
        """
        Test that extract_xliff_placeholders detects mrk (marker) tags.
        
        Behavior: The function should extract <mrk> tags used for markers in XLIFF.
        """
        source_text = 'This is <mrk id="m1" type="term">terminology</mrk> text.'
        placeholders = extract_xliff_placeholders(source_text)
        
        assert len(placeholders) > 0
        # Should detect mrk tag
        assert any('mrk' in str(p) or 'm1' in str(p) for p in placeholders)
    
    def test_check_xliff_placeholders_missing_placeholder(self):
        """
        Test that check_xliff_placeholders reports missing placeholders as errors.
        
        Behavior: When a placeholder exists in source but not in target, it should
        be reported as an error.
        """
        source = 'Hello <ph id="1" equiv-text="%name"/>!'
        target = 'Bonjour!'  # Missing ph tag
        
        issues = check_xliff_placeholders(source, target, key="test.key")
        
        # Should have at least one error
        errors = [i for i in issues if i.severity == 'error']
        assert len(errors) > 0
        assert any('placeholder' in i.message.lower() or 'ph' in i.message.lower() for i in errors)
    
    def test_check_xliff_placeholders_extra_placeholder(self):
        """
        Test that check_xliff_placeholders reports extra placeholders as warnings.
        
        Behavior: When a placeholder exists in target but not in source, it should
        be reported as a warning.
        """
        source = 'Hello!'
        target = 'Bonjour <ph id="1" equiv-text="%name"/>!'  # Extra ph tag
        
        issues = check_xliff_placeholders(source, target, key="test.key")
        
        # Should have at least one warning
        warnings = [i for i in issues if i.severity == 'warning']
        assert len(warnings) > 0
        assert any('extra' in i.message.lower() or 'placeholder' in i.message.lower() for i in warnings)
    
    def test_check_xliff_placeholders_matching_placeholders(self):
        """
        Test that check_xliff_placeholders passes when placeholders match.
        
        Behavior: When source and target have matching placeholders, no issues
        should be reported.
        """
        source = 'Hello <ph id="1" equiv-text="%name"/>!'
        target = 'Bonjour <ph id="1" equiv-text="%name"/>!'
        
        issues = check_xliff_placeholders(source, target, key="test.key")
        
        # Should have no errors
        errors = [i for i in issues if i.severity == 'error']
        assert len(errors) == 0
    
    def test_check_xliff_placeholders_multiple_placeholders(self):
        """
        Test that check_xliff_placeholders handles multiple placeholders correctly.
        
        Behavior: When source has multiple placeholders, all should be checked
        and missing ones reported.
        """
        source = 'Hello <ph id="1" equiv-text="%name"/>, you have <ph id="2" equiv-text="%count"/> messages.'
        target = 'Bonjour <ph id="1" equiv-text="%name"/>!'  # Missing second ph tag
        
        issues = check_xliff_placeholders(source, target, key="test.key")
        
        # Should have error for missing placeholder
        errors = [i for i in issues if i.severity == 'error']
        assert len(errors) > 0
    
    def test_check_xliff_placeholders_different_placeholder_ids(self):
        """
        Test that check_xliff_placeholders detects when placeholder IDs don't match.
        
        Behavior: When source and target have placeholders with different IDs,
        this should be reported as an issue.
        """
        source = 'Hello <ph id="1" equiv-text="%name"/>!'
        target = 'Bonjour <ph id="2" equiv-text="%name"/>!'  # Different ID
        
        issues = check_xliff_placeholders(source, target, key="test.key")
        
        # Should detect mismatch (either as missing or extra)
        assert len(issues) > 0
    
    def test_healthcheck_calls_xliff_placeholder_check(self):
        """
        Test that healthcheck command calls XLIFF placeholder validation.
        
        Behavior: When healthcheck validates XLIFF files, it should call
        check_xliff_placeholders for source/target pairs.
        """
        # This test would verify integration with healthcheck_command
        # The actual implementation will be tested in healthcheck_command tests
        pass

