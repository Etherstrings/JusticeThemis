import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { overnightApi, OvernightBriefUnavailableError } from '../api/overnight';
import { Badge, Card } from '../components/common';
import { OvernightRouteNav } from '../components/overnight/OvernightRouteNav';
import { OvernightSummaryPanel } from '../components/overnight/OvernightSummaryPanel';
import type { OvernightBrief } from '../types/overnight';
import {
  buildOvernightTopicHref,
  getOvernightTopicDefinition,
  getOvernightTopicItems,
  OVERNIGHT_TOPIC_ORDER,
  summarizeOvernightBoardItem,
} from '../utils/overnightView';

const StateCard: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <Card variant="gradient" padding="lg" className="mx-auto max-w-3xl">
    <div className="text-xs uppercase tracking-[0.22em] text-cyan/70">Topic Page</div>
    <h1 className="mt-3 text-2xl font-semibold text-white">{title}</h1>
    <p className="mt-3 text-sm leading-6 text-secondary">{body}</p>
  </Card>
);

const OvernightTopicPage: React.FC = () => {
  const { topicKey = '' } = useParams();
  const [searchParams] = useSearchParams();
  const requestedBriefId = searchParams.get('briefId');
  const topic = getOvernightTopicDefinition(topicKey);

  const [brief, setBrief] = useState<OvernightBrief | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!topic) {
        setError('当前主题不存在。');
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const nextBrief = requestedBriefId
          ? await overnightApi.getBriefById(requestedBriefId)
          : await overnightApi.getLatestBrief();
        setBrief(nextBrief);
      } catch (nextError) {
        if (nextError instanceof OvernightBriefUnavailableError) {
          setError(nextError.message);
        } else {
          setError(nextError instanceof Error ? nextError.message : '加载主题视图失败');
        }
      } finally {
        setIsLoading(false);
      }
    };

    void load();
  }, [requestedBriefId, topic]);

  const topicItems = useMemo(() => {
    if (!brief || !topic) {
      return [];
    }
    return getOvernightTopicItems(brief, topic.key);
  }, [brief, topic]);

  if (isLoading) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="主题视图加载中" body="正在拉取目标晨报并按主题重组内容。" />
        </div>
      </div>
    );
  }

  if (error || !topic || !brief) {
    return (
      <div className="min-h-screen px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <OvernightRouteNav briefId={requestedBriefId} />
          <StateCard title="主题视图不可用" body={error || '当前主题不可用。'} />
          <div className="flex flex-wrap gap-2">
            <Link className="btn-secondary" to="/overnight">
              返回实时晨报
            </Link>
            <Link className="btn-secondary" to="/overnight/history">
              去历史页
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-6 md:px-6 md:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <OvernightRouteNav briefId={brief.briefId} defaultTopicKey={topic.key} />

        <OvernightSummaryPanel brief={brief} />

        <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <Card variant="bordered" padding="md">
            <div className="text-xs uppercase tracking-[0.2em] text-muted">Topic Directory</div>
            <h2 className="mt-1 text-lg font-semibold text-white">按主题切换</h2>
            <div className="mt-4 space-y-2">
              {OVERNIGHT_TOPIC_ORDER.map((key) => {
                const definition = getOvernightTopicDefinition(key);
                if (!definition) {
                  return null;
                }
                const count = getOvernightTopicItems(brief, key).length;
                const href = buildOvernightTopicHref(key, brief.briefId);
                const isActive = key === topic.key;
                return (
                  <Link
                    key={key}
                    to={href}
                    className={`block rounded-2xl border px-4 py-3 transition ${
                      isActive
                        ? 'border-cyan/30 bg-cyan/10'
                        : 'border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/[0.03]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-white">{definition.title}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">{definition.subtitle}</div>
                      </div>
                      <Badge variant={isActive ? 'info' : 'default'}>{count}</Badge>
                    </div>
                  </Link>
                );
              })}
            </div>
          </Card>

          <Card variant="gradient" padding="lg">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-muted">{topic.subtitle}</div>
                <h1 className="mt-1 text-2xl font-semibold text-white">{topic.title}</h1>
              </div>
              <Badge variant="history">{topicItems.length}</Badge>
            </div>

            {topicItems.length === 0 ? (
              <div className="mt-4 text-sm text-secondary">{topic.emptyText}</div>
            ) : (
              <div className="mt-4 space-y-3">
                {topicItems.map((item, index) => {
                  const summary = summarizeOvernightBoardItem(item);
                  return (
                    <div key={`${topic.key}-${index}`} className="rounded-2xl border border-white/6 bg-white/[0.02] px-4 py-4">
                      <div className="text-base font-medium text-white">{summary.headline}</div>
                      {summary.meta.length > 0 ? (
                        <div className="mt-3 space-y-1">
                          {summary.meta.map((line) => (
                            <div key={line} className="text-sm leading-6 text-secondary">
                              {line}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default OvernightTopicPage;
