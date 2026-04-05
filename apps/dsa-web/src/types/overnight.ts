export type OvernightPriorityLevel = 'P0' | 'P1' | 'P2' | 'P3' | string;

export interface OvernightEventSummary {
  eventId: string;
  priorityLevel: OvernightPriorityLevel;
  coreFact: string;
  summary: string;
  whyItMatters: string;
  confidence: number;
}

export interface OvernightEventDetail extends OvernightEventSummary {}

export interface OvernightBoardItem {
  [key: string]: unknown;
}

export interface OvernightWatchBucket {
  title: string;
  items: string[];
}

export interface OvernightPrimarySourceGroup {
  eventId: string;
  links: string[];
}

export interface OvernightBrief {
  briefId: string;
  digestDate: string;
  cutoffTime: string;
  topline: string;
  topEvents: OvernightEventSummary[];
  crossAssetSnapshot: OvernightBoardItem[];
  likelyBeneficiaries: OvernightBoardItem[];
  likelyPressurePoints: OvernightBoardItem[];
  whatMayGetMoreExpensive: OvernightBoardItem[];
  policyRadar: OvernightBoardItem[];
  macroRadar: OvernightBoardItem[];
  sectorTransmission: OvernightBoardItem[];
  riskBoard: OvernightBoardItem[];
  needConfirmation: OvernightEventSummary[];
  todayWatchlist: OvernightWatchBucket[];
  primarySources: OvernightPrimarySourceGroup[];
  evidenceLinks: OvernightBoardItem[];
  generatedAt: string;
  versionNo: number;
}

export interface OvernightBriefHistoryItem {
  briefId: string;
  digestDate: string;
  cutoffTime: string;
  topline: string;
  generatedAt: string;
}

export interface OvernightBriefHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: OvernightBriefHistoryItem[];
}

export interface OvernightApiError {
  error: string;
  message: string;
}
