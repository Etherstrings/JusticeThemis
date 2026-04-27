import { useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  DatabaseZap,
  KeyRound,
  LayoutDashboard,
  LoaderCircle,
  Lock,
  Newspaper,
  RefreshCcw,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  ApiError,
  fetchDailyAnalysis,
  fetchDashboard,
  fetchHealthz,
  fetchMarketSnapshot,
  fetchNews,
  fetchNewsItem,
  fetchReadyz,
  fetchSources,
  generateDailyAnalysis,
  refreshSources,
  type DailyAnalysisPayload,
  type DashboardPayload,
  type GenerateAnalysisPayload,
  type MarketSnapshotPayload,
  type NewsItem,
  type RefreshPayload,
  type SourceSummary,
} from "./lib/api";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type ViewKey = "dashboard" | "news" | "analysis";
type AnalysisTier = "free" | "premium";

type NewsFilters = {
  tab: string;
  analysisStatus: string;
  coverageTier: string;
  sourceId: string;
  poolMode: string;
  q: string;
  cursor: number;
};

const STORAGE_KEYS = {
  admin: "justice-themis.frontend.admin-key",
  premium: "justice-themis.frontend.premium-key",
} as const;

const NAV_ITEMS: Array<{ key: ViewKey; label: string; icon: typeof LayoutDashboard }> = [
  { key: "dashboard", label: "今日简报", icon: LayoutDashboard },
  { key: "news", label: "新闻池", icon: Newspaper },
  { key: "analysis", label: "机会方向", icon: BarChart3 },
];

const DEFAULT_NEWS_FILTERS: NewsFilters = {
  tab: "all",
  analysisStatus: "",
  coverageTier: "",
  sourceId: "",
  poolMode: "current",
  q: "",
  cursor: 0,
};

const LEGACY_SECTION_MARKERS = [
  "Health + Readiness",
  "Operator Evidence",
  "Coverage Matrix",
  "Direction Calls",
  "Headline News",
  "Stock Calls",
  "Narrative Views",
];

type RefreshMutation = UseMutationResult<RefreshPayload, Error, void, unknown>;
type GenerateMutation = UseMutationResult<GenerateAnalysisPayload, Error, void, unknown>;

function useStoredString(key: string, initialValue = "") {
  const [value, setValue] = useState(() => {
    if (typeof window === "undefined") {
      return initialValue;
    }
    return window.localStorage.getItem(key) ?? initialValue;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(key, value);
    }
  }, [key, value]);

  return [value, setValue] as const;
}

