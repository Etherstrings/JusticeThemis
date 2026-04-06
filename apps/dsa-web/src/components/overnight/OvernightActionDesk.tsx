import type React from 'react';
import { Link } from 'react-router-dom';
import { Badge, Card } from '../common';
import type { OvernightBrief, OvernightBriefDeltaResponse, OvernightPreMarketActionItem } from '../../types/overnight';
import { buildPreMarketActionLanes, getEvidenceBadgeVariant } from '../../utils/overnightDecision';

interface OvernightActionDeskProps {
  brief: OvernightBrief;
  delta?: OvernightBriefDeltaResponse | null;
  title?: string;
  subtitle?: string;
  compact?: boolean;
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

function laneVariant(laneKey: string): 'danger' | 'warning' | 'info' | 'default' {
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

function deltaLabel(deltaType?: string | null): string | null {
  switch (deltaType) {
    case 'new':
      return '新增';
    case 'intensified':
      return '升温';
    case 'steady':
      return '主线';
    case 'cooling':
      return '降温';
    case 'dropped':
      return '掉队';
    default:
      return null;
  }
}

const ActionItemCard: React.FC<{ item: OvernightPreMarketActionItem; compact: boolean }> = ({ item, compact }) => (
  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={priorityVariant(item.priorityLevel)}>{item.priorityLevel || 'NA'}</Badge>
          <Badge variant={getEvidenceBadgeVariant(item.evidence.level)}>{item.evidence.label}</Badge>
          {deltaLabel(item.deltaType) ? <Badge variant="default">{deltaLabel(item.deltaType)}</Badge> : null}
        </div>
        <div className="mt-3 text-base font-medium text-white">{item.coreFact}</div>
        <div className="mt-2 text-sm leading-6 text-secondary">{item.ashareLens.actionHeadline}</div>
      </div>
      {item.eventId && item.briefId ? (
        <Link className="btn-secondary" to={`/overnight/events/${item.eventId}?briefId=${item.briefId}`}>
          事件详情
        </Link>
      ) : null}
    </div>

    <div className="mt-4 grid gap-3 md:grid-cols-2">
      <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
        <div className="text-xs uppercase tracking-[0.18em] text-muted">Why Now</div>
        <div className="mt-2 text-sm leading-6 text-secondary">{item.whyNow}</div>
      </div>
      <div className="rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
        <div className="text-xs uppercase tracking-[0.18em] text-muted">盘前动作</div>
        <div className="mt-2 text-sm leading-6 text-secondary">{item.action}</div>
      </div>
    </div>

    <div className="mt-3 rounded-2xl border border-white/6 bg-base/30 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-muted">A股映射</div>
      <div className="mt-2 text-sm leading-6 text-white/90">
        先看: {item.ashareLens.focusAreas.join(' / ')}
      </div>
      <div className="mt-1 text-sm leading-6 text-secondary">
        回避: {item.ashareLens.avoidAreas.join(' / ')}
      </div>
      <div className="mt-1 text-sm leading-6 text-secondary">
        可能涨价: {item.ashareLens.pricePressureAreas.join(' / ')}
      </div>
      {!compact ? (
        <div className="mt-3 text-xs leading-5 text-muted">
          触发条件: {item.trigger}
        </div>
      ) : null}
    </div>
  </div>
);

export const OvernightActionDesk: React.FC<OvernightActionDeskProps> = ({
  brief,
  delta = null,
  title = '盘前 15 分钟清单',
  subtitle = 'A-Share Action Desk',
  compact = false,
}) => {
  const lanes = buildPreMarketActionLanes(brief, delta).map((lane) => ({
    ...lane,
    items: compact ? lane.items.slice(0, 2) : lane.items,
  }));
  const totalItems = lanes.reduce((sum, lane) => sum + lane.items.length, 0);
  const highConvictionItems = lanes
    .filter((lane) => lane.laneKey === 'act-now')
    .reduce((sum, lane) => sum + lane.items.length, 0);
  const confirmationItems = lanes
    .filter((lane) => lane.laneKey === 'wait-confirm')
    .reduce((sum, lane) => sum + lane.items.length, 0);
  const deRiskItems = lanes
    .filter((lane) => lane.laneKey === 'de-risk')
    .reduce((sum, lane) => sum + lane.items.length, 0);

  return (
    <Card variant="gradient" padding="lg">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">{subtitle}</div>
          <h2 className="mt-3 text-2xl font-semibold text-white">{title}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">
            把隔夜事件直接翻译成 A 股盘前动作，不再只停留在“发生了什么”，而是先判断今早该盯、该等还是该降预期。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="history">动作项 {totalItems}</Badge>
          <Badge variant="danger">高优先级 {highConvictionItems}</Badge>
          <Badge variant="warning">待确认 {confirmationItems}</Badge>
          <Badge variant="default">降预期 {deRiskItems}</Badge>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        {lanes.map((lane) => (
          <Card key={lane.laneKey} variant="bordered" padding="md">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-muted">{lane.laneKey}</div>
                <h3 className="mt-1 text-lg font-semibold text-white">{lane.title}</h3>
                <p className="mt-2 text-sm leading-6 text-secondary">{lane.summary}</p>
              </div>
              <Badge variant={laneVariant(lane.laneKey)}>{lane.items.length}</Badge>
            </div>

            <div className="mt-4 space-y-3">
              {lane.items.map((item) => (
                <ActionItemCard key={item.actionId} item={item} compact={compact} />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </Card>
  );
};

