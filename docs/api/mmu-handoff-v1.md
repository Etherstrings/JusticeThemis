# MMU Handoff API V1

This document defines the staged model-facing payloads for the cross-market overnight system.

The purpose of these payloads is to replace one long undifferentiated prompt with several smaller, typed, auditable handoff contracts.

## HTTP Endpoint

Current API endpoint:

`GET /api/v1/mmu/handoff`

Supported query parameters:

1. `limit`
2. `analysis_date`
3. `tier`

Current tier behavior:

1. `tier=free`
   - does not require premium auth
   - returns a free-tier MMU bundle
   - `premium_recommendation` is marked unavailable
2. `tier=premium`
   - requires `X-Premium-Access-Key`
   - loads the premium cached report
   - returns premium recommendation context derived from premium report data

When `analysis_date=YYYY-MM-DD` is provided, the server aligns:

1. handoff news item selection
2. daily analysis report lookup
3. market snapshot lookup

to the same analysis date, instead of mixing a historical report with the latest handoff payload.

## Design Rules

- model payloads must be staged
- payloads must be result-first where relevant
- payloads must be compact and bounded
- payloads must carry ids and source links for auditability
- premium interpretation must reuse the same upstream facts as the free layer

## Handoff Stages

The system uses four MMU stages:

1. `single_item_understanding`
2. `event_consolidation`
3. `market_attribution`
4. `premium_recommendation`

Each stage has its own input and output contract.

---

## Stage 1: `single_item_understanding`

### Purpose

Interpret one normalized news item without forcing the model to reason over the whole overnight session.

### Input Shape

```json
{
  "handoff_type": "single_item_understanding",
  "analysis_date": "2026-04-08",
  "item": {
    "item_id": 101,
    "source_id": "fed_news",
    "source_name": "Federal Reserve News",
    "source_group": "official_policy",
    "coverage_tier": "official_policy",
    "published_at": "2026-04-08T14:00:00+00:00",
    "published_at_display": "2026-04-08 22:00 CST",
    "title": "Sample title",
    "summary": "Normalized item summary...",
    "canonical_url": "https://example.com/article",
    "excerpt_source": "body_selector:main",
    "document_type": "press_release",
    "entities": [],
    "numeric_facts": [],
    "evidence_points": [],
    "source_capture_confidence": {
      "level": "high",
      "score": 91
    },
    "source_integrity": {
      "domain_status": "verified"
    }
  },
  "instructions": {
    "max_output_facts": 8,
    "must_not_give_investment_advice": true
  }
}
```

### Input Rules

- one item only
- summary should already be normalized and compact
- no full raw HTML
- no freeform multi-item context

### Expected Output Shape

```json
{
  "item_id": 101,
  "event_type": "policy_statement",
  "mainline_bucket_candidates": ["rates_liquidity"],
  "is_high_value": true,
  "standard_summary_cn": "这条新闻说明……",
  "key_facts": [
    "事实 1",
    "事实 2"
  ],
  "key_unknowns": [
    "待确认项 1"
  ],
  "affected_assets": ["US2Y", "US10Y", "XLK"],
  "confidence": "high"
}
```

### Output Rules

- no stock recommendation
- no China stock recommendation
- focus on event typing and fact extraction

---

## Stage 2: `event_consolidation`

### Purpose

Merge several related items into one canonical overnight event.

### Input Shape

```json
{
  "handoff_type": "event_consolidation",
  "analysis_date": "2026-04-08",
  "cluster_candidate": {
    "cluster_id": "candidate_rates_001",
    "item_ids": [101, 102, 103],
    "mainline_bucket_hint": "rates_liquidity",
    "items": [
      {
        "item_id": 101,
        "source_name": "Federal Reserve News",
        "coverage_tier": "official_policy",
        "published_at_display": "2026-04-08 22:00 CST",
        "title": "Sample title",
        "summary": "Normalized summary",
        "canonical_url": "https://example.com/1",
        "key_numbers": [],
        "evidence_points": []
      }
    ]
  },
  "instructions": {
    "prefer_official_primary_source": true,
    "max_sources_per_event": 5
  }
}
```

### Input Rules

- one candidate cluster only
- maximum 5 source items
- include official and media evidence when available
- include already-normalized summaries only

### Expected Output Shape

```json
{
  "cluster_id": "candidate_rates_001",
  "event_title": "联储相关利率主线事件",
  "event_type": "policy_event",
  "mainline_bucket": "rates_liquidity",
  "primary_item_id": 101,
  "supporting_item_ids": [102, 103],
  "event_status": "confirmed",
  "canonical_event_summary_cn": "标准事件摘要……",
  "key_facts": [
    "事实 1",
    "事实 2"
  ],
  "conflicts": [],
  "affected_assets": ["US2Y", "US10Y", "XLK"],
  "confidence": "high"
}
```

