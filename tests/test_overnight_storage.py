# -*- coding: utf-8 -*-
"""Tests for overnight config defaults and baseline storage repository."""

import os
import tempfile
import unittest

from sqlalchemy import text

from src.config import Config
from src.core.config_registry import get_field_definition
from src.overnight.brief_builder import RankedEvent, build_morning_brief
from src.storage import DatabaseManager


class OvernightStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_overnight_storage.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self._temp_dir.cleanup()

    def test_overnight_config_defaults(self) -> None:
        config = Config.get_instance()

        self.assertFalse(config.overnight_brief_enabled)
        self.assertEqual(config.overnight_digest_cutoff, "07:30")
        self.assertEqual(config.overnight_priority_alert_threshold, "P0")
        self.assertEqual(config.overnight_source_whitelist, "")

    def test_overnight_config_env_overrides(self) -> None:
        os.environ["OVERNIGHT_BRIEF_ENABLED"] = "true"
        os.environ["OVERNIGHT_DIGEST_CUTOFF"] = "06:45"
        os.environ["OVERNIGHT_PRIORITY_ALERT_THRESHOLD"] = "P1"
        os.environ["OVERNIGHT_SOURCE_WHITELIST"] = "reuters,bloomberg"
        try:
            Config.reset_instance()
            config = Config.get_instance()
            self.assertTrue(config.overnight_brief_enabled)
            self.assertEqual(config.overnight_digest_cutoff, "06:45")
            self.assertEqual(config.overnight_priority_alert_threshold, "P1")
            self.assertEqual(config.overnight_source_whitelist, "reuters,bloomberg")
        finally:
            os.environ.pop("OVERNIGHT_BRIEF_ENABLED", None)
            os.environ.pop("OVERNIGHT_DIGEST_CUTOFF", None)
            os.environ.pop("OVERNIGHT_PRIORITY_ALERT_THRESHOLD", None)
            os.environ.pop("OVERNIGHT_SOURCE_WHITELIST", None)
            Config.reset_instance()

    def test_overnight_digest_cutoff_registry_contract(self) -> None:
        schedule_field = get_field_definition("SCHEDULE_TIME")
        cutoff_field = get_field_definition("OVERNIGHT_DIGEST_CUTOFF")

        self.assertEqual(cutoff_field["data_type"], "time")
        self.assertEqual(cutoff_field["ui_control"], "time")
        self.assertEqual(
            cutoff_field["validation"].get("pattern"),
            schedule_field["validation"].get("pattern"),
        )

    def test_overnight_repository_round_trip(self) -> None:
        from src.repositories.overnight_repo import OvernightRepository

        repo = OvernightRepository(self.db)
        raw_id = repo.create_raw_record(
            source_id="unit-test-source",
            fetch_mode="manual",
            payload_hash="hash-abc-001",
        )
        item_id = repo.create_source_item(
            raw_id=raw_id,
            canonical_url="https://example.com/news/1",
            title="Overnight headline",
            document_type="news",
        )
        cluster_id_1 = repo.upsert_event_cluster(
            core_fact="Fed signaled policy continuity overnight.",
            event_type="macro",
            event_subtype="central_bank",
        )
        cluster_id_2 = repo.upsert_event_cluster(
            core_fact="Fed signaled policy continuity overnight.",
            event_type="macro",
            event_subtype="central_bank",
        )

        self.assertGreater(raw_id, 0)
        self.assertGreater(item_id, 0)
        self.assertGreater(cluster_id_1, 0)
        self.assertEqual(cluster_id_1, cluster_id_2)

        with self.db.get_session() as session:
            raw_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_raw_records")
            ).scalar_one()
            item_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_source_items")
            ).scalar_one()
            cluster_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_event_clusters")
            ).scalar_one()

        self.assertEqual(raw_count, 1)
        self.assertEqual(item_count, 1)
        self.assertEqual(cluster_count, 1)

    def test_overnight_repository_allows_repeated_hash_and_url(self) -> None:
        from src.repositories.overnight_repo import OvernightRepository

        repo = OvernightRepository(self.db)

        raw_id_1 = repo.create_raw_record(
            source_id="unit-test-source",
            fetch_mode="manual",
            payload_hash="same-payload-hash",
        )
        raw_id_2 = repo.create_raw_record(
            source_id="unit-test-source",
            fetch_mode="manual",
            payload_hash="same-payload-hash",
        )

        item_id_1 = repo.create_source_item(
            raw_id=raw_id_1,
            canonical_url="https://example.com/dup-url",
            title="Headline one",
            document_type="news",
        )
        item_id_2 = repo.create_source_item(
            raw_id=raw_id_2,
            canonical_url="https://example.com/dup-url",
            title="Headline two",
            document_type="news",
        )

        self.assertGreater(raw_id_1, 0)
        self.assertGreater(raw_id_2, 0)
        self.assertGreater(item_id_1, 0)
        self.assertGreater(item_id_2, 0)
        self.assertNotEqual(raw_id_1, raw_id_2)
        self.assertNotEqual(item_id_1, item_id_2)

        with self.db.get_session() as session:
            raw_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_raw_records WHERE payload_hash = 'same-payload-hash'")
            ).scalar_one()
            item_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_source_items WHERE canonical_url = 'https://example.com/dup-url'")
            ).scalar_one()

        self.assertEqual(raw_count, 2)
        self.assertEqual(item_count, 2)

    def test_overnight_repository_persists_morning_briefs(self) -> None:
        from src.repositories.overnight_repo import OvernightRepository

        repo = OvernightRepository(self.db)
        brief = build_morning_brief(
            events=[
                RankedEvent(
                    event_id="event_123",
                    core_fact="Fed left policy guidance unchanged.",
                    priority_level="P1",
                    summary="The latest overnight policy event stayed on hold.",
                    why_it_matters="Rates-sensitive assets remain in focus.",
                    confidence=0.81,
                    source_links=["https://www.federalreserve.gov/example-release"],
                )
            ],
            direction_board=[],
            price_pressure_board=[],
            digest_date="2026-04-05",
            cutoff_time="07:30",
            generated_at="2026-04-05T07:31:00",
        )

        repo.save_morning_brief(brief)

        latest = repo.get_latest_morning_brief()
        history = repo.list_morning_briefs(page=1, limit=10)

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.brief_id, brief.brief_id)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["brief_id"], brief.brief_id)

        with self.db.get_session() as session:
            brief_count = session.execute(
                text("SELECT COUNT(1) FROM overnight_brief_artifacts")
            ).scalar_one()

        self.assertEqual(brief_count, 1)


if __name__ == "__main__":
    unittest.main()
