import assert from 'node:assert/strict';
import test from 'node:test';
import type { OvernightBriefDeltaEvent, OvernightEventHistoryItem } from '../src/types/overnight';
import {
  buildEventFreshnessState,
  buildPriorityShiftState,
  findMatchingEventHistoryItem,
  normalizeEventHistoryKey,
} from '../src/utils/overnightEventContext';

const historyItems: OvernightEventHistoryItem[] = [
  {
    eventKey: 'ustr-announced-new-tariffs',
    coreFact: 'USTR announced new tariffs',
    occurrenceCount: 3,
    latestBriefId: 'brief-3',
    latestDigestDate: '2026-04-06',
    latestEventId: 'event-3',
    latestPriorityLevel: 'P0',
    averageConfidence: 0.81,
    occurrences: [
      { briefId: 'brief-3', digestDate: '2026-04-06', eventId: 'event-3', priorityLevel: 'P0', confidence: 0.84 },
      { briefId: 'brief-2', digestDate: '2026-04-05', eventId: 'event-2', priorityLevel: 'P1', confidence: 0.79 },
      { briefId: 'brief-1', digestDate: '2026-04-04', eventId: 'event-1', priorityLevel: 'P1', confidence: 0.8 },
    ],
  },
];

test('normalizeEventHistoryKey follows backend slug format', () => {
  assert.equal(normalizeEventHistoryKey(' USTR announced new tariffs! '), 'ustr-announced-new-tariffs');
});

test('findMatchingEventHistoryItem matches normalized core fact', () => {
  const matched = findMatchingEventHistoryItem('USTR announced new tariffs', historyItems);
  assert.equal(matched?.eventKey, 'ustr-announced-new-tariffs');
});

test('buildEventFreshnessState treats a repeated event as an extended story', () => {
  const freshness = buildEventFreshnessState(historyItems[0]);
  assert.equal(freshness.label, '连续发酵 3 次');
  assert.equal(freshness.tone, 'extended');
  assert.match(freshness.summary, /连续多天|不是第一次出现/);
});

test('buildEventFreshnessState treats missing history as a fresh catalyst', () => {
  const freshness = buildEventFreshnessState(null);
  assert.equal(freshness.label, '首次进入晨报');
  assert.equal(freshness.tone, 'fresh');
  assert.match(freshness.summary, /第一次|新催化/);
});

test('buildPriorityShiftState shows intensified priority movement and confidence change', () => {
  const deltaItem: OvernightBriefDeltaEvent = {
    eventKey: 'ustr-announced-new-tariffs',
    coreFact: 'USTR announced new tariffs',
    currentEventId: 'event-3',
    previousEventId: 'event-2',
    currentPriorityLevel: 'P0',
    previousPriorityLevel: 'P1',
    currentConfidence: 0.84,
    previousConfidence: 0.72,
    deltaType: 'intensified',
    deltaSummary: 'Priority moved from P1 to P0.',
  };

  const shift = buildPriorityShiftState(deltaItem);
  assert.equal(shift.label, 'P1 -> P0');
  assert.equal(shift.tone, 'up');
  assert.equal(shift.confidenceLabel, '+12pt');
  assert.match(shift.summary, /P1 to P0/);
});

test('buildPriorityShiftState marks new events explicitly', () => {
  const deltaItem: OvernightBriefDeltaEvent = {
    eventKey: 'fed-cuts',
    coreFact: 'Fed speakers signaled patience on cuts',
    currentEventId: 'event-fed',
    previousEventId: null,
    currentPriorityLevel: 'P1',
    previousPriorityLevel: '',
    currentConfidence: 0.77,
    previousConfidence: 0,
    deltaType: 'new',
    deltaSummary: 'New event entered the morning brief.',
  };

  const shift = buildPriorityShiftState(deltaItem);
  assert.equal(shift.label, '首次出现');
  assert.equal(shift.tone, 'new');
  assert.equal(shift.confidenceLabel, '首次计入');
});
