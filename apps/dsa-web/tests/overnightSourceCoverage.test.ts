import assert from 'node:assert/strict';
import test from 'node:test';
import type { OvernightSourceCatalogItem } from '../src/types/overnight';
import { groupSourcesByCoverageTier, readCoverageTierCount } from '../src/utils/overnightSourceCoverage';

const sources: OvernightSourceCatalogItem[] = [
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
    coverageFocus: '补充跨市场快讯。',
  },
  {
    sourceId: 'whitehouse_news',
    displayName: 'White House News',
    organizationType: 'official_policy',
    sourceClass: 'policy',
    entryType: 'section_page',
    entryUrls: ['https://www.whitehouse.gov/news/'],
    priority: 100,
    pollIntervalSeconds: 300,
    isMissionCritical: true,
    isEnabled: true,
    coverageTier: 'official_policy',
    regionFocus: 'US policy',
    coverageFocus: '盯政策动作。',
  },
  {
    sourceId: 'bls_release_schedule',
    displayName: 'BLS Release Schedule',
    organizationType: 'official_data',
    sourceClass: 'calendar',
    entryType: 'calendar_page',
    entryUrls: ['https://www.bls.gov/schedule/news_release/'],
    priority: 90,
    pollIntervalSeconds: 86400,
    isMissionCritical: true,
    isEnabled: true,
    coverageTier: 'official_data',
    regionFocus: 'US macro',
    coverageFocus: '盯发布时间表。',
  },
];

test('groupSourcesByCoverageTier orders known tiers ahead of others', () => {
  const groups = groupSourcesByCoverageTier(sources);

  assert.deepEqual(
    groups.map((group) => group.key),
    ['official_policy', 'official_data', 'editorial_media']
  );
  assert.equal(groups[0]?.title, '官方政策');
  assert.equal(groups[1]?.items[0]?.sourceId, 'bls_release_schedule');
});

test('readCoverageTierCount supports camel-cased tier keys from API normalization', () => {
  assert.equal(
    readCoverageTierCount(
      {
        officialPolicy: 4,
        officialData: 3,
        editorialMedia: 2,
      },
      'official_policy'
    ),
    4
  );
});
