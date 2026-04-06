import type { OvernightEventSummary, OvernightPrimarySourceGroup, OvernightSourceCatalogItem } from '../types/overnight';

export interface CapturedNewsItem {
  id: string;
  url: string;
  headline: string;
  sourceName: string;
  coverageTier: string;
  sourceClass: string;
  summary: string;
}

function normalizeHostname(value: string): string {
  return value.replace(/^www\./, '').toLowerCase();
}

function readHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

function deriveHeadline(url: string, fallback: string): string {
  try {
    const pathname = new URL(url).pathname
      .split('/')
      .filter(Boolean)
      .pop();

    if (!pathname) {
      return fallback;
    }

    const normalized = pathname
      .replace(/\.[a-z0-9]+$/i, '')
      .replace(/[-_]+/g, ' ')
      .trim();

    if (!normalized || normalized.length < 6) {
      return fallback;
    }

    return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
  } catch {
    return fallback;
  }
}

function matchCatalogSource(
  url: string,
  catalog: OvernightSourceCatalogItem[]
): OvernightSourceCatalogItem | undefined {
  const hostname = normalizeHostname(readHostname(url));
  if (!hostname) {
    return undefined;
  }

  return catalog.find((item) =>
    item.entryUrls.some((entryUrl) => normalizeHostname(readHostname(entryUrl)) === hostname)
  );
}

export function buildCapturedNewsItems(
  event: OvernightEventSummary,
  sourceGroup: OvernightPrimarySourceGroup | null,
  catalog: OvernightSourceCatalogItem[]
): CapturedNewsItem[] {
  if (!sourceGroup?.links.length) {
    return [];
  }

  return sourceGroup.links.map((url) => {
    const matchedSource = matchCatalogSource(url, catalog);
    const hostname = readHostname(url);

    return {
      id: `${event.eventId}:${url}`,
      url,
      headline: deriveHeadline(url, event.coreFact),
      sourceName: matchedSource?.displayName || hostname || '未知来源',
      coverageTier: matchedSource?.coverageTier || '',
      sourceClass: matchedSource?.sourceClass || '',
      summary: event.summary || event.whyItMatters,
    };
  });
}