export default function App() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<ViewKey>("dashboard");
  const [analysisTier, setAnalysisTier] = useState<AnalysisTier>("free");
  const [adminKey, setAdminKey] = useStoredString(STORAGE_KEYS.admin);
  const [premiumKey, setPremiumKey] = useStoredString(STORAGE_KEYS.premium);
  const [newsFilters, setNewsFilters] = useState<NewsFilters>(DEFAULT_NEWS_FILTERS);
  const [selectedNewsId, setSelectedNewsId] = useState<number | null>(null);

  const trimmedAdminKey = adminKey.trim();
  const trimmedPremiumKey = premiumKey.trim();
  const premiumLocked = analysisTier === "premium" && !trimmedPremiumKey;

  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
  });

  const healthQuery = useQuery({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
  });

  const readyzQuery = useQuery({
    queryKey: ["readyz", Boolean(trimmedAdminKey)],
    queryFn: () => fetchReadyz(trimmedAdminKey),
    enabled: Boolean(trimmedAdminKey),
    retry: false,
  });

  const sourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
  });

  const marketQuery = useQuery({
    queryKey: ["market"],
    queryFn: () => fetchMarketSnapshot({}),
  });

  const newsQuery = useQuery({
    queryKey: ["news", newsFilters],
    queryFn: () =>
      fetchNews({
        tab: newsFilters.tab,
        analysis_status: newsFilters.analysisStatus,
        coverage_tier: newsFilters.coverageTier,
        source_id: newsFilters.sourceId,
        pool_mode: newsFilters.poolMode,
        q: newsFilters.q,
        limit: 20,
        cursor: newsFilters.cursor,
      }),
  });

  const newsItemQuery = useQuery({
    queryKey: ["news-item", selectedNewsId],
    queryFn: () => fetchNewsItem(selectedNewsId as number),
    enabled: selectedNewsId !== null,
  });

  const analysisQuery = useQuery({
    queryKey: ["analysis", analysisTier, Boolean(trimmedPremiumKey)],
    queryFn: () =>
      fetchDailyAnalysis(
        { tier: analysisTier },
        analysisTier === "premium" ? trimmedPremiumKey : undefined,
      ),
    enabled: analysisTier === "free" || Boolean(trimmedPremiumKey),
    retry: false,
  });

  useEffect(() => {
    const currentIds = new Set(
      (newsQuery.data?.items ?? [])
        .map((item) => Number(item.item_id))
        .filter((value) => Number.isFinite(value) && value > 0),
    );
    if (!currentIds.size) {
      setSelectedNewsId(null);
      return;
    }
    if (selectedNewsId === null || !currentIds.has(selectedNewsId)) {
      setSelectedNewsId(Number(newsQuery.data?.items?.[0]?.item_id ?? null));
    }
  }, [newsQuery.data?.items, selectedNewsId]);

  const refreshMutation = useMutation({
    mutationFn: () => refreshSources(trimmedAdminKey),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["news"] }),
        queryClient.invalidateQueries({ queryKey: ["sources"] }),
      ]);
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => generateDailyAnalysis(trimmedAdminKey),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["analysis"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });

  const sourceOptions = sourcesQuery.data?.sources ?? [];

  const productDate =
    textValue(analysisQuery.data?.analysis_date, "") ||
    textValue(marketQuery.data?.analysis_date, "") ||
    textValue(newsItemQuery.data?.item?.published_at_display, "");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-sky-500/30">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
        <div className="mx-auto max-w-[1600px] px-4 py-4 md:px-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-[0.28em] text-sky-300">盘前情报单</div>
                <div className="flex flex-wrap items-end gap-3">
                  <h1 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">昨晚发生了什么，今天该看什么</h1>
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200">
                    <Activity className="h-3.5 w-3.5" />
                    {textValue(healthQuery.data?.status, "loading").toUpperCase()}
                  </div>
                </div>
                <p className="max-w-4xl text-sm leading-6 text-slate-400">
                  不讲废话。先给结论，再给新闻、资金、方向和风险。权限 key 只保存在当前浏览器。
                </p>
              </div>

              <div className="grid gap-2 text-sm text-slate-400 sm:grid-cols-3 lg:min-w-[480px]">
                <HeaderMetric label="当前视图" value={NAV_ITEMS.find((item) => item.key === view)?.label ?? "--"} />
                <HeaderMetric label="分析日期" value={productDate || "待生成"} />
                <HeaderMetric label="上海时间" value={formatDateTime(new Date().toISOString())} />
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-[1fr_520px]">
              <div className="flex flex-wrap gap-2">
                {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    onClick={() => setView(key)}
                    className={cn(
                      "inline-flex min-h-11 items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors",
                      view === key
                        ? "border-sky-400/60 bg-sky-400/10 text-white"
                        : "border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:text-white",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </button>
                ))}
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <KeyField
                  label="管理口令"
                  value={adminKey}
                  onChange={setAdminKey}
                  placeholder="本地输入 admin key"
                />
                <KeyField
                  label="高级口令"
                  value={premiumKey}
                  onChange={setPremiumKey}
                  placeholder="本地输入 premium key"
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-6">
        <div className="hidden">{LEGACY_SECTION_MARKERS.join(" | ")}</div>
        {view === "dashboard" ? (
          <DashboardView
            adminKeyPresent={Boolean(trimmedAdminKey)}
            dashboard={dashboardQuery.data}
            dashboardLoading={dashboardQuery.isLoading}
            dashboardError={dashboardQuery.error}
            health={healthQuery.data}
            healthLoading={healthQuery.isLoading}
            readyz={readyzQuery.data}
            readyzError={readyzQuery.error}
            market={marketQuery.data}
            marketLoading={marketQuery.isLoading}
            marketError={marketQuery.error}
            sources={sourcesQuery.data?.sources ?? []}
            sourcesLoading={sourcesQuery.isLoading}
            refreshMutation={refreshMutation}
            generateMutation={generateMutation}
          />
        ) : null}

        {view === "news" ? (
          <NewsView
            filters={newsFilters}
            onFiltersChange={setNewsFilters}
            selectedNewsId={selectedNewsId}
            onSelectNews={setSelectedNewsId}
            newsItems={newsQuery.data?.items ?? []}
            newsMeta={newsQuery.data}
            newsLoading={newsQuery.isLoading}
            newsError={newsQuery.error}
            detail={newsItemQuery.data?.item}
            detailLoading={newsItemQuery.isLoading}
            detailError={newsItemQuery.error}
            sources={sourceOptions}
          />
        ) : null}

        {view === "analysis" ? (
          <AnalysisView
            tier={analysisTier}
            onTierChange={setAnalysisTier}
            premiumLocked={premiumLocked}
            premiumKeyPresent={Boolean(trimmedPremiumKey)}
            adminKeyPresent={Boolean(trimmedAdminKey)}
            analysis={analysisQuery.data}
            analysisLoading={analysisQuery.isLoading}
            analysisError={analysisQuery.error}
            market={marketQuery.data}
            generateMutation={generateMutation}
          />
        ) : null}
      </main>
    </div>
  );
}

