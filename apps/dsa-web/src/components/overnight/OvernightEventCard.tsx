import type React from 'react';
import { Badge, Card } from '../common';
import type { OvernightEventSummary } from '../../types/overnight';

interface OvernightEventCardProps {
  event: OvernightEventSummary;
  selected?: boolean;
  onSelect?: (eventId: string) => void;
  evidenceLabel?: string;
  evidenceVariant?: 'success' | 'warning' | 'info' | 'default';
  ashareLead?: string;
  deltaLabel?: string | null;
}

function priorityVariant(priorityLevel: string): 'danger' | 'warning' | 'info' | 'default' {
  switch (priorityLevel) {
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

export const OvernightEventCard: React.FC<OvernightEventCardProps> = ({
  event,
  selected = false,
  onSelect,
  evidenceLabel,
  evidenceVariant = 'default',
  ashareLead,
  deltaLabel,
}) => {
  const confidence = `${Math.round((event.confidence || 0) * 100)}%`;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(event.eventId)}
      className="w-full text-left"
    >
      <Card
        variant={selected ? 'gradient' : 'bordered'}
        padding="md"
        className={selected ? 'ring-1 ring-cyan/20' : ''}
        hoverable
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={priorityVariant(event.priorityLevel)} glow={event.priorityLevel === 'P0'}>
              {event.priorityLevel || 'NA'}
            </Badge>
            {evidenceLabel ? (
              <Badge variant={evidenceVariant}>{evidenceLabel}</Badge>
            ) : null}
            {deltaLabel ? (
              <Badge variant="default">{deltaLabel}</Badge>
            ) : null}
            <span className="text-xs uppercase tracking-[0.2em] text-muted">Confidence {confidence}</span>
          </div>
          <span className="text-xs font-mono text-secondary">{event.eventId}</span>
        </div>

        <div className="mt-4">
          <h3 className="text-base font-semibold leading-6 text-white">{event.coreFact}</h3>
          <p className="mt-2 text-sm leading-6 text-secondary">
            {event.summary || '摘要尚未展开，优先参考下方事件详情。'}
          </p>
        </div>

        <div className="mt-4 border-t border-white/6 pt-3">
          <div className="text-xs uppercase tracking-[0.18em] text-muted">Why It Matters</div>
          <p className="mt-2 text-sm leading-6 text-white/90">
            {event.whyItMatters || '当前事件影响链条仍需结合开盘后价格反馈进一步判断。'}
          </p>
        </div>

        {ashareLead ? (
          <div className="mt-4 rounded-2xl border border-cyan/10 bg-cyan/5 px-3 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-cyan/70">A股映射</div>
            <p className="mt-2 text-sm leading-6 text-secondary">{ashareLead}</p>
          </div>
        ) : null}
      </Card>
    </button>
  );
};
