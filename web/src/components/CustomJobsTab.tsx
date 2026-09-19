import React, { useCallback, useEffect, useState } from 'react';
import { ClipboardList, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { apiFetch, deleteJson, errorMessage, postJson } from '../api';
import { formatSalary, parseOptionalNumber, safeUrl } from '../format';
import { CustomJob } from '../types';
import { Notice, Section, inputClass, labelClass } from './ui';

const EMPTY_FORM = {
  title: '',
  company: '',
  location: 'Remote',
  url: '',
  salary_min: '',
  salary_max: '',
  salary_currency: 'USD',
  salary_period: 'yearly',
  description: '',
};

export const CustomJobsTab: React.FC = () => {
  const [jobs, setJobs] = useState<CustomJob[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'error' | 'success'; message: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<{ custom_jobs: CustomJob[] }>('/api/jobs/custom');
      setJobs(data.custom_jobs);
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const set = (field: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [field]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim() || !form.company.trim()) {
      setNotice({ kind: 'error', message: 'A job title and company are required.' });
      return;
    }
    if (form.url.trim() && !safeUrl(form.url.trim())) {
      setNotice({ kind: 'error', message: 'The application link must start with http:// or https://.' });
      return;
    }
    setBusy(true);
    try {
      await postJson('/api/jobs/custom', {
        ...form,
        title: form.title.trim(),
        company: form.company.trim(),
        url: form.url.trim(),
        salary_min: parseOptionalNumber(form.salary_min),
        salary_max: parseOptionalNumber(form.salary_max),
      });
      setForm(EMPTY_FORM);
      setNotice({ kind: 'success', message: 'Saved. It will be scored on the next run.' });
      await load();
    } catch (err) {
      setNotice({ kind: 'error', message: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (job: CustomJob) => {
    if (!window.confirm(`Remove “${job.title}” at ${job.company}?`)) return;
    try {
      await deleteJson(`/api/jobs/custom/${encodeURIComponent(job.id)}`);
      await load();
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  };

  return (
    <div className="space-y-6">
      {notice && <Notice kind={notice.kind} message={notice.message} onClose={() => setNotice(null)} />}

      <Section
        icon={<Plus className="w-5 h-5 text-blue-400" aria-hidden="true" />}
        title="Add a job you found elsewhere"
        description="Referrals, LinkedIn posts, emails: it's scored against your job specs and included in alerts like any other posting."
      >
        <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="cj-title" className={labelClass}>Job title *</label>
            <input id="cj-title" type="text" value={form.title} onChange={set('title')} className={inputClass} required />
          </div>
          <div>
            <label htmlFor="cj-company" className={labelClass}>Company *</label>
            <input id="cj-company" type="text" value={form.company} onChange={set('company')} className={inputClass} required />
          </div>
          <div>
            <label htmlFor="cj-location" className={labelClass}>Location & remote policy</label>
            <input id="cj-location" type="text" value={form.location} onChange={set('location')} placeholder="e.g. Remote (Worldwide)" className={inputClass} />
          </div>
          <div>
            <label htmlFor="cj-url" className={labelClass}>Application link</label>
            <input id="cj-url" type="url" value={form.url} onChange={set('url')} placeholder="https://…" className={inputClass} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="cj-min" className={labelClass}>Salary from</label>
              <input id="cj-min" type="number" min={0} value={form.salary_min} onChange={set('salary_min')} className={inputClass} />
            </div>
            <div>
              <label htmlFor="cj-max" className={labelClass}>Salary to</label>
              <input id="cj-max" type="number" min={0} value={form.salary_max} onChange={set('salary_max')} className={inputClass} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="cj-currency" className={labelClass}>Currency</label>
              <select id="cj-currency" value={form.salary_currency} onChange={set('salary_currency')} className={inputClass}>
                {['USD', 'EUR', 'GBP', 'NGN', 'CAD', 'INR', 'KES', 'GHS', 'ZAR'].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="cj-period" className={labelClass}>Per</label>
              <select id="cj-period" value={form.salary_period} onChange={set('salary_period')} className={inputClass}>
                <option value="yearly">Year</option>
                <option value="monthly">Month</option>
                <option value="hourly">Hour</option>
              </select>
            </div>
          </div>
          <div className="md:col-span-2">
            <label htmlFor="cj-description" className={labelClass}>Description / key requirements</label>
            <textarea id="cj-description" rows={3} value={form.description} onChange={set('description')} className={inputClass} />
          </div>
          <div className="md:col-span-2">
            <button type="submit" disabled={busy}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5">
              <Plus className="w-4 h-4" aria-hidden="true" /> Save job
            </button>
          </div>
        </form>
      </Section>

      <Section
        icon={<ClipboardList className="w-5 h-5 text-emerald-400" aria-hidden="true" />}
        title="Your added jobs"
        actions={
          <button type="button" onClick={() => void load()} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" /> Refresh
          </button>
        }
      >
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-500">No jobs added yet.</p>
        ) : (
          <ul className="space-y-2">
            {jobs.map((job) => {
              const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency, job.salary_period);
              const link = safeUrl(job.url);
              return (
                <li key={job.id} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold text-white text-sm">{job.title}</div>
                    <div className="text-xs text-slate-400">{job.company} · {job.location}{salary ? ` · ${salary}` : ''}</div>
                    {link && <a href={link} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:underline break-all">{link}</a>}
                  </div>
                  <button type="button" aria-label={`Remove ${job.title}`} title="Remove" onClick={() => void remove(job)}
                    className="text-slate-500 hover:text-red-400 p-1 rounded shrink-0">
                    <Trash2 className="w-4 h-4" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </div>
  );
};
