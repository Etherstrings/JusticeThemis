import type React from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { overnightApi } from '../../api/overnight';
import { Badge, Card } from '../common';
import type { OvernightFeedbackType } from '../../types/overnight';

interface OvernightFeedbackPanelProps {
  targetType: 'brief' | 'event';
  targetId: string;
  briefId?: string | null;
  eventId?: string | null;
  title?: string;
}

const OPTIONS: Array<{ value: OvernightFeedbackType; label: string }> = [
  { value: 'useful', label: '有用' },
  { value: 'not_useful', label: '无用' },
  { value: 'too_repetitive', label: '太重复' },
  { value: 'priority_too_high', label: '排太高' },
  { value: 'should_be_higher', label: '应该更靠前' },
  { value: 'conclusion_too_strong', label: '结论过强' },
  { value: 'missed_big_event', label: '漏了大事' },
];

export const OvernightFeedbackPanel: React.FC<OvernightFeedbackPanelProps> = ({
  targetType,
  targetId,
  briefId,
  eventId,
  title = '这条判断有用吗',
}) => {
  const [selectedType, setSelectedType] = useState<OvernightFeedbackType>('useful');
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    setResultMessage(null);

    try {
      const response = await overnightApi.submitFeedback({
        targetType,
        targetId,
        briefId,
        eventId,
        feedbackType: selectedType,
        comment,
      });
      setResultMessage(`已记录到 review queue，状态：${response.status}`);
      setComment('');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '反馈提交失败');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card variant="bordered" padding="md">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-muted">Feedback Loop</div>
          <h3 className="mt-1 text-lg font-semibold text-white">{title}</h3>
        </div>
        <Badge variant="default">{targetType}</Badge>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setSelectedType(option.value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              selectedType === option.value
                ? 'border-cyan/30 bg-cyan/10 text-cyan'
                : 'border-white/8 bg-white/[0.02] text-secondary hover:border-white/12 hover:text-white'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <textarea
        className="mt-4 min-h-[96px] w-full rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-3 text-sm text-white outline-none transition placeholder:text-muted focus:border-cyan/30"
        placeholder="可选备注：比如为什么这条应该更靠前，或者漏了什么。"
        value={comment}
        onChange={(event) => setComment(event.target.value)}
      />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" className="btn-primary" onClick={() => void handleSubmit()} disabled={isSubmitting}>
          {isSubmitting ? '提交中...' : '提交反馈'}
        </button>
        <Link className="text-xs font-medium text-cyan transition hover:text-cyan/80" to="/overnight/review">
          打开 review queue
        </Link>
        {resultMessage ? <div className="text-sm text-emerald-300">{resultMessage}</div> : null}
        {error ? <div className="text-sm text-red-300">{error}</div> : null}
      </div>
    </Card>
  );
};
