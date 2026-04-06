import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightFeedbackPanel } from '../components/overnight/OvernightFeedbackPanel';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type {
  OvernightBrief,
  OvernightBriefDeltaEvent,
  OvernightBriefDeltaResponse,
  OvernightEventDetail,
  OvernightEventHistoryItem,
  OvernightEventSummary,
  OvernightWatchBucket,
} from '../types/overnight';
import {
  buildEventActionItemForBrief,
  buildEventDecisionLens,
  getDeltaTypeLabel,
  getEvidenceBadgeVariant,
} from '../utils/overnightDecision';
import {
  buildEventFreshnessState,
  buildPriorityShiftState,
  findMatchingEventHistoryItem,
  type OvernightFreshnessTone,
  type OvernightShiftTone,
} from '../utils/overnightEventContext';
import { buildRelatedEventLinks } from '../utils/overnightLinkage';
import { buildOvernightTopicHref } from '../utils/overnightView';

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Event Detail</div>
    <h1 className="mt-3 text-2xl font-semibold text-white">{title}</h1>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
  </Card>
);

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

function laneVariant(laneKey?: string): 'danger' | 'warning' | 'info' | 'default' {
  switch (laneKey) {
    case 'act-now':
      return 'danger';
    case 'watch-open':
      return 'info';
    case 'wait-confirm':
      return 'warning';
    default:
      return 'default';
  }
}

function freshnessVariant(tone: OvernightFreshnessTone): 'success' | 'info' | 'history' {
  switch (tone) {
    case 'fresh':
      return 'success';
    case 'developing':
      return 'info';
    default:
      return 'history';
  }
}

function shiftVariant(tone: OvernightShiftTone): 'success' | 'warning' | 'info' | 'history' {
  switch (tone) {
    case 'up':
      return 'success';
    case 'down':
      return 'warning';
    case 'new':
      return 'history';
    default:
      return 'info';
  }
}

