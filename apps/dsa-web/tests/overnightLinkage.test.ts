import assert from 'node:assert/strict';
import test from 'node:test';
import type { OvernightBrief, OvernightBriefDeltaResponse, OvernightEventSummary } from '../src/types/overnight';
import { buildRelatedEventLinks } from '../src/utils/overnightLinkage';

const brief: OvernightBrief = {
  briefId: 'brief-1',
  digestDate: '2026-04-06',
  cutoffTime: '07:30',
  topline: 'Tariffs and rates shaped overnight flow.',
  generatedAt: '2026-04-06T07:31:00',
  versionNo: 1,
  topEvents: [
    {
      eventId: 'event_now_tariff',
      priorityLevel: 'P0',
      coreFact: 'USTR announced new tariffs',
      summary: 'Tariff escalation moved from headline to tradable mainline before Asia open.',
      whyItMatters: 'Trade policy became the highest-conviction transmission line for A-share opening rotation.',
      confidence: 0.84,
    },
    {
      eventId: 'event_now_fed',
      priorityLevel: 'P1',
      coreFact: 'Fed speakers signaled patience on cuts',
      summary: 'Rates commentary stayed hawkish and kept long-duration growth under pressure.',
      whyItMatters: 'A-share style allocation still leans away from expensive long-duration narratives.',
      confidence: 0.8,
    },
    {
      eventId: 'event_now_brent',
      priorityLevel: 'P2',
      coreFact: 'Brent crude extended overnight rally',
      summary: 'Oil still rose but no longer dominated the brief after tariffs took the lead.',
      whyItMatters: 'Cost pressure remained present for transport and chemicals, but it was no longer the top driver.',
      confidence: 0.7,
    },
    {
      eventId: 'event_now_cpi',
      priorityLevel: 'P2',
      coreFact: 'BLS CPI release is due later today',
      summary: 'Calendar release risk remains in front of the US open and can reset rates expectations.',
      whyItMatters: 'If CPI surprises, cyclicals, gold and global risk appetite can all reprice quickly.',
      confidence: 0.69,
    },
  ],
  crossAssetSnapshot: [],
  likelyBeneficiaries: [
    { title: '优先跟踪方向', items: ['自主可控', '军工电子', '黄金', '港口航运'] },
    { title: '相对回避方向', items: ['高估值成长', '纯进口依赖制造链'] },
  ],
  likelyPressurePoints: [],
  whatMayGetMoreExpensive: [
    { title: '最可能先涨', items: ['铜', '原油', '集运运价', '部分化工原料'] },
  ],
  policyRadar: [],
  macroRadar: [],
  sectorTransmission: [],
  riskBoard: [],
  needConfirmation: [],
  todayWatchlist: [
    {
      bucketKey: 'awaiting-pricing',
      title: '待定价',
      summary: '盯第一定价对象，确认是否沿传导链继续扩散。',
      items: [
        {
          watchId: 'awaiting-pricing:event-now-tariff',
          bucketKey: 'awaiting-pricing',
          label: '观察定价扩散',
          eventId: 'event_now_tariff',
          coreFact: 'USTR announced new tariffs',
          priorityLevel: 'P0',
          confidence: 0.84,
          trigger: 'USDCNH weakened first, copper miners outperformed, and shipping remained firm.',
          action: '盯受益方向、承压方向和跨资产跟随，确认是不是单点波动。',
          marketReaction: 'USDCNH weakened first, copper miners outperformed, and shipping remained firm.',
        },
        {
          watchId: 'awaiting-pricing:event-now-fed',
          bucketKey: 'awaiting-pricing',
          label: '观察定价扩散',
          eventId: 'event_now_fed',
          coreFact: 'Fed speakers signaled patience on cuts',
          priorityLevel: 'P1',
          confidence: 0.8,
          trigger: 'US 2Y held up and Nasdaq futures lagged cyclical baskets.',
          action: '盯受益方向、承压方向和跨资产跟随，确认是不是单点波动。',
          marketReaction: 'US 2Y held up and Nasdaq futures lagged cyclical baskets.',
        },
      ],
    },
    {
      bucketKey: 'monitoring',
      title: '待观察',
      summary: '跟踪二次发酵，避免把普通噪音误升级。',
      items: [
        {
          watchId: 'monitoring:event-now-brent',
          bucketKey: 'monitoring',
          label: '跟踪二次发酵',
          eventId: 'event_now_brent',
          coreFact: 'Brent crude extended overnight rally',
          priorityLevel: 'P2',
          confidence: 0.7,
          trigger: 'Brent stayed bid, but breadth moved toward policy-sensitive names instead.',
          action: '盯资源与成本线是否继续扩散。',
          marketReaction: 'Brent stayed bid, but breadth moved toward policy-sensitive names instead.',
        },
      ],
    },
  ],
  primarySources: [],
  evidenceLinks: [],
};

