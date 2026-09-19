import React, { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Clock, Database, MinusCircle, RefreshCw, Trash2, XCircle } from 'lucide-react';
import { apiFetch, errorMessage, postJson } from '../api';
import { formatDateTime } from '../format';
import { CrawlerHealth, RunSummary, SourceStatus } from '../types';
import { Notice, Section } from './ui';

interface Props {
  latestSummary: RunSummary | null;
}

const STATUS_BADGE: Record<SourceStatus, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  healthy: { label: 'Healthy', className: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/80', Icon: CheckCircle2 },
  degraded: { label: 'Degraded', className: 'text-amber-400 bg-amber-950/60 border-amber-800/80', Icon: AlertTriangle },
  error: { label: 'Error', className: 'text-red-400 bg-red-950/60 border-red-800/80', Icon: XCircle },
  disabled: { label: 'Off', className: 'text-slate-400 bg-slate-900 border-slate-700', Icon: MinusCircle },
};

function runOutcome(log: RunSummary): { label: string; className: string } {
  if (log.mode === 'dry_run') return { label: 'Dry run', className: 'bg-slate-800 text-slate-300 border-slate-700' };
  if (log.delivery_errors && log.delivery_errors.length > 0) {
    return { label: `Delivery failed (${log.delivery_errors.length})`, className: 'bg-red-950 text-red-300 border-red-800' };
  }
  if (log.pending_alerts > 0) return { label: `${log.pending_alerts} queued`, className: 'bg-amber-950 text-amber-300 border-amber-800' };
  return { label: log.emails_dispatched > 0 ? 'Sent' : 'Nothing new', className: 'bg-emerald-950 text-emerald-300 border-emerald-800' };
}

export const LogsHealthTab: React.FC<Props> = ({ latestSummary }) => {
  const [logs, setLogs] = useState<RunSummary[]>([]);
  const [seenCount, setSeenCount] = useState<number>(0);
  const [alertedCount, setAlertedCount] = useState<number>(0);
  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTelemetry = useCallback(async () => {
    try {
      const [logData, seenData] = await Promise.all([
        apiFetch<{ logs: RunSummary[] }>('/api/logs'),
        apiFetch<{ total_seen: number; total_alerted: number }>('/api/seen-jobs'),
      ]);
      setLogs(logData.logs);
      setSeenCount(seenData.total_seen);
      setAlertedCount(seenData.total_alerted);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void fetchTelemetry();
  }, [fetchTelemetry, latestSummary]);

  const clearSeenJobs = async () => {
    if (!window.confirm('Forget every processed job? Previously sent postings could then be emailed again. A backup of the file is kept.')) return;
    setIsClearing(true);
    try {
      await postJson('/api/seen-jobs/clear');
      await fetchTelemetry();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setIsClearing(false);
    }
  };

  const health: CrawlerHealth[] = latestSummary?.source_health ?? logs[0]?.source_health ?? [];

  return (
    <div className="space-y-6">
      {error && <Notice kind="error" message={error} onClose={() => setError(null)} />}

      <Section
        icon={<Database className="w-5 h-5 text-blue-400" aria-hidden="true" />}
        title="Processed postings"
        description="Postings already scored are skipped on later runs; alerted ones are never emailed twice. Scheduled runs keep this state on the jobsalert-state branch; scripts/sync_state.sh copies it here."
        actions={
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs text-slate-400 uppercase font-semibold">Tracked / alerted</div>
              <div className="text-2xl font-black text-white">{seenCount} / {alertedCount}</div>
            </div>
            <button type="button" onClick={clearSeenJobs} disabled={isClearing}
              className="bg-red-950/60 hover:bg-red-900/80 border border-red-800 text-red-300 px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-50">
              <Trash2 className="w-4 h-4" aria-hidden="true" /> Forget processed jobs
            </button>
          </div>
        }
      >
        <span className="sr-only">Processed postings summary</span>
      </Section>

      <Section
        icon={<Activity className="w-5 h-5 text-emerald-400" aria-hidden="true" />}
        title="Source health"
        description="Degraded means a source returned nothing or some of its requests failed."
        actions={
          <button type="button" onClick={() => void fetchTelemetry()} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Refresh
          </button>
        }
      >
        {health.length === 0 ? (
          <p className="text-sm text-slate-500">Run a test to see each source's health.</p>
        ) : (
          <ul className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {health.map((source) => {
              const badge = STATUS_BADGE[source.status] ?? STATUS_BADGE.error;
              const found = source.jobs_found ?? source.opportunities_found ?? 0;
              return (
                <li key={source.source_name} className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-sm text-white">{source.source_name}</span>
                    <span className={`flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded border ${badge.className}`}>
                      <badge.Icon className="w-3 h-3" aria-hidden="true" /> {badge.label}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">{found} found · {Math.round(source.latency_ms)} ms</div>
                  {source.error_message && <div className="text-xs text-amber-300/90 break-words">{source.error_message}</div>}
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section icon={<Clock className="w-5 h-5 text-indigo-400" aria-hidden="true" />} title="Recent runs">
        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">No runs recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th scope="col" className="py-2.5 px-3">Time</th>
                  <th scope="col" className="py-2.5 px-3">Trigger</th>
                  <th scope="col" className="py-2.5 px-3">Collected</th>
                  <th scope="col" className="py-2.5 px-3">New</th>
                  <th scope="col" className="py-2.5 px-3">Instant</th>
                  <th scope="col" className="py-2.5 px-3">Digest</th>
                  <th scope="col" className="py-2.5 px-3">Emails</th>
                  <th scope="col" className="py-2.5 px-3">Duration</th>
                  <th scope="col" className="py-2.5 px-3">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {logs.map((log) => {
                  const outcome = runOutcome(log);
                  return (
                    <tr key={log.run_id} className="hover:bg-slate-950/50" title={(log.delivery_errors ?? []).join('\n')}>
                      <td className="py-2 px-3 text-slate-300">{formatDateTime(log.timestamp)}</td>
                      <td className="py-2 px-3 text-slate-400">{log.trigger ?? 'unknown'}</td>
                      <td className="py-2 px-3 font-semibold text-white">{log.total_fetched}</td>
                      <td className="py-2 px-3 text-blue-400">{log.unique_candidates}</td>
                      <td className="py-2 px-3 text-emerald-400 font-bold">{log.instant_matches}</td>
                      <td className="py-2 px-3 text-cyan-400">{log.digest_matches}</td>
                      <td className="py-2 px-3 text-slate-300">{log.emails_dispatched}</td>
                      <td className="py-2 px-3 text-purple-300">{log.execution_time_seconds}s</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-bold border ${outcome.className}`}>{outcome.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
};
