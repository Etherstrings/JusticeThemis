import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card, Pagination } from '../components/common';
import { OvernightActionDesk } from '../components/overnight/OvernightActionDesk';
import { OvernightEventCard } from '../components/overnight/OvernightEventCard';
import { OvernightFeedbackPanel } from '../components/overnight/OvernightFeedbackPanel';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type {
  OvernightBoardItem,
  OvernightBrief,
  OvernightBriefHistoryItem,
  OvernightEventSummary,
  OvernightHealthResponse,
  OvernightPrimarySourceGroup,
  OvernightSourceListResponse,
  OvernightWatchBucket,
} from '../types/overnight';
import {
  buildOvernightTopicHref,
  formatOvernightDateTime,
  summarizeOvernightBoardItem,
} from '../utils/overnightView';
import { buildEventDecisionLens, getEvidenceBadgeVariant } from '../utils/overnightDecision';
import { groupSourcesByCoverageTier, readCoverageTierCount } from '../utils/overnightSourceCoverage';
import { buildCapturedNewsItems } from '../utils/overnightSourceEvidence';

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

const EmptyState: React.FC<{ title: string; body: string; actionLabel?: string; onAction?: () => void }> = ({
  title,
  body,
  actionLabel,
  onAction,
}) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Overnight Feed</div>
    <h2 className="mt-3 text-2xl font-semibold text-white">{title}</h2>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
    {actionLabel && onAction ? (
      <button type="button" className="btn-primary mt-5" onClick={onAction}>
        {actionLabel}
      </button>
    ) : null}
  </Card>
);

