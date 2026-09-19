import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  Building2,
  Check,
  ClipboardList,
  Clock,
  Coins,
  Compass,
  FolderOpen,
  Globe,
  ListChecks,
  Play,
  Plus,
  RefreshCw,
  Save,
  Sliders,
  Sparkles,
} from 'lucide-react';
import { apiFetch, errorMessage, postJson } from './api';
import { AppConfig, RunSummary, ScoredJob } from './types';
import { CustomJobsTab } from './components/CustomJobsTab';
import { DryRunTab } from './components/DryRunTab';
import { FiltersTab } from './components/FiltersTab';
import { IncomeTab } from './components/IncomeTab';
import { JobSpecsTab } from './components/JobSpecsTab';
import { LogsHealthTab } from './components/LogsHealthTab';
import { RoleMatrixTab } from './components/RoleMatrixTab';
import { ScheduleTab } from './components/ScheduleTab';
import { SourcesTab } from './components/SourcesTab';
import { WatchlistTab } from './components/WatchlistTab';
import { Notice } from './components/ui';

type TabId = 'specs' | 'roles' | 'filters' | 'watchlist' | 'sources' | 'schedule' | 'income' | 'custom' | 'dryrun' | 'health';

const TABS: { id: TabId; label: string; Icon: typeof Compass }[] = [
  { id: 'specs', label: 'Job specs', Icon: ListChecks },
  { id: 'roles', label: 'Roles & skills', Icon: Compass },
  { id: 'filters', label: 'Filters & pay', Icon: Sliders },
  { id: 'watchlist', label: 'Companies', Icon: Building2 },
  { id: 'sources', label: 'Sources', Icon: Globe },
  { id: 'schedule', label: 'Schedule & email', Icon: Clock },
  { id: 'income', label: 'Online income', Icon: Coins },
  { id: 'custom', label: 'Custom jobs', Icon: ClipboardList },
  { id: 'dryrun', label: 'Test run & preview', Icon: Sparkles },
  { id: 'health', label: 'Logs & health', Icon: Activity },
];

const PROFILE_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

interface RunResponse {
  summary: RunSummary;
}

interface JobsResponse {
  summary: RunSummary | null;
  jobs: ScoredJob[];
}

interface Banner {
  kind: 'error' | 'success';
  message: string;
}

