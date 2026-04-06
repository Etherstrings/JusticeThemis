export type OvernightPriorityLevel = 'P0' | 'P1' | 'P2' | 'P3' | string;

export interface OvernightEventSummary {
  eventId: string;
  priorityLevel: OvernightPriorityLevel;
  coreFact: string;
  summary: string;
  whyItMatters: string;
  confidence: number;
}

export interface OvernightEvidenceItem {
  headline: string;
  sourceName: string;
  url: string;
  summary: string;
  sourceType: string;
  coverageTier: string;
  sourceClass: string;
}

export type OvernightJudgmentMode = 'model' | 'heuristic' | string;

export interface OvernightEventDetail extends OvernightEventSummary {
  sourceLinks: string[];
  evidenceItems: OvernightEvidenceItem[];
  judgmentSummary: string;
  judgmentMode: OvernightJudgmentMode;
}

export interface OvernightBoardItem {
  [key: string]: unknown;
}

export interface OvernightWatchItem {
  watchId: string;
  bucketKey: string;
  label: string;
  eventId?: string | null;
  coreFact: string;
  priorityLevel: string;
  confidence: number;
  trigger: string;
  action: string;
  marketReaction: string;
}

export interface OvernightWatchBucket {
  bucketKey: string;
  title: string;
  summary: string;
  items: OvernightWatchItem[];
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

export interface OvernightBriefDeltaEvent {
  eventKey: string;
  coreFact: string;
  currentEventId?: string | null;
  previousEventId?: string | null;
  currentPriorityLevel: string;
  previousPriorityLevel: string;
  currentConfidence: number;
  previousConfidence: number;
  deltaType: string;
  deltaSummary: string;
}

export interface OvernightBriefDeltaResponse {
  briefId: string;
  digestDate: string;
  previousBriefId?: string | null;
  previousDigestDate?: string | null;
  summary: string;
  newEvents: OvernightBriefDeltaEvent[];
  intensifiedEvents: OvernightBriefDeltaEvent[];
  steadyEvents: OvernightBriefDeltaEvent[];
  coolingEvents: OvernightBriefDeltaEvent[];
  droppedEvents: OvernightBriefDeltaEvent[];
}

export interface OvernightEventHistoryOccurrence {
  briefId: string;
  digestDate: string;
  eventId: string;
  priorityLevel: string;
  confidence: number;
}

export interface OvernightEventHistoryItem {
  eventKey: string;
  coreFact: string;
  occurrenceCount: number;
  latestBriefId?: string | null;
  latestDigestDate?: string | null;
  latestEventId?: string | null;
  latestPriorityLevel: string;
  averageConfidence: number;
  occurrences: OvernightEventHistoryOccurrence[];
}

export interface OvernightEventHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: OvernightEventHistoryItem[];
}

export interface OvernightTopicHistoryOccurrence {
  briefId: string;
  digestDate: string;
  itemCount: number;
}

export interface OvernightTopicHistoryItem {
  topicKey: string;
  title: string;
  occurrenceCount: number;
  totalItemCount: number;
  latestBriefId?: string | null;
  latestDigestDate?: string | null;
  latestItemCount: number;
  recentBriefs: OvernightTopicHistoryOccurrence[];
}

export interface OvernightTopicHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: OvernightTopicHistoryItem[];
}

export interface OvernightSourceCatalogItem {
  sourceId: string;
  displayName: string;
  organizationType: string;
  sourceClass: string;
  entryType: string;
  entryUrls: string[];
  priority: number;
  pollIntervalSeconds: number;
  isMissionCritical: boolean;
  isEnabled: boolean;
  coverageTier: string;
  regionFocus: string;
  coverageFocus: string;
}

export interface OvernightSourceListResponse {
  total: number;
  missionCritical: number;
  items: OvernightSourceCatalogItem[];
}

