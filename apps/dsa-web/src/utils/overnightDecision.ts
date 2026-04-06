import type {
  OvernightAshareLens,
  OvernightActionLaneKey,
  OvernightBrief,
  OvernightBriefDeltaEvent,
  OvernightBriefDeltaResponse,
  OvernightBoardItem,
  OvernightEvidenceLevel,
  OvernightEvidenceState,
  OvernightEventSummary,
  OvernightPreMarketActionItem,
  OvernightPreMarketActionLane,
  OvernightWatchItem,
} from '../types/overnight';

const ACTION_LANE_META: Record<OvernightActionLaneKey, { title: string; summary: string }> = {
  'act-now': {
    title: '现在先盯',
    summary: '优先确认是不是今天开盘主线，先看强弱排序和第一定价对象。',
  },
  'watch-open': {
    title: '开盘盯扩散',
    summary: '不急着下重结论，先看 9:15 到 9:30 的扩散强度和板块跟随。',
  },
  'wait-confirm': {
    title: '先等确认',
    summary: '事实、细则或发布时间还没完全落地，先确认再升级判断。',
  },
  'de-risk': {
    title: '先降预期',
    summary: '这条线的强度在回落，今早不宜继续把它当第一主线处理。',
  },
};

const FALLBACK_FOCUS = ['自主可控', '高股息', '黄金'];
const FALLBACK_AVOID = ['纯情绪追高', '缺少定价确认的题材'];
const FALLBACK_PRICE_PRESSURE = ['原油', '铜', '进口零部件'];

function normalizeText(value: string | undefined | null): string {
  return (value || '').trim().toLowerCase();
}

function hasAnyKeyword(text: string, keywords: string[]): boolean {
  return keywords.some((keyword) => text.includes(keyword));
}

function uniqueTake(values: string[], limit = 3): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned || seen.has(cleaned)) {
      continue;
    }
    seen.add(cleaned);
    result.push(cleaned);
    if (result.length >= limit) {
      break;
    }
  }
  return result;
}

function sanitizeTermFragments(value: string): string[] {
  return value
    .replace(/^[A-Za-z\u4e00-\u9fa5 ]+:\s*/u, '')
    .split(/[\/,，、]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => item.toLowerCase() !== 'items');
}

function collectBoardTerms(value: unknown, output: string[]): void {
  if (Array.isArray(value)) {
    value.forEach((item) => collectBoardTerms(item, output));
    return;
  }

  if (typeof value === 'string') {
    output.push(...sanitizeTermFragments(value));
    return;
  }

  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, item]) => {
      if (['title', 'subtitle', 'summary'].includes(key)) {
        return;
      }
      collectBoardTerms(item, output);
    });
  }
}

function flattenBoardTerms(items: OvernightBoardItem[]): string[] {
  const terms: string[] = [];
  items.forEach((item) => collectBoardTerms(item, terms));
  return uniqueTake(terms, 12);
}

function selectTerms(pool: string[], keywords: string[], fallback: string[], limit = 3): string[] {
  if (keywords.length === 0) {
    return uniqueTake(pool.length > 0 ? pool : fallback, limit);
  }

  const loweredKeywords = keywords.map((keyword) => keyword.toLowerCase());
  const matched = pool.filter((term) => hasAnyKeyword(term.toLowerCase(), loweredKeywords));
  if (matched.length > 0) {
    return uniqueTake(matched, limit);
  }
  return uniqueTake(fallback, limit);
}

