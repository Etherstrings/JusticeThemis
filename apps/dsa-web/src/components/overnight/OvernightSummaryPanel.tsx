import type React from 'react';
import { Badge, Card } from '../common';
import type { OvernightBrief, OvernightEventSummary } from '../../types/overnight';

interface OvernightSummaryPanelProps {
  brief: OvernightBrief;
  selectedEvent?: OvernightEventSummary | null;
}

function formatConfidence(value: number): string {
  return `${Math.round((value || 0) * 100)}%`;
}

function formatTimestamp(value: string): string {
  if (!value) return '--';
  return value.replace('T', ' ');
}

export const OvernightSummaryPanel: React.FC<OvernightSummaryPanelProps> = ({
  brief,
  selectedEvent,
}) => {
  const highPriorityCount = brief.topEvents.filter(
    (event) => event.priorityLevel === 'P0' || event.priorityLevel === 'P1'
  ).length;
  const avgConfidence =
    brief.topEvents.length > 0
      ? brief.topEvents.reduce((sum, event) => sum + (event.confidence || 0), 0) / brief.topEvents.length
      : 0;
  const sourceLinkCount = brief.primarySources.reduce((sum, item) => sum + item.links.length, 0);

  const metrics = [
    { label: '重点事件', value: String(brief.topEvents.length), accent: 'text-cyan' },
    { label: '高优先级', value: String(highPriorityCount), accent: 'text-amber-400' },
    { label: '待确认', value: String(brief.needConfirmation.length), accent: 'text-red-400' },
    { label: '平均置信度', value: formatConfidence(avgConfidence), accent: 'text-emerald-400' },
    { label: '源链接数', value: String(sourceLinkCount), accent: 'text-white' },
    { label: '观察桶位', value: String(brief.todayWatchlist.length), accent: 'text-purple-400' },
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
      <Card variant="gradient" padding="lg" className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[radial-gradient(circle_at_top_left,rgba(0,212,255,0.24),transparent_58%)]" />
        <div className="relative">
          <span className="label-uppercase">Overnight Morning Brief</span>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge variant="info" glow>
              截止 {brief.cutoffTime}
            </Badge>
            <Badge variant="history">日期 {brief.digestDate}</Badge>
            <Badge variant="default">版本 v{brief.versionNo}</Badge>
          </div>

          <h1 className="mt-4 max-w-4xl text-2xl font-semibold leading-tight text-white md:text-3xl">
            {brief.topline}
          </h1>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-secondary">
            这是给 A 股早盘前阅读的隔夜驱动摘要。页面重点不是复述新闻，而是把你需要先盯的事件、
            受益方向、可能涨价的链条和需要二次确认的点压缩成一个终端面板。
          </p>

          {selectedEvent ? (
            <div className="mt-5 rounded-2xl border border-cyan/15 bg-cyan/6 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{selectedEvent.priorityLevel}</Badge>
                <span className="text-xs uppercase tracking-[0.24em] text-cyan/70">Active Event</span>
              </div>
              <div className="mt-2 text-sm font-medium text-white">{selectedEvent.coreFact}</div>
              <div className="mt-1 text-xs text-secondary">
                当前选中事件置信度 {formatConfidence(selectedEvent.confidence)}
              </div>
            </div>
          ) : null}

          <div className="mt-5 text-xs text-muted">
            生成时间 {formatTimestamp(brief.generatedAt)}
          </div>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
        {metrics.map((metric) => (
          <Card key={metric.label} variant="bordered" padding="md" className="min-h-[112px]">
            <div className="text-xs uppercase tracking-[0.22em] text-muted">{metric.label}</div>
            <div className={`mt-3 text-3xl font-semibold ${metric.accent}`}>{metric.value}</div>
          </Card>
        ))}
      </div>
    </div>
  );
};
