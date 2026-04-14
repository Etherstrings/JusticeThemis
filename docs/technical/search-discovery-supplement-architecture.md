# Search Discovery Supplement Architecture

## Purpose

The overnight project keeps direct official collectors as the primary capture path, then uses search discovery as a bounded supplement for blocked or low-yield official sources. This is designed for the real-world case where U.S. official pages may have uneven section quality even though same-domain article URLs are still discoverable through external search providers.

Current product boundary:

1. Do not touch Chinese government websites.
2. U.S. official websites are allowed.
3. `State/DoD` are not part of the default source surface for this project.

## Runtime Flow

1. `OvernightSourceCaptureService` runs the source's primary collector.
2. If the source opts into search discovery and the primary result set is empty or thin, `SearchDiscoveryService` runs configured search queries.
3. Provider results are normalized into `SourceCandidate`.
4. Candidates are filtered before persistence:
   - same-domain only via `allowed_domains`
   - entry pages excluded
   - binary assets excluded (`.pdf`, `.csv`, `.xls`, `.xlsx`, `.zip`, `.doc`, `.docx`, `.ppt`, `.pptx`)
   - known non-article BLS paths excluded (`.tNN.htm`, `.toc.htm`)
   - source-aware weak-path filters exclude known official-site noise such as `White House gallery/pagination/listing` pages, `USTR node` pages, and `OFAC` category listings
   - source-aware required-path rules can require article-like URL families for selected sources
   - stale results excluded when parseable and older than `max(21, days + 7)`
5. Search summaries are cleaned to remove navigation, cookie, and government-site boilerplate as much as possible.
6. Candidate URLs are deduped canonically before ranking and persistence.
7. Persistence stamps explicit provenance fields: `capture_path`, `capture_provider`, and `article_fetch_status`.
8. Read APIs expose a normalized `capture_provenance` object so frontend and downstream-model handoff consumers can tell whether an item is direct or fallback-derived.
9. The rest of the event clustering and downstream handoff pipeline stays unchanged.

## Provider Injection

`SearchDiscoveryService.from_environment()` reads optional provider keys from the process environment only. It does not depend on another repo or read another project's `.env` file at runtime.

Supported env vars:

- `BOCHA_API_KEYS`, `BOCHA_API_KEY`
- `TAVILY_API_KEYS`, `TAVILY_API_KEY`
- `SERPAPI_API_KEYS`, `SERPAPI_API_KEY`
- `BRAVE_API_KEYS`, `BRAVE_API_KEY`

Behavior:

- Comma/newline/semicolon-separated keys are supported.
- Provider priority is fixed: `SerpAPI -> Bocha -> Tavily -> Brave`.
- Failures are logged without leaking request URLs or API keys.

## Source Opt-In

Two fields were added to `SourceDefinition`:

- `search_discovery_enabled`
- `search_queries`

Currently enabled sources:

- `whitehouse_news`
- `bls_news_releases`
- `treasury_press_releases`
- `ustr_press_releases`
- `doe_articles`
- `ofac_recent_actions`

The intent is not to put every source through search. Only sources with repeated direct-fetch instability or known low-yield section pages should opt in.

## Ranking Rules

Search supplementation does not bypass the existing source ranking. The capture service now also adjusts ranking for search-derived summaries:

- readable, content-like summaries are promoted
- noisy navigation/cookie/menu summaries are penalized
- low-signal titles such as `public schedule` are penalized

This keeps the system from selecting same-domain junk simply because the title matched the query.

## 2026-04-09 Live Smoke Notes

Live smoke was run with local provider env injection using keys available on the machine at command time. Observed provider availability:

- `Bocha`
- `Tavily`
- `SerpAPI`

Observed external-source behavior during the latest live rerun:

- `White House` search produced `4` same-domain results through `Bocha + SerpAPI`
- `USTR / Treasury / OFAC` search produced same-domain results through `SerpAPI`
- `DOE` search currently produced `1` same-domain result through `SerpAPI`
- later `2026-04-10` provider probes confirmed `BIS` still does not have reliable article-level search hits, so it remains disabled for fallback discovery
- `Tavily` returned repeated `http_432` on several official-site queries

Even with partial provider failures, search supplementation still produced same-domain items that were persisted and exposed through the normal API flow.

## Known Limits

- Some official sites still expose weak search snippets when article fetch is blocked and provider-side extraction is noisy.
- `Tavily` can still return unstable errors or noisy content on some official-site queries.
- `SerpAPI` quota/rate limiting means it should be treated as the strongest current discovery path, but not as a guaranteed always-on provider.
- Provenance visibility is implemented, but provider health history and per-query audit storage are still not persisted beyond the captured-item fields themselves.

## Operational Guidance

- Keep direct collectors improving; search discovery is a supplement, not the core truth source.
- Prefer same-domain official results over third-party summaries.
- same-domain official results still need source-aware path quality rules before they are treated as article candidates.
- Use live smoke regularly because external site behavior and provider quotas are unstable.
- If a source repeatedly yields noisy search summaries, add a source-specific cleaner or a more targeted query rather than widening the whole pipeline.
