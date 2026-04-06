import type { OvernightBrief, OvernightBriefDeltaResponse, OvernightPreMarketActionItem } from '../types/overnight';
import { buildPreMarketActionLanes } from './overnightDecision';

export interface OvernightPlaybookStepLine {
  lineId: string;
  headline: string;
  detail: string;
  eventId?: string | null;
}

export interface OvernightPlaybookStep {
  stepKey: 'verify' | 'auction' | 'execute';
  windowLabel: string;
  title: string;
  objective: string;
  lines: OvernightPlaybookStepLine[];
}

export interface OvernightPlaybookRiskGate {
  gateId: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  body: string;
}

export interface OvernightPlaybookView {
  headline: string;
  focusAreas: string[];
  avoidAreas: string[];
  pricePressureAreas: string[];
  steps: OvernightPlaybookStep[];
  riskGates: OvernightPlaybookRiskGate[];
}

function uniqueTake(values: string[], limit = 4): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned || seen.has(cleaned)) {
      continue;
    }
    seen.add(cleaned);
    result.push(cleaned);
    if (result.length >= limit) {
      break;
    }
  }
  return result;
}

function collectByLane(items: OvernightPreMarketActionItem[], laneKey: string): OvernightPreMarketActionItem[] {
  return items.filter((item) => item.laneKey === laneKey);
}

function buildStepLine(
  prefix: string,
  item: OvernightPreMarketActionItem,
  detail: string
): OvernightPlaybookStepLine {
  return {
    lineId: `${prefix}:${item.actionId}`,
    headline: item.coreFact,
    detail,
    eventId: item.eventId,
  };
}

function buildVerifyStep(items: OvernightPreMarketActionItem[]): OvernightPlaybookStep {
  const lines = [
    ...collectByLane(items, 'act-now').map((item) =>
      buildStepLine(
        'verify',
        item,
        `先确认 ${item.trigger}，确认后优先看 ${item.ashareLens.focusAreas.slice(0, 2).join(' / ')}。`
      )
    ),
    ...collectByLane(items, 'wait-confirm').map((item) =>
      buildStepLine(
        'verify',
        item,
        `这条仍属待确认项，先补细则和原文，再决定是否升级成盘前主线。`
      )
    ),
  ].slice(0, 4);

  return {
    stepKey: 'verify',
    windowLabel: '09:00 - 09:15',
    title: '先校验一手信号',
    objective: '先分清哪些是今天真主线，哪些只是海外噪音或尚未落地的预期。',
    lines,
  };
}

function buildAuctionStep(items: OvernightPreMarketActionItem[]): OvernightPlaybookStep {
  const lines = [
    ...collectByLane(items, 'act-now').map((item) =>
      buildStepLine(
        'auction',
        item,
        `竞价阶段先盯 ${item.ashareLens.focusAreas.slice(0, 2).join(' / ')} 是否同步走强，再看是否带动 ${item.ashareLens.pricePressureAreas[0] || '成本线'}。`
      )
    ),
    ...collectByLane(items, 'watch-open').map((item) =>
      buildStepLine(
        'auction',
        item,
        `不要急着追，先看 ${item.ashareLens.focusAreas[0] || '主方向'} 有没有扩散，若无跟随就维持观察。`
      )
    ),
  ].slice(0, 4);

  return {
    stepKey: 'auction',
    windowLabel: '09:15 - 09:25',
    title: '盯竞价扩散',
    objective: '看高优先级事件是否从单点异动扩散成板块共振，避免只盯新闻不看定价。',
    lines,
  };
}

function buildExecuteStep(items: OvernightPreMarketActionItem[]): OvernightPlaybookStep {
  const actionable = [
    ...collectByLane(items, 'act-now'),
    ...collectByLane(items, 'de-risk'),
    ...collectByLane(items, 'watch-open').slice(0, 1),
  ];

  const lines = actionable.map((item) =>
    buildStepLine(
      'execute',
      item,
      item.laneKey === 'de-risk'
        ? `这条今早先降预期，避免再把 ${item.coreFact} 当作第一主线。`
        : `若 ${item.coreFact} 在竞价和开盘初段继续确认，优先处理 ${item.ashareLens.focusAreas.slice(0, 2).join(' / ')}，并回避 ${item.ashareLens.avoidAreas[0] || '情绪追高'}。`
    )
  ).slice(0, 4);

  return {
    stepKey: 'execute',
    windowLabel: '09:25 - 09:30',
    title: '定今早执行框架',
    objective: '开盘前把注意力缩成少数几条可以执行的线，其余全部降级处理。',
    lines,
  };
}

function buildRiskGates(items: OvernightPreMarketActionItem[]): OvernightPlaybookRiskGate[] {
  const gates: OvernightPlaybookRiskGate[] = [];
  const fragile = items.filter((item) => item.evidence.level === 'fragile');
  const deRisk = items.filter((item) => item.laneKey === 'de-risk');
  const concentrated = collectByLane(items, 'act-now');

  if (fragile.length > 0) {
    gates.push({
      gateId: 'fragile-evidence',
      severity: 'high',
      title: '先处理低证据事件',
      body: `当前有 ${fragile.length} 条证据脆弱的线，正式数据或细则没出来前，不要把它们当确定结论。`,
    });
  }

  if (deRisk.length > 0) {
    gates.push({
      gateId: 'de-risk-lines',
      severity: 'medium',
      title: '旧主线已经开始掉队',
      body: `有 ${deRisk.length} 条线已经降温或掉队，今早不要继续沿用昨天的排序。`,
    });
  }

  if (concentrated.length <= 1) {
    gates.push({
      gateId: 'single-mainline',
      severity: 'low',
      title: '主线集中度很高',
      body: '当前高优先级主线不多，开盘后如果第一定价对象不跟随，要防止整页判断一起失真。',
    });
  }

  return gates;
}

export function buildOvernightPlaybook(
  brief: OvernightBrief,
  delta?: OvernightBriefDeltaResponse | null
): OvernightPlaybookView {
  const lanes = buildPreMarketActionLanes(brief, delta);
  const items = lanes.flatMap((lane) => lane.items);
  const focusAreas = uniqueTake(items.flatMap((item) => item.ashareLens.focusAreas), 5);
  const avoidAreas = uniqueTake(items.flatMap((item) => item.ashareLens.avoidAreas), 4);
  const pricePressureAreas = uniqueTake(items.flatMap((item) => item.ashareLens.pricePressureAreas), 4);
  const topActNow = collectByLane(items, 'act-now')[0];

  return {
    headline:
      topActNow
        ? `今早先围绕 ${topActNow.coreFact} 建立主线判断，其余事件按确认度分层处理。`
        : '今早没有单一绝对主线，先看竞价扩散和证据强弱再排序。',
    focusAreas,
    avoidAreas,
    pricePressureAreas,
    steps: [
      buildVerifyStep(items),
      buildAuctionStep(items),
      buildExecuteStep(items),
    ],
    riskGates: buildRiskGates(items),
  };
}