function buildKeywordLens(
  text: string,
  beneficiaryPool: string[],
  pressurePool: string[]
): OvernightAshareLens {
  if (hasAnyKeyword(text, ['brent', 'crude', 'oil', 'copper', 'commodity', '原油', '铜', '大宗'])) {
    const focusAreas = selectTerms(
      beneficiaryPool,
      ['能源', '资源', '有色', '油服', '煤化工'],
      ['能源', '资源', '有色']
    );
    return {
      focusAreas,
      avoidAreas: ['航空', '高燃料成本运输', '成本承压化工下游'],
      pricePressureAreas: selectTerms(
        pressurePool,
        ['原油', '铜', '燃油', '化工', '运价'],
        ['原油', '铜', '航空燃油']
      ),
      actionHeadline: '先看成本线会不会压过成长线',
      actionBody: '先盯资源与能源链有没有溢价扩散，同时避免把高成本承压链误判成补涨。',
    };
  }

  if (hasAnyKeyword(text, ['fed', 'cpi', 'inflation', 'rates', 'yield', '通胀', '利率'])) {
    const focusAreas = selectTerms(
      beneficiaryPool,
      ['黄金', '高股息', '资源', '银行'],
      ['黄金', '高股息', '资源']
    );
    return {
      focusAreas,
      avoidAreas: ['高估值成长', '长久期题材追高'],
      pricePressureAreas: selectTerms(
        pressurePool,
        ['黄金', '美元', '原油', '铜'],
        ['黄金', '原油', '铜']
      ),
      actionHeadline: '先把它翻译成利率与风格选择题',
      actionBody: '先看黄金、高股息和资源相对强弱，再决定是否继续回避高估值成长风格。',
    };
  }

  if (hasAnyKeyword(text, ['tariff', 'ustr', 'trade', '关税', '贸易'])) {
    const focusAreas = selectTerms(
      beneficiaryPool,
      ['自主', '军工', '港口', '航运', '替代', '出口'],
      ['自主可控', '军工电子', '港口航运']
    );
    return {
      focusAreas,
      avoidAreas: ['纯进口依赖制造', '对外需敏感但缺少护城河的链条'],
      pricePressureAreas: selectTerms(
        pressurePool,
        ['运价', '原油', '零部件', '铜', '化工'],
        ['集运运价', '进口零部件', '铜']
      ),
      actionHeadline: '先看政策冲击会不会直接改写 A 股开盘风格',
      actionBody: '先盯自主可控、军工电子和航运替代链是否同步走强，再决定是否把它升级成开盘主线。',
    };
  }

  return {
    focusAreas: selectTerms(beneficiaryPool, [], FALLBACK_FOCUS),
    avoidAreas: uniqueTake(FALLBACK_AVOID, 2),
    pricePressureAreas: selectTerms(pressurePool, [], FALLBACK_PRICE_PRESSURE),
    actionHeadline: '先把海外催化翻译成 A 股能执行的方向',
    actionBody: '先看受益方向、承压方向和跨资产反馈是否一致，没有共振前不急着上主线结论。',
  };
}

function buildEvidenceState(
  confidence: number,
  priorityLevel?: string,
  deltaType?: string | null
): OvernightEvidenceState {
  const normalizedPriority = (priorityLevel || '').toUpperCase();
  const normalizedDelta = deltaType || '';

  let level: OvernightEvidenceLevel;
  if (confidence >= 0.8 && normalizedPriority === 'P0') {
    level = 'strong';
  } else if (confidence >= 0.7) {
    level = 'mixed';
  } else {
    level = 'fragile';
  }

  if (normalizedDelta === 'cooling' || normalizedDelta === 'dropped') {
    level = confidence >= 0.8 ? 'mixed' : 'fragile';
  }

  switch (level) {
    case 'strong':
      return {
        level,
        label: '证据较强',
        summary: '优先级和置信度都够高，可以把它当盘前第一批观察对象。',
      };
    case 'mixed':
      return {
        level,
        label: '证据混合',
        summary: '方向有了，但仍要看开盘后的价格扩散来确认是不是主线。',
      };
    default:
      return {
        level,
        label: '证据脆弱',
        summary: '事实或传导链还不够扎实，先确认，不要急着下重仓判断。',
      };
  }
}

function findWatchItem(brief: OvernightBrief, eventId?: string | null): OvernightWatchItem | null {
  if (!eventId) {
    return null;
  }
  for (const bucket of brief.todayWatchlist) {
    const item = bucket.items.find((candidate) => candidate.eventId === eventId);
    if (item) {
      return item;
    }
  }
  return null;
}

function flattenDeltaEvents(delta: OvernightBriefDeltaResponse | null | undefined): OvernightBriefDeltaEvent[] {
  if (!delta) {
    return [];
  }
  return [
    ...delta.newEvents,
    ...delta.intensifiedEvents,
    ...delta.steadyEvents,
    ...delta.coolingEvents,
    ...delta.droppedEvents,
  ];
}