export interface OvernightCapturedSourceItem {
  itemId: number;
  sourceId: string;
  sourceName: string;
  canonicalUrl: string;
  title: string;
  summary: string;
  documentType: string;
  sourceClass: string;
  coverageTier: string;
  createdAt?: string | null;
}

export interface OvernightCapturedSourceItemListResponse {
  total: number;
  items: OvernightCapturedSourceItem[];
}

export interface OvernightSourceRefreshResponse extends OvernightCapturedSourceItemListResponse {
  collectedSources: number;
  collectedItems: number;
}

export interface OvernightSourceHealth {
  totalSources: number;
  missionCriticalSources: number;
  whitelistedSources: number;
  enabledMissionCriticalSources: number;
  coverageTierCounts: Record<string, number>;
  sourceClassCounts: Record<string, number>;
  coverageGaps: string[];
}

export interface OvernightPipelineHealth {
  briefCount: number;
  latestBriefId: string | null;
  latestDigestDate: string | null;
  latestGeneratedAt: string | null;
}

export interface OvernightContentQuality {
  topEventCount: number;
  averageConfidence: number;
  eventsNeedingConfirmation: number;
  eventsWithPrimarySources: number;
  eventsWithoutPrimarySources: number;
  duplicateCoreFactCount: number;
  minimumEvidenceGatePassed: boolean;
  duplicationGatePassed: boolean;
}

export interface OvernightDeliveryHealth {
  notificationAvailable: boolean;
  configuredChannels: string[];
  channelNames: string;
  overnightBriefEnabled: boolean;
}

export interface OvernightHealthResponse {
  sourceHealth: OvernightSourceHealth;
  pipelineHealth: OvernightPipelineHealth;
  contentQuality: OvernightContentQuality;
  deliveryHealth: OvernightDeliveryHealth;
}

export interface OvernightApiError {
  error: string;
  message: string;
}

export type OvernightFeedbackType =
  | 'useful'
  | 'not_useful'
  | 'too_repetitive'
  | 'priority_too_high'
  | 'should_be_higher'
  | 'conclusion_too_strong'
  | 'missed_big_event';

export type OvernightFeedbackStatus = 'pending_review' | 'reviewed' | 'dismissed' | string;

export interface OvernightFeedbackCreateRequest {
  targetType: 'brief' | 'event';
  targetId: string;
  briefId?: string | null;
  eventId?: string | null;
  feedbackType: OvernightFeedbackType;
  comment?: string;
}

export interface OvernightFeedbackResponse {
  feedbackId: number;
  targetType: string;
  targetId: string;
  briefId?: string | null;
  eventId?: string | null;
  feedbackType: string;
  comment: string;
  status: OvernightFeedbackStatus;
  createdAt?: string | null;
}

export interface OvernightFeedbackListResponse {
  total: number;
  page: number;
  limit: number;
  items: OvernightFeedbackResponse[];
}

export type OvernightEvidenceLevel = 'strong' | 'mixed' | 'fragile';

export interface OvernightEvidenceState {
  level: OvernightEvidenceLevel;
  label: string;
  summary: string;
}

export interface OvernightAshareLens {
  focusAreas: string[];
  avoidAreas: string[];
  pricePressureAreas: string[];
  actionHeadline: string;
  actionBody: string;
}

export type OvernightActionLaneKey = 'act-now' | 'watch-open' | 'wait-confirm' | 'de-risk';

export interface OvernightPreMarketActionItem {
  actionId: string;
  laneKey: OvernightActionLaneKey;
  laneTitle: string;
  eventId?: string | null;
  briefId?: string | null;
  coreFact: string;
  priorityLevel: string;
  confidence: number;
  trigger: string;
  action: string;
  whyNow: string;
  evidence: OvernightEvidenceState;
  ashareLens: OvernightAshareLens;
  deltaType?: string | null;
}

export interface OvernightPreMarketActionLane {
  laneKey: OvernightActionLaneKey;
  title: string;
  summary: string;
  items: OvernightPreMarketActionItem[];
}
