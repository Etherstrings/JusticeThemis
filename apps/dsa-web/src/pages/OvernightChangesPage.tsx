import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightActionDesk } from '../components/overnight/OvernightActionDesk';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type { OvernightBrief, OvernightBriefDeltaEvent, OvernightBriefDeltaResponse } from '../types/overnight';
import { formatOvernightDateTime } from '../utils/overnightView';
import { buildDeltaDecisionLens, getEvidenceBadgeVariant } from '../utils/overnightDecision';

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Brief Delta</div>
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

function deltaVariant(deltaType: string): 'danger' | 'warning' | 'info' | 'default' {
  switch (deltaType) {
    case 'new':
      return 'info';
    case 'intensified':
      return 'danger';
    case 'cooling':
      return 'warning';
    case 'dropped':
      return 'default';
    default:
      return 'default';
  }
}

const DeltaSection: React.FC<{
  title: string;
  subtitle: string;
  brief: OvernightBrief;
  briefId: string;
  previousBriefId?: string | null;
  items: OvernightBriefDeltaEvent[];
}> = ({ title, subtitle, brief, briefId, previousBriefId, items }) => (
  <Card variant="bordered" padding="md">
    <div className="flex items-center justify-between gap-3">
      <div>
        <div className="text-xs uppercase tracking-[0.18em] text-muted">{subtitle}</div>
        <h2 className="mt-1 text-xl font-semibold text-white">{title}</h2>
      </div>
      <Badge variant="history">{items.length}</Badge>
    </div>

    {items.length === 0 ? (
      <div className="mt-4 text-sm text-secondary">当前没有落在这个变化分类里的事件。</div>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item) => {
          const decision = buildDeltaDecisionLens(brief, item);
          const targetBriefId = item.deltaType === 'dropped' ? previousBriefId : briefId;
          const targetEventId = item.deltaType === 'dropped' ? item.previousEventId : item.currentEventId;
          const visiblePriority = item.currentPriorityLevel || item.previousPriorityLevel;
          const visibleConfidence =
            item.currentConfidence > 0 ? item.currentConfidence : item.previousConfidence;
          return (
            <div key={`${title}-${item.eventKey}`} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={deltaVariant(item.deltaType)}>{item.deltaType}</Badge>
                    {visiblePriority ? (
                      <Badge variant={priorityVariant(visiblePriority)}>{visiblePriority}</Badge>
                    ) : null}
                    <Badge variant={getEvidenceBadgeVariant(decision.evidence.level)}>{decision.evidence.label}</Badge>
                    <Badge variant="default">{Math.round((visibleConfidence || 0) * 100)}%</Badge>
                  </div>
                  <div className="mt-3 text-base font-medium text-white">{item.coreFact}</div>
                </div>
                {targetBriefId && targetEventId ? (
                  <Link className="btn-secondary" to={`/overnight/events/${targetEventId}?briefId=${targetBriefId}`}>
                    事件详情
                  </Link>
                ) : null}
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Priority Delta</div>
                  <div className="mt-2 text-sm leading-6 text-secondary">
                    {item.previousPriorityLevel || 'NA'} {'->'} {item.currentPriorityLevel || 'NA'}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted">Confidence Delta</div>
                  <div className="mt-2 text-sm leading-6 text-secondary">
                    {Math.round((item.previousConfidence || 0) * 100)}% {'->'} {Math.round((item.currentConfidence || 0) * 100)}%
                  </div>
                </div>
              </div>

              <div className="mt-3 rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-muted">Delta Summary</div>
                <div className="mt-2 text-sm leading-6 text-secondary">{item.deltaSummary}</div>
              </div>

              <div className="mt-3 rounded-2xl border border-cyan/10 bg-cyan/5 px-4 py-3">
                <div className="text-xs uppercase tracking-[0.18em] text-cyan/70">A股应对</div>
                <div className="mt-2 text-sm leading-6 text-white/90">{decision.ashareLens.actionHeadline}</div>
                <div className="mt-2 text-sm leading-6 text-secondary">
                  先看: {decision.ashareLens.focusAreas.join(' / ')}
                </div>
                <div className="mt-1 text-sm leading-6 text-secondary">
                  回避: {decision.ashareLens.avoidAreas.join(' / ')}
                </div>
                <div className="mt-1 text-sm leading-6 text-secondary">
                  可能涨价: {decision.ashareLens.pricePressureAreas.join(' / ')}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    )}
  </Card>
);

const OvernightChangesPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const requestedBriefId = searchParams.get('briefId');

  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [delta, setDelta] = useState<OvernightBriefDeltaResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [nextBrief, nextDelta] = await Promise.all([
          requestedBriefId ? overnightApi.getBriefById(requestedBriefId) : overnightApi.getLatestBrief(),
          requestedBriefId ? overnightApi.getBriefDeltaById(requestedBriefId) : overnightApi.getLatestBriefDelta(),
        ]);
        setBrief(nextBrief);
        setDelta(nextDelta);
      } catch (nextError) {
        setBrief(null);
        setDelta(null);
        if (nextError instanceof OvernightBriefUnavailableError) {
          setError(nextError.message);
        } else {
          setError(nextError instanceof Error ? nextError.message : '加载晨报变化对照失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [requestedBriefId]);

  const totalChanges = useMemo(() => {
    if (!delta) {
      return 0;
    }
    return (
      delta.newEvents.length +
      delta.intensifiedEvents.length +
      delta.steadyEvents.length +
      delta.coolingEvents.length +
      delta.droppedEvents.length
    );
  }, [delta]);

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="晨报变化对照加载中" body="正在比较当前晨报与上一版晨报的事件变化。" />
        </div>
      </div>
    );
  }

  if (error || !brief || !delta) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="晨报变化对照不可用" body={error || '当前没有可展示的变化对照。'} />
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

        <Card variant="gradient" padding="lg">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Change Desk</div>
              <h1 className="mt-3 text-3xl font-semibold text-white">晨报变化对照</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">{delta.summary}</p>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm text-secondary">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Current Brief</div>
              <div className="mt-2 font-medium text-white">{delta.digestDate}</div>
              <div className="mt-1">{formatOvernightDateTime(brief.generatedAt)}</div>
              <div className="mt-2 text-xs text-secondary">上一版 {delta.previousDigestDate || '暂无'}</div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Total</div>
              <div className="mt-2 text-2xl font-semibold text-white">{totalChanges}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">New</div>
              <div className="mt-2 text-2xl font-semibold text-white">{delta.newEvents.length}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Intensified</div>
              <div className="mt-2 text-2xl font-semibold text-white">{delta.intensifiedEvents.length}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Cooling</div>
              <div className="mt-2 text-2xl font-semibold text-white">{delta.coolingEvents.length}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Dropped</div>
              <div className="mt-2 text-2xl font-semibold text-white">{delta.droppedEvents.length}</div>
            </div>
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
          <div className="space-y-4">
            <DeltaSection
              title="新增催化"
              subtitle="New Events"
              brief={brief}
              briefId={delta.briefId}
              previousBriefId={delta.previousBriefId}
              items={delta.newEvents}
            />
            <DeltaSection
              title="持续升温"
              subtitle="Intensified"
              brief={brief}
              briefId={delta.briefId}
              previousBriefId={delta.previousBriefId}
              items={delta.intensifiedEvents}
            />
            <DeltaSection
              title="持续主线"
              subtitle="Steady"
              brief={brief}
              briefId={delta.briefId}
              previousBriefId={delta.previousBriefId}
              items={delta.steadyEvents}
            />
            <DeltaSection
              title="开始降温"
              subtitle="Cooling"
              brief={brief}
              briefId={delta.briefId}
              previousBriefId={delta.previousBriefId}
              items={delta.coolingEvents}
            />
            <DeltaSection
              title="已经掉队"
              subtitle="Dropped"
              brief={brief}
              briefId={delta.briefId}
              previousBriefId={delta.previousBriefId}
              items={delta.droppedEvents}
            />
          </div>

          <div className="space-y-6">
            <OvernightActionDesk
              brief={brief}
              delta={delta}
              compact
              title="今早怎么处理这些变化"
              subtitle="Action Translation"
            />

            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Navigation</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="btn-secondary" to={`/overnight/briefs/${delta.briefId}`}>
                  当前晨报
                </Link>
                {delta.previousBriefId ? (
                  <Link className="btn-secondary" to={`/overnight/briefs/${delta.previousBriefId}`}>
                    上一版晨报
                  </Link>
                ) : null}
                <Link className="btn-secondary" to="/overnight/opening">
                  行动板
                </Link>
                <Link className="btn-secondary" to={`/overnight/playbook?briefId=${delta.briefId}`}>
                  开盘剧本
                </Link>
                <Link className="btn-secondary" to="/overnight/history?view=event">
                  事件历史
                </Link>
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">How To Read</div>
              <div className="mt-4 space-y-3 text-sm leading-6 text-secondary">
                <div>新增催化：前一版没有，今天第一次进入晨报。</div>
                <div>持续升温：优先级或置信度上调，说明主线更强。</div>
                <div>持续主线：还在，但强弱没有显著变化。</div>
                <div>开始降温：还在晨报里，但优先级或置信度下来了。</div>
                <div>已经掉队：前一版出现过，这一版已经不在重点列表里。</div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OvernightChangesPage;