function findDeltaForEvent(
  event: OvernightEventSummary,
  delta: OvernightBriefDeltaResponse | null | undefined
): OvernightBriefDeltaEvent | null {
  return (
    flattenDeltaEvents(delta).find(
      (item) =>
        item.currentEventId === event.eventId ||
        item.previousEventId === event.eventId ||
        item.coreFact === event.coreFact
    ) || null
  );
}

function decideLane(
  event: OvernightEventSummary,
  watchItem: OvernightWatchItem | null,
  deltaItem: OvernightBriefDeltaEvent | null
): OvernightActionLaneKey {
  if (deltaItem?.deltaType === 'cooling' || deltaItem?.deltaType === 'dropped') {
    return 'de-risk';
  }
  if (watchItem?.bucketKey === 'needs-confirmation' || (event.confidence || 0) < 0.7) {
    return 'wait-confirm';
  }
  if (deltaItem?.deltaType === 'intensified' || (event.priorityLevel || '').toUpperCase() === 'P0') {
    return 'act-now';
  }
  return 'watch-open';
}

function priorityScore(priorityLevel: string): number {
  switch ((priorityLevel || '').toUpperCase()) {
    case 'P0':
      return 40;
    case 'P1':
      return 30;
    case 'P2':
      return 20;
    default:
      return 10;
  }
}

function laneScore(laneKey: OvernightActionLaneKey): number {
  switch (laneKey) {
    case 'act-now':
      return 400;
    case 'watch-open':
      return 300;
    case 'wait-confirm':
      return 200;
    case 'de-risk':
      return 100;
    default:
      return 0;
  }
}

function buildEventAshareLens(event: OvernightEventSummary, brief: OvernightBrief): OvernightAshareLens {
  const beneficiaryPool = flattenBoardTerms(brief.likelyBeneficiaries);
  const pressurePool = flattenBoardTerms(brief.whatMayGetMoreExpensive);
  const text = normalizeText(`${event.coreFact} ${event.summary} ${event.whyItMatters}`);
  const coreText = normalizeText(event.coreFact);
  return buildKeywordLens(coreText || text, beneficiaryPool, pressurePool);
}

function buildDroppedAshareLens(coreFact: string, brief: OvernightBrief): OvernightAshareLens {
  const beneficiaryPool = flattenBoardTerms(brief.likelyBeneficiaries);
  const pressurePool = flattenBoardTerms(brief.whatMayGetMoreExpensive);
  const baseLens = buildKeywordLens(normalizeText(coreFact), beneficiaryPool, pressurePool);
  return {
    ...baseLens,
    actionHeadline: '这条线已经从今早主线里掉队',
    actionBody: '把它降回二线观察，不再作为开盘第一批动作依据，除非出现新的确认催化。',
  };
}

function buildActionItem(
  brief: OvernightBrief,
  event: OvernightEventSummary,
  delta: OvernightBriefDeltaResponse | null | undefined
): OvernightPreMarketActionItem {
  const watchItem = findWatchItem(brief, event.eventId);
  const deltaItem = findDeltaForEvent(event, delta);
  const laneKey = decideLane(event, watchItem, deltaItem);
  const evidence = buildEvidenceState(event.confidence, event.priorityLevel, deltaItem?.deltaType);
  const ashareLens = buildEventAshareLens(event, brief);

  return {
    actionId: `${laneKey}:${event.eventId}`,
    laneKey,
    laneTitle: ACTION_LANE_META[laneKey].title,
    eventId: event.eventId,
    briefId: brief.briefId,
    coreFact: event.coreFact,
    priorityLevel: event.priorityLevel,
    confidence: event.confidence,
    trigger: watchItem?.trigger || event.summary || event.whyItMatters || '等待开盘第一波价格反馈。',
    action: watchItem?.action || ashareLens.actionBody,
    whyNow: deltaItem?.deltaSummary || event.whyItMatters || event.summary || '先看价格是否跟随这条逻辑。',
    evidence,
    ashareLens,
    deltaType: deltaItem?.deltaType || null,
  };
}

