# Overnight Intelligence Morning Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a source-driven overnight intelligence pipeline that ingests curated US official/media signals, stores them as an event ledger, ranks them, and delivers a daily morning brief through notifications, API, and Web UI.

**Architecture:** Add a focused `src/overnight/` package for source registry, collectors, normalization, ledger building, market context, priority scoring, and brief rendering. Persist the ledger inside the existing SQLite/SQLAlchemy layer in [`src/storage.py`](../../../../src/storage.py) with a dedicated repository and service, then expose the results through new FastAPI endpoints and a lightweight React page that fits the current app shell.

**Tech Stack:** Python 3.10+, SQLAlchemy/SQLite, FastAPI, React + Vite, existing notification/config systems, `uv run pytest`, `npm --prefix apps/dsa-web run build`

---

This spec spans multiple subsystems, so the plan is intentionally phased into shippable vertical slices. Each task must finish with green tests and a commit before the next task starts. Use `@superpowers:test-driven-development` for every task and `@superpowers:verification-before-completion` before claiming any milestone complete.

## File Structure

### Create

- `src/overnight/__init__.py` - package exports for the overnight intelligence feature.
- `src/overnight/types.py` - dataclasses and enums for source definitions, candidates, event updates, and brief DTOs.
- `src/overnight/source_registry.py` - curated source catalog, source filtering, and mission-critical source helpers.
- `src/overnight/collectors/__init__.py` - collector package exports.
- `src/overnight/collectors/base.py` - shared collector contract, retry helpers, and raw-record plumbing.
- `src/overnight/collectors/feed.py` - RSS / feed collection.
- `src/overnight/collectors/section.py` - section/topic page collection.
- `src/overnight/collectors/article.py` - article body expansion and canonicalization.
- `src/overnight/collectors/attachment.py` - PDF / attachment discovery and fetch metadata.
- `src/overnight/collectors/calendar.py` - release schedule and `.ics` collection.
- `src/overnight/normalizer.py` - URL, time, text, entity, and numeric fact normalization.
- `src/overnight/ledger.py` - document family assignment, event assignment, and event update emission.
- `src/overnight/clustering.py` - event clustering rules and semantic matching hooks.
- `src/overnight/contradiction.py` - contradiction detection and severity tagging.
- `src/overnight/market_context.py` - market link set generation and reaction snapshot capture.
- `src/overnight/priority.py` - priority scoring, importance bands, and delivery policy.
- `src/overnight/analysis.py` - structured analyst packets and skeptical review orchestration.
- `src/overnight/brief_builder.py` - Flash Alert, Morning Executive Brief, Deep Dive, and Evidence Ledger rendering.
- `src/overnight/runner.py` - end-to-end overnight orchestration entry point.
- `src/repositories/overnight_repo.py` - persistence access for overnight ledger tables.
- `src/services/overnight_service.py` - service layer for API responses and history lookup.
- `api/v1/endpoints/overnight.py` - FastAPI routes for current brief, history, event detail, and sources/health views.
- `api/v1/schemas/overnight.py` - request/response schemas for overnight endpoints.
- `apps/dsa-web/src/api/overnight.ts` - frontend API client.
- `apps/dsa-web/src/types/overnight.ts` - frontend types matching the new API schemas.
- `apps/dsa-web/src/pages/OvernightBriefPage.tsx` - main UI page for morning brief and event drill-down.
- `apps/dsa-web/src/components/overnight/OvernightSummaryPanel.tsx` - top-line summary panel.
- `apps/dsa-web/src/components/overnight/OvernightEventCard.tsx` - reusable event card component.
- `tests/test_overnight_storage.py` - config/schema/repository tests.
- `tests/test_overnight_registry.py` - source registry tests.
- `tests/test_overnight_collectors.py` - feed/section/article/calendar collector tests.
- `tests/test_overnight_ledger.py` - normalization, versioning, family, cluster, and contradiction tests.
- `tests/test_overnight_priority.py` - market link set and priority engine tests.
- `tests/test_overnight_brief_builder.py` - brief rendering tests.
- `tests/test_overnight_api.py` - FastAPI endpoint tests.
- `tests/test_overnight_runner.py` - scheduler/runner integration tests.
- `tests/fixtures/overnight/whitehouse_news.html` - parser fixture.
- `tests/fixtures/overnight/reuters_topics.html` - parser fixture.
- `tests/fixtures/overnight/fed_feed.xml` - feed fixture.
- `tests/fixtures/overnight/bls_schedule.html` - calendar fixture.

