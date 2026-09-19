import React, { useState } from 'react';
import { ExternalLink, Eye, Filter, Play, RefreshCw, Sparkles } from 'lucide-react';
import { RunSummary, ScoredJob } from '../types';
import { formatSalary, humanize, safeUrl } from '../format';

interface Props {
  onTriggerRun: (forceAll: boolean) => Promise<void>;
  isRunning: boolean;
  latestSummary: RunSummary | null;
  scoredJobs: ScoredJob[];
  instantThreshold: number;
}

const Stat: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone = 'text-white' }) => (
  <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
    <div className="text-xs text-slate-400">{label}</div>
    <div className={`text-lg font-bold mt-1 ${tone}`}>{value}</div>
  </div>
);

export const DryRunTab: React.FC<Props> = ({ onTriggerRun, isRunning, latestSummary, scoredJobs, instantThreshold }) => {
  const [viewMode, setViewMode] = useState<'cards' | 'email'>('cards');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(5.0);
  const [forceAll, setForceAll] = useState<boolean>(true);
  const [previewKey, setPreviewKey] = useState(0);

  const filteredJobs = scoredJobs.filter((j) => j.score >= minScoreFilter);

  const run = async () => {
    await onTriggerRun(forceAll);
    setPreviewKey((k) => k + 1);
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" aria-hidden="true" /> Test run & email preview
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Collects, scores and previews with your current settings. Nothing is emailed or saved as seen.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" checked={forceAll} onChange={(e) => setForceAll(e.target.checked)} className="accent-blue-500 rounded" />
            Include postings already processed
          </label>
          <button
            type="button"
            onClick={run}
            disabled={isRunning}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold px-6 py-2.5 rounded-lg text-sm shadow-md flex items-center gap-2 transition"
          >
            {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Play className="w-4 h-4 fill-white" aria-hidden="true" />}
            {isRunning ? 'Running…' : 'Run test'}
          </button>
        </div>
      </div>

      {latestSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          <Stat label="Collected" value={latestSummary.total_fetched} />
          <Stat label="New to score" value={latestSummary.unique_candidates} tone="text-blue-400" />
          <Stat label={`Instant (${instantThreshold.toFixed(1)}+)`} value={latestSummary.instant_matches} tone="text-emerald-400" />
          <Stat label="Digest (7.0+)" value={latestSummary.digest_matches} tone="text-cyan-400" />
          <Stat label="Links unverifiable" value={latestSummary.unverified_links} tone="text-amber-300" />
          <Stat label="Duration" value={`${latestSummary.execution_time_seconds}s`} tone="text-purple-400" />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex gap-2" role="tablist" aria-label="Result view">
          <button type="button" role="tab" aria-selected={viewMode === 'cards'} onClick={() => setViewMode('cards')}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${viewMode === 'cards' ? 'bg-blue-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'}`}>
            Scored postings ({filteredJobs.length})
          </button>
          <button type="button" role="tab" aria-selected={viewMode === 'email'} onClick={() => setViewMode('email')}
            className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition ${viewMode === 'email' ? 'bg-blue-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white'}`}>
            <Eye className="w-4 h-4" aria-hidden="true" /> Email preview
          </button>
        </div>
        {viewMode === 'cards' && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-4 h-4" aria-hidden="true" />
            <label htmlFor="min-score-filter">Show</label>
            <select id="min-score-filter" value={minScoreFilter} onChange={(e) => setMinScoreFilter(parseFloat(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white text-xs focus:outline-none">
              <option value={0}>All scored postings</option>
              <option value={5.0}>5.0+ (including low matches)</option>
              <option value={7.0}>7.0+ (digest and instant)</option>
              <option value={instantThreshold}>{instantThreshold.toFixed(1)}+ (instant only)</option>
            </select>
          </div>
        )}
      </div>

      {viewMode === 'email' ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-2 overflow-hidden">
          <div className="flex justify-between items-center px-4 py-2 bg-slate-950 rounded-t-lg border-b border-slate-800 text-xs text-slate-400">
            <span>Latest rendered digest</span>
            <a href="/api/preview-email" target="_blank" rel="noreferrer" className="text-blue-400 hover:underline flex items-center gap-1">
              Open in new window <ExternalLink className="w-3 h-3" aria-hidden="true" />
            </a>
          </div>
          <iframe key={previewKey} src="/api/preview-email" title="Email digest preview" sandbox=""
            className="w-full h-[750px] border-0 rounded-b-lg bg-white" />
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
          <Sparkles className="w-10 h-10 text-slate-600 mx-auto mb-3" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-slate-300">No postings to show</h3>
          <p className="text-sm text-slate-500 mt-1">Run a test above, or lower the score filter.</p>
        </div>
      ) : (
        <ul className="space-y-4">
          {filteredJobs.map((item, idx) => {
            const isInstant = item.score >= instantThreshold;
            const isDigest = item.score >= 7.0 && !isInstant;
            const salary = formatSalary(item.job.salary_min, item.job.salary_max, item.job.salary_currency, item.job.salary_period);
            const applyUrl = safeUrl(item.job.url);
            return (
              <li key={`${item.job.fingerprint}-${item.spec_name ?? ''}-${idx}`} className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5">
                <div className="flex flex-wrap justify-between items-start gap-2 mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-white">{item.job.title}</h3>
                    <div className="text-sm font-semibold text-blue-400">
                      {item.job.company} · <span className="text-slate-400">{item.job.location}</span>
                    </div>
                  </div>
                  <span className={`text-xs font-black px-3 py-1.5 rounded-lg border ${
                    isInstant ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
                      : isDigest ? 'bg-blue-950/80 text-blue-300 border-blue-700'
                      : 'bg-slate-800 text-slate-300 border-slate-700'}`}>
                    {item.score.toFixed(1)} / 10
                  </span>
                </div>

                <div className="flex flex-wrap gap-2 mb-3 text-xs">
                  {item.spec_name && <span className="bg-indigo-950/60 border border-indigo-800 text-indigo-200 px-2.5 py-1 rounded-md">{item.spec_name}</span>}
                  <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">📍 {item.job.remote_scope || item.job.location}</span>
                  <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">{salary ? `💰 ${salary}` : '💰 Pay not listed'}</span>
                  <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">{humanize(item.job.employment_type)}</span>
                  <span className="bg-slate-950 border border-slate-800 text-purple-300 px-2.5 py-1 rounded-md">{item.job.source}</span>
                </div>

                {item.breakdown.highlights.length > 0 && (
                  <div className="bg-slate-950 border-l-2 border-blue-500 rounded-r-lg p-3 my-3">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">Why you match</div>
                    <ul className="text-xs text-slate-300 space-y-1 pl-4 list-disc">
                      {item.breakdown.highlights.map((highlight, hIdx) => <li key={hIdx}>{highlight}</li>)}
                    </ul>
                  </div>
                )}
                {item.breakdown.penalties_applied.length > 0 && (
                  <ul className="text-xs text-amber-300/90 space-y-1 pl-4 list-disc mb-2">
                    {item.breakdown.penalties_applied.map((penalty, pIdx) => <li key={pIdx}>{penalty}</li>)}
                  </ul>
                )}

                <div className="flex justify-end pt-3 border-t border-slate-800/80 text-xs">
                  {applyUrl ? (
                    <a href={applyUrl} target="_blank" rel="noopener noreferrer"
                      className="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition">
                      View posting <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                    </a>
                  ) : (
                    <span className="text-slate-500">No link provided</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