const OvernightEventDetailPage: React.FC = () => {
  const { eventId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const requestedBriefId = searchParams.get('briefId');

  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [delta, setDelta] = useState<OvernightBriefDeltaResponse | null>(null);
  const [event, setEvent] = useState<OvernightEventSummary | OvernightEventDetail | null>(null);
  const [eventHistory, setEventHistory] = useState<OvernightEventHistoryItem | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [sourceLinks, setSourceLinks] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [briefResult, deltaResult] = await Promise.allSettled([
          requestedBriefId
            ? overnightApi.getBriefById(requestedBriefId)
            : overnightApi.getLatestBrief(),
          requestedBriefId
            ? overnightApi.getBriefDeltaById(requestedBriefId)
            : overnightApi.getLatestBriefDelta(),
        ]);

        if (briefResult.status !== 'fulfilled') {
          throw briefResult.reason;
        }

        const nextBrief = briefResult.value;
        setBrief(nextBrief);
        setDelta(deltaResult.status === 'fulfilled' ? deltaResult.value : null);

        const matchedEvent = nextBrief.topEvents.find((item) => item.eventId === eventId) || null;
        const matchedSources = nextBrief.primarySources.find((item) => item.eventId === eventId)?.links || [];

        if (matchedEvent) {
          setEvent(matchedEvent);
          setSourceLinks(matchedSources);
          return;
        }

        if (!requestedBriefId) {
          const detail = await overnightApi.getEventDetail(eventId);
          if (detail) {
            setEvent(detail);
            setSourceLinks(matchedSources);
            return;
          }
        }

        setEvent(null);
        setDelta(deltaResult.status === 'fulfilled' ? deltaResult.value : null);
        setSourceLinks([]);
        setError('当前选定晨报里找不到这个事件。');
      } catch (nextError) {
        setBrief(null);
        setDelta(null);
        setEvent(null);
        setSourceLinks([]);
        if (nextError instanceof OvernightBriefUnavailableError) {
          setError(nextError.message);
        } else {
          setError(nextError instanceof Error ? nextError.message : '加载事件详情失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [eventId, requestedBriefId]);

  useEffect(() => {
    if (!event?.coreFact) {
      setEventHistory(null);
      setIsHistoryLoading(false);
      return;
    }

    let isCancelled = false;
    setIsHistoryLoading(true);
    setEventHistory(null);

    const loadHistory = async () => {
      try {
        const response = await overnightApi.getEventHistory(1, 8, event.coreFact);
        if (isCancelled) {
          return;
        }
        setEventHistory(findMatchingEventHistoryItem(event.coreFact, response.items));
      } catch {
        if (!isCancelled) {
          setEventHistory(null);
        }
      } finally {
        if (!isCancelled) {
          setIsHistoryLoading(false);
        }
      }
    };

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [event?.coreFact]);

  const briefHref = brief ? `/overnight/briefs/${brief.briefId}` : '/overnight';
  const eventDelta = useMemo<OvernightBriefDeltaEvent | null>(() => {
    if (!delta || !event) {
      return null;
    }

    return (
      [
        ...delta.newEvents,
        ...delta.intensifiedEvents,
        ...delta.steadyEvents,
        ...delta.coolingEvents,
        ...delta.droppedEvents,
      ].find(
        (item) =>
          item.currentEventId === event.eventId ||
          item.previousEventId === event.eventId ||
          item.coreFact === event.coreFact
      ) || null
    );
  }, [delta, event]);
  const eventDecision = useMemo(
    () => (brief && event ? buildEventDecisionLens(brief, event, delta) : null),
    [brief, event, delta]
  );
  const eventAction = useMemo(
    () => (brief && event ? buildEventActionItemForBrief(brief, event, delta) : null),
    [brief, event, delta]
  );
  const eventRank = useMemo(() => {
    if (!brief || !event) {
      return null;
    }
    const index = brief.topEvents.findIndex((item) => item.eventId === event.eventId);
    return index >= 0 ? index + 1 : null;
  }, [brief, event]);
  const watchBucket = useMemo<OvernightWatchBucket | null>(() => {
    if (!brief || !event) {
      return null;
    }
    return brief.todayWatchlist.find((bucket) => bucket.items.some((item) => item.eventId === event.eventId)) || null;
  }, [brief, event]);
  const freshnessState = useMemo(() => buildEventFreshnessState(eventHistory), [eventHistory]);
  const priorityShift = useMemo(() => buildPriorityShiftState(eventDelta), [eventDelta]);
  const relatedEvents = useMemo(
    () => (brief && event ? buildRelatedEventLinks(brief, event, delta) : []),
    [brief, event, delta]
  );
  const historyHref = useMemo(() => {
    if (!event?.coreFact) {
      return '/overnight/history?view=event';
    }
    const params = new URLSearchParams({
      view: 'event',
      q: event.coreFact,
    });
    return `/overnight/history?${params.toString()}`;
  }, [event?.coreFact]);

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="事件详情加载中" body="正在定位对应晨报并提取事件详情。" />
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={brief?.briefId || requestedBriefId} />
          <StateCard title="事件详情不可用" body={error || '当前事件不存在。'} />
          <div className="flex flex-wrap gap-2">
            <Link className="btn-secondary" to={briefHref}>
              返回晨报
            </Link>
            <Link className="btn-secondary" to="/overnight/history">
              查看历史页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={brief?.briefId || requestedBriefId} />

        {brief ? <OvernightSummaryPanel brief={brief} selectedEvent={event} /> : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.9fr)]">
          <div className="space-y-6">
            <Card variant="gradient" padding="lg">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Single Event Desk</div>
                  <h1 className="mt-1 text-2xl font-semibold text-white">{event.coreFact}</h1>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={priorityVariant(event.priorityLevel)} glow>
                    {event.priorityLevel || 'NA'}
                  </Badge>
                  <Badge variant={freshnessVariant(freshnessState.tone)}>{freshnessState.label}</Badge>
                  {eventDecision ? (
                    <Badge variant={getEvidenceBadgeVariant(eventDecision.evidence.level)}>
                      {eventDecision.evidence.label}
                    </Badge>
                  ) : null}
                  {eventDecision?.deltaType ? (
                    <Badge variant="default">{getDeltaTypeLabel(eventDecision.deltaType)}</Badge>
                  ) : null}
                </div>
              </div>

              <div className="mt-5 space-y-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Summary</div>
                  <div className="mt-2 text-sm leading-6 text-secondary">
                    {event.summary || '当前事件还没有更长的摘要描述。'}
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Why It Matters</div>
                  <div className="mt-2 text-sm leading-6 text-white/90">
                    {event.whyItMatters || '当前影响链条仍需结合开盘后市场反馈确认。'}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">Confidence</div>
                    <div className="mt-2 text-3xl font-semibold text-cyan">{Math.round((event.confidence || 0) * 100)}%</div>
                    {eventDecision ? (
                      <div className="mt-2 text-xs leading-5 text-secondary">{eventDecision.evidence.summary}</div>
                    ) : null}
                  </div>

                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">当前处理</div>
                    {eventAction ? (
                      <>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <Badge variant={laneVariant(eventAction.laneKey)}>{eventAction.laneTitle}</Badge>
                          {eventDecision?.deltaType ? (
                            <Badge variant="default">{getDeltaTypeLabel(eventDecision.deltaType)}</Badge>
                          ) : null}
                        </div>
                        <div className="mt-2 text-sm leading-6 text-secondary">{eventAction.action}</div>
                      </>
                    ) : (
                      <div className="mt-2 text-sm leading-6 text-secondary">当前还没有动作建议。</div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">前日对照</div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge variant={shiftVariant(priorityShift.tone)}>{priorityShift.label}</Badge>
                      <Badge variant="default">{priorityShift.confidenceLabel}</Badge>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-secondary">{priorityShift.summary}</div>
                  </div>
                </div>

                {eventAction ? (
                  <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">盘前动作拆解</div>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-muted">Trigger</div>
                        <div className="mt-2 text-sm leading-6 text-secondary">{eventAction.trigger}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-muted">Why Now</div>
                        <div className="mt-2 text-sm leading-6 text-secondary">{eventAction.whyNow}</div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {eventDecision ? (
                  <div className="rounded-2xl border border-cyan/10 bg-cyan/5 px-4 py-4">
                    <div className="text-xs uppercase tracking-[0.18em] text-cyan/70">A股动作映射</div>
                    <div className="mt-2 text-sm leading-6 text-white/90">{eventDecision.ashareLens.actionHeadline}</div>
                    <div className="mt-3 text-sm leading-6 text-secondary">
                      先看: {eventDecision.ashareLens.focusAreas.join(' / ')}
                    </div>
                    <div className="mt-1 text-sm leading-6 text-secondary">
                      回避: {eventDecision.ashareLens.avoidAreas.join(' / ')}
                    </div>
                    <div className="mt-1 text-sm leading-6 text-secondary">
                      可能涨价: {eventDecision.ashareLens.pricePressureAreas.join(' / ')}
                    </div>
                  </div>
                ) : null}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Morning Context</div>
              <h2 className="mt-1 text-lg font-semibold text-white">这条事件在今早晨报里的位置</h2>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Priority Rank</div>
                  <div className="mt-2 text-2xl font-semibold text-white">{eventRank ? `#${eventRank}` : '--'}</div>
                  <div className="mt-2 text-xs text-secondary">当前晨报里的事件排序位置</div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Watch Bucket</div>
                  <div className="mt-2 text-base font-semibold text-white">{watchBucket?.title || '未归类'}</div>
                  <div className="mt-2 text-xs text-secondary">{watchBucket?.summary || '当前没有挂到行动桶位。'}</div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">历史热度</div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Badge variant={freshnessVariant(freshnessState.tone)}>{freshnessState.label}</Badge>
                    {eventHistory?.latestPriorityLevel ? (
                      <Badge variant={priorityVariant(eventHistory.latestPriorityLevel)}>
                        最近 {eventHistory.latestPriorityLevel}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="mt-2 text-xs leading-5 text-secondary">{freshnessState.summary}</div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Primary Sources</div>
                  <div className="mt-2 text-2xl font-semibold text-white">{sourceLinks.length}</div>
                  <div className="mt-2 text-xs text-secondary">当前事件已挂接的一手链接数量</div>
                </div>
              </div>
            </Card>
          </div>

          <div className="space-y-6">
            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Navigation</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="btn-secondary" to={briefHref}>
                  返回晨报
                </Link>
                <Link className="btn-secondary" to={brief ? `/overnight/playbook?briefId=${brief.briefId}` : '/overnight/playbook'}>
                  开盘剧本
                </Link>
                <Link className="btn-secondary" to={brief ? `/overnight/changes?briefId=${brief.briefId}` : '/overnight/changes'}>
                  变化对照
                </Link>
                <Link className="btn-secondary" to="/overnight/history">
                  历史页
                </Link>
                <Link
                  className="btn-secondary"
                  to={brief ? buildOvernightTopicHref('policy-radar', brief.briefId) : '/overnight/topics/policy-radar'}
                >
                  主题页
                </Link>
              </div>
            </Card>

            {eventAction ? (
              <Card variant="bordered" padding="md">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-muted">Opening Call</div>
                    <h2 className="mt-1 text-lg font-semibold text-white">今早怎么处理这条事件</h2>
                  </div>
                  <Badge variant={laneVariant(eventAction.laneKey)}>{eventAction.laneTitle}</Badge>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">盘前动作</div>
                    <div className="mt-2 text-sm leading-6 text-secondary">{eventAction.action}</div>
                  </div>
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">为什么现在处理</div>
                    <div className="mt-2 text-sm leading-6 text-secondary">{eventAction.whyNow}</div>
                  </div>
                </div>
              </Card>
            ) : null}

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">History Trail</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">历史发酵</h2>
                </div>
                <Badge variant={freshnessVariant(freshnessState.tone)}>{freshnessState.label}</Badge>
              </div>

              <div className="mt-4 text-sm leading-6 text-secondary">{freshnessState.summary}</div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">历史出现</div>
                  <div className="mt-2 text-2xl font-semibold text-white">
                    {eventHistory?.occurrenceCount || 1}
                    <span className="ml-1 text-sm font-medium text-secondary">次</span>
                  </div>
                  <div className="mt-2 text-xs text-secondary">看这条线是新催化还是旧主线延续。</div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">均值置信度</div>
                  <div className="mt-2 text-2xl font-semibold text-white">
                    {eventHistory ? `${Math.round((eventHistory.averageConfidence || 0) * 100)}%` : '--'}
                  </div>
                  <div className="mt-2 text-xs text-secondary">历史归档里这条线的平均强度。</div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">最近出现</div>
                  <div className="mt-2 text-base font-semibold text-white">{eventHistory?.latestDigestDate || '仅当前晨报'}</div>
                  <div className="mt-2 text-xs text-secondary">
                    {eventHistory?.latestPriorityLevel ? `最近一次优先级 ${eventHistory.latestPriorityLevel}` : '当前还没有更早的归档记录。'}
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {isHistoryLoading ? (
                  <div className="text-sm text-secondary">正在检索历史发酵轨迹...</div>
                ) : eventHistory?.occurrences.length ? (
                  eventHistory.occurrences.map((occurrence) => (
                    <Link
                      key={`${occurrence.briefId}-${occurrence.eventId}`}
                      className="block rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 transition hover:border-white/12 hover:bg-white/[0.03]"
                      to={`/overnight/events/${occurrence.eventId}?briefId=${occurrence.briefId}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-white">{occurrence.digestDate}</div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={priorityVariant(occurrence.priorityLevel)}>{occurrence.priorityLevel || 'NA'}</Badge>
                          <Badge variant="info">{Math.round((occurrence.confidence || 0) * 100)}%</Badge>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-secondary">打开这一天的同事件页，确认它是持续发酵还是已经钝化。</div>
                    </Link>
                  ))
                ) : (
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm leading-6 text-secondary">
                    当前还没有抓到更早的重复记录，先把它按“新催化”处理。
                  </div>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="btn-secondary" to={historyHref}>
                  事件历史
                </Link>
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Related Chain</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">同晨报联动</h2>
                </div>
                <Badge variant="history">{relatedEvents.length}</Badge>
              </div>

              <div className="mt-4 text-sm leading-6 text-secondary">
                用同一观察桶、共享受益方向、共享涨价链和盘前动作重合度判断这条消息是不是正在形成板块共振。
              </div>

              <div className="mt-4 space-y-3">
                {relatedEvents.length > 0 ? (
                  relatedEvents.slice(0, 4).map((item) => {
                    const relationDecision = brief ? buildEventDecisionLens(brief, item.event, delta) : null;
                    const relationAction = brief ? buildEventActionItemForBrief(brief, item.event, delta) : null;

                    return (
                      <Link
                        key={item.event.eventId}
                        className="block rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4 transition hover:border-white/12 hover:bg-white/[0.03]"
                        to={`/overnight/events/${item.event.eventId}?briefId=${brief?.briefId || requestedBriefId || ''}`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={priorityVariant(item.event.priorityLevel)}>{item.event.priorityLevel || 'NA'}</Badge>
                              {relationDecision ? (
                                <Badge variant={getEvidenceBadgeVariant(relationDecision.evidence.level)}>
                                  {relationDecision.evidence.label}
                                </Badge>
                              ) : null}
                              {relationAction ? (
                                <Badge variant={laneVariant(relationAction.laneKey)}>{relationAction.laneTitle}</Badge>
                              ) : null}
                            </div>
                            <div className="mt-3 text-sm font-medium text-white">{item.event.coreFact}</div>
                          </div>
                          <Badge variant="default">{Math.round((item.event.confidence || 0) * 100)}%</Badge>
                        </div>

                        <div className="mt-3 space-y-1">
                          {item.reasons.map((reason) => (
                            <div key={`${item.event.eventId}-${reason}`} className="text-xs leading-5 text-secondary">
                              {reason}
                            </div>
                          ))}
                        </div>

                        {relationDecision ? (
                          <div className="mt-3 text-xs leading-5 text-secondary">
                            A股 lead: {relationDecision.ashareLens.focusAreas.slice(0, 3).join(' / ')}
                          </div>
                        ) : null}
                      </Link>
                    );
                  })
                ) : (
                  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm leading-6 text-secondary">
                    当前还没有形成明显的同晨报联动，先把它按单点驱动处理。
                  </div>
                )}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Primary Sources</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">原始链接</h2>
                </div>
                <Badge variant="default">{sourceLinks.length}</Badge>
              </div>

              <div className="mt-4 space-y-2">
                {sourceLinks.length > 0 ? (
                  sourceLinks.map((link) => (
                    <a
                      key={link}
                      href={link}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-xl border border-white/6 bg-white/[0.02] px-3 py-2 text-sm text-cyan transition hover:border-cyan/30 hover:bg-cyan/6"
                    >
                      {link}
                    </a>
                  ))
                ) : (
                  <div className="text-sm text-secondary">当前事件还没有挂接到 primary source links。</div>
                )}
              </div>
            </Card>

            <OvernightFeedbackPanel
              targetType="event"
              targetId={event.eventId}
              briefId={brief?.briefId}
              eventId={event.eventId}
              title="这条事件排序和结论是否合理"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default OvernightEventDetailPage;