### Output Rules

- decide one primary source item
- note conflicts explicitly instead of smoothing them away
- still no stock recommendation

---

## Stage 3: `market_attribution`

### Purpose

Explain the overnight move using the completed market results plus the most important event records.

### Input Shape

```json
{
  "handoff_type": "market_attribution",
  "analysis_date": "2026-04-08",
  "market_board": {
    "headline": "纳指领涨，油价回落，收益率回落。",
    "indexes": [],
    "sectors": [],
    "rates_fx": [],
    "precious_metals": [],
    "energy": [],
    "industrial_metals": [],
    "china_mapped_futures": []
  },
  "main_candidate_events": [
    {
      "cluster_id": "energy_001",
      "event_title": "中东停火与油价回落",
      "mainline_bucket": "geopolitics_energy",
      "primary_source_name": "EIA Pressroom",
      "canonical_event_summary_cn": "……",
      "affected_assets": ["WTI", "Brent", "NDX", "XLK"],
      "confidence": "high"
    }
  ],
  "instructions": {
    "max_mainlines": 12,
    "must_start_from_market_results": true
  }
}
```

### Input Rules

- include the Market Board
- include only the top event layer, not the full raw pool
- event count should remain small and curated

### Expected Output Shape

```json
{
  "analysis_date": "2026-04-08",
  "market_mainline_summary_cn": "昨夜市场主线是……",
  "mainlines": [
    {
      "mainline_id": "mainline_001",
      "headline": "科技风险偏好修复",
      "mainline_bucket": "tech_semiconductor",
      "importance_rank": 1,
      "linked_event_ids": ["energy_001"],
      "affected_assets": ["NDX", "XLK", "SOXX"],
      "market_effect": "科技偏多",
      "confidence": "high"
    }
  ],
  "cross_market_links": [
    "油价回落对应科技风险偏好改善"
  ],
  "open_questions": [
    "需要确认停火持续性"
  ]
}
```

### Output Rules

- must explain what already moved
- must identify the overnight mainlines
- still no stock picks

---

## Stage 4: `premium_recommendation`

### Purpose

Convert confirmed mainlines into premium China-facing stock and commodity recommendations.

### Input Shape

```json
{
  "handoff_type": "premium_recommendation",
  "analysis_date": "2026-04-08",
  "market_attribution": {
    "market_mainline_summary_cn": "昨夜主线……",
    "mainlines": []
  },
  "china_mapping_context": {
    "sector_direction_map": [],
    "commodity_direction_map": [],
    "candidate_stock_pool": []
  },
  "instructions": {
    "max_stock_recommendations": 25,
    "must_include_risk_points": true
  }
}
```

### Input Rules

- only use confirmed mainlines
- reuse the same Market Board and event facts
- candidate stock pool should be explicit and bounded

### Expected Output Shape

```json
{
  "analysis_date": "2026-04-08",
  "premium_summary_cn": "付费层总结……",
  "direction_calls": [
    {
      "direction": "自主可控半导体链",
      "stance": "positive",
      "confidence": "medium",
      "evidence_mainline_ids": ["mainline_001"],
      "risk_points": ["风险点 1"]
    }
  ],
  "commodity_calls": [
    {
      "commodity_direction": "甲醇链观察偏多",
      "confidence": "medium",
      "evidence_mainline_ids": ["mainline_002"]
    }
  ],
  "stock_recommendations": [
    {
      "ticker": "688981.SH",
      "name": "中芯国际",
      "stance": "positive",
      "confidence": "medium",
      "linked_mainline_ids": ["mainline_001"],
      "why": "推荐理由……",
      "risk_points": ["风险点 1"],
      "trigger_conditions": ["触发条件 1"]
    }
  ]
}
```

### Output Rules

- must trace every recommendation back to mainlines
- must include risks and trigger conditions
- cannot invent unsupported stock calls

---

## Shared Fields

All stages should preserve these identifiers whenever available:

- `analysis_date`
- `item_id`
- `cluster_id`
- `mainline_id`
- `source_id`
- `canonical_url`

This makes downstream review and replay possible.

## Length Controls

The handoff system should enforce bounded inputs:

- single-item summaries should be compact
- one event handoff should contain only a small number of sources
- market attribution should only see the curated top event layer
- premium recommendation should only see confirmed mainlines plus bounded candidate pools

## Auditability Rules

Every stage should preserve enough structure to answer:

- where did this claim come from?
- which source or event supported this step?
- what was still uncertain?
- which later stage consumed it?

## Non-Goals

These handoff payloads should not:

- carry raw HTML
- carry entire article bodies by default
- collapse all overnight evidence into one message
- hide source ids or canonical URLs
- treat premium output as detached from free-layer facts