### Modify

- `src/config.py` - add overnight feature flags, scheduling, retention, and alert threshold config.
- `src/core/config_registry.py` - register overnight settings for the settings UI.
- `src/storage.py` - add SQLAlchemy models and `DatabaseManager` helpers for raw records, source items, document families, event clusters, snapshots, and briefs.
- `src/notification.py` - add overnight-specific send/render entry points while reusing existing Telegram/email channels.
- `src/scheduler.py` - add overnight polling windows and digest scheduling helpers.
- `main.py` - add overnight runner wiring and schedule integration.
- `api/v1/endpoints/__init__.py` - export the new overnight endpoint module if the package uses explicit exports.
- `api/v1/router.py` - register `/api/v1/overnight`.
- `apps/dsa-web/src/App.tsx` - add the new route and dock navigation item.
- `apps/dsa-web/src/utils/systemConfigI18n.ts` - label new overnight settings.
- `README.md` - document the feature at a high level.
- `docs/full-guide.md` - add configuration and runbook details.
- `docs/CHANGELOG.md` - record the new feature.

## Task 1: Add Overnight Config, Tables, and Repository

**Files:**
- Create: `src/repositories/overnight_repo.py`
- Test: `tests/test_overnight_storage.py`
- Modify: `src/config.py`
- Modify: `src/core/config_registry.py`
- Modify: `src/storage.py`

- [ ] **Step 1: Write the failing storage/config tests**

```python
def test_overnight_config_defaults():
    cfg = Config.get_instance()
    assert cfg.overnight_brief_enabled is False
    assert cfg.overnight_digest_cutoff == "07:30"
    assert cfg.overnight_priority_alert_threshold == "P0"


def test_overnight_repo_round_trip(db_manager):
    repo = OvernightRepository(db_manager)
    raw_id = repo.create_raw_record(source_id="whitehouse_news", fetch_mode="section_scan", payload_hash="abc123")
    item_id = repo.create_source_item(raw_id=raw_id, canonical_url="https://example.com/a", title="Test", document_type="press_release")
    event_id = repo.upsert_event_cluster(core_fact="Test event", event_type="policy_action", event_subtype="fact_sheet")
    assert raw_id and item_id and event_id
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_overnight_storage.py -v`  
Expected: FAIL with missing config fields, missing repository class, and missing overnight tables.

- [ ] **Step 3: Add minimal config fields, ORM models, and repository methods**

```python
@dataclass
class Config:
    overnight_brief_enabled: bool = False
    overnight_digest_cutoff: str = "07:30"
    overnight_priority_alert_threshold: str = "P0"
    overnight_source_whitelist: str = ""


class OvernightRawRecord(Base):
    __tablename__ = "overnight_raw_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(64), nullable=False, index=True)
    fetch_mode = Column(String(32), nullable=False)
    payload_hash = Column(String(128), nullable=False, index=True)


class OvernightRepository:
    def create_raw_record(self, *, source_id: str, fetch_mode: str, payload_hash: str) -> int: ...
    def create_source_item(self, *, raw_id: int, canonical_url: str, title: str, document_type: str) -> int: ...
    def upsert_event_cluster(self, *, core_fact: str, event_type: str, event_subtype: str) -> int: ...
```

- [ ] **Step 4: Run the tests to verify the storage slice passes**

Run: `uv run pytest tests/test_overnight_storage.py -v`  
Expected: PASS for config defaults, table creation, and basic repository round-trip.

- [ ] **Step 5: Commit the storage baseline**

