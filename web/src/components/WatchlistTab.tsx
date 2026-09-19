import React, { useState } from 'react';
import { Building2, Plus, ShieldAlert, Trash2, Zap } from 'lucide-react';
import { AppConfig } from '../types';
import { Section, TagInput, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

const MULTIPLIERS = [
  { value: 1.15, label: '1.15x (strong interest)' },
  { value: 1.2, label: '1.20x (target company)' },
  { value: 1.25, label: '1.25x (top priority)' },
  { value: 1.3, label: '1.30x (dream employer)' },
  { value: 1.5, label: '1.50x (always alert)' },
];

export const WatchlistTab: React.FC<Props> = ({ config, onChange }) => {
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newMultiplier, setNewMultiplier] = useState(1.25);

  const addWatchlistCompany = () => {
    const name = newCompanyName.trim();
    if (!name || config.company_watchlist.some((c) => c.name.toLowerCase() === name.toLowerCase())) return;
    onChange({ ...config, company_watchlist: [...config.company_watchlist, { name, priority_multiplier: newMultiplier }] });
    setNewCompanyName('');
    setNewMultiplier(1.25);
  };

  return (
    <div className="space-y-6">
      <Section
        icon={<Building2 className="w-5 h-5 text-amber-400" aria-hidden="true" />}
        title="Priority watchlist"
        description="Postings from these companies get a boost on the company score. Names are matched as whole words."
      >
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="watchlist-company" className={labelClass}>Company name</label>
            <input
              id="watchlist-company"
              type="text"
              placeholder="e.g. Moniepoint, Flutterwave, Deel"
              value={newCompanyName}
              onChange={(e) => setNewCompanyName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addWatchlistCompany()}
              className={inputClass}
            />
          </div>
          <div className="w-[200px]">
            <label htmlFor="watchlist-multiplier" className={labelClass}>Score boost</label>
            <select
              id="watchlist-multiplier"
              value={newMultiplier}
              onChange={(e) => setNewMultiplier(parseFloat(e.target.value))}
              className={inputClass}
            >
              {MULTIPLIERS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={addWatchlistCompany}
            className="bg-amber-600 hover:bg-amber-500 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition"
          >
            <Plus className="w-4 h-4" aria-hidden="true" /> Add to watchlist
          </button>
        </div>

        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" aria-label="Watchlist companies">
          {config.company_watchlist.map((company, idx) => (
            <li key={`${company.name}-${idx}`} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold text-white">{company.name}</div>
                <div className="text-xs text-amber-400/90 font-medium flex items-center gap-1">
                  <Zap className="w-3 h-3" aria-hidden="true" /> {company.priority_multiplier}x boost
                </div>
              </div>
              <button
                type="button"
                aria-label={`Remove ${company.name} from the watchlist`}
                title={`Remove ${company.name}`}
                onClick={() => onChange({ ...config, company_watchlist: config.company_watchlist.filter((_, i) => i !== idx) })}
                className="text-slate-500 hover:text-red-400 p-1 rounded transition"
              >
                <Trash2 className="w-4 h-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        icon={<ShieldAlert className="w-5 h-5 text-red-400" aria-hidden="true" />}
        title="Excluded companies"
        description="Staffing agencies or companies you don't want to hear from. Their postings score 0 in every job spec."
      >
        <TagInput
          id="excluded-companies"
          label="Excluded companies"
          tone="red"
          values={config.filters.excluded_companies}
          onChange={(excluded_companies) => onChange({ ...config, filters: { ...config.filters, excluded_companies } })}
          placeholder="e.g. Generic Staffing Corp"
          addLabel="Exclude"
        />
      </Section>
    </div>
  );
};
