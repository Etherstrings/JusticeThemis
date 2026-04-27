export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export const ADMIN_ACCESS_HEADER = "X-Admin-Access-Key";
export const PREMIUM_ACCESS_HEADER = "X-Premium-Access-Key";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export type DashboardPayload = {
  generated_at?: string;
  hero?: Record<string, number>;
  lead_signals?: NewsItem[];
  watchlist?: NewsItem[];
  background?: NewsItem[];
  source_health?: {
    total_sources?: number;
    active_sources?: number;
    inactive_sources?: number;
    sources?: SourceSummary[];
  };
  market_board?: Record<string, unknown>;
  mainlines?: AnalysisMainline[];
  market_regimes?: AnalysisRegime[];
  secondary_event_groups?: SecondaryEventGroup[];
};

export type HealthPayload = {
  status?: string;
  service?: string;
};

export type ReadinessPayload = {
  status?: string;
  service?: string;
  database?: Record<string, unknown>;
  runtime?: Record<string, unknown>;
  auth?: Record<string, unknown>;
  features?: Record<string, unknown>;
  source_registry?: Record<string, unknown>;
};

export type NewsListPayload = {
  total?: number;
  returned?: number;
  next_cursor?: string | null;
  current_window_total?: number;
  full_pool_total?: number;
  items?: NewsItem[];
};

export type NewsDetailPayload = {
  item?: NewsItem;
};

export type SourcesPayload = {
  total_sources?: number;
  active_sources?: number;
  inactive_sources?: number;
  sources?: SourceSummary[];
};

export type MarketSnapshotPayload = Record<string, unknown> & {
  analysis_date?: string;
  asset_board?: Record<string, unknown>;
  capture_summary?: Record<string, unknown>;
  market_regimes?: AnalysisRegime[];
};

export type DailyAnalysisPayload = Record<string, unknown> & {
  analysis_date?: string;
  access_tier?: string;
  version?: number;
  mainlines?: AnalysisMainline[];
  market_regimes?: AnalysisRegime[];
  secondary_event_groups?: SecondaryEventGroup[];
  narratives?: Record<string, unknown>;
  headline_news?: Array<Record<string, unknown>>;
  direction_calls?: Array<Record<string, unknown>>;
  stock_calls?: Array<Record<string, unknown>>;
};

export type DailyVersionsPayload = {
  analysis_date?: string;
  access_tier?: string;
  versions?: Array<{
    version: number;
    created_at?: string | null;
    input_fingerprint?: string;
    report_fingerprint?: string;
  }>;
};

export type RefreshPayload = Record<string, unknown>;
export type GenerateAnalysisPayload = Record<string, unknown>;

export type NewsItem = Record<string, unknown> & {
  item_id?: number;
  source_id?: string;
  source_name?: string;
  title?: string;
  summary?: string;
  canonical_url?: string;
  coverage_tier?: string;
  published_at_display?: string;
  published_at?: string;
  analysis_status?: string;
  a_share_relevance?: string;
  impact_summary?: string;
  why_it_matters_cn?: string;
  entities?: Array<{ name?: string }>;
  numeric_facts?: Array<{
    metric?: string;
    value?: number;
    unit?: string;
    subject?: string | null;
  }>;
  policy_actions?: string[];
  uncertainties?: string[];
  follow_up_checks?: string[];
};

export type SourceSummary = Record<string, unknown> & {
  source_id?: string;
  source_name?: string;
  coverage_tier?: string;
  operational_status?: string;
  item_count?: number;
  ready_count?: number;
  review_count?: number;
  background_count?: number;
  latest_title?: string | null;
  latest_published_at?: string | null;
};

export type AnalysisMainline = Record<string, unknown> & {
  mainline_id?: string;
  title?: string;
  summary?: string;
  direction?: string;
  confidence?: string;
};

export type AnalysisRegime = Record<string, unknown> & {
  regime_id?: string;
  title?: string;
  summary?: string;
  stance?: string;
};

export type SecondaryEventGroup = Record<string, unknown> & {
  cluster_id?: string;
  title?: string;
  summary?: string;
};

type RequestOptions = {
  method?: string;
  params?: Record<string, string | number | boolean | undefined | null>;
  adminKey?: string;
  premiumKey?: string;
  body?: unknown;
};

function toUrl(path: string, params?: RequestOptions["params"]): string {
  const url = new URL(path, `${API_BASE_URL}/`);
  if (!params) {
    return url.toString();
  }
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers();
  headers.set("Accept", "application/json");
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.adminKey?.trim()) {
    headers.set(ADMIN_ACCESS_HEADER, options.adminKey.trim());
  }
  if (options.premiumKey?.trim()) {
    headers.set(PREMIUM_ACCESS_HEADER, options.premiumKey.trim());
  }

  const response = await fetch(toUrl(path, options.params), {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail?: string }).detail ?? response.statusText)
        : response.statusText;
    throw new ApiError(detail || "Request failed", response.status, payload);
  }
  return payload as T;
}

export async function fetchDashboard(): Promise<DashboardPayload> {
  return requestJson<DashboardPayload>("/api/v1/dashboard");
}

export async function fetchHealthz(): Promise<HealthPayload> {
  return requestJson<HealthPayload>("/healthz");
}

export async function fetchReadyz(adminKey?: string): Promise<ReadinessPayload> {
  return requestJson<ReadinessPayload>("/readyz", { adminKey });
}

export async function fetchNews(params: RequestOptions["params"]): Promise<NewsListPayload> {
  return requestJson<NewsListPayload>("/api/v1/news", { params });
}

export async function fetchNewsItem(itemId: number): Promise<NewsDetailPayload> {
  return requestJson<NewsDetailPayload>(`/api/v1/news/${itemId}`);
}

export async function fetchSources(): Promise<SourcesPayload> {
  return requestJson<SourcesPayload>("/api/v1/sources");
}

export async function fetchMarketSnapshot(params: RequestOptions["params"]): Promise<MarketSnapshotPayload> {
  return requestJson<MarketSnapshotPayload>("/api/v1/market/us/daily", { params });
}

export async function fetchDailyAnalysis(params: RequestOptions["params"], premiumKey?: string): Promise<DailyAnalysisPayload> {
  return requestJson<DailyAnalysisPayload>("/api/v1/analysis/daily", { params, premiumKey });
}

export async function fetchDailyVersions(
  params: RequestOptions["params"],
  premiumKey?: string,
): Promise<DailyVersionsPayload> {
  return requestJson<DailyVersionsPayload>("/api/v1/analysis/daily/versions", { params, premiumKey });
}

export async function refreshSources(adminKey: string): Promise<RefreshPayload> {
  return requestJson<RefreshPayload>("/refresh", { method: "POST", adminKey });
}

export async function generateDailyAnalysis(adminKey: string): Promise<GenerateAnalysisPayload> {
  return requestJson<GenerateAnalysisPayload>("/api/v1/analysis/daily/generate", {
    method: "POST",
    adminKey,
  });
}

export async function refreshMarketSnapshot(adminKey: string): Promise<RefreshPayload> {
  return requestJson<RefreshPayload>("/api/v1/market/us/refresh", { method: "POST", adminKey });
}

export async function updateIFindToken(adminKey: string, token: string): Promise<{ status: string; message: string }> {
  return requestJson<{ status: string; message: string }>("/api/v1/config/ifind", {
    method: "POST",
    adminKey,
    body: { token },
  });
}