const delta: OvernightBriefDeltaResponse = {
  briefId: 'brief-1',
  digestDate: '2026-04-06',
  previousBriefId: 'brief-0',
  previousDigestDate: '2026-04-05',
  summary: 'Tariff intensified, oil cooled.',
  newEvents: [],
  intensifiedEvents: [
    {
      eventKey: 'ustr-announced-new-tariffs',
      coreFact: 'USTR announced new tariffs',
      currentEventId: 'event_now_tariff',
      previousEventId: 'event_prev_tariff',
      currentPriorityLevel: 'P0',
      previousPriorityLevel: 'P1',
      currentConfidence: 0.84,
      previousConfidence: 0.72,
      deltaType: 'intensified',
      deltaSummary: 'Priority moved from P1 to P0.',
    },
  ],
  steadyEvents: [
    {
      eventKey: 'fed-speakers-signaled-patience-on-cuts',
      coreFact: 'Fed speakers signaled patience on cuts',
      currentEventId: 'event_now_fed',
      previousEventId: 'event_prev_fed',
      currentPriorityLevel: 'P1',
      previousPriorityLevel: 'P1',
      currentConfidence: 0.8,
      previousConfidence: 0.78,
      deltaType: 'steady',
      deltaSummary: 'Rates commentary stayed on the board.',
    },
  ],
  coolingEvents: [
    {
      eventKey: 'brent-crude-extended-overnight-rally',
      coreFact: 'Brent crude extended overnight rally',
      currentEventId: 'event_now_brent',
      previousEventId: 'event_prev_brent',
      currentPriorityLevel: 'P2',
      previousPriorityLevel: 'P1',
      currentConfidence: 0.7,
      previousConfidence: 0.76,
      deltaType: 'cooling',
      deltaSummary: 'Oil remained relevant but lost ranking.',
    },
  ],
  droppedEvents: [],
};

function getEvent(eventId: string): OvernightEventSummary {
  const event = brief.topEvents.find((item) => item.eventId === eventId);
  if (!event) {
    throw new Error(`Missing fixture event: ${eventId}`);
  }
  return event;
}

test('buildRelatedEventLinks ranks same-bucket events ahead of weaker overlaps', () => {
  const related = buildRelatedEventLinks(brief, getEvent('event_now_tariff'), delta);

  assert.equal(related.length, 3);
  assert.equal(related[0]?.event.eventId, 'event_now_fed');
  assert.equal(related[1]?.event.eventId, 'event_now_brent');
});

test('buildRelatedEventLinks explains the shared linkage for each related event', () => {
  const related = buildRelatedEventLinks(brief, getEvent('event_now_tariff'), delta);
  const fed = related.find((item) => item.event.eventId === 'event_now_fed');
  const brent = related.find((item) => item.event.eventId === 'event_now_brent');

  assert.ok(fed);
  assert.ok(brent);
  assert.match(fed.reasons.join(' | '), /同一观察桶: 待定价/);
  assert.match(fed.reasons.join(' | '), /同一盘前动作/);
  assert.match(brent.reasons.join(' | '), /共享涨价链: 铜/);
});

test('buildRelatedEventLinks omits the current event itself', () => {
  const related = buildRelatedEventLinks(brief, getEvent('event_now_tariff'), delta);
  assert.equal(related.some((item) => item.event.eventId === 'event_now_tariff'), false);
});
