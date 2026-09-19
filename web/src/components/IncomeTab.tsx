import React, { useCallback, useEffect, useState } from 'react';
import { Coins, ExternalLink, Plus, RefreshCw, ShieldCheck, SlidersHorizontal, Trash2, X } from 'lucide-react';
import { apiFetch, deleteJson, errorMessage, postJson } from '../api';
import { formatSalary, humanize, safeUrl } from '../format';
import { AppConfig, CatalogSourceKey, CustomIncome, OnlineIncomeConfig, ScoredOpportunity } from '../types';
import { Notice, Section, TagInput, Toggle, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

type SubTab = 'tracks' | 'email' | 'preferences' | 'custom';

const CATEGORIES = [
  'ai_evaluation', 'data_annotation', 'research', 'academic_editing', 'proofreading', 'tutoring',
  'user_testing', 'transcription', 'virtual_assistant', 'customer_support', 'data_entry', 'bookkeeping',
];

const CATALOG_SOURCES: { key: CatalogSourceKey; label: string }[] = [
  { key: 'ai_evaluation', label: 'AI evaluation & annotation (DataAnnotation, Outlier, OneForma, TELUS, Appen)' },
  { key: 'user_testing', label: 'User testing & research studies (UserTesting, Testbirds, Respondent, Prolific)' },
  { key: 'academic_tutoring', label: 'Proofreading & tutoring (Cambridge Proofreading, Scribbr, Preply, Cambly)' },
  { key: 'transcription_support', label: 'Transcription & remote support (Rev, GoTranscript, ModSquad, Time etc)' },
];

const EMPTY_GIG = {
  title: '',
  organization: '',
  category: 'ai_evaluation',
  pay_rate_display: '',
  url: '',
  location_eligibility: 'Worldwide',
  description: '',
};

export const IncomeTab: React.FC<Props> = ({ config, onChange }) => {
  const [tab, setTab] = useState<SubTab>('tracks');
  const [items, setItems] = useState<ScoredOpportunity[]>([]);
  const [minQuality, setMinQuality] = useState('7');
  const [minFit, setMinFit] = useState('0');
  const [tier, setTier] = useState('');
  const [category, setCategory] = useState('');
  const [includeRejected, setIncludeRejected] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);
  const [custom, setCustom] = useState<CustomIncome[]>([]);
  const [gig, setGig] = useState(EMPTY_GIG);
  const [notice, setNotice] = useState<{ kind: 'error' | 'success'; message: string } | null>(null);

  const income = config.online_income;
  const setIncome = (patch: Partial<OnlineIncomeConfig>) => onChange({ ...config, online_income: { ...income, ...patch } });
  const setCatalogSource = (key: CatalogSourceKey, enabled: boolean) =>
    setIncome({ sources: { ...income.sources, [key]: { ...income.sources[key], enabled } } });

  const loadOpportunities = useCallback(async () => {
    const params = new URLSearchParams({ min_quality: minQuality, min_side_job_fit: minFit, include_rejected: String(includeRejected), limit: '100' });
    if (tier) params.set('source_trust_tier', tier);
    if (category) params.set('category', category);
    try {
      const data = await apiFetch<{ opportunities: ScoredOpportunity[] }>(`/api/income/opportunities?${params.toString()}`);
      setItems(data.opportunities);
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  }, [minQuality, minFit, tier, category, includeRejected]);

  const loadCustom = useCallback(async () => {
    try {
      const data = await apiFetch<{ custom_opportunities: CustomIncome[] }>('/api/income/custom');
      setCustom(data.custom_opportunities);
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  }, []);

  useEffect(() => {
    void loadOpportunities();
  }, [loadOpportunities]);

  useEffect(() => {
    if (tab === 'custom') void loadCustom();
  }, [tab, loadCustom]);

  const scan = async () => {
    setScanning(true);
    try {
      const data = await postJson<{ opportunities_count: number }>('/api/income/run', { dry_run: true, force_all: true });
      setNotice({ kind: 'success', message: `Scanned ${data.opportunities_count} opportunities (test run: nothing emailed or saved).` });
      setPreviewKey((k) => k + 1);
      await loadOpportunities();
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    } finally {
      setScanning(false);
    }
  };

  const dismiss = async (item: ScoredOpportunity) => {
    if (!window.confirm(`Hide “${item.opportunity.title}” from future alerts?`)) return;
    try {
      await postJson('/api/income/dismiss', { fingerprint: item.opportunity.fingerprint });
      setItems(items.filter((i) => i.opportunity.fingerprint !== item.opportunity.fingerprint));
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  };

  const addGig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gig.title.trim() || !gig.organization.trim()) {
      setNotice({ kind: 'error', message: 'A title and platform/organization are required.' });
      return;
    }
    if (gig.url.trim() && !safeUrl(gig.url.trim())) {
      setNotice({ kind: 'error', message: 'The link must start with http:// or https://.' });
      return;
    }
    try {
      await postJson('/api/income/custom', { ...gig, title: gig.title.trim(), organization: gig.organization.trim(), url: gig.url.trim() });
      setGig(EMPTY_GIG);
      setNotice({ kind: 'success', message: 'Saved. It will be screened and scored on the next run.' });
      await loadCustom();
    } catch (err) {
      setNotice({ kind: 'error', message: errorMessage(err) });
    }
  };

  const removeGig = async (entry: CustomIncome) => {
    if (!window.confirm(`Remove “${entry.title}”?`)) return;
    try {
      await deleteJson(`/api/income/custom/${encodeURIComponent(entry.id)}`);
      await loadCustom();
    } catch (e) {
      setNotice({ kind: 'error', message: errorMessage(e) });
    }
  };

  const setGigField = (field: keyof typeof EMPTY_GIG) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setGig({ ...gig, [field]: e.target.value });

  const tabButton = (id: SubTab, label: string) => (
    <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${tab === id ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'}`}>
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      {notice && <Notice kind={notice.kind} message={notice.message} onClose={() => setNotice(null)} />}

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Coins className="w-5 h-5 text-emerald-400" aria-hidden="true" /> Online income
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Flexible paid work that fits alongside a job: AI evaluation, user testing, tutoring, transcription.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-2" role="tablist" aria-label="Online income views">
            {tabButton('tracks', 'Opportunities')}
            {tabButton('email', 'Email preview')}
            {tabButton('preferences', 'Preferences')}
            {tabButton('custom', 'Custom gigs')}
          </div>
          <button type="button" onClick={scan} disabled={scanning}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold px-3.5 py-2 rounded-lg flex items-center gap-1.5">
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} aria-hidden="true" /> {scanning ? 'Scanning…' : 'Scan now'}
          </button>
        </div>
      </div>

      {tab === 'tracks' && (
        <>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-end gap-4 text-xs">
            <div>
              <label htmlFor="income-quality" className={labelClass}>Quality</label>
              <select id="income-quality" value={minQuality} onChange={(e) => setMinQuality(e.target.value)} className={inputClass}>
                <option value="7">Passed the quality gate (7.0+)</option>
                <option value="8.5">Top tier (8.5+)</option>
                <option value="0">Any quality</option>
              </select>
            </div>
            <div>
              <label htmlFor="income-fit" className={labelClass}>Side-job fit</label>
              <select id="income-fit" value={minFit} onChange={(e) => setMinFit(e.target.value)} className={inputClass}>
                <option value="0">Any schedule</option>
                <option value="7">Good fit (7.0+)</option>
                <option value="9">Fully asynchronous (9.0+)</option>
              </select>
            </div>
            <div>
              <label htmlFor="income-tier" className={labelClass}>Source</label>
              <select id="income-tier" value={tier} onChange={(e) => setTier(e.target.value)} className={inputClass}>
                <option value="">Any source</option>
                <option value="tier_1">Tier 1 (official portals)</option>
                <option value="tier_2">Tier 2 (established platforms, your entries)</option>
                <option value="tier_3">Tier 3 (feeds, needs review)</option>
              </select>
            </div>
            <div>
              <label htmlFor="income-category" className={labelClass}>Category</label>
              <select id="income-category" value={category} onChange={(e) => setCategory(e.target.value)} className={inputClass}>
                <option value="">All categories</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
              </select>
            </div>
            <Toggle id="income-include-rejected" label="Show discarded" checked={includeRejected} onChange={setIncludeRejected} />
          </div>

          {items.length === 0 ? (
            <Notice kind="info" message="No opportunities match these filters yet. Use “Scan now” to run a test scan." />
          ) : (
            <ul className="space-y-4">
              {items.map((item) => {
                const opp = item.opportunity;
                const link = safeUrl(opp.application_url || opp.url);
                const pay = opp.pay_rate_display || formatSalary(opp.estimated_pay_min, opp.estimated_pay_max, opp.pay_currency, opp.pay_frequency);
                const discarded = item.action === 'discard';
                const reasons = item.breakdown.rejection_reasons?.length ? item.breakdown.rejection_reasons : opp.rejection_reasons;
                return (
                  <li key={opp.fingerprint} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                    <div className="flex flex-wrap justify-between gap-3">
                      <div>
                        <h3 className="text-base font-bold text-white">{opp.title}</h3>
                        <div className="text-sm text-emerald-400 font-semibold">
                          {opp.organization} · <span className="text-slate-400">📍 {opp.location_eligibility}</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <div className="text-right text-xs text-slate-400">
                          <div className="text-sm font-black text-white">{item.score.toFixed(1)} / 10</div>
                          Quality {item.breakdown.quality_score.toFixed(1)} · Fit {item.breakdown.side_job_fit_score.toFixed(1)}
                        </div>
                        <button type="button" aria-label={`Hide ${opp.title}`} title="Hide from future alerts" onClick={() => void dismiss(item)}
                          className="text-slate-500 hover:text-red-400 p-1 rounded">
                          <X className="w-4 h-4" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">💵 {pay || 'Pay not stated'}</span>
                      <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">{humanize(opp.category)}</span>
                      <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">{humanize(opp.source_trust_tier)}</span>
                      {opp.is_asynchronous && <span className="bg-slate-950 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-md">🌙 Asynchronous</span>}
                      {opp.last_reviewed && (
                        <span className={`px-2.5 py-1 rounded-md border ${opp.review_overdue ? 'bg-amber-950/60 border-amber-800 text-amber-300' : 'bg-slate-950 border-slate-800 text-slate-400'}`}>
                          Catalogue entry, reviewed {opp.last_reviewed}
                        </span>
                      )}
                    </div>
                    {opp.description && <p className="text-sm text-slate-400">{opp.description}</p>}
                    {discarded && reasons.length > 0 ? (
                      <ul className="text-xs text-red-300 pl-4 list-disc space-y-1" aria-label="Why it was discarded">
                        {reasons.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    ) : (
                      <ul className="text-xs text-slate-300 pl-4 list-disc space-y-1" aria-label="Why it's worth considering">
                        {item.breakdown.highlights.map((h, i) => <li key={i}>{h}</li>)}
                      </ul>
                    )}
                    {item.breakdown.penalties_applied.length > 0 && !discarded && (
                      <ul className="text-xs text-amber-300/90 pl-4 list-disc space-y-1">
                        {item.breakdown.penalties_applied.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                    )}
                    <div className="flex justify-between items-center pt-3 border-t border-slate-800 text-xs">
                      <span className="text-slate-500">Source: {humanize(opp.source)}</span>
                      {link && (
                        <a href={link} target="_blank" rel="noopener noreferrer"
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-1.5 rounded-lg flex items-center gap-1">
                          Open <ExternalLink className="w-3 h-3" aria-hidden="true" />
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}

      {tab === 'email' && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-2 overflow-hidden">
          <iframe key={previewKey} src="/api/income/preview-email" title="Online income digest preview" sandbox=""
            className="w-full h-[700px] border-0 rounded-lg bg-white" />
        </div>
      )}

      {tab === 'preferences' && (
        <div className="space-y-6">
          <Notice kind="info" message="Changes here are saved with the “Save changes” button at the top." />
          <Section icon={<SlidersHorizontal className="w-5 h-5 text-emerald-400" aria-hidden="true" />} title="What to look for">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <TagInput id="income-countries" label="Where you can work from" tone="emerald" values={income.eligible_countries}
                onChange={(eligible_countries) => setIncome({ eligible_countries })} placeholder="e.g. Nigeria, Africa, Worldwide" />
              <TagInput id="income-currencies" label="Currencies you can be paid in" tone="emerald" values={income.preferred_currencies}
                onChange={(preferred_currencies) => setIncome({ preferred_currencies: preferred_currencies.map((c) => c.toUpperCase()) })} placeholder="e.g. USD" />
              <div>
                <label htmlFor="income-min-rate" className={labelClass}>Minimum hourly pay (USD)</label>
                <input id="income-min-rate" type="number" min={0} step={0.5} value={income.minimum_hourly_rate_usd} className={inputClass}
                  onChange={(e) => setIncome({ minimum_hourly_rate_usd: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <label htmlFor="income-max-hours" className={labelClass}>Most hours you can give per week</label>
                <input id="income-max-hours" type="number" min={1} max={60} value={income.maximum_hours_per_week} className={inputClass}
                  onChange={(e) => setIncome({ maximum_hours_per_week: parseInt(e.target.value, 10) || 1 })} />
              </div>
              <div>
                <label htmlFor="income-flexibility" className={labelClass}>Schedule flexibility you need</label>
                <select id="income-flexibility" value={income.preferred_flexibility} className={inputClass}
                  onChange={(e) => setIncome({ preferred_flexibility: e.target.value })}>
                  <option value="high">High (work whenever I want)</option>
                  <option value="medium">Medium</option>
                  <option value="any">Any</option>
                </select>
              </div>
              <div>
                <label htmlFor="income-max-digest" className={labelClass}>Opportunities per digest</label>
                <input id="income-max-digest" type="number" min={1} max={20} value={income.max_digest_items} className={inputClass}
                  onChange={(e) => setIncome({ max_digest_items: parseInt(e.target.value, 10) || 1 })} />
              </div>
            </div>
            <div className="space-y-3 pt-2">
              <Toggle id="income-async-only" label="Only fully asynchronous work" checked={income.allow_asynchronous_only}
                onChange={(allow_asynchronous_only) => setIncome({ allow_asynchronous_only })} />
              <Toggle id="income-include-digest" label="Include online income in the daily digest" checked={income.include_in_daily_digest}
                onChange={(include_in_daily_digest) => setIncome({ include_in_daily_digest })} />
            </div>
          </Section>

          <Section icon={<ShieldCheck className="w-5 h-5 text-emerald-400" aria-hidden="true" />} title="Safety & sources">
            <div className="space-y-3">
              <Toggle id="income-verified-only" label="Only alert from known platforms and my own entries"
                description="Items from feeds stay visible here for review but aren't emailed." checked={income.require_verified_source}
                onChange={(require_verified_source) => setIncome({ require_verified_source })} />
              <Toggle id="income-link-check" label="Check that application links still work" checked={income.require_link_verification}
                onChange={(require_link_verification) => setIncome({ require_link_verification })} />
              <Toggle id="income-unknown-eligibility" label="Skip listings that don't say where they're open"
                checked={income.reject_unknown_eligibility} onChange={(reject_unknown_eligibility) => setIncome({ reject_unknown_eligibility })} />
              <Toggle id="income-unknown-pay" label="Skip listings that don't state pay"
                checked={income.reject_unknown_compensation} onChange={(reject_unknown_compensation) => setIncome({ reject_unknown_compensation })} />
            </div>
            <div className="space-y-3 pt-2 border-t border-slate-800">
              <p className="text-xs text-slate-400 pt-3">Curated platform catalogue (config/income_catalog.yaml):</p>
              {CATALOG_SOURCES.map((source) => (
                <Toggle key={source.key} id={`income-source-${source.key}`} label={source.label}
                  checked={income.sources[source.key].enabled} onChange={(enabled) => setCatalogSource(source.key, enabled)} />
              ))}
            </div>
          </Section>
        </div>
      )}

      {tab === 'custom' && (
        <div className="space-y-6">
          <Section icon={<Plus className="w-5 h-5 text-emerald-400" aria-hidden="true" />} title="Add an income opportunity">
            <form onSubmit={addGig} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="gig-title" className={labelClass}>Title *</label>
                <input id="gig-title" type="text" value={gig.title} onChange={setGigField('title')} className={inputClass} required />
              </div>
              <div>
                <label htmlFor="gig-org" className={labelClass}>Platform / organization *</label>
                <input id="gig-org" type="text" value={gig.organization} onChange={setGigField('organization')} className={inputClass} required />
              </div>
              <div>
                <label htmlFor="gig-category" className={labelClass}>Category</label>
                <select id="gig-category" value={gig.category} onChange={setGigField('category')} className={inputClass}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{humanize(c)}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="gig-pay" className={labelClass}>Pay as listed</label>
                <input id="gig-pay" type="text" value={gig.pay_rate_display} onChange={setGigField('pay_rate_display')} placeholder="e.g. $20–$30/hr" className={inputClass} />
              </div>
              <div>
                <label htmlFor="gig-url" className={labelClass}>Application link</label>
                <input id="gig-url" type="url" value={gig.url} onChange={setGigField('url')} placeholder="https://…" className={inputClass} />
              </div>
              <div>
                <label htmlFor="gig-location" className={labelClass}>Where it's open</label>
                <input id="gig-location" type="text" value={gig.location_eligibility} onChange={setGigField('location_eligibility')} className={inputClass} />
              </div>
              <div className="md:col-span-2">
                <label htmlFor="gig-description" className={labelClass}>Description</label>
                <textarea id="gig-description" rows={3} value={gig.description} onChange={setGigField('description')} className={inputClass} />
              </div>
              <div className="md:col-span-2">
                <button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5">
                  <Plus className="w-4 h-4" aria-hidden="true" /> Save opportunity
                </button>
              </div>
            </form>
          </Section>

          <Section icon={<Coins className="w-5 h-5 text-emerald-400" aria-hidden="true" />} title="Your added opportunities">
            {custom.length === 0 ? (
              <p className="text-sm text-slate-500">Nothing added yet.</p>
            ) : (
              <ul className="space-y-2">
                {custom.map((entry) => (
                  <li key={entry.id} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold text-white text-sm">{entry.title}</div>
                      <div className="text-xs text-slate-400">
                        {entry.organization} · {humanize(entry.category)}{entry.pay_rate_display ? ` · ${entry.pay_rate_display}` : ''}
                      </div>
                    </div>
                    <button type="button" aria-label={`Remove ${entry.title}`} title="Remove" onClick={() => void removeGig(entry)}
                      className="text-slate-500 hover:text-red-400 p-1 rounded shrink-0">
                      <Trash2 className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      )}
    </div>
  );
};
