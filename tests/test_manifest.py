"""Tests for manifest."""


from repo_conformance.manifest import parse_manifest


def test_parse_manifest() -> None:
   """Test parsing the current manifest in the repo."""

   manifest = parse_manifest()
   assert len(manifest.repos) > 0
