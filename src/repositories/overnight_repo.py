# -*- coding: utf-8 -*-
"""Repository for overnight baseline ledger tables."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select

from src.storage import (
    DatabaseManager,
    OvernightEventCluster,
    OvernightRawRecord,
    OvernightSourceItem,
)


class OvernightRepository:
    """Thin DB access wrapper for overnight baseline tables."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def create_raw_record(self, source_id: str, fetch_mode: str, payload_hash: str) -> int:
        with self.db.get_session() as session:
            record = OvernightRawRecord(
                source_id=source_id,
                fetch_mode=fetch_mode,
                payload_hash=payload_hash,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return int(record.id)

    def create_source_item(
        self,
        raw_id: int,
        canonical_url: str,
        title: str,
        document_type: str,
    ) -> int:
        with self.db.get_session() as session:
            item = OvernightSourceItem(
                raw_id=raw_id,
                canonical_url=canonical_url,
                title=title,
                document_type=document_type,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return int(item.id)

    def upsert_event_cluster(self, core_fact: str, event_type: str, event_subtype: str) -> int:
        with self.db.get_session() as session:
            existing = session.execute(
                select(OvernightEventCluster)
                .where(OvernightEventCluster.core_fact == core_fact)
                .limit(1)
            ).scalar_one_or_none()

            if existing:
                existing.event_type = event_type
                existing.event_subtype = event_subtype
                existing.updated_at = datetime.now()
                session.commit()
                return int(existing.id)

            cluster = OvernightEventCluster(
                core_fact=core_fact,
                event_type=event_type,
                event_subtype=event_subtype,
            )
            session.add(cluster)
            session.commit()
            session.refresh(cluster)
            return int(cluster.id)
