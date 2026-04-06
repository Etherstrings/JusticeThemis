import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { overnightApi } from '../api/overnight';
import { Badge, Card, Pagination } from '../components/common';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import type {
  OvernightBriefHistoryItem,
  OvernightEventHistoryItem,
  OvernightHealthResponse,
  OvernightTopicHistoryItem,
} from '../types/overnight';
import {
  buildOvernightTopicHref,
  formatOvernightDateTime,
  getOvernightTopicDefinition,
  type OvernightTopicKey,
} from '../utils/overnightView';

const historyPageSize = 10;

type HistoryView = 'day' | 'event' | 'topic';

const HISTORY_VIEW_OPTIONS: Array<{ value: HistoryView; label: string; body: string }> = [
  { value: 'day', label: '按天看', body: '按生成日期回看完整晨报，适合复盘每天早上到底推了什么。' },
  { value: 'event', label: '按事件看', body: '把跨天重复出现的事件聚合起来，快速判断哪些线索在持续发酵。' },
  { value: 'topic', label: '按主题看', body: '追踪政策、涨价链、受益方向等主题在历史晨报里的覆盖密度。' },
];

const SEARCH_PLACEHOLDERS: Record<HistoryView, string> = {
  day: '搜索日期、topline 或 brief id',
  event: '搜索事件主线，例如 tariff、fed、oil',
  topic: '搜索主题，例如 policy、price、beneficiaries',
};

function normalizeHistoryView(value: string | null): HistoryView {
  if (value === 'event' || value === 'topic') {
    return value;
  }
  return 'day';
}

function priorityVariant(priorityLevel?: string): 'danger' | 'warning' | 'info' | 'default' {
  switch ((priorityLevel || '').toUpperCase()) {
    case 'P0':
      return 'danger';
    case 'P1':
      return 'warning';
    case 'P2':
      return 'info';
    default:
      return 'default';
  }
}

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Overnight History</div>
    <h1 className="mt-3 text-2xl font-semibold text-white">{title}</h1>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
  </Card>
);

const ViewChip: React.FC<{ active: boolean; label: string; onClick: () => void }> = ({ active, label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
      active
        ? 'border-cyan/30 bg-cyan/10 text-cyan'
        : 'border-white/8 bg-white/[0.02] text-secondary hover:border-white/12 hover:text-white'
    }`}
  >
    {label}
  </button>
);

const StatCard: React.FC<{ title: string; value: string; body: string }> = ({ title, value, body }) => (
  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
    <div className="text-xs uppercase tracking-[0.18em] text-muted">{title}</div>
    <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    <div className="mt-1 text-xs text-secondary">{body}</div>
  </div>
);

const DayHistorySection: React.FC<{
  items: OvernightBriefHistoryItem[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}> = ({ items, page, totalPages, onPageChange }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Day View</div>
        <h2 className="mt-1 text-xl font-semibold text-white">按天回看晨报</h2>
      </div>
      <Badge variant="history">{items.length}</Badge>
    </div>

    {items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">当前还没有任何可回看的隔夜晨报归档。</div>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div key={item.briefId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium text-white">{item.digestDate}</div>
                  <Badge variant="default">{item.cutoffTime}</Badge>
                </div>
                <div className="mt-2 text-sm leading-6 text-secondary">{item.topline}</div>
                <div className="mt-2 text-xs text-muted">{formatOvernightDateTime(item.generatedAt)}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link className="btn-secondary" to={`/overnight/briefs/${item.briefId}`}>
                  打开晨报
                </Link>
                <Link className="btn-secondary" to={`/overnight/topics/policy-radar?briefId=${item.briefId}`}>
                  看主题页
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    )}

    <Pagination className="mt-4 justify-start" currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
  </Card>
);

const EventHistorySection: React.FC<{
  items: OvernightEventHistoryItem[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}> = ({ items, page, totalPages, onPageChange }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Event View</div>
        <h2 className="mt-1 text-xl font-semibold text-white">按事件追踪发酵路径</h2>
      </div>
      <Badge variant="history">{items.length}</Badge>
    </div>

    {items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">当前还没有可聚合的历史事件。</div>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div key={item.eventKey} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={priorityVariant(item.latestPriorityLevel)}>{item.latestPriorityLevel || 'NA'}</Badge>
                  <Badge variant="history">出现 {item.occurrenceCount} 次</Badge>
                  <Badge variant="info">均值 {Math.round(item.averageConfidence * 100)}%</Badge>
                </div>
                <div className="mt-3 text-base font-medium text-white">{item.coreFact}</div>
                <div className="mt-2 text-xs text-muted">最近出现：{item.latestDigestDate || '暂无记录'}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {item.latestBriefId && item.latestEventId ? (
                  <Link className="btn-secondary" to={`/overnight/events/${item.latestEventId}?briefId=${item.latestBriefId}`}>
                    最新事件页
                  </Link>
                ) : null}
                {item.latestBriefId ? (
                  <Link className="btn-secondary" to={`/overnight/briefs/${item.latestBriefId}`}>
                    最新晨报
                  </Link>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {item.occurrences.map((occurrence) => (
                <Link
                  key={`${item.eventKey}-${occurrence.briefId}-${occurrence.eventId}`}
                  className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3 transition hover:border-white/12 hover:bg-white/[0.03]"
                  to={`/overnight/events/${occurrence.eventId}?briefId=${occurrence.briefId}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-white">{occurrence.digestDate}</div>
                    <Badge variant={priorityVariant(occurrence.priorityLevel)}>{occurrence.priorityLevel || 'NA'}</Badge>
                  </div>
                  <div className="mt-2 text-sm text-secondary">
                    置信度 {Math.round((occurrence.confidence || 0) * 100)}%
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    )}

    <Pagination className="mt-4 justify-start" currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
  </Card>
);

