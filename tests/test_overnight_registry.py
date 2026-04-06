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
        self.assertIn("ustr_press_releases", source_ids)
        self.assertIn("treasury_press_releases", source_ids)
        self.assertIn("bls_news_releases", source_ids)
        self.assertIn("bls_release_schedule", source_ids)
        self.assertIn("bea_news", source_ids)
        self.assertIn("eia_pressroom", source_ids)
        self.assertIn("ap_politics", source_ids)
        self.assertIn("ap_business", source_ids)
        self.assertIn("cnbc_world", source_ids)
        self.assertIn("reuters_topics", source_ids)

    def test_source_class_filter_returns_only_policy_sources(self) -> None:
        policy_sources = build_default_source_registry(source_class="policy")

        self.assertGreater(len(policy_sources), 0)
        self.assertTrue(all(source.source_class == "policy" for source in policy_sources))

    def test_required_source_metadata_is_seeded(self) -> None:
        sources = {source.source_id: source for source in build_default_source_registry()}

        whitehouse = sources["whitehouse_news"]
        self.assertEqual(whitehouse.entry_type, "section_page")
        self.assertEqual(whitehouse.priority, 100)
        self.assertEqual(whitehouse.poll_interval_seconds, 300)
        self.assertTrue(whitehouse.is_mission_critical)
        self.assertEqual(whitehouse.coverage_tier, "official_policy")
        self.assertEqual(whitehouse.region_focus, "US policy")
        self.assertIn("白宫", whitehouse.coverage_focus)

        fed = sources["fed_news"]
        self.assertEqual(fed.entry_type, "rss")
        self.assertEqual(fed.priority, 100)
        self.assertEqual(fed.poll_interval_seconds, 300)
        self.assertTrue(fed.is_mission_critical)
        self.assertEqual(fed.coverage_tier, "official_policy")

        reuters = sources["reuters_topics"]
        self.assertEqual(reuters.entry_type, "section_page")
        self.assertEqual(reuters.priority, 90)
        self.assertEqual(reuters.poll_interval_seconds, 600)
        self.assertTrue(reuters.is_mission_critical)
        self.assertEqual(reuters.coverage_tier, "editorial_media")

        bls_schedule = sources["bls_release_schedule"]
        self.assertEqual(bls_schedule.entry_type, "calendar_page")
        self.assertEqual(bls_schedule.coverage_tier, "official_data")
        self.assertEqual(bls_schedule.region_focus, "US macro")
        self.assertIn("发布时间表", bls_schedule.coverage_focus)

    def test_entry_urls_do_not_leak_mutation_across_registry_calls(self) -> None:
        first_registry = build_default_source_registry()
        whitehouse_first = next(source for source in first_registry if source.source_id == "whitehouse_news")

        self.assertIsInstance(whitehouse_first.entry_urls, tuple)
        with self.assertRaises(AttributeError):
            whitehouse_first.entry_urls.append("https://example.com/poison")

        second_registry = build_default_source_registry()
        whitehouse_second = next(source for source in second_registry if source.source_id == "whitehouse_news")
        self.assertEqual(whitehouse_second.entry_urls, ("https://www.whitehouse.gov/news/",))


if __name__ == "__main__":
    unittest.main()
