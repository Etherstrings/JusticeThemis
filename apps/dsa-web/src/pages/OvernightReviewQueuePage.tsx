import type React from 'react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { overnightApi } from '../api/overnight';
import { Badge, Card, Pagination } from '../components/common';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import type { OvernightFeedbackResponse } from '../types/overnight';
import { formatOvernightDateTime } from '../utils/overnightView';

const reviewPageSize = 20;

type QueueTargetFilter = 'all' | 'brief' | 'event';
type QueueStatusFilter = 'all' | 'pending_review' | 'reviewed' | 'dismissed';

const TARGET_FILTERS: Array<{ value: QueueTargetFilter; label: string }> = [
  { value: 'all', label: '全部对象' },
  { value: 'event', label: '事件' },
  { value: 'brief', label: '晨报' },
];

const STATUS_FILTERS: Array<{ value: QueueStatusFilter; label: string }> = [
  { value: 'all', label: '全部状态' },
  { value: 'pending_review', label: '待复核' },
  { value: 'reviewed', label: '已复核' },
  { value: 'dismissed', label: '已忽略' },
];

const FEEDBACK_TYPE_LABELS: Record<string, string> = {
  useful: '有用',
  not_useful: '无用',
  too_repetitive: '太重复',
  priority_too_high: '排太高',
  should_be_higher: '应该更靠前',
  conclusion_too_strong: '结论过强',
  missed_big_event: '漏了大事',
};

function normalizeTargetFilter(value: string | null): QueueTargetFilter {
  return value === 'brief' || value === 'event' ? value : 'all';
}

function normalizeStatusFilter(value: string | null): QueueStatusFilter {
  return value === 'pending_review' || value === 'reviewed' || value === 'dismissed'
    ? value
    : 'all';
}

function statusLabel(status: string): string {
  switch (status) {
    case 'pending_review':
      return '待复核';
    case 'reviewed':
      return '已复核';
    case 'dismissed':
      return '已忽略';
    default:
      return status || '未知状态';
  }
}

function statusVariant(status: string): 'warning' | 'success' | 'default' {
  switch (status) {
    case 'pending_review':
      return 'warning';
    case 'reviewed':
      return 'success';
    default:
      return 'default';
  }
}

function targetLabel(targetType: string): string {
  return targetType === 'event' ? '事件' : targetType === 'brief' ? '晨报' : targetType;
}

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Review Queue</div>
    <h1 className="mt-3 text-2xl font-semibold text-white">{title}</h1>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
  </Card>
);