```bash
git add src/config.py src/core/config_registry.py src/storage.py src/repositories/overnight_repo.py tests/test_overnight_storage.py
git commit -m "feat: add overnight ledger storage baseline"
```

## Task 2: Create the Source Registry and Collector Contracts

**Files:**
- Create: `src/overnight/__init__.py`
- Create: `src/overnight/types.py`
- Create: `src/overnight/source_registry.py`
- Create: `src/overnight/collectors/__init__.py`
- Create: `src/overnight/collectors/base.py`
- Test: `tests/test_overnight_registry.py`

- [ ] **Step 1: Write the failing registry tests**

```python
def test_registry_contains_mission_critical_sources():
    registry = build_default_source_registry()
    ids = {item.source_id for item in registry}
    assert "whitehouse_news" in ids
    assert "fed_news" in ids
    assert "reuters_topics" in ids


def test_registry_filters_by_source_class():
    registry = build_default_source_registry(source_class="policy")
    assert all(item.source_class == "policy" for item in registry)
```

- [ ] **Step 2: Run the registry tests to verify they fail**

Run: `uv run pytest tests/test_overnight_registry.py -v`  
Expected: FAIL with missing `SourceDefinition`, registry builder, and collector contract.

- [ ] **Step 3: Add the source definition types and default registry**

```python
@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    display_name: str
    organization_type: str
    source_class: str
    entry_type: str
    entry_urls: list[str]
    priority: int
    poll_interval_seconds: int
    is_mission_critical: bool = False


def build_default_source_registry(source_class: str | None = None) -> list[SourceDefinition]:
    sources = [
        SourceDefinition("whitehouse_news", "White House News", "official_policy", "policy", "section_page", ["https://www.whitehouse.gov/news/"], 100, 300, True),
        SourceDefinition("fed_news", "Federal Reserve News", "official_policy", "policy", "rss", ["https://www.federalreserve.gov/feeds/press_all.xml"], 100, 300, True),
        SourceDefinition("reuters_topics", "Reuters Topics", "wire_media", "market", "section_page", ["https://reutersbest.com/topic/"], 90, 600, True),
    ]
    return [src for src in sources if source_class is None or src.source_class == source_class]
```

- [ ] **Step 4: Add the collector base contract**

```python
class BaseCollector(Protocol):
    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        ...
```

- [ ] **Step 5: Run the registry tests to verify they pass**

Run: `uv run pytest tests/test_overnight_registry.py -v`  
Expected: PASS for registry membership and source-class filtering.

- [ ] **Step 6: Commit the source registry slice**

```bash
git add src/overnight/__init__.py src/overnight/types.py src/overnight/source_registry.py src/overnight/collectors/__init__.py src/overnight/collectors/base.py tests/test_overnight_registry.py
git commit -m "feat: add overnight source registry contracts"
```

## Task 3: Implement Feed, Section, Article, Attachment, and Calendar Collectors

**Files:**
- Create: `src/overnight/collectors/feed.py`
- Create: `src/overnight/collectors/section.py`
- Create: `src/overnight/collectors/article.py`
- Create: `src/overnight/collectors/attachment.py`
- Create: `src/overnight/collectors/calendar.py`
- Create: `tests/fixtures/overnight/whitehouse_news.html`
- Create: `tests/fixtures/overnight/reuters_topics.html`
- Create: `tests/fixtures/overnight/fed_feed.xml`
- Create: `tests/fixtures/overnight/bls_schedule.html`
- Test: `tests/test_overnight_collectors.py`

- [ ] **Step 1: Write the failing collector fixture tests**

```python
def test_feed_collector_parses_fed_items(fixture_loader):
    collector = FeedCollector(http_client=FixtureClient("tests/fixtures/overnight/fed_feed.xml"))
    candidates = collector.collect(FED_SOURCE)
    assert candidates[0].candidate_type == "feed_item"
    assert "Federal Reserve" in candidates[0].candidate_title


def test_section_collector_extracts_whitehouse_cards(fixture_loader):
    collector = SectionCollector(http_client=FixtureClient("tests/fixtures/overnight/whitehouse_news.html"))
    candidates = collector.collect(WHITE_HOUSE_SOURCE)
    assert candidates[0].needs_article_fetch is True
```