export const App: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('specs');
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [latestSummary, setLatestSummary] = useState<RunSummary | null>(null);
  const [scoredJobs, setScoredJobs] = useState<ScoredJob[]>([]);
  const [banner, setBanner] = useState<Banner | null>(null);

  const flashSaved = () => {
    setSaveSuccess(true);
    window.setTimeout(() => setSaveSuccess(false), 2500);
  };

  const loadProfiles = useCallback(async () => {
    const data = await apiFetch<{ profiles: string[] }>('/api/profiles');
    setProfiles(data.profiles);
  }, []);

  const loadResults = useCallback(async () => {
    const data = await apiFetch<JobsResponse>('/api/jobs?limit=200');
    setScoredJobs(data.jobs);
    if (data.summary) setLatestSummary(data.summary);
  }, []);

  const loadConfig = useCallback(async () => {
    setLoadError(null);
    try {
      setConfig(await apiFetch<AppConfig>('/api/config'));
      await Promise.all([loadProfiles(), loadResults()]);
    } catch (e) {
      setLoadError(errorMessage(e));
    }
  }, [loadProfiles, loadResults]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const handleSaveConfig = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
      const data = await postJson<{ config: AppConfig }>('/api/config', config);
      setConfig(data.config);
      setBanner(null);
      flashSaved();
    } catch (e) {
      setBanner({ kind: 'error', message: `Settings were not saved: ${errorMessage(e)}` });
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadProfile = async (profileName: string) => {
    if (!profileName) return;
    if (!window.confirm(`Replace the active settings with the “${profileName}” profile? Unsaved changes will be lost.`)) return;
    try {
      const data = await postJson<{ config: AppConfig }>('/api/profiles/load', { profile_name: profileName });
      setConfig(data.config);
      setSelectedProfile(profileName);
      setBanner({ kind: 'success', message: `Profile “${profileName}” is now active.` });
    } catch (e) {
      setBanner({ kind: 'error', message: `Could not load the profile: ${errorMessage(e)}` });
    }
  };

  const handleSaveAsProfile = async () => {
    const name = window.prompt('Save the current settings as a profile. Name (letters, digits, - and _):')?.trim();
    if (!name) return;
    if (!PROFILE_NAME.test(name)) {
      setBanner({ kind: 'error', message: 'Profile names may contain letters, digits, “-” and “_” only.' });
      return;
    }
    try {
      await postJson('/api/profiles/save', { profile_name: name });
      await loadProfiles();
      setSelectedProfile(name);
      setBanner({ kind: 'success', message: `Saved profile “${name}”.` });
    } catch (e) {
      setBanner({ kind: 'error', message: `Could not save the profile: ${errorMessage(e)}` });
    }
  };

  const handleTriggerRun = async (forceAll = true) => {
    setIsRunning(true);
    try {
      const data = await postJson<RunResponse>('/api/run', { dry_run: true, force_all: forceAll });
      setLatestSummary(data.summary);
      await loadResults();
      setActiveTab('dryrun');
      setBanner(null);
    } catch (e) {
      setBanner({ kind: 'error', message: `The test run failed: ${errorMessage(e)}` });
    } finally {
      setIsRunning(false);
    }
  };

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-300 p-6">
        {loadError ? (
          <div className="max-w-md space-y-4 text-center">
            <Notice kind="error" message={loadError} />
            <button type="button" onClick={() => void loadConfig()}
              className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm px-4 py-2 rounded-lg inline-flex items-center gap-2">
              <RefreshCw className="w-4 h-4" aria-hidden="true" /> Try again
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3" role="status">
            <RefreshCw className="w-5 h-5 animate-spin text-blue-500" aria-hidden="true" />
            <span>Loading settings…</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="sticky top-0 z-30 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/80 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white">
            <Compass className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-extrabold text-base tracking-tight text-white">JobsAlert</h1>
            <div className="text-xs text-slate-400">Job and online income alerts</div>
          </div>
        </div>

        <div className="flex items-center flex-wrap gap-2.5">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs">
            <FolderOpen className="w-3.5 h-3.5 text-blue-400" aria-hidden="true" />
            <label htmlFor="profile-select" className="sr-only">Profile</label>
            <select id="profile-select" value={selectedProfile} onChange={(e) => void handleLoadProfile(e.target.value)}
              className="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer">
              <option value="" className="bg-slate-900">Active settings</option>
              {profiles.map((p) => (
                <option key={p} value={p} className="bg-slate-900">Profile: {p}</option>
              ))}
            </select>
          </div>

          <button type="button" onClick={() => void handleSaveAsProfile()} aria-label="Save current settings as a profile" title="Save as profile"
            className="p-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg text-slate-300 transition">
            <Plus className="w-4 h-4" aria-hidden="true" />
          </button>

          <button type="button" onClick={() => void handleTriggerRun(true)} disabled={isRunning}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold text-xs px-3.5 py-2 rounded-lg flex items-center gap-1.5 transition">
            {isRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" aria-hidden="true" /> : <Play className="w-3.5 h-3.5 fill-white" aria-hidden="true" />}
            {isRunning ? 'Running…' : 'Test run'}
          </button>

          <button type="button" onClick={() => void handleSaveConfig()} disabled={isSaving}
            className={`text-xs font-bold px-4 py-2 rounded-lg flex items-center gap-1.5 transition ${
              saveSuccess ? 'bg-emerald-600 text-white' : 'bg-slate-800 hover:bg-slate-700 text-white border border-slate-700'
            }`}>
            {saveSuccess ? <Check className="w-3.5 h-3.5" aria-hidden="true" /> : <Save className="w-3.5 h-3.5" aria-hidden="true" />}
            {saveSuccess ? 'Saved' : isSaving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </header>

      <nav className="bg-slate-950 border-b border-slate-800 px-6 overflow-x-auto" aria-label="Sections">
        <div className="flex space-x-1 py-2 text-xs font-semibold whitespace-nowrap" role="tablist">
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} type="button" role="tab" aria-selected={activeTab === id} onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
                activeTab === id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}>
              <Icon className="w-4 h-4" aria-hidden="true" /> {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {banner && <Notice kind={banner.kind} message={banner.message} onClose={() => setBanner(null)} />}
        {activeTab === 'specs' && <JobSpecsTab config={config} onChange={setConfig} />}
        {activeTab === 'roles' && <RoleMatrixTab config={config} onChange={setConfig} />}
        {activeTab === 'filters' && <FiltersTab config={config} onChange={setConfig} />}
        {activeTab === 'watchlist' && <WatchlistTab config={config} onChange={setConfig} />}
        {activeTab === 'sources' && <SourcesTab config={config} onChange={setConfig} />}
        {activeTab === 'schedule' && <ScheduleTab config={config} onChange={setConfig} />}
        {activeTab === 'income' && <IncomeTab config={config} onChange={setConfig} />}
        {activeTab === 'custom' && <CustomJobsTab />}
        {activeTab === 'dryrun' && (
          <DryRunTab
            onTriggerRun={handleTriggerRun}
            isRunning={isRunning}
            latestSummary={latestSummary}
            scoredJobs={scoredJobs}
            instantThreshold={config.schedule.instant_alert_threshold}
          />
        )}
        {activeTab === 'health' && <LogsHealthTab latestSummary={latestSummary} />}
      </main>

      <footer className="border-t border-slate-800/80 px-6 py-4 text-center text-xs text-slate-500 bg-slate-950">
        JobsAlert runs on a schedule with GitHub Actions and emails you through your chosen provider.
      </footer>
    </div>
  );
};
