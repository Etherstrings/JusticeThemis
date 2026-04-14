# Market Snapshot API V1

> **Status:** This document describes the current implemented cross-asset market snapshot API. The live payload already includes the broader `asset_board` object, cross-asset groups, and China-mapped futures watch rows. See [cross-market-overnight-architecture.md](/Users/boyuewu/Documents/Projects/AIProjects/overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md).

This document describes the persisted U.S. market-close snapshot and cross-asset Market Board layer implemented in `JusticeThemis`.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/market/us/refresh` | Fetch the latest supported U.S. market-close instruments and persist one daily snapshot |
| `GET /api/v1/market/us/daily` | Read the stored U.S. market-close snapshot for one `analysis_date` |

## Product Semantics

- The snapshot is designed for China-morning usage.
- `market_date` is the original U.S. market session date.
- `analysis_date` is the corresponding `Asia/Shanghai` date after timezone conversion.
- The current snapshot is daily-close oriented, not intraday and not real-time.
- The payload is cross-asset rather than U.S.-equity-only: indexes, sectors, rates/FX, precious metals, energy, and industrial metals are captured together when available.
- `china_mapped_futures` is derived from the cross-asset board to provide a China-facing watch layer for products such as 甲醇、PTA、纯碱、工业硅、碳酸锂。

## `POST /api/v1/market/us/refresh`

### Behavior

- Fetches the configured cross-asset instrument set from market-data chart endpoints.
- Falls back across configured providers on a per-instrument basis when the primary provider fails.
- Normalizes the rows into one persisted `us_close` snapshot plus one reusable `asset_board`.
- Upserts by `analysis_date + session_name`.

### Success Response

```json
{
  "analysis_date": "2026-04-07",
  "market_date": "2026-04-06",
  "session_name": "us_close",
  "source_name": "Yahoo Finance Chart",
  "source_url": "https://finance.yahoo.com/",
  "headline": "标普500 +2.00%；纳指综指 +2.00%；VIX -10.00%；板块上 科技板块 领涨，能源板块 偏弱。",
  "capture_summary": {
    "capture_status": "complete",
    "expected_instrument_count": 23,
    "captured_instrument_count": 23,
    "missing_instrument_count": 0,
    "captured_symbols": ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "XLK", "SOXX"],
    "missing_symbols": [],
    "failed_instruments": []
  },
  "indexes": [],
  "sectors": [],
  "sentiment": [],
  "rates_fx": [],
  "precious_metals": [],
  "energy": [],
  "industrial_metals": [],
  "china_mapped_futures": [],
  "asset_board": {},
  "risk_signals": {
    "risk_mode": "risk_on"
  }
}
```

## `GET /api/v1/market/us/daily`

### Query Params

| Param | Type | Default | Meaning |
| --- | --- | --- | --- |
| `analysis_date` | string or null | latest stored snapshot | Target China-morning analysis date in `YYYY-MM-DD` format |

### Not Found

```json
{
  "detail": "U.S. market snapshot not found"
}
```

Status: `404`

## Snapshot Shape

### `indexes`, `sectors`, `sentiment`, `rates_fx`, `precious_metals`, `energy`, `industrial_metals`

Each instrument row contains:

- `symbol`
- `display_name`
- `bucket`
- `priority`
- `quote_url`
- `market_time`
- `market_time_local`
- `analysis_time_shanghai`
- `market_date`
- `analysis_date`
- `instrument_type`
- `exchange_name`
- `exchange_timezone_name`
- `currency`
- `close`
- `close_text`
- `previous_close`
- `previous_close_text`
- `change`
- `change_text`
- `change_pct`
- `change_pct_text`
- `change_direction`
- `day_high`
- `day_low`
- `volume`
- `volume_text`
- `provider_name`
- `provider_url`

These fields intentionally keep both:

- raw numeric values for downstream computation
- formatted string values for direct UI/model use

`provider_name` and `provider_url` identify which market-data provider successfully supplied the row after fallback resolution.

### `capture_summary`

| Field | Meaning |
| --- | --- |
| `capture_status` | `complete` or `partial` |
| `expected_instrument_count` | Number of configured symbols that should have been fetched |
| `captured_instrument_count` | Number of symbols successfully captured |
| `missing_instrument_count` | Number of configured symbols not captured in this run |
| `captured_symbols` | Successfully captured symbols |
| `missing_symbols` | Symbols missing from this snapshot |
| `failed_instruments` | Failure details for missing symbols |

### `risk_signals`

| Field | Meaning |
| --- | --- |
| `risk_mode` | Deterministic market-tone label: `risk_on`, `risk_off`, `mixed` |
| `advancing_sector_count` | Number of positive sector proxies |
| `declining_sector_count` | Number of negative sector proxies |
| `positive_index_count` | Number of positive broad-index proxies |
| `negative_index_count` | Number of negative broad-index proxies |
| `strongest_sector` | Best-performing captured sector proxy |
| `weakest_sector` | Worst-performing captured sector proxy |
| `strongest_index` | Best-performing captured index proxy |
| `weakest_index` | Worst-performing captured index proxy |
| `volatility_proxy` | Current volatility proxy, currently `^VIX` when available |

### `china_mapped_futures`

Each row maps the completed U.S. overnight board into a China-facing futures watchlist.

| Field | Meaning |
| --- | --- |
| `future_code` | Stable machine code such as `methanol` or `industrial_silicon` |
| `future_name` | Chinese display name |
| `watch_direction` | `up`, `down`, or `mixed` |
| `watch_score` | Averaged driver score used for the watch direction |
| `driver_symbols` | Cross-asset symbols used to build the watch row |
| `driver_display_names` | Human-readable names of the driver symbols |
| `driver_summary` | Short Chinese summary of the driver moves |

### `asset_board`

This is the normalized cross-asset board intended for direct reuse by the dashboard, daily-analysis layer, and MMU handoff.

| Field | Meaning |
| --- | --- |
| `analysis_date` | China-morning analysis date |
| `market_date` | Original U.S. market session date |
| `headline` | Compact cross-asset overnight headline |
| `indexes` | Broad-index rows |
| `sectors` | Sector proxy rows |
| `sentiment` | Sentiment/volatility proxy rows |
| `rates_fx` | Rates and FX rows |
| `precious_metals` | Gold/silver rows |
| `energy` | Energy futures rows |
| `industrial_metals` | Industrial-metals rows |
| `china_mapped_futures` | China-facing futures watch rows |
| `key_moves` | Strongest and weakest cross-asset moves |
| `risk_signals` | Reused risk-summary block |

## Current Limitations

- Source is a public vendor endpoint, not an exchange-direct market data contract.
- The snapshot is daily-close oriented and intentionally avoids intraday claims.
- The current layer does not yet persist a multi-version history per day; it upserts one snapshot per `analysis_date + session_name`.
- `capture_status=partial` still returns a valid snapshot when enough instruments were captured to build one.
