"""
Privacy Tools API - Approved Tool for Log Analysis MCP Server

This module provides PII scrubbing and data anonymization capabilities.
It enables the AI agent to process sensitive data LOCALLY in the sandbox,
scrub all PII, and only send anonymized text to the LLM.

This solves the "data privacy" problem: sensitive customer data never
leaves the secure sandbox.

Security: This file is managed via GitOps. Changes require security approval
via pull request.
"""

import re
from typing import List, Dict, Optional


def scrub_emails(text: str, replacement: str = "[EMAIL_REDACTED]") -> str:
    """
    Removes email addresses from text.
    
    Args:
        text: Input text that may contain email addresses
        replacement: String to replace emails with (default: "[EMAIL_REDACTED]")
    
    Returns:
        Text with emails replaced
    
    Example:
        >>> scrub_emails("Contact john@example.com for help")
        'Contact [EMAIL_REDACTED] for help'
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.sub(email_pattern, replacement, text)


def scrub_phone_numbers(text: str, replacement: str = "[PHONE_REDACTED]") -> str:
    """
    Removes phone numbers from text.
    
    Supports various formats:
    - (123) 456-7890
    - 123-456-7890
    - 123.456.7890
    - 1234567890
    
    Args:
        text: Input text that may contain phone numbers
        replacement: String to replace phone numbers with
    
    Returns:
        Text with phone numbers replaced
    """
    # Various phone number patterns
    patterns = [
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (123) 456-7890
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',     # 123-456-7890
        r'\d{10}',                           # 1234567890
    ]
    
    result = text
    for pattern in patterns:
        result = re.sub(pattern, replacement, result)
    
    return result


def scrub_ssn(text: str, replacement: str = "[SSN_REDACTED]") -> str:
    """
    Removes Social Security Numbers from text.
    
    Formats supported:
    - 123-45-6789
    - 123 45 6789
    
    Args:
        text: Input text that may contain SSNs
        replacement: String to replace SSNs with
    
    Returns:
        Text with SSNs replaced
    """
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    return re.sub(ssn_pattern, replacement, text)


def scrub_credit_cards(text: str, replacement: str = "[CC_REDACTED]") -> str:
    """
    Removes credit card numbers from text.
    
    Args:
        text: Input text that may contain credit card numbers
        replacement: String to replace credit cards with
    
    Returns:
        Text with credit card numbers replaced
    """
    # Match 13-19 digit credit card numbers (with optional spaces/dashes)
    cc_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}(?:\d{3})?\b'
    return re.sub(cc_pattern, replacement, text)


def scrub_ip_addresses(text: str, replacement: str = "[IP_REDACTED]") -> str:
    """
    Removes IP addresses from text.
    
    Args:
        text: Input text that may contain IP addresses
        replacement: String to replace IPs with
    
    Returns:
        Text with IP addresses replaced
    """
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    return re.sub(ip_pattern, replacement, text)


def scrub_all_pii(text: str) -> str:
    """
    Applies all PII scrubbing functions to the text.
    
    This is the recommended function to use for general-purpose
    data anonymization before sending to the LLM.
    
    Args:
        text: Input text that may contain PII
    
    Returns:
        Fully anonymized text
    
    Example:
        >>> data = "User john@example.com at 192.168.1.1 called 123-456-7890"
        >>> clean = scrub_all_pii(data)
        >>> print(clean)
        'User [EMAIL_REDACTED] at [IP_REDACTED] called [PHONE_REDACTED]'
    """
    result = text
    result = scrub_emails(result)
    result = scrub_phone_numbers(result)
    result = scrub_ssn(result)
    result = scrub_credit_cards(result)
    result = scrub_ip_addresses(result)
    return result


def anonymize_names(
    text: str,
    name_map: Optional[Dict[str, str]] = None
) -> tuple[str, Dict[str, str]]:
    """
    Replaces real names with pseudonyms (e.g., "User A", "User B").
    
    This allows the LLM to track entities while protecting privacy.
    
    Args:
        text: Input text containing names
        name_map: Optional mapping of real names to pseudonyms.
                  If not provided, a new map is created.
    
    Returns:
        Tuple of (anonymized_text, name_map)
    
    Example:
        >>> text = "Alice sent a message to Bob and Charlie"
        >>> anon, mapping = anonymize_names(text)
        >>> print(anon)
        'User-A sent a message to User-B and User-C'
        >>> print(mapping)
        {'Alice': 'User-A', 'Bob': 'User-B', 'Charlie': 'User-C'}
    """
    if name_map is None:
        name_map = {}
    
    # Simple name detection (capitalized words)
    # In production, use a more sophisticated NER model
    name_pattern = r'\b[A-Z][a-z]+\b'
    
    result = text
    counter = len(name_map)
    
    for match in re.finditer(name_pattern, text):
        name = match.group()
        
        # Skip common words that aren't names
        if name.lower() in ['the', 'a', 'an', 'this', 'that', 'user', 'admin']:
            continue
        
        if name not in name_map:
            counter += 1
            name_map[name] = f"User-{chr(64 + counter)}"  # User-A, User-B, etc.
        
        result = result.replace(name, name_map[name])
    
    return result, name_map


def create_privacy_report(original: str, scrubbed: str) -> dict:
    """
    Creates a report showing what PII was removed.
    
    Args:
        original: Original text
        scrubbed: Scrubbed text
    
    Returns:
        Dictionary with statistics about removed PII
    """
    return {
        "original_length": len(original),
        "scrubbed_length": len(scrubbed),
        "emails_removed": original.count("@") - scrubbed.count("@"),
        "redaction_count": scrubbed.count("_REDACTED]"),
        "safety_check": "[EMAIL_REDACTED]" in scrubbed or 
                       "[PHONE_REDACTED]" in scrubbed or
                       scrubbed == original
    }


# Example usage (for testing)
if __name__ == "__main__":
    print("=== Privacy Tools API Demo ===")
    print()
    
    # Test data with PII
    test_data = """
    Customer Record:
    Name: John Smith
    Email: john.smith@example.com
    Phone: (555) 123-4567
    SSN: 123-45-6789
    Credit Card: 4532-1234-5678-9010
    IP Address: 192.168.1.100
    
    Notes: Customer called about billing issue. Contact alice@support.com
    """
    
    print("ORIGINAL DATA:")
    print(test_data)
    print()
    
    print("SCRUBBED DATA (Safe to send to LLM):")
    scrubbed = scrub_all_pii(test_data)
    print(scrubbed)
    print()
    
    print("PRIVACY REPORT:")
    report = create_privacy_report(test_data, scrubbed)
    for key, value in report.items():
        print(f"  {key}: {value}")
    print()
    
    print("NAME ANONYMIZATION:")
    anon, mapping = anonymize_names("Alice sent a message to Bob and Charlie")
    print(f"  Original: Alice sent a message to Bob and Charlie")
    print(f"  Anonymized: {anon}")
    print(f"  Mapping: {mapping}")

