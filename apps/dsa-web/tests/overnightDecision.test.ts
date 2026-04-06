import assert from 'node:assert/strict';
import test from 'node:test';
import type { OvernightBrief, OvernightEventSummary } from '../src/types/overnight';
import { buildEventDecisionLens } from '../src/utils/overnightDecision';

const brief: OvernightBrief = {
  briefId: 'brief-1',
  digestDate: '2026-04-06',
  cutoffTime: '07:30',
  topline: 'Tariffs and rates shaped overnight flow.',
  generatedAt: '2026-04-06T07:31:00',
  versionNo: 1,
  topEvents: [],
  crossAssetSnapshot: [],
  likelyBeneficiaries: [
    { title: '优先跟踪方向', items: ['自主可控', '军工电子', '黄金', '港口航运'] },
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
  todayWatchlist: [],
  primarySources: [],
  evidenceLinks: [],
};

test('commodity events fall back to domain defaults when beneficiary board has no direct match', () => {
  const event: OvernightEventSummary = {
    eventId: 'event_now_brent',
    priorityLevel: 'P2',
    coreFact: 'Brent crude extended overnight rally',
    summary: 'Oil still rose but no longer dominated the brief after tariffs took the lead.',
    whyItMatters: 'Cost pressure remained present for transport and chemicals, but it was no longer the top driver.',
    confidence: 0.7,
  };

  const decision = buildEventDecisionLens(brief, event);
  assert.deepEqual(decision.ashareLens.focusAreas, ['能源', '资源', '有色']);
  assert.equal(decision.ashareLens.avoidAreas.includes('航空'), true);
});
