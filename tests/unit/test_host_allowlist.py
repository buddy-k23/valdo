"""Tests for src/utils/host_allowlist.py."""
from __future__ import annotations

import pytest

from src.utils.host_allowlist import is_host_allowed, parse_allowed_hosts


class TestParseAllowedHosts:
    def test_empty_string_means_no_restriction(self):
        assert parse_allowed_hosts("") == ()

    def test_none_means_no_restriction(self):
        assert parse_allowed_hosts(None) == ()

    def test_entries_are_trimmed_and_lowercased(self):
        assert parse_allowed_hosts(" API.Example.com , *.Corp.com,, ") == ("api.example.com", "*.corp.com")


class TestIsHostAllowed:
    def test_empty_allowlist_allows_any_host(self):
        assert is_host_allowed("anything.example", ())

    def test_exact_match_is_case_insensitive(self):
        assert is_host_allowed("API.example.com", ("api.example.com",))

    def test_unlisted_host_is_rejected(self):
        assert not is_host_allowed("169.254.169.254", ("api.example.com",))

    def test_wildcard_matches_subdomains(self):
        assert is_host_allowed("svc.corp.com", ("*.corp.com",))
        assert is_host_allowed("a.b.corp.com", ("*.corp.com",))

    @pytest.mark.parametrize("host", ["corp.com", "evilcorp.com", "corp.com.evil.io"])
    def test_wildcard_does_not_match_apex_or_lookalikes(self, host):
        assert not is_host_allowed(host, ("*.corp.com",))

    def test_missing_host_is_rejected_when_restricted(self):
        assert not is_host_allowed("", ("api.example.com",))
