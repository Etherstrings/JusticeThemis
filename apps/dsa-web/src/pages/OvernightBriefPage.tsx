import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightEventCard } from '../components/overnight/OvernightEventCard';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type {
  OvernightBoardItem,
  OvernightBrief,
  OvernightEventDetail,
  OvernightEventSummary,
  OvernightPrimarySourceGroup,
  OvernightWatchBucket,
} from '../types/overnight';

function humanizeKey(key: string): string {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^./, (char) => char.toUpperCase());
}

function stringifyValue(value: unknown): string {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map((item) => stringifyValue(item)).filter(Boolean).join(' / ');
  if (typeof value === 'object') return '';
  return String(value);
}

function summarizeBoardItem(item: OvernightBoardItem): { headline: string; meta: string[] } {
  const preferredHeadline =
    stringifyValue(item.title) ||
    stringifyValue(item.coreFact) ||
    stringifyValue(item.summary) ||
    stringifyValue(item.eventId) ||
    'Untitled';

  const meta = Object.entries(item)
    .filter(([key, value]) => !['title', 'coreFact', 'summary', 'eventId'].includes(key) && stringifyValue(value))
    .slice(0, 3)
    .map(([key, value]) => `${humanizeKey(key)}: ${stringifyValue(value)}`);

  return { headline: preferredHeadline, meta };
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

const BoardSection: React.FC<{ title: string; subtitle: string; items: OvernightBoardItem[]; emptyText: string }> = ({
  title,
  subtitle,
  items,
  emptyText,
}) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-muted">{subtitle}</div>
        <h3 className="mt-1 text-lg font-semibold text-white">{title}</h3>
      </div>
      <Badge variant="default">{items.length}</Badge>
    </div>

    {items.length === 0 ? (
      <p className="mt-4 text-sm text-secondary">{emptyText}</p>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => {
          const summary = summarizeBoardItem(item);
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

const WatchlistSection: React.FC<{ buckets: OvernightWatchBucket[] }> = ({ buckets }) => (
  <Card variant="bordered" padding="md">
    <div className="text-xs uppercase tracking-[0.2em] text-muted">Watchlist</div>
    <h3 className="mt-1 text-lg font-semibold text-white">今日开盘前要盯的四个桶</h3>

    <div className="mt-4 grid gap-3 md:grid-cols-2">
      {buckets.map((bucket) => (
        <div key={bucket.title} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium text-white">{bucket.title}</div>
            <Badge variant="default">{bucket.items.length}</Badge>
          </div>
          {bucket.items.length === 0 ? (
            <div className="mt-3 text-sm text-secondary">暂无项目</div>
          ) : (
            <div className="mt-3 space-y-2">
              {bucket.items.map((item) => (
                <div key={item} className="text-sm leading-6 text-secondary">
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  </Card>
);

const SourceList: React.FC<{ links: string[] }> = ({ links }) => (
  <div className="space-y-2">
    {links.map((link) => (
      <a
        key={link}
        href={link}
        target="_blank"
        rel="noreferrer"
        className="block rounded-xl border border-white/6 bg-white/[0.02] px-3 py-2 text-sm text-cyan transition hover:border-cyan/30 hover:bg-cyan/6"
      >
        {link}
      </a>
    ))}
  </div>
);

const OvernightBriefPage: React.FC = () => {
  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedEventDetail, setSelectedEventDetail] = useState<OvernightEventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);

  const loadBrief = async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const nextBrief = await overnightApi.getLatestBrief();
      setBrief(nextBrief);
      setEmptyMessage(null);
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
        return;
      }
      setLoadError(error instanceof Error ? error.message : '加载隔夜晨报失败');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadBrief();
  }, []);

  useEffect(() => {
    if (!selectedEventId) {
      setSelectedEventDetail(null);
      return;
    }

    let active = true;
    setIsLoadingDetail(true);

    overnightApi
      .getEventDetail(selectedEventId)
      .then((detail) => {
        if (active) {
          setSelectedEventDetail(detail);
        }
      })
      .catch((error) => {
        if (active) {
          console.error('Failed to load overnight event detail:', error);
          setSelectedEventDetail(null);
        }
      })
      .finally(() => {
        if (active) {
          setIsLoadingDetail(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedEventId]);

  const selectedEvent = useMemo<OvernightEventSummary | null>(() => {
    if (!brief || !selectedEventId) return null;
    return brief.topEvents.find((item) => item.eventId === selectedEventId) || null;
  }, [brief, selectedEventId]);

  const selectedSources = useMemo<OvernightPrimarySourceGroup | null>(() => {
    if (!brief || !selectedEventId) return null;
    return brief.primarySources.find((item) => item.eventId === selectedEventId) || null;
  }, [brief, selectedEventId]);

  const detailToRender = selectedEventDetail || selectedEvent;

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <EmptyState title="隔夜晨报加载中" body="正在从后端拉取最新一轮隔夜摘要与事件优先级。" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <EmptyState
          title="隔夜晨报加载失败"
          body={loadError}
          actionLabel="重新加载"
          onAction={() => {
            void loadBrief();
          }}
        />
      </div>
    );
  }

  if (!brief) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <EmptyState
          title="当前还没有可读的隔夜晨报"
          body={
            emptyMessage ||
            '这通常说明最近一个截止窗口内还没有成功落库的隔夜事件，而不是页面本身坏掉。'
          }
          actionLabel="再次检查"
          onAction={() => {
            void loadBrief();
          }}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightSummaryPanel brief={brief} selectedEvent={selectedEvent} />

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
                  </div>
                </div>
              ) : isLoadingDetail ? (
                <div className="mt-4 text-sm text-secondary">正在加载事件详情...</div>
              ) : (
                <div className="mt-4 text-sm text-secondary">选择左侧事件后可查看详细拆解。</div>
              )}
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Primary Sources</div>
                  <h3 className="mt-1 text-lg font-semibold text-white">当前事件源链接</h3>
                </div>
                <Badge variant="default">{selectedSources?.links.length || 0}</Badge>
              </div>

              <div className="mt-4">
                {selectedSources?.links.length ? (
                  <SourceList links={selectedSources.links} />
                ) : (
                  <div className="text-sm text-secondary">当前选中事件还没有挂接原始链接。</div>
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
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <BoardSection
            title="可能受益方向"
            subtitle="Beneficiaries"
            items={brief.likelyBeneficiaries}
            emptyText="当前这轮摘要还没有明确的受益方向卡片。"
          />
          <BoardSection
            title="可能涨价/更贵的方向"
            subtitle="Price Pressure"
            items={brief.whatMayGetMoreExpensive}
            emptyText="还没有形成明确的涨价链条。"
          />
          <BoardSection
            title="政策雷达"
            subtitle="Policy Radar"
            items={brief.policyRadar}
            emptyText="本轮没有新的政策雷达条目。"
          />
          <BoardSection
            title="市场传导"
            subtitle="Transmission"
            items={brief.sectorTransmission}
            emptyText="市场传导卡片仍待后端补充。"
          />
        </div>

        <WatchlistSection buckets={brief.todayWatchlist} />
      </div>
    </div>
  );
};

export default OvernightBriefPage;
