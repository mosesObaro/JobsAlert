import React, { useState, useEffect } from 'react';
import { RunSummary, CrawlerHealth } from '../types';
import { Activity, Database, Trash2, CheckCircle2, AlertTriangle, XCircle, Clock, RefreshCw } from 'lucide-react';

interface Props {
  latestSummary: RunSummary | null;
  onRefresh: () => void;
}

export const LogsHealthTab: React.FC<Props> = ({ latestSummary, onRefresh }) => {
  const [logs, setLogs] = useState<RunSummary[]>([]);
  const [seenCount, setSeenCount] = useState<number>(0);
  const [isClearing, setIsClearing] = useState<boolean>(false);

  const fetchTelemetry = async () => {
    try {
      const resLogs = await fetch('/api/logs');
      const dataLogs = await resLogs.json();
      setLogs(dataLogs.logs || []);

      const resSeen = await fetch('/api/seen-jobs');
      const dataSeen = await resSeen.json();
      setSeenCount(dataSeen.total_seen || 0);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, [latestSummary]);

  const clearSeenJobs = async () => {
    if (!window.confirm('Clear all deduplication history? This will allow all previously seen jobs to be re-evaluated on the next crawl.')) {
      return;
    }
    setIsClearing(true);
    try {
      await fetch('/api/seen-jobs/clear', { method: 'POST' });
      await fetchTelemetry();
    } catch (e) {
      console.error(e);
    } finally {
      setIsClearing(false);
    }
  };

  const healthReports: CrawlerHealth[] = latestSummary?.source_health || [];

  return (
    <div className="space-y-8">
      {/* Deduplication & State Cache Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-blue-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Deduplication State & Persistence Layer</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Cached in <code className="bg-slate-950 px-1.5 py-0.5 rounded text-blue-300 font-mono">data/seen_jobs.json</code> (or Supabase Postgres). Guarantees zero duplicate alerts.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-slate-400 uppercase font-semibold">Tracked Fingerprints</div>
            <div className="text-2xl font-black text-white">{seenCount}</div>
          </div>
          <button
            onClick={clearSeenJobs}
            disabled={isClearing}
            className="bg-red-950/60 hover:bg-red-900/80 border border-red-800 text-red-300 px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <Trash2 className="w-4 h-4" /> Clear Seen Cache
          </button>
        </div>
      </div>

      {/* Source Health & Latency Cards */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white">Connector Health & Latency Telemetry</h2>
          </div>
          <button
            onClick={fetchTelemetry}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh Health
          </button>
        </div>

        {healthReports.length === 0 ? (
          <p className="text-sm text-slate-500">Run a dry run to inspect live endpoint health.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {healthReports.map((source, idx) => (
              <div
                key={idx}
                className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-sm text-white capitalize">{source.source_name}</div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    {source.jobs_found} jobs • {source.latency_ms}ms
                  </div>
                </div>

                <div>
                  {source.status === 'healthy' ? (
                    <span className="flex items-center gap-1 text-emerald-400 text-xs font-bold bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/80">
                      <CheckCircle2 className="w-3 h-3" /> Healthy
                    </span>
                  ) : source.status === 'degraded' ? (
                    <span className="flex items-center gap-1 text-amber-400 text-xs font-bold bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/80">
                      <AlertTriangle className="w-3 h-3" /> Degraded
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-400 text-xs font-bold bg-red-950/60 px-2 py-0.5 rounded border border-red-800/80">
                      <XCircle className="w-3 h-3" /> Error
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Historical Execution Log */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-white">Recent Pipeline Execution History</h2>
        </div>

        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">No historical runs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Run ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Fetched</th>
                  <th className="py-2.5 px-3">Unique</th>
                  <th className="py-2.5 px-3">Instant (9.0+)</th>
                  <th className="py-2.5 px-3">Digest (7.0+)</th>
                  <th className="py-2.5 px-3">Duration</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {logs.map((log, idx) => (
                  <tr key={idx} className="hover:bg-slate-950/50">
                    <td className="py-2 px-3 font-mono text-slate-300">{log.run_id}</td>
                    <td className="py-2 px-3 text-slate-400">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 px-3 font-semibold text-white">{log.total_fetched}</td>
                    <td className="py-2 px-3 text-blue-400">{log.unique_candidates}</td>
                    <td className="py-2 px-3 text-emerald-400 font-bold">{log.instant_matches}</td>
                    <td className="py-2 px-3 text-cyan-400">{log.digest_matches}</td>
                    <td className="py-2 px-3 text-purple-300">{log.execution_time_seconds}s</td>
                    <td className="py-2 px-3">
                      <span className="bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded text-[11px] font-bold border border-emerald-800">
                        SUCCESS
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