- [ ] **Step 2: Run the collector tests to verify they fail**

Run: `uv run pytest tests/test_overnight_collectors.py -v`  
Expected: FAIL with missing collector classes and missing fixture files.

- [ ] **Step 3: Add fixture files and implement the collectors with deterministic parsing**

```python
class FeedCollector:
    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        feed = feedparser.parse(self._fetch(source.entry_urls[0]))
        return [
            SourceCandidate(
                candidate_id=f"{source.source_id}:{entry.link}",
                raw_id="fixture",
                candidate_type="feed_item",
                candidate_url=entry.link,
                candidate_title=entry.title,
                candidate_summary=getattr(entry, "summary", ""),
                candidate_published_at=getattr(entry, "published", None),
                candidate_section=source.display_name,
                candidate_tags=[],
                needs_article_fetch=True,
                needs_attachment_fetch=False,
            )
            for entry in feed.entries
        ]
```

- [ ] **Step 4: Add canonical article and attachment expansion helpers**

```python
class ArticleCollector:
    def expand(self, candidate: SourceCandidate) -> SourceCandidate:
        canonical_url, title, summary = extract_article_shell(self._fetch(candidate.candidate_url))
        return replace(candidate, candidate_url=canonical_url, candidate_title=title, candidate_summary=summary)
```

- [ ] **Step 5: Run the collector tests to verify they pass**

Run: `uv run pytest tests/test_overnight_collectors.py -v`  
Expected: PASS for feed parsing, section-card extraction, article canonicalization, and schedule parsing.

- [ ] **Step 6: Commit the collector slice**

```bash
git add src/overnight/collectors/feed.py src/overnight/collectors/section.py src/overnight/collectors/article.py src/overnight/collectors/attachment.py src/overnight/collectors/calendar.py tests/test_overnight_collectors.py tests/fixtures/overnight
git commit -m "feat: add overnight collectors and fixtures"
```

## Task 4: Build Normalization, Versioning, Families, Clusters, and Contradiction Checks

**Files:**
- Create: `src/overnight/normalizer.py`
- Create: `src/overnight/ledger.py`
- Create: `src/overnight/clustering.py`
- Create: `src/overnight/contradiction.py`
- Test: `tests/test_overnight_ledger.py`
- Modify: `src/repositories/overnight_repo.py`
- Modify: `src/storage.py`

- [ ] **Step 1: Write the failing ledger tests**

```python
def test_normalizer_extracts_numeric_fact_and_entities():
    item = normalize_candidate(make_candidate(title="USTR raises tariffs to 25%", summary="Tariffs on selected goods rise to 25% effective April 15."))
    assert item.document_type == "fact_sheet"
    assert any(fact.metric_name == "tariff_rate" and fact.value == 25 for fact in item.numeric_facts)


def test_ledger_groups_versions_and_creates_event_update(repo):
    first = repo.persist_source_item(make_source_item(canonical_url="https://example.com/a", title="Title v1", content_hash="one"))
    second = repo.persist_source_item(make_source_item(canonical_url="https://example.com/a", title="Title v2", content_hash="two"))
    cluster = build_event_cluster([first, second])
    assert cluster.status in {"breaking", "developing", "confirmed"}
    assert cluster.event_update.update_type == "version_revised"
```

- [ ] **Step 2: Run the ledger tests to verify they fail**

Run: `uv run pytest tests/test_overnight_ledger.py -v`  
Expected: FAIL with missing normalizer, clustering, contradiction engine, and repository persistence helpers.

- [ ] **Step 3: Implement normalization and version/family persistence**

