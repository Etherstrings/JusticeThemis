import type { OvernightBoardItem, OvernightBrief } from '../types/overnight';

export type OvernightTopicKey =
  | 'beneficiaries'
  | 'price-pressure'
  | 'policy-radar'
  | 'macro-radar'
  | 'sector-transmission'
  | 'risk-board'
  | 'cross-asset'
  | 'pressure-points';

type OvernightTopicDefinition = {
  key: OvernightTopicKey;
  title: string;
  subtitle: string;
  emptyText: string;
};

const TOPIC_DEFINITIONS: Record<OvernightTopicKey, OvernightTopicDefinition> = {
  beneficiaries: {
    key: 'beneficiaries',
    title: '可能受益方向',
    subtitle: 'Beneficiaries',
    emptyText: '当前这轮摘要还没有明确的受益方向卡片。',
  },
  'price-pressure': {
    key: 'price-pressure',
    title: '可能涨价/更贵的方向',
    subtitle: 'Price Pressure',
    emptyText: '还没有形成明确的涨价链条。',
  },
  'policy-radar': {
    key: 'policy-radar',
    title: '政策雷达',
    subtitle: 'Policy Radar',
    emptyText: '本轮没有新的政策雷达条目。',
  },
  'macro-radar': {
    key: 'macro-radar',
    title: '宏观雷达',
    subtitle: 'Macro Radar',
    emptyText: '本轮没有新的宏观雷达条目。',
  },
  'sector-transmission': {
    key: 'sector-transmission',
    title: '市场传导',
    subtitle: 'Transmission',
    emptyText: '市场传导卡片仍待后端补充。',
  },
  'risk-board': {
    key: 'risk-board',
    title: '风险板',
    subtitle: 'Risk Board',
    emptyText: '当前没有新的风险板条目。',
  },
  'cross-asset': {
    key: 'cross-asset',
    title: '跨资产快照',
    subtitle: 'Cross Asset',
    emptyText: '当前简报还没有跨资产快照。',
  },
  'pressure-points': {
    key: 'pressure-points',
    title: '承压方向',
    subtitle: 'Pressure Points',
    emptyText: '当前没有新的承压方向卡片。',
  },
};

export const OVERNIGHT_TOPIC_ORDER: OvernightTopicKey[] = [
  'beneficiaries',
  'price-pressure',
  'policy-radar',
  'macro-radar',
  'sector-transmission',
  'risk-board',
  'cross-asset',
  'pressure-points',
];

export function getOvernightTopicDefinition(topicKey: string): OvernightTopicDefinition | null {
  return TOPIC_DEFINITIONS[topicKey as OvernightTopicKey] || null;
}

export function getOvernightTopicItems(brief: OvernightBrief, topicKey: OvernightTopicKey): OvernightBoardItem[] {
  switch (topicKey) {
    case 'beneficiaries':
      return brief.likelyBeneficiaries;
    case 'price-pressure':
      return brief.whatMayGetMoreExpensive;
    case 'policy-radar':
      return brief.policyRadar;
    case 'macro-radar':
      return brief.macroRadar;
    case 'sector-transmission':
      return brief.sectorTransmission;
    case 'risk-board':
      return brief.riskBoard;
    case 'cross-asset':
      return brief.crossAssetSnapshot;
    case 'pressure-points':
      return brief.likelyPressurePoints;
    default:
      return [];
  }
}

export function buildOvernightTopicHref(topicKey: OvernightTopicKey, briefId?: string | null): string {
  const path = `/overnight/topics/${topicKey}`;
  if (!briefId) {
    return path;
  }
  const params = new URLSearchParams({ briefId });
  return `${path}?${params.toString()}`;
}

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

export function summarizeOvernightBoardItem(item: OvernightBoardItem): { headline: string; meta: string[] } {
  const preferredHeadline =
    stringifyValue(item.title) ||
    stringifyValue(item.coreFact) ||
    stringifyValue(item.summary) ||
    stringifyValue(item.eventId) ||
    'Untitled';

  const meta = Object.entries(item)
    .filter(([key, value]) => !['title', 'coreFact', 'summary', 'eventId'].includes(key) && stringifyValue(value))
    .slice(0, 3)
    .map(([key, value]) => {
      const text = stringifyValue(value);
      if (Array.isArray(value) || key === 'items') {
        return text;
      }
      return `${humanizeKey(key)}: ${text}`;
    });

  return { headline: preferredHeadline, meta };
}

export function formatOvernightDateTime(value?: string | null): string {
  return value ? value.replace('T', ' ') : '暂无记录';
}
