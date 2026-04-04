# -*- coding: utf-8 -*-
"""Tests for overnight config defaults and baseline storage repository."""

import os
import tempfile
import unittest

from sqlalchemy import text

from src.config import Config
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


if __name__ == "__main__":
    unittest.main()