```python
def normalize_candidate(candidate: SourceCandidate) -> NormalizedSourceItem:
    canonical_url = canonicalize_url(candidate.candidate_url)
    document_type = infer_document_type(candidate)
    numeric_facts = extract_numeric_facts(candidate.candidate_title, candidate.candidate_summary)
    return NormalizedSourceItem(canonical_url=canonical_url, document_type=document_type, numeric_facts=numeric_facts, ...)


class OvernightRepository:
    def persist_source_item(self, item: NormalizedSourceItem) -> StoredSourceItem: ...
    def attach_document_version(self, item_id: int, *, body_hash: str, title_hash: str) -> int: ...
    def assign_document_family(self, item_id: int, *, family_key: str, family_type: str) -> int: ...
```

- [ ] **Step 4: Implement event clustering, contradiction checks, and event updates**

```python
def build_event_cluster(items: list[StoredSourceItem]) -> EventCluster:
    cluster_key = derive_cluster_key(items)
    contradiction_flags = detect_contradictions(items)
    status = "contradictory" if contradiction_flags else "confirmed"
    return EventCluster(cluster_key=cluster_key, status=status, contradiction_flags=contradiction_flags, ...)
```

- [ ] **Step 5: Run the ledger tests to verify they pass**

Run: `uv run pytest tests/test_overnight_ledger.py -v`  
Expected: PASS for canonicalization, numeric fact extraction, family assignment, clustering, and contradiction detection.

- [ ] **Step 6: Commit the ledger slice**

```bash
git add src/overnight/normalizer.py src/overnight/ledger.py src/overnight/clustering.py src/overnight/contradiction.py src/repositories/overnight_repo.py src/storage.py tests/test_overnight_ledger.py
git commit -m "feat: add overnight ledger pipeline"
```

## Task 5: Add Market Context, Transmission Maps, and Priority Scoring

**Files:**
- Create: `src/overnight/market_context.py`
- Create: `src/overnight/priority.py`
- Test: `tests/test_overnight_priority.py`
- Modify: `src/config.py`
- Modify: `src/repositories/overnight_repo.py`

- [ ] **Step 1: Write the failing market/priority tests**

```python
def test_market_link_set_maps_policy_event_to_assets():
    event = make_event(event_type="trade_action", event_subtype="tariff_announcement", entities=["USTR", "China"])
    link_set = build_market_link_set(event)
    assert "USDCNH" in link_set.linked_fx_pairs
    assert "Brent" in link_set.linked_commodities


def test_priority_engine_promotes_official_trade_shock():
    event = make_event(event_type="trade_action", importance_score=0.0, official_evidence_count=2, market_reaction_score=0.8)
    score = PriorityEngine().score(event)
    assert score.priority_level in {"P0", "P1"}
    assert score.delivery_policy in {"night_alert_and_brief", "morning_brief_highlight"}
```

- [ ] **Step 2: Run the market/priority tests to verify they fail**

Run: `uv run pytest tests/test_overnight_priority.py -v`  
Expected: FAIL with missing link-set builder, snapshot persistence, and priority engine.

- [ ] **Step 3: Implement market link generation and snapshot storage**

```python
def build_market_link_set(event: EventCluster) -> MarketLinkSet:
    return MarketLinkSet(
        event_id=event.event_id,
        linked_indices=["SPX_FUT", "NDX_FUT"],
        linked_rates=["UST2Y", "UST10Y"],
        linked_fx_pairs=["DXY", "USDCNH"],
        linked_commodities=["Brent", "WTI", "Gold"],
        linked_sector_etfs=["XLE", "SOXX"],
        linked_companies=["NVDA", "AAPL"],
        linked_regions=["US", "China"],
    )
```

- [ ] **Step 4: Implement transmission maps and priority scoring**

```python
class PriorityEngine:
    def score(self, event: EventCluster) -> PriorityResult:
        officiality = 1.0 if event.official_evidence_ids else 0.0
        importance = 0.30 * officiality + 0.25 * event.market_reaction_score + 0.25 * event.impact_breadth_score + 0.20 * event.impact_depth_score
        priority_level = "P0" if importance >= 0.85 else "P1" if importance >= 0.65 else "P2"
        return PriorityResult(priority_level=priority_level, delivery_policy="night_alert_and_brief" if priority_level == "P0" else "morning_brief_highlight", ...)
```