const FilterChip: React.FC<{
  active: boolean;
  label: string;
  onClick: () => void;
}> = ({ active, label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
      active
        ? 'border-cyan/30 bg-cyan/10 text-cyan'
        : 'border-white/8 bg-white/[0.02] text-secondary hover:border-white/12 hover:text-white'
    }`}
  >
    {label}
  </button>
);

const SummaryStat: React.FC<{ title: string; value: number; body: string }> = ({ title, value, body }) => (
  <div className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-3">
    <div className="text-xs uppercase tracking-[0.18em] text-muted">{title}</div>
    <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    <div className="mt-1 text-xs text-secondary">{body}</div>
  </div>
);

interface QueueSummary {
  pendingReview: number;
  reviewed: number;
  briefTargets: number;
  eventTargets: number;
}

const OvernightReviewQueuePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(Number.parseInt(searchParams.get('page') || '1', 10) || 1, 1);
  const targetFilter = normalizeTargetFilter(searchParams.get('targetType'));
  const statusFilter = normalizeStatusFilter(searchParams.get('status'));

  const [items, setItems] = useState<OvernightFeedbackResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<QueueSummary>({
    pendingReview: 0,
    reviewed: 0,
    briefTargets: 0,
    eventTargets: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [updatingFeedbackId, setUpdatingFeedbackId] = useState<number | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [queueResponse, pendingResponse, reviewedResponse, briefResponse, eventResponse] = await Promise.all([
          overnightApi.getFeedback(
            page,
            reviewPageSize,
            targetFilter === 'all' ? undefined : targetFilter,
            statusFilter === 'all' ? undefined : statusFilter
          ),
          overnightApi.getFeedback(1, 1, undefined, 'pending_review'),
          overnightApi.getFeedback(1, 1, undefined, 'reviewed'),
          overnightApi.getFeedback(1, 1, 'brief', undefined),
          overnightApi.getFeedback(1, 1, 'event', undefined),
        ]);

        setItems(queueResponse.items);
        setTotal(queueResponse.total);
        setSummary({
          pendingReview: pendingResponse.total,
          reviewed: reviewedResponse.total,
          briefTargets: briefResponse.total,
          eventTargets: eventResponse.total,
        });
      } catch (nextError) {
        setItems([]);
        setTotal(0);
        setError(nextError instanceof Error ? nextError.message : '加载 feedback review queue 失败');
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [page, refreshToken, statusFilter, targetFilter]);

  const totalPages = Math.max(1, Math.ceil(total / reviewPageSize));

  const updateQuery = (next: {
    page?: number;
    targetType?: QueueTargetFilter;
    status?: QueueStatusFilter;
  }) => {
    const params = new URLSearchParams();
    const nextPage = next.page ?? page;
    const nextTargetType = next.targetType ?? targetFilter;
    const nextStatus = next.status ?? statusFilter;

    if (nextPage > 1) {
      params.set('page', String(nextPage));
    }
    if (nextTargetType !== 'all') {
      params.set('targetType', nextTargetType);
    }
    if (nextStatus !== 'all') {
      params.set('status', nextStatus);
    }

    setSearchParams(params);
  };

  const handleStatusUpdate = async (
    feedbackId: number,
    status: 'reviewed' | 'dismissed'
  ) => {
    setUpdatingFeedbackId(feedbackId);
    setActionError(null);

    try {
      await overnightApi.updateFeedbackStatus(feedbackId, status);
      setRefreshToken((current) => current + 1);
    } catch (nextError) {
      setActionError(nextError instanceof Error ? nextError.message : '更新反馈状态失败');
    } finally {
      setUpdatingFeedbackId(null);
    }
  };

  if (isLoading && items.length === 0) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav />
          <StateCard title="Review Queue 加载中" body="正在读取用户反馈、队列积压和对象分布。" />
        </div>
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav />
          <StateCard title="Review Queue 暂时不可用" body={error} />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav />

        <Card variant="gradient" padding="lg">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Feedback Ops</div>
              <h1 className="mt-3 text-3xl font-semibold text-white">隔夜晨报 Review Queue</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-secondary">
                这里聚合了用户对晨报和事件卡片的反馈，方便你早上先看积压、再按对象类型和状态筛选，最后跳回原始上下文复核。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="warning">待复核 {summary.pendingReview}</Badge>
              <Badge variant="success">已复核 {summary.reviewed}</Badge>
              <Badge variant="info">当前筛选 {total}</Badge>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            <SummaryStat title="Pending Review" value={summary.pendingReview} body="尚未完成人工复核的反馈" />
            <SummaryStat title="Reviewed" value={summary.reviewed} body="已经进入复核完成状态的反馈" />
            <SummaryStat title="Event Feedback" value={summary.eventTargets} body="指向单条事件的反馈数量" />
            <SummaryStat title="Brief Feedback" value={summary.briefTargets} body="指向整份晨报的反馈数量" />
          </div>
        </Card>

        <Card variant="bordered" padding="md">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Queue Filters</div>
              <h2 className="mt-1 text-xl font-semibold text-white">按对象与状态筛选</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link className="btn-secondary" to="/overnight">
                返回晨报
              </Link>
              <Link className="btn-secondary" to="/overnight/history">
                查看历史页
              </Link>
            </div>
          </div>

          <div className="mt-4 space-y-4">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Target Type</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {TARGET_FILTERS.map((option) => (
                  <FilterChip
                    key={option.value}
                    active={targetFilter === option.value}
                    label={option.label}
                    onClick={() => updateQuery({ page: 1, targetType: option.value })}
                  />
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Status</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {STATUS_FILTERS.map((option) => (
                  <FilterChip
                    key={option.value}
                    active={statusFilter === option.value}
                    label={option.label}
                    onClick={() => updateQuery({ page: 1, status: option.value })}
                  />
                ))}
              </div>
            </div>

            {error ? <div className="text-sm text-red-300">{error}</div> : null}
            {actionError ? <div className="text-sm text-red-300">{actionError}</div> : null}
          </div>
        </Card>

        <Card variant="bordered" padding="md">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-muted">Queue Items</div>
              <h2 className="mt-1 text-xl font-semibold text-white">反馈明细</h2>
            </div>
            <Badge variant="history">{items.length}</Badge>
          </div>

          {items.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4 text-sm text-secondary">
              当前筛选条件下没有反馈项。你可以先去晨报页或事件详情页提交反馈，再回到这里复核。
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {items.map((item) => {
                const briefHref = item.briefId ? `/overnight/briefs/${item.briefId}` : null;
                const eventHref = item.eventId
                  ? `/overnight/events/${item.eventId}${item.briefId ? `?briefId=${item.briefId}` : ''}`
                  : null;

                return (
                  <div key={item.feedbackId} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
                          <Badge variant="default">{targetLabel(item.targetType)}</Badge>
                          <Badge variant="info">{FEEDBACK_TYPE_LABELS[item.feedbackType] || item.feedbackType}</Badge>
                        </div>
                        <div className="mt-3 text-sm text-secondary">
                          目标 ID: <span className="text-white/90">{item.targetId}</span>
                        </div>
                        <div className="mt-1 text-xs text-muted">{formatOvernightDateTime(item.createdAt)}</div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {item.status === 'pending_review' ? (
                          <>
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => void handleStatusUpdate(item.feedbackId, 'reviewed')}
                              disabled={updatingFeedbackId === item.feedbackId}
                            >
                              {updatingFeedbackId === item.feedbackId ? '处理中...' : '标记已复核'}
                            </button>
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => void handleStatusUpdate(item.feedbackId, 'dismissed')}
                              disabled={updatingFeedbackId === item.feedbackId}
                            >
                              {updatingFeedbackId === item.feedbackId ? '处理中...' : '忽略'}
                            </button>
                          </>
                        ) : null}
                        {eventHref ? (
                          <Link className="btn-secondary" to={eventHref}>
                            打开事件
                          </Link>
                        ) : null}
                        {briefHref ? (
                          <Link className="btn-secondary" to={briefHref}>
                            打开晨报
                          </Link>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-4 rounded-2xl border border-white/6 bg-base/40 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.18em] text-muted">Comment</div>
                      <div className="mt-2 text-sm leading-6 text-white/90">
                        {item.comment.trim() || '用户没有填写额外备注。'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <Pagination
            className="mt-4 justify-start"
            currentPage={page}
            totalPages={totalPages}
            onPageChange={(nextPage) => updateQuery({ page: nextPage })}
          />
        </Card>
      </div>
    </div>
  );
};

export default OvernightReviewQueuePage;