const BoardSection: React.FC<{
  title: string;
  subtitle: string;
  items: OvernightBoardItem[];
  emptyText: string;
  href?: string;
}> = ({
  title,
  subtitle,
  items,
  emptyText,
  href,
}) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">{subtitle}</div>
        <h3 className="mt-1 text-lg font-semibold text-white">{title}</h3>
      </div>
      <div className="flex items-center gap-2">
        {href ? (
          <Link to={href} className="text-xs font-medium text-cyan transition hover:text-cyan/80">
            打开主题页
          </Link>
        ) : null}
        <Badge variant="default">{items.length}</Badge>
      </div>
    </div>

    {items.length === 0 ? (
      <p className="mt-4 text-sm text-secondary">{emptyText}</p>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => {
          const summary = summarizeOvernightBoardItem(item);
          return (
            <div key={`${title}-${index}`} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-sm font-medium text-white">{summary.headline}</div>
              {summary.meta.length > 0 ? (
                <div className="mt-2 space-y-1">
                  {summary.meta.map((line) => (
                    <div key={line} className="text-xs leading-5 text-secondary">
                      {line}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    )}
  </Card>
);

const WatchlistSection: React.FC<{ buckets: OvernightWatchBucket[]; briefId: string }> = ({ buckets, briefId }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Watchlist</div>
        <h3 className="mt-1 text-lg font-semibold text-white">今日开盘前行动板</h3>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Link to={`/overnight/playbook?briefId=${encodeURIComponent(briefId)}`} className="text-xs font-medium text-cyan transition hover:text-cyan/80">
          开盘剧本
        </Link>
        <Link to={`/overnight/changes?briefId=${encodeURIComponent(briefId)}`} className="text-xs font-medium text-cyan transition hover:text-cyan/80">
          变化对照
        </Link>
        <Link to={`/overnight/opening?briefId=${encodeURIComponent(briefId)}`} className="text-xs font-medium text-cyan transition hover:text-cyan/80">
          打开独立行动板
        </Link>
      </div>
    </div>

    <div className="mt-4 grid gap-3 md:grid-cols-2">
      {buckets.map((bucket) => (
        <div key={bucket.title} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm font-medium text-white">{bucket.title}</div>
              <div className="mt-1 text-xs text-secondary">{bucket.summary}</div>
            </div>
            <Badge variant="default">{bucket.items.length}</Badge>
          </div>
          {bucket.items.length === 0 ? (
            <div className="mt-3 text-sm text-secondary">暂无项目</div>
          ) : (
            <div className="mt-3 space-y-2">
              {bucket.items.map((item) => (
                <div key={item.watchId} className="rounded-2xl border border-white/6 bg-base/30 px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="info">{item.label}</Badge>
                      {item.priorityLevel ? (
                        <Badge variant={priorityVariant(item.priorityLevel)}>{item.priorityLevel}</Badge>
                      ) : null}
                      <Badge variant="default">{Math.round((item.confidence || 0) * 100)}%</Badge>
                    </div>
                    {item.eventId ? (
                      <Link
                        className="text-xs font-medium text-cyan transition hover:text-cyan/80"
                        to={`/overnight/events/${item.eventId}?briefId=${briefId}`}
                      >
                        事件页
                      </Link>
                    ) : null}
                  </div>
                  <div className="mt-2 text-sm font-medium text-white">{item.coreFact}</div>
                  <div className="mt-3 space-y-1 text-xs leading-5 text-secondary">
                    <div>触发条件: {item.trigger}</div>
                    <div>建议动作: {item.action}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  </Card>
);

const HistoryPanel: React.FC<{
  items: OvernightBriefHistoryItem[];
  activeBriefId?: string | null;
  isLoading: boolean;
  currentPage: number;
  totalPages: number;
  onSelect: (briefId: string) => void;
  onPageChange: (page: number) => void;
}> = ({ items, activeBriefId, isLoading, currentPage, totalPages, onSelect, onPageChange }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">History View</div>
        <h3 className="mt-1 text-lg font-semibold text-white">按天回看晨报</h3>
      </div>
      <div className="flex items-center gap-2">
        <Link to="/overnight/history" className="text-xs font-medium text-cyan transition hover:text-cyan/80">
          独立历史页
        </Link>
        <Badge variant="history">{items.length}</Badge>
      </div>
    </div>

    {isLoading ? (
      <div className="mt-4 text-sm text-secondary">正在加载历史晨报...</div>
    ) : items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">还没有可回看的隔夜晨报归档。</div>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <button
            key={item.briefId}
            type="button"
            onClick={() => onSelect(item.briefId)}
            className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
              item.briefId === activeBriefId
                ? 'border-cyan/30 bg-cyan/8'
                : 'border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/[0.03]'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-white">{item.digestDate}</div>
              <Badge variant={item.briefId === activeBriefId ? 'info' : 'default'}>
                {item.cutoffTime}
              </Badge>
            </div>
            <div className="mt-2 text-sm leading-6 text-secondary">{item.topline}</div>
            <div className="mt-2 text-xs text-muted">{formatOvernightDateTime(item.generatedAt)}</div>
          </button>
        ))}
      </div>
    )}

    <Pagination
      className="mt-4 justify-start"
      currentPage={currentPage}
      totalPages={totalPages}
      onPageChange={onPageChange}
    />
  </Card>
);

const SourceCatalogPanel: React.FC<{
  sources: OvernightSourceListResponse | null;
  isLoading: boolean;
  error: string | null;
}> = ({ sources, isLoading, error }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Source Registry</div>
        <h3 className="mt-1 text-lg font-semibold text-white">当前源覆盖面</h3>
      </div>
      <Badge variant="default">{sources?.total || 0}</Badge>
    </div>

    {isLoading ? (
      <div className="mt-4 text-sm text-secondary">正在加载源目录...</div>
    ) : error ? (
      <div className="mt-4 text-sm text-red-300">{error}</div>
    ) : !sources || sources.items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">当前还没有可展示的源目录。</div>
    ) : (
      <div className="mt-4 space-y-4">
        {groupSourcesByCoverageTier(sources.items).map((group) => (
          <div key={group.key} className="space-y-3">
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">{group.title}</div>
                  <div className="mt-1 text-xs leading-5 text-secondary">{group.description}</div>
                </div>
                <Badge variant="default">{group.items.length}</Badge>
              </div>
            </div>

            {group.items.map((source) => (
              <div key={source.sourceId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">{source.displayName}</div>
                    <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">{source.sourceId}</div>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Badge variant={source.isEnabled ? 'success' : 'default'}>
                      {source.isEnabled ? '已启用' : '未启用'}
                    </Badge>
                    {source.isMissionCritical ? <Badge variant="danger">关键源</Badge> : null}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-secondary">
                  <span>{source.sourceClass}</span>
                  <span>·</span>
                  <span>{source.entryType}</span>
                  <span>·</span>
                  <span>{Math.round(source.pollIntervalSeconds / 60)} 分钟轮询</span>
                  <span>·</span>
                  <span>优先级 {source.priority}</span>
                </div>
                <div className="mt-3 space-y-1 text-sm text-secondary">
                  <div>Region focus: {source.regionFocus || '未标注'}</div>
                  <div>{source.coverageFocus || '当前还没有补充这条源的覆盖说明。'}</div>
                </div>
                {source.entryUrls[0] ? (
                  <a
                    href={source.entryUrls[0]}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 block truncate text-sm text-cyan transition hover:text-cyan/80"
                  >
                    {source.entryUrls[0]}
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        ))}
      </div>
    )}
  </Card>
);

const HealthPanel: React.FC<{
  health: OvernightHealthResponse | null;
  isLoading: boolean;
  error: string | null;
}> = ({ health, isLoading, error }) => (
  <Card variant="gradient" padding="lg">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">Operations</div>
        <h3 className="mt-1 text-lg font-semibold text-white">采集与投递健康状态</h3>
      </div>
      <Badge variant={health?.deliveryHealth.notificationAvailable ? 'success' : 'warning'}>
        {health?.deliveryHealth.notificationAvailable ? '可投递' : '待配置'}
      </Badge>
    </div>

    {isLoading ? (
      <div className="mt-4 text-sm text-secondary">正在加载健康状态...</div>
    ) : error ? (
      <div className="mt-4 text-sm text-red-300">{error}</div>
    ) : !health ? (
      <div className="mt-4 text-sm text-secondary">当前还没有健康状态可展示。</div>
    ) : (
      <div className="mt-4 space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Sources</div>
            <div className="mt-2 text-2xl font-semibold text-white">{health.sourceHealth.totalSources}</div>
            <div className="mt-2 text-xs text-secondary">
              关键源 {health.sourceHealth.missionCriticalSources} / 当前启用 {health.sourceHealth.whitelistedSources}
            </div>
            <div className="mt-1 text-xs text-secondary">
              已启用关键源 {health.sourceHealth.enabledMissionCriticalSources}
            </div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Pipeline</div>
            <div className="mt-2 text-2xl font-semibold text-white">{health.pipelineHealth.briefCount}</div>
            <div className="mt-2 text-xs text-secondary">已归档晨报数量</div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Delivery</div>
            <div className="mt-2 text-2xl font-semibold text-white">
              {health.deliveryHealth.configuredChannels.length}
            </div>
            <div className="mt-2 text-xs text-secondary">已识别投递渠道</div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Avg Confidence</div>
            <div className="mt-2 text-2xl font-semibold text-white">
              {Math.round((health.contentQuality.averageConfidence || 0) * 100)}%
            </div>
            <div className="mt-2 text-xs text-secondary">Top events 平均置信度</div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Evidence Gate</div>
            <div className="mt-2 text-2xl font-semibold text-white">
              {health.contentQuality.eventsWithPrimarySources}/{health.contentQuality.topEventCount}
            </div>
            <div className="mt-2 text-xs text-secondary">
              {health.contentQuality.minimumEvidenceGatePassed ? '全部事件已有 primary source' : '仍有事件缺少 primary source'}
            </div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Need Confirm</div>
            <div className="mt-2 text-2xl font-semibold text-white">{health.contentQuality.eventsNeedingConfirmation}</div>
            <div className="mt-2 text-xs text-secondary">低置信度待确认事件</div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Duplication</div>
            <div className="mt-2 text-2xl font-semibold text-white">{health.contentQuality.duplicateCoreFactCount}</div>
            <div className="mt-2 text-xs text-secondary">
              {health.contentQuality.duplicationGatePassed ? '未发现重复核心事实' : '存在重复核心事实'}
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Coverage Layers</div>
              <div className="mt-3 space-y-2 text-sm text-secondary">
              <div>官方政策: {readCoverageTierCount(health.sourceHealth.coverageTierCounts, 'official_policy')}</div>
              <div>官方数据: {readCoverageTierCount(health.sourceHealth.coverageTierCounts, 'official_data')}</div>
              <div>主流媒体: {readCoverageTierCount(health.sourceHealth.coverageTierCounts, 'editorial_media')}</div>
              </div>
          </div>
          <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-muted">Coverage Gaps</div>
            {health.sourceHealth.coverageGaps.length === 0 ? (
              <div className="mt-3 text-sm text-secondary">当前覆盖层没有明显缺口。</div>
            ) : (
              <div className="mt-3 space-y-2">
                {health.sourceHealth.coverageGaps.map((gap) => (
                  <div key={gap} className="text-sm text-secondary">
                    {gap}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Latest Persisted Brief</div>
              <div className="mt-2 text-sm font-medium text-white">
                {health.pipelineHealth.latestDigestDate || '暂无已落库晨报'}
              </div>
            </div>
            <Badge variant={health.deliveryHealth.overnightBriefEnabled ? 'success' : 'default'}>
              {health.deliveryHealth.overnightBriefEnabled ? '已开启' : '未开启'}
            </Badge>
          </div>
          <div className="mt-3 space-y-1 text-sm text-secondary">
            <div>Brief ID: {health.pipelineHealth.latestBriefId || '暂无'}</div>
            <div>Generated At: {formatOvernightDateTime(health.pipelineHealth.latestGeneratedAt)}</div>
            <div>
              Channels:{' '}
              {health.deliveryHealth.channelNames || '当前未配置企业微信 / 飞书 / Telegram / 邮件等投递渠道'}
            </div>
          </div>
        </div>
      </div>
    )}
  </Card>
);

const OvernightBriefPage: React.FC = () => {
  const { briefId } = useParams();
  const navigate = useNavigate();
  const historyPageSize = 6;
  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<OvernightBriefHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [sources, setSources] = useState<OvernightSourceListResponse | null>(null);
  const [health, setHealth] = useState<OvernightHealthResponse | null>(null);
  const [isOperationsLoading, setIsOperationsLoading] = useState(true);
  const [operationsError, setOperationsError] = useState<string | null>(null);

  const loadHistory = async (page = 1) => {
    setIsHistoryLoading(true);
    try {
      const response = await overnightApi.getHistory(page, historyPageSize);
      setHistoryItems(response.items);
      setHistoryPage(response.page);
      setHistoryTotal(response.total);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const loadBrief = async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const nextBrief = briefId ? await overnightApi.getBriefById(briefId) : await overnightApi.getLatestBrief();
      setBrief(nextBrief);
      setEmptyMessage(null);
      await loadHistory(1);
      setSelectedEventId((current) => {
        if (current && nextBrief.topEvents.some((item) => item.eventId === current)) {
          return current;
        }
        return nextBrief.topEvents[0]?.eventId || null;
      });
    } catch (error) {
      setBrief(null);
      setSelectedEventId(null);
      if (error instanceof OvernightBriefUnavailableError) {
        setEmptyMessage(error.message);
        setHistoryItems([]);
        setHistoryTotal(0);
        return;
      }
      setLoadError(error instanceof Error ? error.message : '加载隔夜晨报失败');
    } finally {
      setIsLoading(false);
    }
  };

  const loadOperations = async () => {
    setIsOperationsLoading(true);
    setOperationsError(null);

    try {
      const [nextSources, nextHealth] = await Promise.all([
        overnightApi.getSources(),
        overnightApi.getHealth(),
      ]);
      setSources(nextSources);
      setHealth(nextHealth);
    } catch (error) {
      setOperationsError(error instanceof Error ? error.message : '加载运行状态失败');
    } finally {
      setIsOperationsLoading(false);
    }
  };

  const refreshPage = () => {
    void loadBrief();
    void loadOperations();
  };

  useEffect(() => {
    void loadBrief();
    void loadOperations();
  }, [briefId]);

  const selectedEvent = useMemo<OvernightEventSummary | null>(() => {
    if (!brief || !selectedEventId) return null;
    return brief.topEvents.find((item) => item.eventId === selectedEventId) || null;
  }, [brief, selectedEventId]);

  const selectedSources = useMemo<OvernightPrimarySourceGroup | null>(() => {
    if (!brief || !selectedEventId) return null;
    return brief.primarySources.find((item) => item.eventId === selectedEventId) || null;
  }, [brief, selectedEventId]);
  const eventDecisionMap = useMemo(() => {
    if (!brief) {
      return new Map<string, ReturnType<typeof buildEventDecisionLens>>();
    }
    return new Map(
      brief.topEvents.map((event) => [
        event.eventId,
        buildEventDecisionLens(brief, event),
      ])
    );
  }, [brief]);

  const detailToRender = selectedEvent;
  const selectedDecision = detailToRender ? eventDecisionMap.get(detailToRender.eventId) || null : null;
  const capturedNewsItems = useMemo(() => {
    if (!detailToRender || !selectedSources) {
      return [];
    }
    return buildCapturedNewsItems(detailToRender, selectedSources, sources?.items || []);
  }, [detailToRender, selectedSources, sources]);
  const totalHistoryPages = Math.max(1, Math.ceil(historyTotal / historyPageSize));

  const handleHistoryPageChange = (page: number) => {
    void loadHistory(page);
  };

  const handleBriefSelect = (nextBriefId: string) => {
    if (nextBriefId === brief?.briefId) {
      return;
    }
    void navigate(`/overnight/briefs/${nextBriefId}`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={briefId} />
          <EmptyState title="隔夜晨报加载中" body="正在从后端拉取最新一轮隔夜摘要与事件优先级。" />
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={briefId} />
        <EmptyState
          title="隔夜晨报加载失败"
          body={loadError}
          actionLabel="重新加载"
          onAction={refreshPage}
        />
        <div className="mx-auto mt-6 max-w-7xl grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
          <SourceCatalogPanel sources={sources} isLoading={isOperationsLoading} error={operationsError} />
          <HealthPanel health={health} isLoading={isOperationsLoading} error={operationsError} />
        </div>
        </div>
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={briefId} />
        <EmptyState
          title="当前还没有可读的隔夜晨报"
          body={
            emptyMessage ||
            '这通常说明最近一个截止窗口内还没有成功落库的隔夜事件，而不是页面本身坏掉。'
          }
          actionLabel="再次检查"
          onAction={refreshPage}
        />
        <div className="mx-auto mt-6 max-w-7xl grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
          <SourceCatalogPanel sources={sources} isLoading={isOperationsLoading} error={operationsError} />
          <HealthPanel health={health} isLoading={isOperationsLoading} error={operationsError} />
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={brief.briefId} />
        <OvernightSummaryPanel brief={brief} selectedEvent={selectedEvent} />
        <OvernightActionDesk brief={brief} />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.9fr)]">
          <Card variant="bordered" padding="md">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-muted">Priority Queue</div>
                <h2 className="mt-1 text-xl font-semibold text-white">隔夜事件优先队列</h2>
              </div>
              <Badge variant="history">{brief.topEvents.length}</Badge>
            </div>

            <div className="mt-4 space-y-3">
              {brief.topEvents.map((event) => (
                <OvernightEventCard
                  key={event.eventId}
                  event={event}
                  selected={event.eventId === selectedEventId}
                  onSelect={setSelectedEventId}
                  evidenceLabel={eventDecisionMap.get(event.eventId)?.evidence.label}
                  evidenceVariant={getEvidenceBadgeVariant(eventDecisionMap.get(event.eventId)?.evidence.level || 'mixed')}
                  ashareLead={eventDecisionMap.get(event.eventId)?.ashareLens.actionBody}
                />
              ))}
            </div>
          </Card>

          <div className="space-y-6">
            <Card variant="gradient" padding="lg">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Event Detail</div>
                  <h2 className="mt-1 text-xl font-semibold text-white">当前事件拆解</h2>
                </div>
                {detailToRender ? (
                  <Badge variant={priorityVariant(detailToRender.priorityLevel)} glow>
                    {detailToRender.priorityLevel}
                  </Badge>
                ) : null}
              </div>

              {detailToRender ? (
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">Core Fact</div>
                    <div className="mt-2 text-lg font-medium text-white">{detailToRender.coreFact}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">Summary</div>
                    <div className="mt-2 text-sm leading-6 text-secondary">
                      {detailToRender.summary || '事件摘要暂缺，后续可通过后端分析包补强。'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">Transmission</div>
                    <div className="mt-2 text-sm leading-6 text-white/90">
                      {detailToRender.whyItMatters || '等待更多 cross-asset 反馈来确认影响链条。'}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">Confidence</div>
                    <div className="mt-2 text-2xl font-semibold text-cyan">
                      {Math.round((detailToRender.confidence || 0) * 100)}%
                    </div>
                    {selectedDecision ? (
                      <div className="mt-3">
                        <Badge variant={getEvidenceBadgeVariant(selectedDecision.evidence.level)}>
                          {selectedDecision.evidence.label}
                        </Badge>
                        <div className="mt-2 text-xs leading-5 text-secondary">{selectedDecision.evidence.summary}</div>
                      </div>
                    ) : null}
                  </div>
                  {selectedDecision ? (
                    <div className="rounded-2xl border border-cyan/10 bg-cyan/5 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-cyan/70">A股动作映射</div>
                      <div className="mt-2 text-sm leading-6 text-white/90">{selectedDecision.ashareLens.actionHeadline}</div>
                      <div className="mt-2 text-sm leading-6 text-secondary">
                        先看: {selectedDecision.ashareLens.focusAreas.join(' / ')}
                      </div>
                      <div className="mt-1 text-sm leading-6 text-secondary">
                        回避: {selectedDecision.ashareLens.avoidAreas.join(' / ')}
                      </div>
                      <div className="mt-1 text-sm leading-6 text-secondary">
                        可能涨价: {selectedDecision.ashareLens.pricePressureAreas.join(' / ')}
                      </div>
                    </div>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Link className="btn-secondary" to={`/overnight/events/${detailToRender.eventId}?briefId=${brief.briefId}`}>
                      打开事件详情页
                    </Link>
                    <Link className="btn-secondary" to={buildOvernightTopicHref('policy-radar', brief.briefId)}>
                      看主题页
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="mt-4 text-sm text-secondary">选择左侧事件后可查看详细拆解。</div>
              )}
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Primary Sources</div>
                  <h3 className="mt-1 text-lg font-semibold text-white">抓到的新闻来源</h3>
                </div>
                <Badge variant="default">{capturedNewsItems.length}</Badge>
              </div>

              <div className="mt-4">
                {capturedNewsItems.length ? (
                  <div className="space-y-3">
                    {capturedNewsItems.map((item) => (
                      <a
                        key={item.id}
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 transition hover:border-cyan/30 hover:bg-cyan/6"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-white">{item.headline}</div>
                          <div className="flex flex-wrap gap-2">
                            {item.coverageTier === 'official_policy' || item.coverageTier === 'official_data' ? (
                              <Badge variant="danger">官方源</Badge>
                            ) : item.coverageTier === 'editorial_media' ? (
                              <Badge variant="info">媒体源</Badge>
                            ) : null}
                            {item.sourceClass ? <Badge variant="default">{item.sourceClass}</Badge> : null}
                          </div>
                        </div>
                        <div className="mt-2 text-sm text-secondary">来源: {item.sourceName}</div>
                        {item.summary ? (
                          <div className="mt-2 text-sm leading-6 text-secondary">{item.summary}</div>
                        ) : null}
                        <div className="mt-3 truncate text-sm text-cyan">{item.url}</div>
                      </a>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-secondary">当前选中事件还没有挂接可展示的新闻来源。</div>
                )}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Need Confirmation</div>
                  <h3 className="mt-1 text-lg font-semibold text-white">需要二次确认的点</h3>
                </div>
                <Badge variant="warning">{brief.needConfirmation.length}</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {brief.needConfirmation.length === 0 ? (
                  <div className="text-sm text-secondary">这一轮高优先级事件的置信度尚可，没有额外待确认项。</div>
                ) : (
                  brief.needConfirmation.map((event) => (
                    <div key={event.eventId} className="rounded-2xl border border-amber-500/10 bg-amber-500/[0.03] px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-white">{event.coreFact}</div>
                        <Badge variant="warning">{Math.round((event.confidence || 0) * 100)}%</Badge>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-secondary">{event.summary || event.whyItMatters}</div>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {detailToRender ? (
              <OvernightFeedbackPanel
                targetType="event"
                targetId={detailToRender.eventId}
                briefId={brief.briefId}
                eventId={detailToRender.eventId}
                title="对当前选中事件提反馈"
              />
            ) : null}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <BoardSection
            title="可能受益方向"
            subtitle="Beneficiaries"
            items={brief.likelyBeneficiaries}
            emptyText="当前这轮摘要还没有明确的受益方向卡片。"
            href={buildOvernightTopicHref('beneficiaries', brief.briefId)}
          />
          <BoardSection
            title="可能涨价/更贵的方向"
            subtitle="Price Pressure"
            items={brief.whatMayGetMoreExpensive}
            emptyText="还没有形成明确的涨价链条。"
            href={buildOvernightTopicHref('price-pressure', brief.briefId)}
          />
          <BoardSection
            title="政策雷达"
            subtitle="Policy Radar"
            items={brief.policyRadar}
            emptyText="本轮没有新的政策雷达条目。"
            href={buildOvernightTopicHref('policy-radar', brief.briefId)}
          />
          <BoardSection
            title="市场传导"
            subtitle="Transmission"
            items={brief.sectorTransmission}
            emptyText="市场传导卡片仍待后端补充。"
            href={buildOvernightTopicHref('sector-transmission', brief.briefId)}
          />
        </div>

        <HistoryPanel
          items={historyItems}
          activeBriefId={brief.briefId}
          isLoading={isHistoryLoading}
          currentPage={historyPage}
          totalPages={totalHistoryPages}
          onSelect={handleBriefSelect}
          onPageChange={handleHistoryPageChange}
        />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)]">
          <SourceCatalogPanel sources={sources} isLoading={isOperationsLoading} error={operationsError} />
          <HealthPanel health={health} isLoading={isOperationsLoading} error={operationsError} />
        </div>

        <WatchlistSection buckets={brief.todayWatchlist} briefId={brief.briefId} />
      </div>
    </div>
  );
};

export default OvernightBriefPage;
