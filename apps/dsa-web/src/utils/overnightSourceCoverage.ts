import type { OvernightSourceCatalogItem } from '../types/overnight';

export interface OvernightSourceCoverageGroup {
  key: string;
  title: string;
  description: string;
  items: OvernightSourceCatalogItem[];
}

const COVERAGE_TIER_META: Record<string, { title: string; description: string }> = {
  official_policy: {
    title: '官方政策',
    description: '优先盯白宫、联储、财政部、USTR 这类直接改变交易预期的官方表态。',
  },
  official_data: {
    title: '官方数据',
    description: '盯宏观数据原文和发布时间表，避免把预期、日历和结果混在一起。',
  },
  editorial_media: {
    title: '主流媒体',
    description: '补充官方原文之外的跨市场快讯与编辑部排序，但不替代一手证据。',
  },
};

const COVERAGE_ORDER = ['official_policy', 'official_data', 'editorial_media'] as const;

export function groupSourcesByCoverageTier(
  sources: OvernightSourceCatalogItem[]
): OvernightSourceCoverageGroup[] {
  const grouped = new Map<string, OvernightSourceCatalogItem[]>();

  for (const source of sources) {
    const key = source.coverageTier || 'other';
    const bucket = grouped.get(key) || [];
    bucket.push(source);
    grouped.set(key, bucket);
  }

  const orderedKeys = [
    ...COVERAGE_ORDER.filter((key) => grouped.has(key)),
    ...Array.from(grouped.keys()).filter((key) => !COVERAGE_ORDER.includes(key as (typeof COVERAGE_ORDER)[number])),
  ];

  return orderedKeys.map((key) => {
    const meta = COVERAGE_TIER_META[key] || {
      title: key || '其他',
      description: '当前分组尚未补充说明。',
    };
    return {
      key,
      title: meta.title,
      description: meta.description,
      items: grouped.get(key) || [],
    };
  });
}

function toCamelCaseKey(value: string): string {
  return value.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase());
}

export function readCoverageTierCount(
  counts: Record<string, number>,
  key: string
): number {
  return counts[key] || counts[toCamelCaseKey(key)] || 0;
}
