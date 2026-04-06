import type {
  OvernightBrief,
  OvernightBriefDeltaResponse,
  OvernightEventSummary,
  OvernightWatchBucket,
} from '../types/overnight';
import { buildEventActionItemForBrief, buildEventDecisionLens } from './overnightDecision';

export interface OvernightRelatedEventLink {
  event: OvernightEventSummary;
  reasons: string[];
  sharedFocusAreas: string[];
  sharedPricePressureAreas: string[];
  sharedWatchBucketTitle?: string | null;
  score: number;
}

function normalizeTerm(value: string): string {
  return value.trim().toLowerCase();
}

function intersectTerms(left: string[], right: string[]): string[] {
  const rightSet = new Set(right.map((value) => normalizeTerm(value)));
  const output: string[] = [];
  const seen = new Set<string>();

  for (const item of left) {
    const normalized = normalizeTerm(item);
    if (!normalized || !rightSet.has(normalized) || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    output.push(item.trim());
  }

  return output;
}

function findWatchBucket(brief: OvernightBrief, eventId: string): OvernightWatchBucket | null {
  return brief.todayWatchlist.find((bucket) => bucket.items.some((item) => item.eventId === eventId)) || null;
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

function buildReasonLabel(prefix: string, terms: string[]): string {
  return `${prefix}: ${terms.slice(0, 3).join(' / ')}`;
}

export function buildRelatedEventLinks(
  brief: OvernightBrief,
  currentEvent: OvernightEventSummary,
  delta?: OvernightBriefDeltaResponse | null
): OvernightRelatedEventLink[] {
  const currentDecision = buildEventDecisionLens(brief, currentEvent, delta);
  const currentAction = buildEventActionItemForBrief(brief, currentEvent, delta);
  const currentBucket = findWatchBucket(brief, currentEvent.eventId);

  const results = brief.topEvents
    .filter((event) => event.eventId !== currentEvent.eventId)
    .map((event) => {
      const decision = buildEventDecisionLens(brief, event, delta);
      const action = buildEventActionItemForBrief(brief, event, delta);
      const bucket = findWatchBucket(brief, event.eventId);

      const sharedFocusAreas = intersectTerms(
        currentDecision.ashareLens.focusAreas,
        decision.ashareLens.focusAreas
      );
      const sharedPricePressureAreas = intersectTerms(
        currentDecision.ashareLens.pricePressureAreas,
        decision.ashareLens.pricePressureAreas
      );

      const reasons: string[] = [];
      if (currentBucket && bucket && currentBucket.bucketKey === bucket.bucketKey) {
        reasons.push(`同一观察桶: ${bucket.title}`);
      }
      if (sharedFocusAreas.length > 0) {
        reasons.push(buildReasonLabel('共享受益方向', sharedFocusAreas));
      }
      if (sharedPricePressureAreas.length > 0) {
        reasons.push(buildReasonLabel('共享涨价链', sharedPricePressureAreas));
      }
      if (currentAction.action === action.action) {
        reasons.push('同一盘前动作');
      }

      const score =
        (currentBucket && bucket && currentBucket.bucketKey === bucket.bucketKey ? 50 : 0) +
        sharedFocusAreas.length * 18 +
        sharedPricePressureAreas.length * 16 +
        (currentAction.action === action.action ? 14 : 0) +
        priorityScore(event.priorityLevel) +
        Math.round((event.confidence || 0) * 10);

      return {
        event,
        reasons: reasons.slice(0, 3),
        sharedFocusAreas,
        sharedPricePressureAreas,
        sharedWatchBucketTitle:
          currentBucket && bucket && currentBucket.bucketKey === bucket.bucketKey ? bucket.title : null,
        score,
      };
    })
    .filter((item) => item.score > 0 && item.reasons.length > 0)
    .sort((left, right) => right.score - left.score);

  return results;
}
