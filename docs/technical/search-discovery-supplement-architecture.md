# Search Discovery Supplement Architecture

## Purpose

The overnight project keeps direct collectors as the primary capture path, then uses search discovery as a bounded supplement for blocked or low-yield sources. This is designed for two real-world cases:

1. U.S. official pages with uneven section quality even though same-domain article URLs are discoverable through external search providers.
2. Dynamic market pages that render usable article links poorly in the raw section HTML, while same-domain article URLs are still discoverable through external search providers.

Current product boundary:

1. Do not touch mainland Chinese government, regulator, tax, customs, central-bank, statistics, or ministry websites. This is enforced at both the source-registry layer and the URL-validation layer for enabled sources, search queries, direct collectors, and search-discovery candidates.
2. U.S. official websites are allowed.
3. Selected editorial market sources may also opt in when they are directly tied to result-first bucket gaps and same-domain article URLs remain enforceable.
4. `State/DoD` are not part of the default source surface for this project.

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
   - source-aware required-path rules can require article-like URL families for selected sources, including BLS `news.release/*.nr0.htm` release summaries and IEA `news / commentaries / reports` pages
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
- `AIHUBMIX_API_KEYS`, `AIHUBMIX_API_KEY`
- optional overrides:
  - `AIHUBMIX_BASE_URL`
  - `AIHUBMIX_SEARCH_MODEL`

Behavior:

- Comma/newline/semicolon-separated keys are supported.
- Provider priority is fixed: `SerpAPI -> Bocha -> Tavily -> Brave -> AIHubMix`.
- Failures are logged without leaking request URLs or API keys.
- `AIHubMix` is intentionally last-priority because it is a model-mediated search fallback, not a raw search engine. The current adapter first tries `annotations`, then structured JSON, then markdown-link fallback so it can still feed the existing `SearchDiscoveryResult -> SourceCandidate` contract.

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
- `iea_news`
- `scmp_markets`
- `tradingeconomics_hk`

The intent is not to put every source through search. Only sources with repeated direct-fetch instability, dynamic section rendering, or known low-yield section pages should opt in.

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

## AIHubMix Notes

- Current integration uses the OpenAI-compatible `chat/completions` surface through `AIHubMix`.
- Default model is `gpt-4o-mini:surfing`, which allows the project to reuse AIHubMix-hosted search capability without changing the downstream search-discovery contract.
- Because AIHubMix is model-mediated, the adapter does not trust the raw answer directly. It extracts article candidates in this order:
  1. `annotations`
  2. JSON payload returned by the model
  3. markdown links in the answer body
- same-domain URL filtering, stale-result filtering, weak-path filtering, and article fetch still happen inside the existing project pipeline after extraction.

## Result-First Expansion Notes

- `scmp_markets` and `tradingeconomics_hk` are enabled specifically for the `中国代理` bucket. Their direct section HTML can be reachable while still yielding zero generic article candidates, so they depend on search-discovery for article-level URLs.
- `bls_news_releases` now uses tighter query strings around CPI, PPI, Employment Situation, payrolls, import/export prices, productivity, and real earnings. The path gate accepts only BLS release-summary URLs ending in `.nr0.htm`, while `.toc.htm`, table pages, schedules, and entry pages stay out.
- `iea_news` now searches both `/news` and `/reports` so oil/gas market reports and energy-security updates can feed the `能源运输` bucket when the news index itself is thin. Topic pages remain filtered by source-aware required paths.
- These rules keep source expansion additive: direct collectors still run first, search remains same-domain, and downstream report builders continue to consume ordinary captured candidates with explicit provenance.

## Known Limits

- Some official sites still expose weak search snippets when article fetch is blocked and provider-side extraction is noisy.
- Some market-editorial sites expose section HTML that is technically reachable but still yields zero article candidates for the generic collector, so they currently depend on search supplementation to become useful.
- `Tavily` can still return unstable errors or noisy content on some official-site queries.
- `SerpAPI` quota/rate limiting means it should be treated as the strongest current discovery path, but not as a guaranteed always-on provider.
- Provenance visibility is implemented, but provider health history and per-query audit storage are still not persisted beyond the captured-item fields themselves.

## Operational Guidance

- Keep direct collectors improving; search discovery is a supplement, not the core truth source.
- Prefer same-domain official results over third-party summaries.
- same-domain official results still need source-aware path quality rules before they are treated as article candidates.
- Use live smoke regularly because external site behavior and provider quotas are unstable.
- If a source repeatedly yields noisy search summaries, add a source-specific cleaner or a more targeted query rather than widening the whole pipeline.