function buildDroppedActionItem(
  brief: OvernightBrief,
  item: OvernightBriefDeltaEvent
): OvernightPreMarketActionItem {
  const laneKey: OvernightActionLaneKey = 'de-risk';
  const confidence = item.previousConfidence || 0;
  const priorityLevel = item.previousPriorityLevel || '';
  const evidence = buildEvidenceState(confidence, priorityLevel, item.deltaType);
  const ashareLens = buildDroppedAshareLens(item.coreFact, brief);

  return {
    actionId: `${laneKey}:${item.eventKey}`,
    laneKey,
    laneTitle: ACTION_LANE_META[laneKey].title,
    eventId: item.previousEventId,
    briefId: null,
    coreFact: item.coreFact,
    priorityLevel,
    confidence,
    trigger: item.deltaSummary || '上一版出现过，但今天已经退出重点序列。',
    action: ashareLens.actionBody,
    whyNow: item.deltaSummary || '今早不再把这条旧逻辑放在第一优先级。',
    evidence,
    ashareLens,
    deltaType: item.deltaType,
  };
}

function sortActionItems(items: OvernightPreMarketActionItem[]): OvernightPreMarketActionItem[] {
  return [...items].sort((left, right) => {
    const leftScore =
      laneScore(left.laneKey) + priorityScore(left.priorityLevel) + Math.round((left.confidence || 0) * 100);
    const rightScore =
      laneScore(right.laneKey) + priorityScore(right.priorityLevel) + Math.round((right.confidence || 0) * 100);
    return rightScore - leftScore;
  });
}

export function getEvidenceBadgeVariant(level: OvernightEvidenceLevel): 'success' | 'info' | 'warning' {
  switch (level) {
    case 'strong':
      return 'success';
    case 'mixed':
      return 'info';
    default:
      return 'warning';
  }
}

export function buildPreMarketActionLanes(
  brief: OvernightBrief,
  delta?: OvernightBriefDeltaResponse | null
): OvernightPreMarketActionLane[] {
  const baseItems = brief.topEvents.map((event) => buildActionItem(brief, event, delta));
  const droppedItems = (delta?.droppedEvents || []).map((item) => buildDroppedActionItem(brief, item));
  const allItems = sortActionItems([...baseItems, ...droppedItems]);

  return (Object.entries(ACTION_LANE_META) as Array<[OvernightActionLaneKey, { title: string; summary: string }]>)
    .map(([laneKey, meta]) => ({
      laneKey,
      title: meta.title,
      summary: meta.summary,
      items: allItems.filter((item) => item.laneKey === laneKey).slice(0, laneKey === 'de-risk' ? 3 : 4),
    }))
    .filter((lane) => lane.items.length > 0);
}

export function buildEventActionItemForBrief(
  brief: OvernightBrief,
  event: OvernightEventSummary,
  delta?: OvernightBriefDeltaResponse | null
): OvernightPreMarketActionItem {
  return buildActionItem(brief, event, delta);
}

export function getDeltaTypeLabel(deltaType?: string | null): string | null {
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

export function buildEventDecisionLens(
  brief: OvernightBrief,
  event: OvernightEventSummary,
  delta?: OvernightBriefDeltaResponse | null
): { evidence: OvernightEvidenceState; ashareLens: OvernightAshareLens; deltaType?: string | null } {
  const deltaItem = findDeltaForEvent(event, delta);
  return {
    evidence: buildEvidenceState(event.confidence, event.priorityLevel, deltaItem?.deltaType),
    ashareLens: buildEventAshareLens(event, brief),
    deltaType: deltaItem?.deltaType || null,
  };
}

export function buildDeltaDecisionLens(
  brief: OvernightBrief,
  item: OvernightBriefDeltaEvent
): { evidence: OvernightEvidenceState; ashareLens: OvernightAshareLens } {
  const beneficiaryPool = flattenBoardTerms(brief.likelyBeneficiaries);
  const pressurePool = flattenBoardTerms(brief.whatMayGetMoreExpensive);
  const referenceConfidence = item.currentConfidence || item.previousConfidence || 0;
  const referencePriority = item.currentPriorityLevel || item.previousPriorityLevel || '';
  const evidence = buildEvidenceState(referenceConfidence, referencePriority, item.deltaType);
  const ashareLens =
    item.deltaType === 'dropped'
      ? buildDroppedAshareLens(item.coreFact, brief)
      : buildKeywordLens(
          normalizeText(item.coreFact) || normalizeText(`${item.coreFact} ${item.deltaSummary}`),
          beneficiaryPool,
          pressurePool
        );

  return { evidence, ashareLens };
}
