import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightActionDesk } from '../components/overnight/OvernightActionDesk';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type { OvernightBrief, OvernightWatchBucket } from '../types/overnight';
import {
  buildOvernightTopicHref,
  formatOvernightDateTime,
  summarizeOvernightBoardItem,
} from '../utils/overnightView';

type BucketFilter = 'all' | string;

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Opening Board</div>
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

function bucketVariant(bucketKey: string): 'danger' | 'warning' | 'info' | 'default' {
  switch (bucketKey) {
    case 'needs-confirmation':
      return 'warning';
    case 'awaiting-pricing':
      return 'danger';
    case 'scheduled-release':
      return 'info';
    default:
      return 'default';
  }
}

const OpeningBoardPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedBriefId = searchParams.get('briefId');
  const bucketFilter = (searchParams.get('bucket') || 'all') as BucketFilter;

  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const nextBrief = requestedBriefId
          ? await overnightApi.getBriefById(requestedBriefId)
          : await overnightApi.getLatestBrief();
        setBrief(nextBrief);
      } catch (nextError) {
        setBrief(null);
        if (nextError instanceof OvernightBriefUnavailableError) {
          setError(nextError.message);
        } else {
          setError(nextError instanceof Error ? nextError.message : '加载开盘前行动板失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [requestedBriefId]);

  const bucketOptions = useMemo(() => {
    if (!brief) {
      return [{ key: 'all', label: '全部' }];
    }
    return [
      { key: 'all', label: '全部' },
      ...brief.todayWatchlist.map((bucket) => ({
        key: bucket.bucketKey,
        label: bucket.title,
      })),
    ];
  }, [brief]);

  const normalizedBucketFilter = useMemo(() => {
    if (bucketFilter === 'all') {
      return 'all';
    }
    return bucketOptions.some((option) => option.key === bucketFilter) ? bucketFilter : 'all';
  }, [bucketFilter, bucketOptions]);

  const visibleBuckets = useMemo<OvernightWatchBucket[]>(() => {
    if (!brief) {
      return [];
    }
    if (normalizedBucketFilter === 'all') {
      return brief.todayWatchlist;
    }
    return brief.todayWatchlist.filter((bucket) => bucket.bucketKey === normalizedBucketFilter);
  }, [brief, normalizedBucketFilter]);

  const totalWatchItems = useMemo(
    () => (brief ? brief.todayWatchlist.reduce((sum, bucket) => sum + bucket.items.length, 0) : 0),
    [brief]
  );
  const urgentWatchItems = useMemo(
    () =>
      visibleBuckets.reduce(
        (sum, bucket) =>
          sum + bucket.items.filter((item) => ['P0', 'P1'].includes((item.priorityLevel || '').toUpperCase())).length,
        0
      ),
    [visibleBuckets]
  );
  const linkedEvents = useMemo(
    () => visibleBuckets.reduce((sum, bucket) => sum + bucket.items.filter((item) => item.eventId).length, 0),
    [visibleBuckets]
  );

  const updateQuery = (next: { bucket?: string }) => {
    const params = new URLSearchParams();
    const nextBucket = next.bucket ?? normalizedBucketFilter;
    if (requestedBriefId) {
      params.set('briefId', requestedBriefId);
    }
    if (nextBucket && nextBucket !== 'all') {
      params.set('bucket', nextBucket);
    }
    setSearchParams(params);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="开盘前行动板加载中" body="正在读取当前晨报中的关注项、触发条件和行动建议。" />
        </div>
      </div>
    );
  }

  if (error || !brief) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="开盘前行动板不可用" body={error || '当前没有可展示的行动板。'} />
          <div className="flex flex-wrap gap-2">
            <Link className="btn-secondary" to="/overnight">
              返回实时晨报
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
        <OvernightRouteNav briefId={brief.briefId} />
        <OvernightSummaryPanel brief={brief} />
        <OvernightActionDesk
          brief={brief}
          compact
          title="开盘前 15 分钟动作总览"
          subtitle="Opening Translator"
        />

        <Card variant="gradient" padding="lg">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Opening Board</div>
              <h1 className="mt-3 text-3xl font-semibold text-white">开盘前行动板</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">
                把隔夜晨报里的重点事件重新整理成“触发条件 + 建议动作”。早上不是只看新闻，而是快速知道该先确认什么、先盯什么、先等什么。
              </p>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm text-secondary">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Loaded Brief</div>
              <div className="mt-2 font-medium text-white">{brief.digestDate}</div>
              <div className="mt-1">{formatOvernightDateTime(brief.generatedAt)}</div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Watch Items</div>
              <div className="mt-2 text-2xl font-semibold text-white">{totalWatchItems}</div>
              <div className="mt-2 text-xs text-secondary">当前晨报已拆成多少条可执行关注项</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Urgent Focus</div>
              <div className="mt-2 text-2xl font-semibold text-white">{urgentWatchItems}</div>
              <div className="mt-2 text-xs text-secondary">当前筛选下的 P0 / P1 关注项</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Linked Events</div>
              <div className="mt-2 text-2xl font-semibold text-white">{linkedEvents}</div>
              <div className="mt-2 text-xs text-secondary">可以直接点进事件详情继续追踪</div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {bucketOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => updateQuery({ bucket: option.key })}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  normalizedBucketFilter === option.key
                    ? 'border-cyan/30 bg-cyan/10 text-cyan'
                    : 'border-white/8 bg-white/[0.02] text-secondary hover:border-white/12 hover:text-white'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
          <div className="space-y-4">
            {visibleBuckets.map((bucket) => (
              <Card key={bucket.bucketKey} variant="bordered" padding="md">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">{bucket.bucketKey}</div>
                    <h2 className="mt-1 text-xl font-semibold text-white">{bucket.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-secondary">{bucket.summary}</p>
                  </div>
                  <Badge variant={bucketVariant(bucket.bucketKey)}>{bucket.items.length}</Badge>
                </div>

                {bucket.items.length === 0 ? (
                  <div className="mt-4 text-sm text-secondary">当前桶里没有待处理项目。</div>
                ) : (
                  <div className="mt-4 space-y-3">
                    {bucket.items.map((item) => (
                      <div key={item.watchId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="info">{item.label}</Badge>
                              {item.priorityLevel ? (
                                <Badge variant={priorityVariant(item.priorityLevel)}>{item.priorityLevel}</Badge>
                              ) : null}
                              <Badge variant="default">{Math.round((item.confidence || 0) * 100)}%</Badge>
                            </div>
                            <div className="mt-3 text-base font-medium text-white">{item.coreFact}</div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {item.eventId ? (
                              <Link className="btn-secondary" to={`/overnight/events/${item.eventId}?briefId=${brief.briefId}`}>
                                事件详情
                              </Link>
                            ) : null}
                            <Link className="btn-secondary" to={`/overnight/briefs/${brief.briefId}`}>
                              返回晨报
                            </Link>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                            <div className="text-xs uppercase tracking-[0.18em] text-muted">Trigger</div>
                            <div className="mt-2 text-sm leading-6 text-secondary">{item.trigger}</div>
                          </div>
                          <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                            <div className="text-xs uppercase tracking-[0.18em] text-muted">Action</div>
                            <div className="mt-2 text-sm leading-6 text-secondary">{item.action}</div>
                          </div>
                        </div>

                        {item.marketReaction ? (
                          <div className="mt-3 rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                            <div className="text-xs uppercase tracking-[0.18em] text-muted">First Priced Object</div>
                            <div className="mt-2 text-sm leading-6 text-white/90">{item.marketReaction}</div>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>

          <div className="space-y-6">
            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Navigation</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="btn-secondary" to={`/overnight/briefs/${brief.briefId}`}>
                  当前晨报
                </Link>
                <Link className="btn-secondary" to={`/overnight/playbook?briefId=${brief.briefId}`}>
                  开盘剧本
                </Link>
                <Link className="btn-secondary" to={`/overnight/changes?briefId=${brief.briefId}`}>
                  变化对照
                </Link>
                <Link className="btn-secondary" to="/overnight/history">
                  历史页
                </Link>
                <Link className="btn-secondary" to={buildOvernightTopicHref('policy-radar', brief.briefId)}>
                  政策主题页
                </Link>
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Likely Beneficiaries</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">可能受益方向</h2>
                </div>
                <Badge variant="default">{brief.likelyBeneficiaries.length}</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {brief.likelyBeneficiaries.slice(0, 3).map((item, index) => {
                  const summary = summarizeOvernightBoardItem(item);
                  return (
                    <div key={`beneficiary-${index}`} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                      <div className="text-sm font-medium text-white">{summary.headline}</div>
                      {summary.meta.map((line) => (
                        <div key={line} className="mt-1 text-xs leading-5 text-secondary">
                          {line}
                        </div>
                      ))}
                    </div>
                  );
                })}
                {brief.likelyBeneficiaries.length === 0 ? (
                  <div className="text-sm text-secondary">当前晨报还没有明确受益方向。</div>
                ) : null}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Price Pressure</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">可能涨价 / 更贵方向</h2>
                </div>
                <Badge variant="default">{brief.whatMayGetMoreExpensive.length}</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {brief.whatMayGetMoreExpensive.slice(0, 3).map((item, index) => {
                  const summary = summarizeOvernightBoardItem(item);
                  return (
                    <div key={`price-pressure-${index}`} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
                      <div className="text-sm font-medium text-white">{summary.headline}</div>
                      {summary.meta.map((line) => (
                        <div key={line} className="mt-1 text-xs leading-5 text-secondary">
                          {line}
                        </div>
                      ))}
                    </div>
                  );
                })}
                {brief.whatMayGetMoreExpensive.length === 0 ? (
                  <div className="text-sm text-secondary">当前晨报还没有明确的涨价链。</div>
                ) : null}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted">Need Confirmation</div>
                  <h2 className="mt-1 text-lg font-semibold text-white">仍需确认的事件</h2>
                </div>
                <Badge variant="warning">{brief.needConfirmation.length}</Badge>
              </div>
              <div className="mt-4 space-y-2">
                {brief.needConfirmation.length === 0 ? (
                  <div className="text-sm text-secondary">当前没有低置信度事件。</div>
                ) : (
                  brief.needConfirmation.map((event) => (
                    <Link
                      key={event.eventId}
                      to={`/overnight/events/${event.eventId}?briefId=${brief.briefId}`}
                      className="block rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 transition hover:border-white/12 hover:bg-white/[0.03]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-white">{event.coreFact}</div>
                        <Badge variant={priorityVariant(event.priorityLevel)}>{event.priorityLevel}</Badge>
                      </div>
                      <div className="mt-2 text-xs text-secondary">置信度 {Math.round((event.confidence || 0) * 100)}%</div>
                    </Link>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OpeningBoardPage;