const TopicHistorySection: React.FC<{
  items: OvernightTopicHistoryItem[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}> = ({ items, page, totalPages, onPageChange }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Topic View</div>
        <h2 className="mt-1 text-xl font-semibold text-white">按主题看覆盖密度</h2>
      </div>
      <Badge variant="history">{items.length}</Badge>
    </div>

    {items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">当前还没有形成可回看的主题历史。</div>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item) => {
          const topicDefinition = getOvernightTopicDefinition(item.topicKey);
          const topicHref = item.latestBriefId
            ? buildOvernightTopicHref(item.topicKey as OvernightTopicKey, item.latestBriefId)
            : null;

          return (
            <div key={item.topicKey} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="history">出现 {item.occurrenceCount} 次</Badge>
                    <Badge variant="info">累计 {item.totalItemCount} 条</Badge>
                    <Badge variant="default">最近 {item.latestItemCount} 条</Badge>
                  </div>
                  <div className="mt-3 text-base font-medium text-white">{item.title}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">
                    {(topicDefinition?.subtitle || item.topicKey).toUpperCase()}
                  </div>
                  <div className="mt-2 text-xs text-muted">最近出现：{item.latestDigestDate || '暂无记录'}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {topicHref ? (
                    <Link className="btn-secondary" to={topicHref}>
                      最新主题页
                    </Link>
                  ) : null}
                  {item.latestBriefId ? (
                    <Link className="btn-secondary" to={`/overnight/briefs/${item.latestBriefId}`}>
                      最新晨报
                    </Link>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {item.recentBriefs.map((brief) => (
                  <Link
                    key={`${item.topicKey}-${brief.briefId}`}
                    className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3 transition hover:border-white/12 hover:bg-white/[0.03]"
                    to={buildOvernightTopicHref(item.topicKey as OvernightTopicKey, brief.briefId)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white">{brief.digestDate}</div>
                      <Badge variant="default">{brief.itemCount} 条</Badge>
                    </div>
                    <div className="mt-2 text-sm text-secondary">打开该日主题视图</div>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    )}

    <Pagination className="mt-4 justify-start" currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
  </Card>
);

const OvernightHistoryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = normalizeHistoryView(searchParams.get('view'));
  const page = Math.max(Number.parseInt(searchParams.get('page') || '1', 10) || 1, 1);
  const query = (searchParams.get('q') || '').trim();

  const [dayItems, setDayItems] = useState<OvernightBriefHistoryItem[]>([]);
  const [dayTotal, setDayTotal] = useState(0);
  const [eventItems, setEventItems] = useState<OvernightEventHistoryItem[]>([]);
  const [eventTotal, setEventTotal] = useState(0);
  const [topicItems, setTopicItems] = useState<OvernightTopicHistoryItem[]>([]);
  const [topicTotal, setTopicTotal] = useState(0);
  const [health, setHealth] = useState<OvernightHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState(query);

  useEffect(() => {
    setSearchText(query);
  }, [query]);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        if (activeView === 'day') {
          const [historyResponse, healthResponse] = await Promise.all([
            overnightApi.getHistory(page, historyPageSize, query || undefined),
            overnightApi.getHealth(),
          ]);
          setDayItems(historyResponse.items);
          setDayTotal(historyResponse.total);
          setHealth(healthResponse);
          return;
        }

        if (activeView === 'event') {
          const [historyResponse, healthResponse] = await Promise.all([
            overnightApi.getEventHistory(page, historyPageSize, query || undefined),
            overnightApi.getHealth(),
          ]);
          setEventItems(historyResponse.items);
          setEventTotal(historyResponse.total);
          setHealth(healthResponse);
          return;
        }

        const [historyResponse, healthResponse] = await Promise.all([
          overnightApi.getTopicHistory(page, historyPageSize, query || undefined),
          overnightApi.getHealth(),
        ]);
        setTopicItems(historyResponse.items);
        setTopicTotal(historyResponse.total);
        setHealth(healthResponse);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : '加载隔夜历史失败');
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [activeView, page, query]);

  const activeViewMeta = useMemo(
    () => HISTORY_VIEW_OPTIONS.find((option) => option.value === activeView) || HISTORY_VIEW_OPTIONS[0],
    [activeView]
  );

  const currentTotal = activeView === 'day' ? dayTotal : activeView === 'event' ? eventTotal : topicTotal;
  const currentItemsLength =
    activeView === 'day' ? dayItems.length : activeView === 'event' ? eventItems.length : topicItems.length;
  const totalPages = Math.max(1, Math.ceil(currentTotal / historyPageSize));

  const updateSearchState = (next: { view?: HistoryView; page?: number; q?: string }) => {
    const params = new URLSearchParams();
    const nextView = next.view ?? activeView;
    const nextPage = next.page ?? page;
    const nextQuery = (next.q ?? query).trim();

    if (nextView !== 'day') {
      params.set('view', nextView);
    }
    if (nextPage > 1) {
      params.set('page', String(nextPage));
    }
    if (nextQuery) {
      params.set('q', nextQuery);
    }

    setSearchParams(params);
  };

  if (isLoading && currentItemsLength === 0) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={health?.pipelineHealth.latestBriefId || null} />
          <StateCard title="历史视图加载中" body="正在读取隔夜晨报历史与聚合视图。" />
        </div>
      </div>
    );
  }

  if (error && currentItemsLength === 0) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={health?.pipelineHealth.latestBriefId || null} />
          <StateCard title="历史视图加载失败" body={error} />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={health?.pipelineHealth.latestBriefId || null} />

        <Card variant="gradient" padding="lg">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">History Workspace</div>
              <h1 className="mt-3 text-3xl font-semibold text-white">隔夜历史三视角</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">{activeViewMeta.body}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="history">当前视图 {currentTotal}</Badge>
              <Badge variant={health?.deliveryHealth.notificationAvailable ? 'success' : 'warning'}>
                {health?.deliveryHealth.notificationAvailable ? '投递可用' : '投递待配置'}
              </Badge>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {HISTORY_VIEW_OPTIONS.map((option) => (
              <ViewChip
                key={option.value}
                active={activeView === option.value}
                label={option.label}
                onClick={() => updateSearchState({ view: option.value, page: 1, q: query })}
              />
            ))}
          </div>

          <form
            className="mt-5 flex flex-wrap items-center gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              updateSearchState({ page: 1, q: searchText });
            }}
          >
            <input
              className="min-w-[260px] flex-1 rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-3 text-sm text-white outline-none transition placeholder:text-muted focus:border-cyan/30"
              placeholder={SEARCH_PLACEHOLDERS[activeView]}
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
            />
            <button type="submit" className="btn-primary">
              搜索
            </button>
            {query ? (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setSearchText('');
                  updateSearchState({ page: 1, q: '' });
                }}
              >
                清除
              </button>
            ) : null}
            {query ? <Badge variant="info">关键词 {query}</Badge> : null}
          </form>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <StatCard
              title="Archived Briefs"
              value={String(health?.pipelineHealth.briefCount || 0)}
              body="已落库晨报总数"
            />
            <StatCard
              title="Latest Brief"
              value={health?.pipelineHealth.latestDigestDate || '暂无'}
              body={formatOvernightDateTime(health?.pipelineHealth.latestGeneratedAt)}
            />
            <StatCard
              title="Average Confidence"
              value={`${Math.round(((health?.contentQuality.averageConfidence || 0) as number) * 100)}%`}
              body="最新晨报重点事件平均置信度"
            />
            <StatCard
              title="Evidence Gate"
              value={`${health?.contentQuality.eventsWithPrimarySources || 0}/${health?.contentQuality.topEventCount || 0}`}
              body={health?.contentQuality.minimumEvidenceGatePassed ? '证据门禁通过' : '仍有事件缺链接'}
            />
          </div>
        </Card>

        {error ? (
          <Card variant="bordered" padding="md">
            <div className="text-sm text-red-300">{error}</div>
          </Card>
        ) : null}

        {activeView === 'day' ? (
          <DayHistorySection items={dayItems} page={page} totalPages={totalPages} onPageChange={(nextPage) => updateSearchState({ page: nextPage })} />
        ) : null}

        {activeView === 'event' ? (
          <EventHistorySection
            items={eventItems}
            page={page}
            totalPages={totalPages}
            onPageChange={(nextPage) => updateSearchState({ page: nextPage })}
          />
        ) : null}

        {activeView === 'topic' ? (
          <TopicHistorySection
            items={topicItems}
            page={page}
            totalPages={totalPages}
            onPageChange={(nextPage) => updateSearchState({ page: nextPage })}
          />
        ) : null}
      </div>
    </div>
  );
};

export default OvernightHistoryPage;