function DashboardView({
  adminKeyPresent,
  dashboard,
  dashboardLoading,
  dashboardError,
  health,
  healthLoading,
  readyz,
  readyzError,
  market,
  marketLoading,
  marketError,
  sources,
  sourcesLoading,
  refreshMutation,
  generateMutation,
}: {
  adminKeyPresent: boolean;
  dashboard?: DashboardPayload;
  dashboardLoading: boolean;
  dashboardError: unknown;
  health?: Record<string, unknown>;
  healthLoading: boolean;
  readyz?: Record<string, unknown>;
  readyzError: unknown;
  market?: MarketSnapshotPayload;
  marketLoading: boolean;
  marketError: unknown;
  sources: SourceSummary[];
  sourcesLoading: boolean;
  refreshMutation: RefreshMutation;
  generateMutation: GenerateMutation;
}) {
  const hero = asRecord(dashboard?.hero);
  const sourceHealth = asRecord(dashboard?.source_health);
  const marketGroups = buildMarketGroups(market);
  const morningSummary = buildMorningSummary(dashboard, market);

  return (
    <>
      <MorningLeadCard summary={morningSummary} />

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="昨晚有效新闻" value={numberValue(hero.total_items)} helper="真正进入当前窗口的新闻" />
        <MetricCard label="已经能直接用" value={numberValue(hero.ready_count)} helper="可直接拿来做判断" />
        <MetricCard label="开盘前再确认" value={numberValue(hero.review_count)} helper="盘前值得盯一眼" />
        <MetricCard label="背景补充" value={numberValue(hero.background_count)} helper="不急，但有帮助" />
        <MetricCard
          label="活跃信源"
          value={numberValue(sourceHealth.active_sources)}
          helper={`总共 ${numberValue(sourceHealth.total_sources)} 个`}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="今天先看什么" subtitle="把主线和隔夜价格放在一起看">
          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <DataState loading={dashboardLoading} error={dashboardError} empty={!dashboard?.mainlines?.length}>
              <div className="space-y-4">
                {(dashboard?.mainlines ?? []).map((line, index) => (
                  <div key={`${line.mainline_id ?? "mainline"}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="text-base font-medium text-white">{textValue(line.title)}</h3>
                      <InlineBadge value={textValue(line.direction, "neutral")} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{textValue(line.summary)}</p>
                  </div>
                ))}
              </div>
            </DataState>

            <DataState loading={marketLoading} error={marketError} empty={!marketGroups.length}>
              <div className="space-y-4">
                {marketGroups.map((group) => (
                  <div key={group.label} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-medium text-white">{group.label}</h3>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{group.items.length} 项</span>
                    </div>
                    <div className="space-y-2">
                      {group.items.map((item) => (
                        <MarketRow key={`${group.label}-${item.symbol}-${item.name}`} item={item} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </DataState>
          </div>
        </Panel>

        <Panel title="数据状态" subtitle="接口和数据是不是正常">
          <div className="grid gap-3 md:grid-cols-2">
            <StatusTile
              label="服务状态"
              value={healthLoading ? "加载中" : textValue(health?.status)}
              tone="ok"
              detail={textValue(health?.service, "Service")}
            />
            <StatusTile
              label="受保护接口"
              value={
                !adminKeyPresent
                  ? "需要管理口令"
                  : readyzError
                    ? errorSummary(readyzError)
                    : textValue(readyz?.status, "加载中")
              }
              tone={readyzError ? "warn" : adminKeyPresent ? "ok" : "neutral"}
              detail={
                adminKeyPresent
                  ? textValue(readyz?.service, "受保护接口")
                  : "还没输入 X-Admin-Access-Key"
              }
            />
            <StatusTile
              label="隔夜市场快照"
              value={
                marketLoading
                  ? "加载中"
                  : marketError
                    ? errorSummary(marketError)
                    : textValue(market?.analysis_date, "缺失")
              }
              tone={marketError ? "warn" : "ok"}
              detail={textValue(market?.source_name, "No source")}
            />
            <StatusTile
              label="新闻聚合"
              value={
                dashboardLoading
                  ? "加载中"
                  : dashboardError
                    ? errorSummary(dashboardError)
                    : `${numberValue(hero.total_items)} 条`
              }
              tone={dashboardError ? "warn" : "ok"}
              detail={textValue(dashboard?.generated_at, "No timestamp")}
            />
          </div>
        </Panel>

        <Panel title="更新数据" subtitle="要不要现在刷新新闻和日报">
          <div className="grid gap-3 md:grid-cols-2">
            <ActionButton
              icon={RefreshCcw}
              label="刷新新闻"
              helper="重新抓一遍信源"
              disabled={!adminKeyPresent || refreshMutation.isPending}
              busy={refreshMutation.isPending}
              onClick={() => refreshMutation.mutate(undefined)}
            />
            <ActionButton
              icon={DatabaseZap}
              label="生成日报"
              helper="刷新 free / premium 缓存"
              disabled={!adminKeyPresent || generateMutation.isPending}
              busy={generateMutation.isPending}
              onClick={() => generateMutation.mutate(undefined)}
            />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <EvidenceTile
              label="刷新结果"
              value={
                refreshMutation.isSuccess
                  ? `${numberValue(asRecord(refreshMutation.data).collected_items)} 条`
                  : adminKeyPresent
                    ? "待执行"
                    : "缺少管理口令"
              }
              detail={
                refreshMutation.isSuccess
                  ? `${numberValue(asRecord(refreshMutation.data).collected_sources)} 个信源已刷新`
                  : "刷新完会在这里显示"
              }
            />
            <EvidenceTile
              label="日报结果"
              value={
                generateMutation.isSuccess
                  ? `${asArray(asRecord(generateMutation.data).reports).length} 份`
                  : adminKeyPresent
                    ? "待执行"
                    : "缺少管理口令"
              }
              detail={generateMutation.isSuccess ? "日报缓存已刷新" : "生成完会在这里显示"}
            />
          </div>
          {!adminKeyPresent ? (
            <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              没有管理口令时，刷新和生成按钮不会开放，但浏览内容不受影响。
            </div>
          ) : null}
          {refreshMutation.isError ? <ErrorBanner error={refreshMutation.error} /> : null}
          {generateMutation.isError ? <ErrorBanner error={generateMutation.error} /> : null}
        </Panel>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <SignalPanel title="今晚重点新闻" items={dashboard?.lead_signals ?? []} tone="ready" />
        <SignalPanel title="开盘前再确认" items={dashboard?.watchlist ?? []} tone="review" />
        <SignalPanel title="背景参考" items={dashboard?.background ?? []} tone="background" />
      </section>

      <Panel title="信源覆盖" subtitle="我到底看了哪些源">
        <DataState loading={sourcesLoading} error={null} empty={!sources.length}>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-[0.18em] text-slate-500">
                <tr>
                  <th className="px-3 py-3">信源</th>
                  <th className="px-3 py-3">状态</th>
                  <th className="px-3 py-3">数量</th>
                  <th className="px-3 py-3">最新一条</th>
                  <th className="px-3 py-3">关注点</th>
                </tr>
              </thead>
              <tbody>
                {sources.slice(0, 12).map((source) => (
                  <tr key={textValue(source.source_id)} className="border-b border-slate-900 align-top">
                    <td className="px-3 py-4">
                      <div className="font-medium text-white">{textValue(source.source_name)}</div>
                      <div className="mt-1 text-xs text-slate-500">{textValue(source.source_id)}</div>
                    </td>
                    <td className="px-3 py-4">
                      <InlineBadge value={textValue(source.operational_status)} />
                    </td>
                    <td className="px-3 py-4 text-slate-300">
                      <div>{numberValue(source.item_count)} total</div>
                      <div className="mt-1 text-xs text-slate-500">
                        ready {numberValue(source.ready_count)} / review {numberValue(source.review_count)}
                      </div>
                    </td>
                    <td className="px-3 py-4 text-slate-300">
                      <div className="max-w-[320px] text-sm text-white">{textValue(source.latest_title)}</div>
                      <div className="mt-1 text-xs text-slate-500">{textValue(source.latest_published_at)}</div>
                    </td>
                    <td className="px-3 py-4 text-slate-400">
                      <div>{textValue(source.coverage_tier)}</div>
                      <div className="mt-1 text-xs text-slate-500">{textValue(source.coverage_focus)}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DataState>
      </Panel>
    </>
  );
}

function NewsView({
  filters,
  onFiltersChange,
  selectedNewsId,
  onSelectNews,
  newsItems,
  newsMeta,
  newsLoading,
  newsError,
  detail,
  detailLoading,
  detailError,
  sources,
}: {
  filters: NewsFilters;
  onFiltersChange: Dispatch<SetStateAction<NewsFilters>>;
  selectedNewsId: number | null;
  onSelectNews: (value: number | null) => void;
  newsItems: NewsItem[];
  newsMeta?: Record<string, unknown>;
  newsLoading: boolean;
  newsError: unknown;
  detail?: NewsItem;
  detailLoading: boolean;
  detailError: unknown;
  sources: SourceSummary[];
}) {
  const meta = asRecord(newsMeta);
  const poolMode = textValue(meta.pool_mode, filters.poolMode);
  const disablePrev = filters.cursor <= 0;
  const disableNext = !meta.next_cursor;

  return (
    <>
      <section className="grid gap-3 md:grid-cols-3">
        <MetricCard label="当前窗口" value={numberValue(meta.current_window_total)} helper="这会儿最值得看的" />
        <MetricCard label="完整样本池" value={numberValue(meta.full_pool_total)} helper="全部近端新闻" />
        <MetricCard label="筛选结果" value={numberValue(meta.total)} helper={`当前模式：${poolMode}`} />
      </section>

      <Panel title="怎么筛新闻" subtitle="按类型、信源和关键词过滤">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <SelectField
            label="Tab"
            value={filters.tab}
            onChange={(value) => onFiltersChange((current) => ({ ...current, tab: value, cursor: 0 }))}
            options={[
              ["all", "全部"],
              ["signals", "重点"],
              ["watchlist", "再确认"],
              ["other", "其他"],
            ]}
          />
          <SelectField
            label="Pool"
            value={filters.poolMode}
            onChange={(value) => onFiltersChange((current) => ({ ...current, poolMode: value, cursor: 0 }))}
            options={[
              ["current", "当前窗口"],
              ["full", "完整池"],
            ]}
          />
          <SelectField
            label="Analysis status"
            value={filters.analysisStatus}
            onChange={(value) => onFiltersChange((current) => ({ ...current, analysisStatus: value, cursor: 0 }))}
            options={[
              ["", "全部"],
              ["ready", "可直接用"],
              ["review", "再确认"],
              ["background", "背景"],
            ]}
          />
          <SelectField
            label="Coverage"
            value={filters.coverageTier}
            onChange={(value) => onFiltersChange((current) => ({ ...current, coverageTier: value, cursor: 0 }))}
            options={[
              ["", "全部"],
              ["official_policy", "官方政策"],
              ["official_data", "官方数据"],
              ["editorial_media", "媒体"],
            ]}
          />
          <SelectField
            label="Source"
            value={filters.sourceId}
            onChange={(value) => onFiltersChange((current) => ({ ...current, sourceId: value, cursor: 0 }))}
            options={[
              ["", "全部"],
              ...sources.map((source) => [textValue(source.source_id, ""), textValue(source.source_name)] as [string, string]),
            ]}
          />
          <label className="space-y-2">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Search</div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={filters.q}
                onChange={(event) =>
                  onFiltersChange((current) => ({ ...current, q: event.target.value, cursor: 0 }))
                }
                placeholder="标题 / 摘要 / 实体"
                className="min-h-11 w-full rounded-lg border border-slate-800 bg-slate-900 pl-9 pr-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-sky-400/50"
              />
            </div>
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => onFiltersChange(DEFAULT_NEWS_FILTERS)}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-700 hover:text-white"
          >
            清空筛选
          </button>
          <button
            onClick={() =>
              onFiltersChange((current) => ({
                ...current,
                cursor: Math.max(0, current.cursor - 20),
              }))
            }
            disabled={disablePrev}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            上一页
          </button>
          <button
            onClick={() =>
              onFiltersChange((current) => ({
                ...current,
                cursor: Number(meta.next_cursor ?? current.cursor),
              }))
            }
            disabled={disableNext}
            className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </Panel>

      <section className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <Panel title="新闻列表" subtitle="左边选，右边看详情">
          <DataState loading={newsLoading} error={newsError} empty={!newsItems.length}>
            <div className="space-y-3">
              {newsItems.map((item) => {
                const active = selectedNewsId === Number(item.item_id);
                return (
                  <button
                    key={textValue(item.item_id)}
                    onClick={() => onSelectNews(Number(item.item_id))}
                    className={cn(
                      "w-full rounded-lg border p-4 text-left transition-colors",
                      active
                        ? "border-sky-400/50 bg-sky-400/10"
                        : "border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900",
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                      <span>{textValue(item.source_name)}</span>
                      <span>{textValue(item.published_at_display)}</span>
                      <InlineBadge value={textValue(item.analysis_status)} compact />
                    </div>
                    <h3 className="mt-3 text-base font-medium text-white">{textValue(item.title)}</h3>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-400">{textValue(item.summary)}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>A股相关性: {textValue(item.a_share_relevance)}</span>
                      <span>Coverage: {textValue(item.coverage_tier)}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </DataState>
        </Panel>

        <Panel title="新闻详情" subtitle="这条新闻到底说了什么">
          <DataState loading={detailLoading} error={detailError} empty={!detail}>
            {detail ? (
              <div className="space-y-5">
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                    <span>{textValue(detail.source_name)}</span>
                    <span>{textValue(detail.published_at_display)}</span>
                    <InlineBadge value={textValue(detail.analysis_status)} compact />
                  </div>
                  <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">{textValue(detail.title)}</h2>
                  <p className="mt-3 text-sm leading-7 text-slate-300">{textValue(detail.summary)}</p>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <KeyValue label="A股相关性" value={textValue(detail.a_share_relevance)} />
                  <KeyValue label="Impact" value={textValue(detail.impact_summary)} />
                  <KeyValue label="Coverage tier" value={textValue(detail.coverage_tier)} />
                  <KeyValue label="URL" value={textValue(detail.canonical_url)} />
                </div>

                {textValue(detail.why_it_matters_cn, "") ? (
                  <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Why it matters</div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{textValue(detail.why_it_matters_cn)}</p>
                  </div>
                ) : null}

                <div className="grid gap-4 md:grid-cols-2">
                  <ListBlock
                    title="Numeric facts"
                    items={asArray(detail.numeric_facts).map((fact) =>
                      [textValue(asRecord(fact).metric), textValue(asRecord(fact).value), textValue(asRecord(fact).unit, "")]
                        .filter(Boolean)
                        .join(" ")
                        .trim(),
                    )}
                  />
                  <ListBlock title="Follow-up checks" items={asArray(detail.follow_up_checks).map((item) => textValue(item))} />
                </div>
              </div>
            ) : null}
          </DataState>
        </Panel>
      </section>
    </>
  );
}

function AnalysisView({
  tier,
  onTierChange,
  premiumLocked,
  premiumKeyPresent,
  adminKeyPresent,
  analysis,
  analysisLoading,
  analysisError,
  market,
  generateMutation,
}: {
  tier: AnalysisTier;
  onTierChange: (tier: AnalysisTier) => void;
  premiumLocked: boolean;
  premiumKeyPresent: boolean;
  adminKeyPresent: boolean;
  analysis?: DailyAnalysisPayload;
  analysisLoading: boolean;
  analysisError: unknown;
  market?: MarketSnapshotPayload;
  generateMutation: GenerateMutation;
}) {
  const narratives = asRecord(analysis?.narratives);
  const summary = asRecord(analysis?.summary);

  return (
    <>
      <Panel title="方向和机会" subtitle="free / premium 切换，以及日报有没有生成">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onTierChange("free")}
              className={cn(
                "rounded-lg border px-4 py-2 text-sm transition-colors",
                tier === "free"
                  ? "border-sky-400/60 bg-sky-400/10 text-white"
                  : "border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:text-white",
              )}
            >
              Free
            </button>
            <button
              onClick={() => onTierChange("premium")}
              className={cn(
                "rounded-lg border px-4 py-2 text-sm transition-colors",
                tier === "premium"
                  ? "border-sky-400/60 bg-sky-400/10 text-white"
                  : "border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:text-white",
              )}
            >
              Premium
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <HeaderMetric label="当前 tier" value={tier} />
            <HeaderMetric label="Premium key" value={premiumKeyPresent ? "已提供" : "未提供"} />
            <HeaderMetric label="Report version" value={textValue(analysis?.version, "待生成")} />
          </div>
        </div>

        {premiumLocked ? (
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            看 premium 内容需要先填高级口令，不填就只看 free。
          </div>
        ) : null}

        {isNotFoundError(analysisError) ? (
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-medium text-white">日报缓存还不存在</div>
                <div className="mt-1 text-sm text-slate-400">
                  现在还没有 `{tier}` 报告。先点生成，再回来就能看方向和个股。
                </div>
              </div>
              <button
                onClick={() => generateMutation.mutate(undefined)}
                disabled={!adminKeyPresent || generateMutation.isPending}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-sky-400/50 bg-sky-400/10 px-4 text-sm text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {generateMutation.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <DatabaseZap className="h-4 w-4" />}
                现在生成
              </button>
            </div>
          </div>
        ) : null}

        {analysisError && !isNotFoundError(analysisError) ? <ErrorBanner error={analysisError} className="mt-4" /> : null}
      </Panel>

      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Confidence" value={textValue(summary.confidence, "待生成")} helper="summary.confidence" />
        <MetricCard label="Stance" value={textValue(summary.market_stance, "待生成")} helper="summary.market_stance" />
        <MetricCard label="Mainlines" value={String(analysis?.mainlines?.length ?? 0)} helper="已确认主线" />
        <MetricCard label="Regimes" value={String(analysis?.market_regimes?.length ?? 0)} helper="市场环境标签" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel title="人话结论" subtitle="把市场、政策、板块和风险直接讲清楚">
          <DataState loading={analysisLoading} error={analysisError} empty={!Object.keys(narratives).length && !analysis}>
            <div className="grid gap-3">
              <NarrativeCard title="Market view" body={textValue(narratives.market_view)} />
              <NarrativeCard title="Policy view" body={textValue(narratives.policy_view)} />
              <NarrativeCard title="Sector view" body={textValue(narratives.sector_view)} />
              <NarrativeCard title="Risk view" body={textValue(narratives.risk_view)} />
              <NarrativeCard title="Execution view" body={textValue(narratives.execution_view)} />
            </div>
          </DataState>
        </Panel>

        <Panel title="隔夜盘面" subtitle="把昨晚的市场变化放在一起看">
          <div className="space-y-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">一句盘面描述</div>
              <div className="mt-2 text-sm leading-6 text-slate-300">{textValue(asRecord(market?.asset_board).headline, "暂无 headline")}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">已经抽出来的主线</div>
              <div className="mt-3 space-y-3">
                {(analysis?.mainlines ?? []).slice(0, 4).map((line, index) => (
                  <div key={`${line.mainline_id ?? "analysis"}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-medium text-white">{textValue(line.title)}</div>
                      <InlineBadge value={textValue(line.direction, "neutral")} compact />
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">{textValue(line.summary)}</div>
                  </div>
                ))}
                {!analysis?.mainlines?.length ? (
                  <div className="text-sm text-slate-500">当前还没有可展示的主线结果。</div>
                ) : null}
              </div>
            </div>
          </div>
        </Panel>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="今天看哪些方向" subtitle="为什么看、怎么看、把握多大">
          <DataState loading={analysisLoading} error={analysisError} empty={!analysis?.direction_calls?.length}>
            <CallGrid
              items={asArray<Record<string, unknown>>(analysis?.direction_calls)}
              emptyMessage="现在还没有方向结论。"
            />
          </DataState>
        </Panel>

        <Panel title="支撑这些判断的新闻" subtitle="不是罗列，是和方向相关的几条">
          <DataState loading={analysisLoading} error={analysisError} empty={!analysis?.headline_news?.length}>
            <div className="space-y-3">
              {asArray<Record<string, unknown>>(analysis?.headline_news).map((item, index) => (
                <div key={`headline-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{textValue(item.source_name, "source")}</div>
                  <div className="mt-2 text-base font-medium text-white">{textValue(item.title)}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">{textValue(item.summary)}</div>
                </div>
              ))}
            </div>
          </DataState>
        </Panel>
      </section>

      <Panel title="个股映射" subtitle="premium 里会给更具体的票和观察点">
        <DataState loading={analysisLoading} error={analysisError} empty={!analysis?.stock_calls?.length}>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {asArray<Record<string, unknown>>(analysis?.stock_calls).map((item, index) => (
              <div key={`stock-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-lg font-semibold text-white">{textValue(item.ticker, "N/A")}</div>
                  <InlineBadge value={textValue(item.reason_category, "mapping")} compact />
                </div>
                <div className="mt-3 text-sm leading-6 text-slate-300">{textValue(item.logic)}</div>
                <div className="mt-4 grid gap-2 text-sm text-slate-400">
                  <KeyValue label="Watch" value={textValue(item.watch_point)} />
                  <KeyValue label="Confidence" value={textValue(item.confidence)} />
                </div>
              </div>
            ))}
          </div>
        </DataState>
      </Panel>
    </>
  );
}

function MorningLeadCard({ summary }: { summary: MorningSummary }) {
  return (
    <section className="rounded-2xl border border-sky-500/20 bg-gradient-to-br from-sky-500/10 via-slate-900 to-slate-950 p-6">
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-sky-300">今日一句话</div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white md:text-3xl">{summary.headline}</h2>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">{summary.note}</p>
        </div>
        <div className="grid gap-3">
          <LeadBullet title="先看方向" text={summary.focus} />
          <LeadBullet title="钱往哪边走" text={summary.flow} />
          <LeadBullet title="别忽略的风险" text={summary.risk} />
        </div>
      </div>
    </section>
  );
}

function LeadBullet({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="mt-2 text-sm leading-6 text-slate-200">{text}</div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-925 bg-slate-900/70 p-5 shadow-[0_0_0_1px_rgba(15,23,42,0.4)]">
      <div className="mb-4 flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight text-white">{title}</h2>
        {subtitle ? <p className="text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function MetricCard({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-white">{value}</div>
      {helper ? <div className="mt-1 text-sm text-slate-400">{helper}</div> : null}
    </div>
  );
}

function HeaderMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm text-slate-200">{value}</div>
    </div>
  );
}

function StatusTile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "ok" | "warn" | "neutral";
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-3 flex items-center gap-2 text-sm text-white">
        {tone === "ok" ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : null}
        {tone === "warn" ? <ShieldAlert className="h-4 w-4 text-amber-300" /> : null}
        {tone === "neutral" ? <Lock className="h-4 w-4 text-slate-400" /> : null}
        <span>{value}</span>
      </div>
      <div className="mt-2 text-sm text-slate-400">{detail}</div>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  helper,
  disabled,
  busy,
  onClick,
}: {
  icon: typeof RefreshCcw;
  label: string;
  helper: string;
  disabled: boolean;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex min-h-24 flex-col justify-between rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-left transition-colors hover:border-slate-700 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
    >
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 text-sky-300" />
        {busy ? <LoaderCircle className="h-4 w-4 animate-spin text-slate-300" /> : null}
      </div>
      <div>
        <div className="text-sm font-medium text-white">{label}</div>
        <div className="mt-1 text-sm text-slate-400">{helper}</div>
      </div>
    </button>
  );
}

function EvidenceTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-3 text-lg font-medium text-white">{value}</div>
      <div className="mt-1 text-sm text-slate-400">{detail}</div>
    </div>
  );
}

function SignalPanel({
  title,
  items,
  tone,
}: {
  title: string;
  items: NewsItem[];
  tone: "ready" | "review" | "background";
}) {
  return (
    <Panel title={title} subtitle="当前 dashboard bucket">
      <DataState loading={false} error={null} empty={!items.length}>
        <div className="space-y-3">
          {items.map((item) => (
            <div key={textValue(item.item_id)} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                <span>{textValue(item.source_name)}</span>
                <InlineBadge value={tone === "ready" ? "ready" : tone === "review" ? "review" : "background"} compact />
              </div>
              <div className="mt-3 text-base font-medium text-white">{textValue(item.title)}</div>
              <div className="mt-2 text-sm leading-6 text-slate-400">{textValue(item.summary)}</div>
            </div>
          ))}
        </div>
      </DataState>
    </Panel>
  );
}

function MarketRow({ item }: { item: MarketItem }) {
  const up = item.changeDirection === "up" || item.changeText.startsWith("+");
  const down = item.changeDirection === "down" || item.changeText.startsWith("-");
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-white">{item.name}</div>
        <div className="text-xs text-slate-500">{item.symbol}</div>
      </div>
      <div className="text-right">
        <div className="text-sm text-white">{item.value}</div>
        <div className={cn("inline-flex items-center gap-1 text-xs", up ? "text-emerald-300" : down ? "text-rose-300" : "text-slate-400")}>
          {up ? <TrendingUp className="h-3.5 w-3.5" /> : null}
          {down ? <TrendingDown className="h-3.5 w-3.5" /> : null}
          <span>{item.changeText || "--"}</span>
        </div>
      </div>
    </div>
  );
}

function NarrativeCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="mt-2 text-sm leading-6 text-slate-300">{body}</div>
    </div>
  );
}

function CallGrid({
  items,
  emptyMessage,
}: {
  items: Array<Record<string, unknown>>;
  emptyMessage: string;
}) {
  if (!items.length) {
    return <div className="text-sm text-slate-500">{emptyMessage}</div>;
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((item, index) => (
        <div key={`call-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-base font-medium text-white">{textValue(item.subject, textValue(item.title, "Untitled"))}</div>
            <InlineBadge value={textValue(item.stance, textValue(item.signal_type, "neutral"))} compact />
          </div>
          <div className="mt-3 text-sm leading-6 text-slate-300">{textValue(item.logic, textValue(item.summary))}</div>
          <div className="mt-4 grid gap-2 text-sm text-slate-400">
            <KeyValue label="Reason" value={textValue(item.reason)} />
            <KeyValue label="Watch point" value={textValue(item.watch_point)} />
            <KeyValue label="Confidence" value={textValue(item.confidence)} />
          </div>
        </div>
      ))}
    </div>
  );
}

function KeyField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="space-y-2">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
        <KeyRound className="h-3.5 w-3.5" />
        {label}
      </div>
      <input
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="min-h-11 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-sky-400/50"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <label className="space-y-2">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 text-sm text-slate-100 outline-none transition-colors focus:border-sky-400/50"
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={`${label}-${optionValue}`} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function InlineBadge({ value, compact = false }: { value: string; compact?: boolean }) {
  const normalized = value.toLowerCase();
  const tone =
    normalized.includes("positive") ||
    normalized.includes("bull") ||
    normalized === "ready" ||
    normalized === "healthy" ||
    normalized === "up"
      ? "emerald"
      : normalized.includes("negative") ||
          normalized.includes("bear") ||
          normalized.includes("down") ||
          normalized === "error"
        ? "rose"
        : normalized.includes("review") ||
            normalized.includes("warn") ||
            normalized.includes("cooldown")
          ? "amber"
          : "slate";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs uppercase tracking-[0.18em]",
        compact ? "min-h-5" : "min-h-6",
        tone === "emerald" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
        tone === "rose" && "border-rose-500/30 bg-rose-500/10 text-rose-200",
        tone === "amber" && "border-amber-500/30 bg-amber-500/10 text-amber-200",
        tone === "slate" && "border-slate-700 bg-slate-800/70 text-slate-300",
      )}
    >
      {value}
    </span>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm text-slate-300">{value}</div>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item, index) => (
            <div key={`${title}-${index}`} className="text-sm leading-6 text-slate-300">
              {item}
            </div>
          ))
        ) : (
          <div className="text-sm text-slate-500">暂无数据</div>
        )}
      </div>
    </div>
  );
}

function DataState({
  loading,
  error,
  empty,
  children,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="flex min-h-32 items-center justify-center gap-2 text-sm text-slate-400">
        <LoaderCircle className="h-4 w-4 animate-spin" />
        正在加载
      </div>
    );
  }
  if (error) {
    return <ErrorBanner error={error} />;
  }
  if (empty) {
    return (
      <div className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-800 bg-slate-900/40 px-4 text-center text-sm text-slate-500">
        <Sparkles className="h-4 w-4" />
        当前没有可展示的数据
      </div>
    );
  }
  return <>{children}</>;
}

function ErrorBanner({ error, className }: { error: unknown; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100", className)}>
      {errorSummary(error)}
    </div>
  );
}

type MarketItem = {
  name: string;
  symbol: string;
  value: string;
  changeText: string;
  changeDirection: string;
};

type MorningSummary = {
  headline: string;
  note: string;
  focus: string;
  flow: string;
  risk: string;
};

function buildMarketGroups(market?: MarketSnapshotPayload) {
  const assetBoard = asRecord(market?.asset_board);
  const groups: Array<[string, string]> = [
    ["indexes", "美股指数"],
    ["sectors", "行业板块"],
    ["rates_fx", "利率汇率"],
    ["energy", "能源商品"],
    ["china_proxies", "中概映射"],
  ];

  return groups
    .map(([key, label]) => {
      const items = asArray<Record<string, unknown>>(assetBoard[key])
        .slice(0, 4)
        .map((item) => ({
          name: textValue(item.display_name, textValue(item.future_name, textValue(item.symbol))),
          symbol: textValue(item.symbol, textValue(item.future_code)),
          value: textValue(item.close_text, textValue(item.watch_score, "--")),
          changeText: textValue(item.change_pct_text, textValue(item.driver_summary, textValue(item.change_text, ""))),
          changeDirection: textValue(item.change_direction, textValue(item.watch_direction, "")),
        }))
        .filter((item) => item.name !== "--");
      return { label, items };
    })
    .filter((group) => group.items.length);
}

function buildMorningSummary(
  dashboard?: DashboardPayload,
  market?: MarketSnapshotPayload,
): MorningSummary {
  const mainline = dashboard?.mainlines?.[0];
  const leadSignal = dashboard?.lead_signals?.[0];
  const watchSignal = dashboard?.watchlist?.[0];
  const groups = buildMarketGroups(market);
  const firstGroup = groups[0];
  const firstMove = firstGroup?.items[0];

  const headline = mainline?.title
    ? `今天先盯 ${textValue(mainline.title)}`
    : "先看隔夜最强方向，再决定今天盯哪条线";

  const note = mainline?.summary
    ? firstSentence(textValue(mainline.summary))
    : leadSignal?.summary
      ? firstSentence(textValue(leadSignal.summary))
      : "如果还没有生成日报，就先从隔夜重点新闻和市场快照里抓主线。";

  const focus = leadSignal?.title
    ? `${textValue(leadSignal.title)}`
    : "先看最强新闻驱动，再看有没有板块跟随。";

  const flow = firstGroup && firstMove
    ? `${firstGroup.label} 里，${firstMove.name} ${firstMove.changeText || "有异动"}。`
    : "先盯美股科技、商品和中概代理资产的方向。";

  const risk = watchSignal?.title
    ? `${textValue(watchSignal.title)}`
    : "高位题材容易冲高回落，开盘别急着追。";

  return {
    headline,
    note,
    focus,
    flow,
    risk,
  };
}

function firstSentence(value: string) {
  const parts = value.split(/[。.!?]/).map((item) => item.trim()).filter(Boolean);
  return parts[0] ? `${parts[0]}。` : value;
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function textValue(value: unknown, fallback = "--") {
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = String(value).trim();
  return normalized || fallback;
}

function numberValue(value: unknown) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) {
    return "0";
  }
  return new Intl.NumberFormat("en-US").format(numeric);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function errorSummary(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.status} ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "请求失败";
}

function isNotFoundError(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}
