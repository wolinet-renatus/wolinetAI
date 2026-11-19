"""
Unit tests for Wolinet Browser Adapter security & output controls.
Validates:
1. Blocking of loopback (127.0.0.1, localhost)
2. Blocking of cloud metadata (169.254.169.254)
3. Blocking of RFC 1918 private IPv4 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
4. Blocking of IPv6 loopback (::1), unique-local (fc00::/7), and link-local (fe80::/10)
5. Allowing legitimate public domains (news.ycombinator.com, example.com)
6. Enforcing 25,000 character output truncation limit and marker
"""

import sys
import os

# Add gateway to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gateway")))

from wolinet_browser_adapter import (
    is_forbidden_navigation_target,
    enforce_output_limit,
    MAX_OUTPUT_CHARS,
)


def test_ssrf_blocking():
    # 1. Loopback addresses
    blocked, reason = is_forbidden_navigation_target("http://127.0.0.1:8080")
    assert blocked, f"Expected 127.0.0.1 to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://localhost:4000")
    assert blocked, f"Expected localhost to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://127.0.0.2")
    assert blocked, f"Expected 127.0.0.2 to be blocked, got allowed ({reason})"

    # 2. Cloud metadata addresses
    blocked, reason = is_forbidden_navigation_target("http://169.254.169.254/latest/meta-data/")
    assert blocked, f"Expected 169.254.169.254 to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://metadata.google.internal")
    assert blocked, f"Expected metadata.google.internal to be blocked, got allowed ({reason})"

    # 3. RFC 1918 Private networks
    blocked, reason = is_forbidden_navigation_target("http://10.0.0.1")
    assert blocked, f"Expected 10.0.0.1 to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://172.16.0.1")
    assert blocked, f"Expected 172.16.0.1 to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://172.31.255.255")
    assert blocked, f"Expected 172.31.255.255 to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://192.168.1.1")
    assert blocked, f"Expected 192.168.1.1 to be blocked, got allowed ({reason})"

    # 4. IPv6 Private and Loopback
    blocked, reason = is_forbidden_navigation_target("http://[::1]")
    assert blocked, f"Expected [::1] to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://[fc00::1]")
    assert blocked, f"Expected [fc00::1] to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("http://[fe80::1]")
    assert blocked, f"Expected [fe80::1] to be blocked, got allowed ({reason})"

    # 5. Invalid Schemes
    blocked, reason = is_forbidden_navigation_target("file:///etc/passwd")
    assert blocked, f"Expected file:// to be blocked, got allowed ({reason})"

    blocked, reason = is_forbidden_navigation_target("gopher://example.com")
    assert blocked, f"Expected gopher:// to be blocked, got allowed ({reason})"

    # 6. Public targets should be permitted
    blocked, reason = is_forbidden_navigation_target("https://news.ycombinator.com")
    assert not blocked, f"Expected https://news.ycombinator.com to be permitted, got blocked: {reason}"

    blocked, reason = is_forbidden_navigation_target("https://example.com")
    assert not blocked, f"Expected https://example.com to be permitted, got blocked: {reason}"

    print("✓ test_ssrf_blocking PASSED")


def test_output_truncation():
    # Test short content (< 25,000 chars)
    short_text = "This is a brief page description."
    result = enforce_output_limit(short_text)
    assert result == short_text
    assert "truncated" not in result

    # Test exact limit (25,000 chars)
    exact_text = "x" * MAX_OUTPUT_CHARS
    result = enforce_output_limit(exact_text)
    assert result == exact_text
    assert "truncated" not in result

    # Test overflowing content (> MAX_OUTPUT_CHARS chars)
    overflow_text = "y" * (MAX_OUTPUT_CHARS + 10000)
    result = enforce_output_limit(overflow_text)
    assert len(result) > MAX_OUTPUT_CHARS
    assert f"[Content truncated: exceeded {MAX_OUTPUT_CHARS} character limit" in result
    assert "10000 additional characters omitted" in result
    assert result.startswith("y" * MAX_OUTPUT_CHARS)

    print("✓ test_output_truncation PASSED")


if __name__ == "__main__":
    test_ssrf_blocking()
    test_output_truncation()
    print("All security and output tests passed successfully!")
