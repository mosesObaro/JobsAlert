import React, { useState } from 'react';
import { AppConfig, WatchlistCompany } from '../types';
import { Building2, ShieldAlert, Plus, Trash2, Zap } from 'lucide-react';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const WatchlistTab: React.FC<Props> = ({ config, onChange }) => {
  const [newCompanyName, setNewCompanyName] = useState('');
  const [newMultiplier, setNewMultiplier] = useState(1.25);
  const [newBlacklistCompany, setNewBlacklistCompany] = useState('');

  const addWatchlistCompany = () => {
    if (!newCompanyName.trim()) return;
    const exists = config.company_watchlist.some(
      (c) => c.name.toLowerCase() === newCompanyName.trim().toLowerCase()
    );
    if (exists) return;

    onChange({
      ...config,
      company_watchlist: [
        ...config.company_watchlist,
        { name: newCompanyName.trim(), priority_multiplier: newMultiplier },
      ],
    });
    setNewCompanyName('');
    setNewMultiplier(1.25);
  };

  const removeWatchlistCompany = (index: number) => {
    onChange({
      ...config,
      company_watchlist: config.company_watchlist.filter((_, idx) => idx !== index),
    });
  };

  const addBlacklistCompany = () => {
    if (!newBlacklistCompany.trim()) return;
    onChange({
      ...config,
      filters: {
        ...config.filters,
        excluded_companies: [...config.filters.excluded_companies, newBlacklistCompany.trim()],
      },
    });
    setNewBlacklistCompany('');
  };

  const removeBlacklistCompany = (index: number) => {
    onChange({
      ...config,
      filters: {
        ...config.filters,
        excluded_companies: config.filters.excluded_companies.filter((_, idx) => idx !== index),
      },
    });
  };

  return (
    <div className="space-y-8">
      {/* Priority Watchlist */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Building2 className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-white">Target Dream Companies (Priority Watchlist)</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Postings from these organizations receive direct multipliers on the company score vector to elevate them into the 9.0+ immediate alert tier.
        </p>

        {/* Add Company Input */}
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 mb-6 flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Target Company Name
            </label>
            <input
              type="text"
              placeholder="e.g. Cloudflare, Stripe, Linear, OpenAI"
              value={newCompanyName}
              onChange={(e) => setNewCompanyName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addWatchlistCompany()}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="w-[180px]">
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Score Boost: <span className="text-amber-400 font-bold">{newMultiplier.toFixed(2)}x</span>
            </label>
            <select
              value={newMultiplier}
              onChange={(e) => setNewMultiplier(parseFloat(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
            >
              <option value={1.15}>1.15x (Strong Interest)</option>
              <option value={1.20}>1.20x (Target Company)</option>
              <option value={1.25}>1.25x (Top Priority)</option>
              <option value={1.30}>1.30x (Dream Employer)</option>
              <option value={1.50}>1.50x (Immediate Alert)</option>
            </select>
          </div>

          <button
            onClick={addWatchlistCompany}
            className="bg-amber-600 hover:bg-amber-500 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition"
          >
            <Plus className="w-4 h-4" /> Add to Watchlist
          </button>
        </div>

        {/* Watchlist Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {config.company_watchlist.map((company, idx) => (
            <div
              key={idx}
              className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between hover:border-slate-700 transition"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 font-bold text-xs">
                  {company.name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{company.name}</div>
                  <div className="text-xs text-amber-400/90 font-medium flex items-center gap-1">
                    <Zap className="w-3 h-3" /> {company.priority_multiplier}x Multiplier
                  </div>
                </div>
              </div>

              <button
                onClick={() => removeWatchlistCompany(idx)}
                className="text-slate-500 hover:text-red-400 p-1 rounded transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Blacklist */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <ShieldAlert className="w-5 h-5 text-red-400" />
          <h2 className="text-lg font-bold text-white">Excluded Entities & Blacklist</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Exclude third-party staffing agencies, body shops, or companies you do not wish to work with. Any posting from these names will be immediately discarded (Score: 0.0).
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. CyberCoders, Revature, Generic Staffing Corp"
            value={newBlacklistCompany}
            onChange={(e) => setNewBlacklistCompany(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addBlacklistCompany()}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-red-500"
          />
          <button
            onClick={addBlacklistCompany}
            className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add to Blacklist
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.filters.excluded_companies.map((company, idx) => (
            <span
              key={idx}
              className="bg-red-950/60 border border-red-800/80 text-red-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              ⛔ {company}
              <button onClick={() => removeBlacklistCompany(idx)} className="hover:text-red-400">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
