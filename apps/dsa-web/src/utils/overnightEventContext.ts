import type { OvernightBriefDeltaEvent, OvernightEventHistoryItem } from '../types/overnight';

export type OvernightFreshnessTone = 'fresh' | 'developing' | 'extended';
export type OvernightShiftTone = 'up' | 'flat' | 'down' | 'new';

export interface OvernightEventFreshnessState {
  label: string;
  tone: OvernightFreshnessTone;
  summary: string;
  occurrenceCount: number;
  latestDigestDate?: string | null;
  latestPriorityLevel?: string | null;
  averageConfidence?: number;
}

export interface OvernightPriorityShiftState {
  label: string;
  tone: OvernightShiftTone;
  summary: string;
  confidenceLabel: string;
}

export function normalizeEventHistoryKey(coreFact: string): string {
  return coreFact
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'event';
}

export function findMatchingEventHistoryItem(
  coreFact: string,
  items: OvernightEventHistoryItem[]
): OvernightEventHistoryItem | null {
  const normalizedCoreFact = coreFact.trim().toLowerCase();
  const normalizedKey = normalizeEventHistoryKey(coreFact);
  return (
    items.find(
      (item) =>
        item.eventKey === normalizedKey ||
        item.coreFact.trim().toLowerCase() === normalizedCoreFact
    ) || null
  );
}

export function buildEventFreshnessState(historyItem: OvernightEventHistoryItem | null): OvernightEventFreshnessState {
  if (!historyItem || (historyItem.occurrenceCount || 0) <= 1) {
    return {
      label: '首次进入晨报',
      tone: 'fresh',
      summary: '历史归档里这条线还是第一次出现，先把它当新催化处理。',
      occurrenceCount: historyItem?.occurrenceCount || 0,
      latestDigestDate: historyItem?.latestDigestDate,
      latestPriorityLevel: historyItem?.latestPriorityLevel,
      averageConfidence: historyItem?.averageConfidence,
    };
  }

  const occurrenceCount = historyItem.occurrenceCount || 0;
  if (occurrenceCount === 2) {
    return {
      label: '连续发酵 2 次',
      tone: 'developing',
      summary: '这已经不是第一次出现，说明隔夜市场开始预热，今天重点看是否继续升温。',
      occurrenceCount,
      latestDigestDate: historyItem.latestDigestDate,
      latestPriorityLevel: historyItem.latestPriorityLevel,
      averageConfidence: historyItem.averageConfidence,
    };
  }

  return {
    label: `连续发酵 ${occurrenceCount} 次`,
    tone: 'extended',
    summary: '这条线已经连续多天进入晨报，若没有新增确认，更像延续交易而不是全新主线。',
    occurrenceCount,
    latestDigestDate: historyItem.latestDigestDate,
    latestPriorityLevel: historyItem.latestPriorityLevel,
    averageConfidence: historyItem.averageConfidence,
  };
}

function formatConfidenceShift(deltaItem?: OvernightBriefDeltaEvent | null): string {
  if (!deltaItem) {
    return '--';
  }
  if (deltaItem.deltaType === 'new') {
    return '首次计入';
  }
  if (deltaItem.deltaType === 'dropped') {
    return '退出跟踪';
  }

  const currentConfidence = deltaItem.currentConfidence || 0;
  const previousConfidence = deltaItem.previousConfidence || 0;
  const deltaPoints = Math.round((currentConfidence - previousConfidence) * 100);
  if (deltaPoints === 0) {
    return '持平';
  }
  return `${deltaPoints > 0 ? '+' : ''}${deltaPoints}pt`;
}

function buildPriorityShiftLabel(deltaItem: OvernightBriefDeltaEvent): string {
  if (deltaItem.deltaType === 'new') {
    return '首次出现';
  }
  if (deltaItem.deltaType === 'dropped') {
    return '退出重点';
  }

  const currentPriority = (deltaItem.currentPriorityLevel || '').trim();
  const previousPriority = (deltaItem.previousPriorityLevel || '').trim();
  if (currentPriority && previousPriority && currentPriority !== previousPriority) {
    return `${previousPriority} -> ${currentPriority}`;
  }
  if (currentPriority) {
    return `${currentPriority} 延续`;
  }
  if (previousPriority) {
    return `${previousPriority} 回落`;
  }
  return '无前日对照';
}

export function buildPriorityShiftState(deltaItem?: OvernightBriefDeltaEvent | null): OvernightPriorityShiftState {
  if (!deltaItem) {
    return {
      label: '无前日对照',
      tone: 'flat',
      summary: '当前缺少上一版晨报对照，先看今天开盘第一定价对象。',
      confidenceLabel: '--',
    };
  }

  let tone: OvernightShiftTone;
  switch (deltaItem.deltaType) {
    case 'new':
      tone = 'new';
      break;
    case 'intensified':
      tone = 'up';
      break;
    case 'cooling':
    case 'dropped':
      tone = 'down';
      break;
    default:
      tone = 'flat';
      break;
  }

  return {
    label: buildPriorityShiftLabel(deltaItem),
    tone,
    summary: deltaItem.deltaSummary || '当前缺少上一版晨报对照。',
    confidenceLabel: formatConfidenceShift(deltaItem),
  };
}