- [ ] **Step 5: Run the market/priority tests to verify they pass**

Run: `uv run pytest tests/test_overnight_priority.py -v`  
Expected: PASS for market link mapping, snapshot capture, and priority policy rules.

- [ ] **Step 6: Commit the market-priority slice**

```bash
git add src/overnight/market_context.py src/overnight/priority.py src/config.py src/repositories/overnight_repo.py tests/test_overnight_priority.py
git commit -m "feat: add overnight market context and priority scoring"
```

## Task 6: Implement Structured Analysis Packets and Brief Rendering

**Files:**
- Create: `src/overnight/analysis.py`
- Create: `src/overnight/brief_builder.py`
- Test: `tests/test_overnight_brief_builder.py`
- Modify: `src/notification.py`

- [ ] **Step 1: Write the failing brief-builder tests**

```python
def test_brief_builder_renders_topline_and_price_pressure():
    brief = build_morning_brief(
        events=[make_ranked_event(core_fact="USTR announced new tariffs", priority_level="P0")],
        direction_board=[{"title": "Policy beneficiaries", "items": ["defense"]}],
        price_pressure_board=[{"title": "直接涨价", "items": ["Brent crude"]}],
    )
    assert brief.topline
    assert brief.what_may_get_more_expensive[0]["items"] == ["Brent crude"]


def test_notification_service_formats_flash_alert():
    content = NotificationService().format_overnight_flash_alert(make_flash_alert())
    assert "watch next" in content.lower()
```

- [ ] **Step 2: Run the brief-builder tests to verify they fail**

Run: `uv run pytest tests/test_overnight_brief_builder.py -v`  
Expected: FAIL with missing analysis packets, brief builder, and notification formatter.

- [ ] **Step 3: Implement analyst packet models and skeptical review output**

```python
@dataclass
class PolicyAnalystOutput:
    event_id: str
    policy_status: str
    issuing_authority: str
    immediate_implications: list[str]
    confidence: float


@dataclass
class SkepticalReviewPacket:
    event_id: str
    challenge_points: list[str]
    downgraded_confidence: float
```

- [ ] **Step 4: Implement brief builders and notification render helpers**

```python
def build_morning_brief(*, events: list[RankedEvent], direction_board: list[dict], price_pressure_board: list[dict]) -> MorningExecutiveBrief:
    topline = synthesize_topline(events)
    return MorningExecutiveBrief(
        brief_id=str(uuid4()),
        digest_date=date.today().isoformat(),
        cutoff_time="07:30",
        topline=topline,
        top_events=[render_event_summary(event) for event in events[:10]],
        likely_beneficiaries=direction_board,
        likely_pressure_points=[],
        what_may_get_more_expensive=price_pressure_board,
        ...
    )
```

- [ ] **Step 5: Run the brief-builder tests to verify they pass**

Run: `uv run pytest tests/test_overnight_brief_builder.py -v`  
Expected: PASS for morning brief rendering, flash-alert rendering, and evidence-ledger serialization.

- [ ] **Step 6: Commit the analysis/brief slice**

```bash
git add src/overnight/analysis.py src/overnight/brief_builder.py src/notification.py tests/test_overnight_brief_builder.py
git commit -m "feat: add overnight analysis packets and brief rendering"
```

## Task 7: Wire the Runner, Scheduler, and Notification Delivery

**Files:**
- Create: `src/overnight/runner.py`
- Test: `tests/test_overnight_runner.py`
- Modify: `src/scheduler.py`
- Modify: `main.py`
- Modify: `src/config.py`
- Modify: `src/notification.py`

- [ ] **Step 1: Write the failing runner/scheduler tests**

```python
def test_runner_generates_digest_from_event_updates(monkeypatch):
    runner = OvernightRunner(repo=FakeRepo.with_ranked_event(), notifier=FakeNotifier())
    result = runner.run_digest(cutoff_time="07:30")
    assert result.morning_brief is not None
    assert result.sent_alerts == []


def test_scheduler_registers_overnight_digest_job():
    scheduler = Scheduler(schedule_time="18:00")
    scheduler.set_overnight_task(lambda: None, digest_cutoff="07:30")
    assert scheduler.schedule.get_jobs()
```

