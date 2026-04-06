import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightActionDesk } from '../components/overnight/OvernightActionDesk';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type { OvernightBrief, OvernightBriefDeltaResponse } from '../types/overnight';
import { formatOvernightDateTime } from '../utils/overnightView';
import { buildOvernightPlaybook } from '../utils/overnightPlaybook';

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Opening Playbook</div>
    <h1 className="mt-3 text-2xl font-semibold text-white">{title}</h1>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
  </Card>
);

function severityVariant(severity: string): 'danger' | 'warning' | 'info' | 'default' {
  switch (severity) {
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
      return 'info';
    default:
      return 'default';
  }
}

const OvernightPlaybookPage: React.FC = () => {
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
          setError(nextError instanceof Error ? nextError.message : '加载开盘剧本失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [requestedBriefId]);

  const playbook = useMemo(() => {
    if (!brief) {
      return null;
    }
    return buildOvernightPlaybook(brief, delta);
  }, [brief, delta]);

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="开盘剧本加载中" body="正在把晨报事件压缩成时间顺序、方向共识和风险红线。" />
        </div>
      </div>
    );
  }

  if (error || !brief || !delta || !playbook) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="开盘剧本不可用" body={error || '当前没有可展示的开盘剧本。'} />
          <div className="flex flex-wrap gap-2">
            <Link className="btn-secondary" to="/overnight">
              返回实时晨报
            </Link>
            <Link className="btn-secondary" to="/overnight/opening">
              去行动板
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
              <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Opening Playbook</div>
              <h1 className="mt-3 text-3xl font-semibold text-white">开盘剧本</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">{playbook.headline}</p>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm text-secondary">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Loaded Brief</div>
              <div className="mt-2 font-medium text-white">{brief.digestDate}</div>
              <div className="mt-1">{formatOvernightDateTime(brief.generatedAt)}</div>
              <div className="mt-2 text-xs text-secondary">变化摘要 {delta.summary}</div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">先看方向</div>
              <div className="mt-2 text-sm leading-6 text-white">{playbook.focusAreas.join(' / ')}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">先回避</div>
              <div className="mt-2 text-sm leading-6 text-white">{playbook.avoidAreas.join(' / ')}</div>
            </div>
            <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">可能涨价</div>
              <div className="mt-2 text-sm leading-6 text-white">{playbook.pricePressureAreas.join(' / ')}</div>
            </div>
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(340px,0.9fr)]">
          <div className="space-y-4">
            {playbook.steps.map((step) => (
              <Card key={step.stepKey} variant="bordered" padding="md">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-muted">{step.windowLabel}</div>
                    <h2 className="mt-1 text-xl font-semibold text-white">{step.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-secondary">{step.objective}</p>
                  </div>
                  <Badge variant="history">{step.lines.length}</Badge>
                </div>

                <div className="mt-4 space-y-3">
                  {step.lines.map((line) => (
                    <div key={line.lineId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-white">{line.headline}</div>
                          <div className="mt-2 text-sm leading-6 text-secondary">{line.detail}</div>
                        </div>
                        {line.eventId ? (
                          <Link className="btn-secondary" to={`/overnight/events/${line.eventId}?briefId=${brief.briefId}`}>
                            事件详情
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </div>

          <div className="space-y-6">
            <OvernightActionDesk
              brief={brief}
              delta={delta}
              compact
              title="动作压缩版"
              subtitle="Action Compression"
            />

            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Risk Gates</div>
              <h2 className="mt-1 text-lg font-semibold text-white">今早的风险红线</h2>
              <div className="mt-4 space-y-3">
                {playbook.riskGates.map((gate) => (
                  <div key={gate.gateId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white">{gate.title}</div>
                      <Badge variant={severityVariant(gate.severity)}>{gate.severity}</Badge>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-secondary">{gate.body}</div>
                  </div>
                ))}
              </div>
            </Card>

            <Card variant="bordered" padding="md">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Navigation</div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="btn-secondary" to={`/overnight/briefs/${brief.briefId}`}>
                  当前晨报
                </Link>
                <Link className="btn-secondary" to={`/overnight/opening?briefId=${brief.briefId}`}>
                  行动板
                </Link>
                <Link className="btn-secondary" to={`/overnight/changes?briefId=${brief.briefId}`}>
                  变化对照
                </Link>
                <Link className="btn-secondary" to="/overnight/history">
                  历史页
                </Link>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OvernightPlaybookPage;

