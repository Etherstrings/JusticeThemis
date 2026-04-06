import assert from 'node:assert/strict';
import test from 'node:test';
import type { OvernightEventSummary, OvernightPrimarySourceGroup, OvernightSourceCatalogItem } from '../src/types/overnight';
import { buildCapturedNewsItems } from '../src/utils/overnightSourceEvidence';

const event: OvernightEventSummary = {
  eventId: 'evt-001',
  priorityLevel: 'P0',
  coreFact: 'USTR announced new tariffs',
  summary: 'Tariff escalation was published by USTR.',
  whyItMatters: 'Trade policy became the key overnight driver.',
  confidence: 0.84,
};

const sourceGroup: OvernightPrimarySourceGroup = {
  eventId: 'evt-001',
  links: [
    'https://ustr.gov/about-us/policy-offices/press-office/press-releases/2026/april/tariff-update-for-critical-minerals',
    'https://www.reuters.com/world/us/us-tariff-update-2026-04-06/',
  ],
};

const catalog: OvernightSourceCatalogItem[] = [
  {
    sourceId: 'ustr_press_releases',
    displayName: 'USTR Press Releases',
    organizationType: 'official_policy',
    sourceClass: 'policy',
    entryType: 'section_page',
    entryUrls: ['https://ustr.gov/about-us/policy-offices/press-office/press-releases'],
    priority: 100,
    pollIntervalSeconds: 300,
    isMissionCritical: true,
    isEnabled: true,
    coverageTier: 'official_policy',
    regionFocus: 'US trade policy',
    coverageFocus: '盯关税和贸易政策。',
  },
  {
    sourceId: 'reuters_topics',
    displayName: 'Reuters Topics',
    organizationType: 'wire_media',
    sourceClass: 'market',
    entryType: 'section_page',
    entryUrls: ['https://reutersbest.com/topic/'],
    priority: 90,
    pollIntervalSeconds: 600,
    isMissionCritical: true,
    isEnabled: true,
    coverageTier: 'editorial_media',
    regionFocus: 'Global markets',
    coverageFocus: '补充跨市场媒体确认。',
  },
];

test('buildCapturedNewsItems turns raw source links into readable cards with source labels', () => {
  const items = buildCapturedNewsItems(event, sourceGroup, catalog);

  assert.equal(items.length, 2);
  assert.equal(items[0]?.sourceName, 'USTR Press Releases');
  assert.equal(items[0]?.coverageTier, 'official_policy');
  assert.match(items[0]?.headline || '', /tariff update/i);
  assert.equal(items[1]?.sourceName, 'www.reuters.com');
  assert.equal(items[1]?.headline, 'Us Tariff Update 2026 04 06');
});

test('buildCapturedNewsItems falls back to event core fact when link path is not readable', () => {
  const unreadableGroup: OvernightPrimarySourceGroup = {
    eventId: 'evt-001',
    links: ['https://example.com/'],
  };

  const items = buildCapturedNewsItems(event, unreadableGroup, catalog);

  assert.equal(items[0]?.sourceName, 'example.com');
  assert.equal(items[0]?.headline, 'USTR announced new tariffs');
});