- [ ] **Step 2: Run the runner/scheduler tests to verify they fail**

Run: `uv run pytest tests/test_overnight_runner.py -v`  
Expected: FAIL with missing runner class and missing scheduler/main integration.

- [ ] **Step 3: Implement the overnight runner and delivery hooks**

```python
class OvernightRunner:
    def run_digest(self, *, cutoff_time: str) -> OvernightRunResult:
        events = self.repo.list_ranked_events(cutoff_time=cutoff_time)
        brief = build_morning_brief(events=events, direction_board=self._build_directions(events), price_pressure_board=self._build_prices(events))
        self.notifier.send_overnight_brief(brief)
        return OvernightRunResult(morning_brief=brief, sent_alerts=[])
```

- [ ] **Step 4: Add config flags and main/scheduler wiring**

```python
if args.overnight_brief or config.overnight_brief_enabled:
    runner = OvernightRunner(...)
    if args.schedule or config.schedule_enabled:
        scheduler.set_overnight_task(lambda: runner.run_digest(cutoff_time=config.overnight_digest_cutoff), digest_cutoff=config.overnight_digest_cutoff)
    else:
        runner.run_digest(cutoff_time=config.overnight_digest_cutoff)
```

- [ ] **Step 5: Run the runner/scheduler tests to verify they pass**

Run: `uv run pytest tests/test_overnight_runner.py -v`  
Expected: PASS for digest generation, scheduler registration, and notification invocation.

- [ ] **Step 6: Commit the runner slice**

```bash
git add src/overnight/runner.py src/scheduler.py main.py src/config.py src/notification.py tests/test_overnight_runner.py
git commit -m "feat: wire overnight runner into scheduling and delivery"
```

## Task 8: Expose Overnight Briefs Through FastAPI

**Files:**
- Create: `src/services/overnight_service.py`
- Create: `api/v1/schemas/overnight.py`
- Create: `api/v1/endpoints/overnight.py`
- Test: `tests/test_overnight_api.py`
- Modify: `api/v1/router.py`
- Modify: `api/v1/endpoints/__init__.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_get_current_overnight_brief(client):
    response = client.get("/api/v1/overnight/brief/latest")
    assert response.status_code == 200
    assert "topline" in response.json()


def test_get_overnight_event_detail(client):
    response = client.get("/api/v1/overnight/events/event_123")
    assert response.status_code == 200
    assert response.json()["event_id"] == "event_123"
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run: `uv run pytest tests/test_overnight_api.py -v`  
Expected: FAIL with missing service, schema, endpoint, and router registration.

- [ ] **Step 3: Implement the service and API schemas**

```python
class OvernightService:
    def get_latest_brief(self) -> MorningExecutiveBrief: ...
    def get_event_detail(self, event_id: str) -> dict: ...
    def list_history(self, *, page: int, limit: int) -> dict: ...
```

- [ ] **Step 4: Implement the FastAPI routes and register them**

```python
@router.get("/brief/latest", response_model=OvernightBriefResponse)
def get_latest_brief(service: OvernightService = Depends(get_overnight_service)):
    return service.get_latest_brief()


@router.get("/events/{event_id}", response_model=OvernightEventResponse)
def get_event_detail(event_id: str, service: OvernightService = Depends(get_overnight_service)):
    return service.get_event_detail(event_id)
