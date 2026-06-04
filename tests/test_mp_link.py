"""Tests for mp_link URL parser."""
import pytest

from autoref.core.mp_link import MpLink, parse_mp_link


class TestParseMpLink:
    def test_basic_mp_link(self):
        result = parse_mp_link("https://osu.ppy.sh/mp/123456")
        assert result == MpLink(match_id=123456, game_id=None)

    def test_mp_link_with_game_id(self):
        result = parse_mp_link("https://osu.ppy.sh/mp/123456/789")
        assert result == MpLink(match_id=123456, game_id=789)

    def test_community_matches_link(self):
        result = parse_mp_link("https://osu.ppy.sh/community/matches/123456")
        assert result == MpLink(match_id=123456, game_id=None)

    def test_community_matches_with_game_id(self):
        result = parse_mp_link("https://osu.ppy.sh/community/matches/123456/789")
        assert result == MpLink(match_id=123456, game_id=789)

    def test_http_link(self):
        result = parse_mp_link("http://osu.ppy.sh/mp/123456")
        assert result == MpLink(match_id=123456, game_id=None)

    def test_link_with_trailing_slash(self):
        result = parse_mp_link("https://osu.ppy.sh/mp/123456/")
        assert result == MpLink(match_id=123456, game_id=None)

    def test_link_in_text(self):
        result = parse_mp_link("Check out this match: https://osu.ppy.sh/mp/123456 cool!")
        assert result == MpLink(match_id=123456, game_id=None)

    def test_invalid_url(self):
        assert parse_mp_link("https://google.com") is None

    def test_invalid_mp_url(self):
        assert parse_mp_link("https://osu.ppy.sh/beatmaps/123456") is None

    def test_empty_string(self):
        assert parse_mp_link("") is None

    def test_just_number(self):
        assert parse_mp_link("123456") is None

    def test_large_match_id(self):
        result = parse_mp_link("https://osu.ppy.sh/mp/999999999")
        assert result == MpLink(match_id=999999999, game_id=None)
