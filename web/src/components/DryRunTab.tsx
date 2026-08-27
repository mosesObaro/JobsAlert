import React, { useState } from 'react';
import { ScoredJob, RunSummary } from '../types';
import { Play, Eye, CheckCircle2, AlertCircle, ExternalLink, RefreshCw, Sparkles, Filter } from 'lucide-react';

interface Props {
  onTriggerRun: (dryRun: boolean, forceAll: boolean) => Promise<any>;
  isRunning: boolean;
  latestSummary: RunSummary | null;
  scoredJobs: ScoredJob[];
}

export const DryRunTab: React.FC<Props> = ({
  onTriggerRun,
  isRunning,
  latestSummary,
  scoredJobs,
}) => {
  const [viewMode, setViewMode] = useState<'cards' | 'email'>('cards');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(5.0);
  const [forceAll, setForceAll] = useState<boolean>(true);

  const filteredJobs = scoredJobs.filter((j) => j.score >= minScoreFilter);

  return (
    <div className="space-y-6">
      {/* Control Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            Instant Dry-Run & Email Previewer
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Execute a real-time test run to collect, deduplicate, and score opportunities against your current rules without dispatching real emails.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={forceAll}
              onChange={(e) => setForceAll(e.target.checked)}
              className="accent-blue-500 rounded"
            />
            Force All (Ignore Cache)
          </label>

          <button
            onClick={() => onTriggerRun(true, forceAll)}
            disabled={isRunning}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold px-6 py-2.5 rounded-lg text-sm shadow-md flex items-center gap-2 transition"
          >
            {isRunning ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" /> Running Scout...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" /> Test Run & Preview
              </>
            )}
          </button>
        </div>
      </div>

      {/* Latest Run Telemetry Bar */}
      {latestSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">Total Collected</div>
            <div className="text-lg font-bold text-white mt-1">{latestSummary.total_fetched}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">Unique Candidates</div>
            <div className="text-lg font-bold text-blue-400 mt-1">{latestSummary.unique_candidates}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">★ Instant (9.0+)</div>
            <div className="text-lg font-bold text-emerald-400 mt-1">{latestSummary.instant_matches}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">✦ Digest (7.0-8.9)</div>
            <div className="text-lg font-bold text-cyan-400 mt-1">{latestSummary.digest_matches}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">· Low Matches</div>
            <div className="text-lg font-bold text-slate-400 mt-1">{latestSummary.low_matches}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-center">
            <div className="text-xs text-slate-400">Execution Time</div>
            <div className="text-lg font-bold text-purple-400 mt-1">{latestSummary.execution_time_seconds}s</div>
          </div>
        </div>
      )}

      {/* View Switcher & Filters */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('cards')}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
              viewMode === 'cards'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-white'
            }`}
          >
            Scored Job Cards ({filteredJobs.length})
          </button>
          <button
            onClick={() => setViewMode('email')}
            className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition ${
              viewMode === 'email'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-white'
            }`}
          >
            <Eye className="w-4 h-4" /> Live HTML Email Preview
          </button>
        </div>

        {viewMode === 'cards' && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-4 h-4 text-slate-400" />
            <span>Score Filter:</span>
            <select
              value={minScoreFilter}
              onChange={(e) => setMinScoreFilter(parseFloat(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-white text-xs focus:outline-none"
            >
              <option value={0}>All Postings (0.0+)</option>
              <option value={5.0}>5.0+ (Matches & Low Matches)</option>
              <option value={7.0}>7.0+ (Digest & Instant Only)</option>
              <option value={9.0}>9.0+ (Instant Alerts Only)</option>
            </select>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {viewMode === 'email' ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-2 overflow-hidden shadow-2xl">
          <div className="flex justify-between items-center px-4 py-2 bg-slate-950 rounded-t-lg border-b border-slate-800 text-xs text-slate-400">
            <span>Rendered Template: <code className="text-blue-400 font-mono">src/notifier/templates/digest.html</code></span>
            <a
              href="/api/preview-email"
              target="_blank"
              rel="noreferrer"
              className="text-blue-400 hover:underline flex items-center gap-1"
            >
              Open in New Window <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <iframe
            src="/api/preview-email"
            title="Email Digest Preview"
            className="w-full h-[750px] border-0 rounded-b-lg bg-slate-950"
          />
        </div>
      ) : (
        <div className="space-y-4">
          {filteredJobs.length === 0 ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-400">
              <Sparkles className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-slate-300">No Postings Match Current Filter</h3>
              <p className="text-sm text-slate-500 mt-1">
                Click <strong>"Test Run & Preview"</strong> above or lower the score threshold filter.
              </p>
            </div>
          ) : (
            filteredJobs.map((item, idx) => {
              const isInstant = item.score >= 9.0;
              const isDigest = item.score >= 7.0 && item.score < 9.0;

              return (
                <div
                  key={idx}
                  className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 shadow-sm transition"
                >
                  <div className="flex flex-wrap justify-between items-start gap-2 mb-3">
                    <div>
                      <h3 className="text-lg font-bold text-white">{item.job.title}</h3>
                      <div className="text-sm font-semibold text-blue-400">
                        {item.job.company} • <span className="text-slate-400">{item.job.location}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-black px-3 py-1.5 rounded-lg border flex items-center gap-1 ${
                          isInstant
                            ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700'
                            : isDigest
                            ? 'bg-blue-950/80 text-blue-300 border-blue-700'
                            : 'bg-slate-800 text-slate-300 border-slate-700'
                        }`}
                      >
                        {isInstant ? '★ ' : isDigest ? '✦ ' : '· '}
                        {item.score.toFixed(1)} / 10 Match
                      </span>
                    </div>
                  </div>

                  {/* Chips */}
                  <div className="flex flex-wrap gap-2 mb-3 text-xs">
                    <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">
                      📍 {item.job.remote_scope || item.job.location}
                    </span>
                    {item.job.salary_min || item.job.salary_max ? (
                      <span className="bg-amber-950/40 border border-amber-800/60 text-amber-300 px-2.5 py-1 rounded-md font-semibold">
                        💰 ${(item.job.salary_min || 0).toLocaleString()} - ${(item.job.salary_max || 0).toLocaleString()}
                      </span>
                    ) : (
                      <span className="bg-slate-950 border border-slate-800 text-slate-400 px-2.5 py-1 rounded-md">
                        💰 Comp Unlisted
                      </span>
                    )}
                    <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">
                      👔 {item.job.employment_type.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="bg-slate-950 border border-slate-800 text-purple-300 px-2.5 py-1 rounded-md font-medium">
                      🔗 {item.job.source.toUpperCase()}
                    </span>
                  </div>

                  {/* Why You Match Bullets */}
                  <div className="bg-slate-950 border-l-2 border-blue-500 rounded-r-lg p-3 my-3">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                      Why You Match:
                    </div>
                    <ul className="text-xs text-slate-300 space-y-1 pl-4 list-disc">
                      {item.breakdown.highlights.map((highlight, hIdx) => (
                        <li key={hIdx}>{highlight}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Footer & Apply Link */}
                  <div className="flex justify-between items-center pt-3 border-t border-slate-800/80 text-xs">
                    <span className="text-slate-500 font-mono">
                      Fingerprint: {item.job.fingerprint.slice(0, 12)}...
                    </span>
                    <a
                      href={item.job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition"
                    >
                      Apply Now <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