```

- [ ] **Step 5: Run the API tests to verify they pass**

Run: `uv run pytest tests/test_overnight_api.py -v`  
Expected: PASS for latest brief, event detail, and paginated history endpoints.

- [ ] **Step 6: Commit the API slice**

```bash
git add src/services/overnight_service.py api/v1/schemas/overnight.py api/v1/endpoints/overnight.py api/v1/router.py api/v1/endpoints/__init__.py tests/test_overnight_api.py
git commit -m "feat: add overnight brief api"
```

## Task 9: Add the Web UI, Settings Labels, Docs, and Final Verification

**Files:**
- Create: `apps/dsa-web/src/api/overnight.ts`
- Create: `apps/dsa-web/src/types/overnight.ts`
- Create: `apps/dsa-web/src/pages/OvernightBriefPage.tsx`
- Create: `apps/dsa-web/src/components/overnight/OvernightSummaryPanel.tsx`
- Create: `apps/dsa-web/src/components/overnight/OvernightEventCard.tsx`
- Modify: `apps/dsa-web/src/App.tsx`
- Modify: `apps/dsa-web/src/utils/systemConfigI18n.ts`
- Modify: `README.md`
- Modify: `docs/full-guide.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: Write the failing UI/build checks**

- Add the new `/overnight` route import and navigation item in `apps/dsa-web/src/App.tsx`, referencing `OvernightBriefPage`, `OvernightSummaryPanel`, and `OvernightEventCard` before those files exist.
- Add the new overnight config labels in `apps/dsa-web/src/utils/systemConfigI18n.ts`.

- [ ] **Step 2: Run the backend regression suite and frontend build to capture the current failure**

Run: `uv run pytest tests/test_overnight_storage.py tests/test_overnight_registry.py tests/test_overnight_collectors.py tests/test_overnight_ledger.py tests/test_overnight_priority.py tests/test_overnight_brief_builder.py tests/test_overnight_runner.py tests/test_overnight_api.py -v`  
Expected: PASS before UI wiring changes.

Run: `npm --prefix apps/dsa-web run build`  
Expected: FAIL with missing overnight page/component/api client modules or unresolved type references.

- [ ] **Step 3: Implement the UI route, page, and API client**

```tsx
// apps/dsa-web/src/App.tsx
<Route path="/overnight" element={<OvernightBriefPage />} />

// apps/dsa-web/src/pages/OvernightBriefPage.tsx
const { data, isLoading } = useOvernightBrief();
return <OvernightSummaryPanel brief={data} loading={isLoading} />;
```

- [ ] **Step 4: Update docs and settings labels**

```ts
// apps/dsa-web/src/utils/systemConfigI18n.ts
OVERNIGHT_BRIEF_ENABLED: "隔夜晨报",
OVERNIGHT_DIGEST_CUTOFF: "晨报截止时间",
OVERNIGHT_PRIORITY_ALERT_THRESHOLD: "夜间提醒阈值",
```

- [ ] **Step 5: Run final verification**

Run: `uv run pytest tests/test_overnight_storage.py tests/test_overnight_registry.py tests/test_overnight_collectors.py tests/test_overnight_ledger.py tests/test_overnight_priority.py tests/test_overnight_brief_builder.py tests/test_overnight_runner.py tests/test_overnight_api.py tests/test_system_config_service.py -v`  
Expected: PASS for the new overnight slices and config regression coverage.

Run: `npm --prefix apps/dsa-web run build`  
Expected: PASS with a successful Vite production build.

- [ ] **Step 6: Commit the UI/docs slice**

```bash
git add apps/dsa-web/src/api/overnight.ts apps/dsa-web/src/types/overnight.ts apps/dsa-web/src/pages/OvernightBriefPage.tsx apps/dsa-web/src/components/overnight/OvernightSummaryPanel.tsx apps/dsa-web/src/components/overnight/OvernightEventCard.tsx apps/dsa-web/src/App.tsx apps/dsa-web/src/utils/systemConfigI18n.ts README.md docs/full-guide.md docs/CHANGELOG.md
git commit -m "feat: add overnight morning brief ui and docs"
```

## Local Plan Review Notes

- This plan deliberately stages the feature as vertical slices so the repo has working software after each task.
- The first milestone is storage + source contracts; no collector work should start before that persistence baseline is in place.
- The API/UI work is intentionally last so the backend ledger, ranking, and rendering formats can settle before the frontend depends on them.
- If any task reveals the spec is too broad for a single branch, stop after the current green milestone and split the remaining tasks into a follow-up plan instead of widening the current task.
