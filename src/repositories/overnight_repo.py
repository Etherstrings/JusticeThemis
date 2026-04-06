# -*- coding: utf-8 -*-
"""Repository for overnight baseline ledger tables."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from typing import Optional

from sqlalchemy import func, select

from src.overnight.brief_builder import MorningExecutiveBrief
from src.overnight.market_context import MarketLinkSet, MarketSnapshot
from src.overnight.ledger import StoredSourceItem
from src.overnight.normalizer import EntityMention, NormalizedSourceItem, NumericFact
from src.storage import (
    DatabaseManager,
    OvernightBriefArtifact,
    OvernightDocumentFamily,
    OvernightDocumentVersion,
    OvernightEventCluster,
    OvernightFeedbackArtifact,
    OvernightMarketSnapshot,
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
                summary="",
                document_type=document_type,
                normalized_entities="[]",
                normalized_numeric_facts="[]",
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return int(item.id)

    def persist_source_item(self, item: NormalizedSourceItem) -> StoredSourceItem:
        if item.raw_id is None:
            raise ValueError("NormalizedSourceItem.raw_id is required for persistence")

        with self.db.get_session() as session:
            row = OvernightSourceItem(
                raw_id=item.raw_id,
                canonical_url=item.canonical_url,
                title=item.title,
                summary=item.summary,
                document_type=item.document_type,
                title_hash=item.title_hash,
                body_hash=item.body_hash,
                content_hash=item.content_hash,
                normalized_entities=json.dumps(
                    [asdict(entity) for entity in item.entities],
                    ensure_ascii=True,
                ),
                normalized_numeric_facts=json.dumps(
                    [asdict(fact) for fact in item.numeric_facts],
                    ensure_ascii=True,
                ),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_stored_item(row)

    def assign_document_family(self, item_id: int, *, family_key: str, family_type: str) -> int:
        with self.db.get_session() as session:
            family = session.execute(
                select(OvernightDocumentFamily)
                .where(OvernightDocumentFamily.family_key == family_key)
                .limit(1)
            ).scalar_one_or_none()

            if family is None:
                family = OvernightDocumentFamily(
                    family_key=family_key,
                    family_type=family_type,
                )
                session.add(family)
                session.flush()

            item = session.execute(
                select(OvernightSourceItem)
                .where(OvernightSourceItem.id == item_id)
                .limit(1)
            ).scalar_one()
            item.family_id = family.id
            family.updated_at = datetime.now()
            session.commit()
            return int(family.id)

    def attach_document_version(self, item_id: int, *, body_hash: str, title_hash: str) -> int:
        with self.db.get_session() as session:
            existing = session.execute(
                select(OvernightDocumentVersion)
                .where(OvernightDocumentVersion.item_id == item_id)
                .where(OvernightDocumentVersion.body_hash == body_hash)
                .where(OvernightDocumentVersion.title_hash == title_hash)
                .limit(1)
            ).scalar_one_or_none()

            if existing is not None:
                return int(existing.id)

            version = OvernightDocumentVersion(
                item_id=item_id,
                body_hash=body_hash,
                title_hash=title_hash,
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            return int(version.id)

    def list_source_items_by_family_key(self, family_key: str) -> list[StoredSourceItem]:
        with self.db.get_session() as session:
            family = session.execute(
                select(OvernightDocumentFamily)
                .where(OvernightDocumentFamily.family_key == family_key)
                .limit(1)
            ).scalar_one_or_none()
            if family is None:
                return []

            rows = session.execute(
                select(OvernightSourceItem)
                .where(OvernightSourceItem.family_id == family.id)
                .order_by(OvernightSourceItem.created_at.asc(), OvernightSourceItem.id.asc())
            ).scalars().all()
            if not rows:
                return []
            version_rows = session.execute(
                select(OvernightDocumentVersion)
                .where(OvernightDocumentVersion.item_id.in_([row.id for row in rows]))
            ).scalars().all()
            version_by_item_id = {row.item_id: row.id for row in version_rows}

            return [
                self._to_stored_item(
                    row,
                    family=family,
                    version_id=version_by_item_id.get(row.id),
                )
                for row in rows
            ]

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

    def save_market_snapshot(
        self,
        snapshot: MarketSnapshot,
        *,
        cluster_id: int | None = None,
    ) -> int:
        with self.db.get_session() as session:
            row = OvernightMarketSnapshot(
                cluster_id=cluster_id,
                event_key=snapshot.event_key,
                event_type=snapshot.event_type,
                event_subtype=snapshot.event_subtype,
                link_set_json=json.dumps(snapshot.link_set.to_dict(), ensure_ascii=True, sort_keys=True),
                transmission_map_json=json.dumps(
                    {key: list(values) for key, values in snapshot.transmission_map.items()},
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                rationale_json=json.dumps(list(snapshot.rationale), ensure_ascii=True),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)

    def list_market_snapshots(
        self,
        *,
        event_key: str | None = None,
        cluster_id: int | None = None,
    ) -> list[MarketSnapshot]:
        with self.db.get_session() as session:
            query = select(OvernightMarketSnapshot)
            if event_key is not None:
                query = query.where(OvernightMarketSnapshot.event_key == event_key)
            if cluster_id is not None:
                query = query.where(OvernightMarketSnapshot.cluster_id == cluster_id)

            rows = session.execute(
                query.order_by(OvernightMarketSnapshot.created_at.asc(), OvernightMarketSnapshot.id.asc())
            ).scalars().all()
            return [self._to_market_snapshot(row) for row in rows]

    def save_morning_brief(self, brief: MorningExecutiveBrief) -> str:
        payload_json = json.dumps(asdict(brief), ensure_ascii=True, sort_keys=True)

        with self.db.get_session() as session:
            existing = session.execute(
                select(OvernightBriefArtifact)
                .where(OvernightBriefArtifact.brief_id == brief.brief_id)
                .limit(1)
            ).scalar_one_or_none()

            if existing is None:
                row = OvernightBriefArtifact(
                    brief_id=brief.brief_id,
                    digest_date=brief.digest_date,
                    cutoff_time=brief.cutoff_time,
                    topline=brief.topline,
                    generated_at=brief.generated_at,
                    payload_json=payload_json,
                )
                session.add(row)
            else:
                existing.digest_date = brief.digest_date
                existing.cutoff_time = brief.cutoff_time
                existing.topline = brief.topline
                existing.generated_at = brief.generated_at
                existing.payload_json = payload_json

            session.commit()
            return brief.brief_id

    def get_latest_morning_brief(self) -> MorningExecutiveBrief | None:
        with self.db.get_session() as session:
            row = session.execute(
                select(OvernightBriefArtifact)
                .order_by(OvernightBriefArtifact.created_at.desc(), OvernightBriefArtifact.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_morning_brief(row)

    def get_morning_brief(self, brief_id: str) -> MorningExecutiveBrief | None:
        with self.db.get_session() as session:
            row = session.execute(
                select(OvernightBriefArtifact)
                .where(OvernightBriefArtifact.brief_id == brief_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_morning_brief(row)

    def get_previous_morning_brief(self, brief_id: str) -> MorningExecutiveBrief | None:
        with self.db.get_session() as session:
            rows = session.execute(
                select(OvernightBriefArtifact)
                .order_by(OvernightBriefArtifact.generated_at.desc(), OvernightBriefArtifact.id.desc())
            ).scalars().all()

        for index, row in enumerate(rows):
            if row.brief_id != brief_id:
                continue
            if index + 1 >= len(rows):
                return None
            return self._to_morning_brief(rows[index + 1])

        return None

    def list_morning_briefs(self, *, page: int, limit: int) -> dict[str, object]:
        offset = max(page - 1, 0) * limit

        with self.db.get_session() as session:
            total = session.execute(
                select(func.count()).select_from(OvernightBriefArtifact)
            ).scalar_one()
            rows = session.execute(
                select(OvernightBriefArtifact)
                .order_by(OvernightBriefArtifact.created_at.desc(), OvernightBriefArtifact.id.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()

        return {
            "page": page,
            "limit": limit,
            "total": int(total),
            "items": [
                {
                    "brief_id": row.brief_id,
                    "digest_date": row.digest_date,
                    "cutoff_time": row.cutoff_time,
                    "topline": row.topline,
                    "generated_at": row.generated_at,
                }
                for row in rows
            ],
        }

    def save_feedback(
        self,
        *,
        target_type: str,
        target_id: str,
        brief_id: str | None,
        event_id: str | None,
        feedback_type: str,
        comment: str,
        status: str = "pending_review",
    ) -> int:
        with self.db.get_session() as session:
            row = OvernightFeedbackArtifact(
                target_type=target_type,
                target_id=target_id,
                brief_id=brief_id,
                event_id=event_id,
                feedback_type=feedback_type,
                comment=comment,
                status=status,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)

    def list_feedback(
        self,
        *,
        page: int,
        limit: int,
        target_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        offset = max(page - 1, 0) * limit

        with self.db.get_session() as session:
            count_query = select(func.count()).select_from(OvernightFeedbackArtifact)
            items_query = select(OvernightFeedbackArtifact)

            if target_type:
                count_query = count_query.where(OvernightFeedbackArtifact.target_type == target_type)
                items_query = items_query.where(OvernightFeedbackArtifact.target_type == target_type)
            if status:
                count_query = count_query.where(OvernightFeedbackArtifact.status == status)
                items_query = items_query.where(OvernightFeedbackArtifact.status == status)

            total = session.execute(count_query).scalar_one()
            rows = session.execute(
                items_query
                .order_by(OvernightFeedbackArtifact.created_at.desc(), OvernightFeedbackArtifact.id.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()

        return {
            "page": page,
            "limit": limit,
            "total": int(total),
            "items": [
                {
                    "feedback_id": int(row.id),
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "brief_id": row.brief_id,
                    "event_id": row.event_id,
                    "feedback_type": row.feedback_type,
                    "comment": row.comment,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
                }
                for row in rows
            ],
        }

    def update_feedback_status(self, feedback_id: int, *, status: str) -> dict[str, object] | None:
        with self.db.get_session() as session:
            row = session.execute(
                select(OvernightFeedbackArtifact)
                .where(OvernightFeedbackArtifact.id == feedback_id)
                .limit(1)
            ).scalar_one_or_none()

            if row is None:
                return None

            row.status = status
            session.commit()
            session.refresh(row)

            return {
                "feedback_id": int(row.id),
                "target_type": row.target_type,
                "target_id": row.target_id,
                "brief_id": row.brief_id,
                "event_id": row.event_id,
                "feedback_type": row.feedback_type,
                "comment": row.comment,
                "status": row.status,
                "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
            }

    def _to_stored_item(
        self,
        row: OvernightSourceItem,
        *,
        family: OvernightDocumentFamily | None = None,
        version_id: int | None = None,
    ) -> StoredSourceItem:
        entities_payload = json.loads(row.normalized_entities or "[]")
        numeric_payload = json.loads(row.normalized_numeric_facts or "[]")

        return StoredSourceItem(
            id=int(row.id),
            raw_id=int(row.raw_id),
            canonical_url=row.canonical_url,
            title=row.title,
            summary=row.summary or "",
            document_type=row.document_type,
            title_hash=row.title_hash or "",
            body_hash=row.body_hash or "",
            content_hash=row.content_hash or "",
            entities=tuple(EntityMention(**payload) for payload in entities_payload),
            numeric_facts=tuple(NumericFact(**payload) for payload in numeric_payload),
            family_id=int(family.id) if family is not None else row.family_id,
            family_key=family.family_key if family is not None else None,
            family_type=family.family_type if family is not None else None,
            version_id=version_id,
            created_at=row.created_at,
        )

    def _to_market_snapshot(self, row: OvernightMarketSnapshot) -> MarketSnapshot:
        link_set_payload = json.loads(row.link_set_json or "{}")
        transmission_payload = json.loads(row.transmission_map_json or "{}")
        rationale_payload = json.loads(row.rationale_json or "[]")

        return MarketSnapshot(
            id=int(row.id),
            cluster_id=row.cluster_id,
            event_key=row.event_key,
            event_type=row.event_type,
            event_subtype=row.event_subtype,
            link_set=MarketLinkSet.from_dict(link_set_payload),
            transmission_map={
                key: tuple(values)
                for key, values in transmission_payload.items()
            },
            rationale=tuple(rationale_payload),
            created_at=row.created_at,
        )

    def _to_morning_brief(self, row: OvernightBriefArtifact) -> MorningExecutiveBrief:
        payload = json.loads(row.payload_json)
        return MorningExecutiveBrief(**payload)
