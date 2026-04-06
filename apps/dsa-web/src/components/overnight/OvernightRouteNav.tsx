import type React from 'react';
import { NavLink } from 'react-router-dom';
import { buildOvernightTopicHref, type OvernightTopicKey } from '../../utils/overnightView';

interface OvernightRouteNavProps {
  briefId?: string | null;
  defaultTopicKey?: OvernightTopicKey;
}

export const OvernightRouteNav: React.FC<OvernightRouteNavProps> = ({
  briefId,
  defaultTopicKey = 'policy-radar',
}) => {
  const openingHref = briefId ? `/overnight/opening?briefId=${encodeURIComponent(briefId)}` : '/overnight/opening';
  const playbookHref = briefId ? `/overnight/playbook?briefId=${encodeURIComponent(briefId)}` : '/overnight/playbook';
  const changesHref = briefId ? `/overnight/changes?briefId=${encodeURIComponent(briefId)}` : '/overnight/changes';
  const items = [
    { label: '实时晨报', to: '/overnight' },
    { label: '行动板', to: openingHref },
    { label: '开盘剧本', to: playbookHref },
    { label: '变化对照', to: changesHref },
    { label: '历史回看', to: '/overnight/history' },
    { label: 'Review Queue', to: '/overnight/review' },
    { label: '主题视图', to: buildOvernightTopicHref(defaultTopicKey, briefId) },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {items.map((item) => (
        <NavLink
          key={item.label}
          to={item.to}
          className={({ isActive }) =>
            `rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              isActive
                ? 'border-cyan/30 bg-cyan/10 text-cyan'
                : 'border-white/8 bg-white/[0.02] text-secondary hover:border-white/12 hover:text-white'
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  );
};
