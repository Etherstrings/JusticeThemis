# -*- coding: utf-8 -*-
"""Tests for overnight source registry defaults."""

import unittest

from src.overnight.source_registry import build_default_source_registry


class TestOvernightSourceRegistry(unittest.TestCase):
    def test_default_registry_contains_required_source_ids(self) -> None:
        sources = build_default_source_registry()
        source_ids = {source.source_id for source in sources}

        self.assertIn("whitehouse_news", source_ids)
        self.assertIn("fed_news", source_ids)
        self.assertIn("reuters_topics", source_ids)

    def test_source_class_filter_returns_only_policy_sources(self) -> None:
        policy_sources = build_default_source_registry(source_class="policy")

        self.assertGreater(len(policy_sources), 0)
        self.assertTrue(all(source.source_class == "policy" for source in policy_sources))


if __name__ == "__main__":
    unittest.main()
