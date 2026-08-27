import React, { useState, useEffect } from 'react';
import { AppConfig, ScoredJob, RunSummary } from './types';
import { RoleMatrixTab } from './components/RoleMatrixTab';
import { FiltersTab } from './components/FiltersTab';
import { WatchlistTab } from './components/WatchlistTab';
import { SourcesTab } from './components/SourcesTab';
import { ScheduleTab } from './components/ScheduleTab';
import { DryRunTab } from './components/DryRunTab';
import { LogsHealthTab } from './components/LogsHealthTab';
import {
  Compass,
  Sliders,
  Building2,
  Globe,
  Clock,
  Sparkles,
  Activity,
  Save,
  Play,
  Check,
  FolderOpen,
  Plus,
  RefreshCw,
} from 'lucide-react';

export const App: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [activeTab, setActiveTab] = useState<
    'roles' | 'filters' | 'watchlist' | 'sources' | 'schedule' | 'dryrun' | 'health'
  >('roles');
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [latestSummary, setLatestSummary] = useState<RunSummary | null>(null);
  const [scoredJobs, setScoredJobs] = useState<ScoredJob[]>([]);

  // Fetch initial config and profiles
  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      setConfig(data);

      const pRes = await fetch('/api/profiles');
      const pData = await pRes.json();
      setProfiles(pData.profiles || []);
    } catch (e) {
      console.error('Error loading config:', e);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleSaveConfig = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (e) {
      console.error('Save failed:', e);
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadProfile = async (profileName: string) => {
    if (!profileName) return;
    try {
      const res = await fetch('/api/profiles/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_name: profileName }),
      });
      const data = await res.json();
      if (data.config) {
        setConfig(data.config);
        setSelectedProfile(profileName);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (e) {
      console.error('Profile load failed:', e);
    }
  };

  const handleSaveAsProfile = async () => {
    const name = window.prompt('Enter new profile preset name (e.g. remote_contractor):');
    if (!name) return;
    try {
      await fetch('/api/profiles/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_name: name }),
      });
      const pRes = await fetch('/api/profiles');
      const pData = await pRes.json();
      setProfiles(pData.profiles || []);
      setSelectedProfile(name);
    } catch (e) {
      console.error('Save profile failed:', e);
    }
  };

  const handleTriggerRun = async (dryRun: boolean = true, forceAll: boolean = true) => {
    setIsRunning(true);
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: dryRun, force_all: forceAll }),
      });
      const data = await res.json();
      if (data.summary) {
        setLatestSummary(data.summary);
      }
      // Fetch the scored jobs
      const jobsRes = await fetch('/api/jobs?limit=100');
      const jobsData = await jobsRes.json();
      setScoredJobs(jobsData.jobs || []);
      setActiveTab('dryrun');
    } catch (e) {
      console.error('Run failed:', e);
    } finally {
      setIsRunning(false);
    }
  };

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
          <span>Connecting to JobsAlert Intelligence API...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <div className="font-extrabold text-base tracking-tight text-white flex items-center gap-2">
              JobsAlert
              <span className="text-[10px] bg-blue-950 text-blue-400 font-bold px-2 py-0.5 rounded-full border border-blue-800">
                PRO CONTROL PANEL
              </span>
            </div>
            <div className="text-xs text-slate-400">Autonomous Career Intelligence & Opportunity Scout</div>
          </div>
        </div>

        {/* Profile Preset Switcher & Action Buttons */}
        <div className="flex items-center flex-wrap gap-2.5">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs">
            <FolderOpen className="w-3.5 h-3.5 text-blue-400" />
            <select
              value={selectedProfile}
              onChange={(e) => handleLoadProfile(e.target.value)}
              className="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-slate-900">Current Active Config</option>
              {profiles.map((p) => (
                <option key={p} value={p} className="bg-slate-900">
                  Profile: {p}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleSaveAsProfile}
            title="Save as new preset profile"
            className="p-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg text-slate-300 transition"
          >
            <Plus className="w-4 h-4" />
          </button>

          <button
            onClick={() => handleTriggerRun(true, true)}
            disabled={isRunning}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold text-xs px-3.5 py-2 rounded-lg flex items-center gap-1.5 shadow-md transition"
          >
            {isRunning ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-white" /> Test Run & Preview
              </>
            )}
          </button>

          <button
            onClick={handleSaveConfig}
            disabled={isSaving}
            className={`text-xs font-bold px-4 py-2 rounded-lg flex items-center gap-1.5 transition ${
              saveSuccess
                ? 'bg-emerald-600 text-white'
                : 'bg-slate-800 hover:bg-slate-700 text-white border border-slate-700'
            }`}
          >
            {saveSuccess ? (
              <>
                <Check className="w-3.5 h-3.5" /> Saved!
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" /> Save Changes
              </>
            )}
          </button>
        </div>
      </header>

      {/* Navigation Sub-Header */}
      <div className="bg-slate-950 border-b border-slate-800 px-6 overflow-x-auto">
        <nav className="flex space-x-1 py-2 text-xs font-semibold whitespace-nowrap">
          <button
            onClick={() => setActiveTab('roles')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'roles'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Compass className="w-4 h-4" /> Role & Skill Matrices
          </button>

          <button
            onClick={() => setActiveTab('filters')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'filters'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Sliders className="w-4 h-4" /> Filters & Comp Rules
          </button>

          <button
            onClick={() => setActiveTab('watchlist')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'watchlist'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Building2 className="w-4 h-4" /> Company Watchlist & Blacklist
          </button>

          <button
            onClick={() => setActiveTab('sources')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'sources'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Globe className="w-4 h-4" /> Sources & ATS Endpoints
          </button>

          <button
            onClick={() => setActiveTab('schedule')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'schedule'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Clock className="w-4 h-4" /> Schedule & Email Delivery
          </button>

          <button
            onClick={() => setActiveTab('dryrun')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'dryrun'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Sparkles className="w-4 h-4 text-amber-400" /> Dry-Run & Email Preview
          </button>

          <button
            onClick={() => setActiveTab('health')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition ${
              activeTab === 'health'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Activity className="w-4 h-4 text-emerald-400" /> Logs & Source Health
          </button>
        </nav>
      </div>

      {/* Main Tab Content View */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {activeTab === 'roles' && <RoleMatrixTab config={config} onChange={setConfig} />}
        {activeTab === 'filters' && <FiltersTab config={config} onChange={setConfig} />}
        {activeTab === 'watchlist' && <WatchlistTab config={config} onChange={setConfig} />}
        {activeTab === 'sources' && <SourcesTab config={config} onChange={setConfig} />}
        {activeTab === 'schedule' && <ScheduleTab config={config} onChange={setConfig} />}
        {activeTab === 'dryrun' && (
          <DryRunTab
            onTriggerRun={handleTriggerRun}
            isRunning={isRunning}
            latestSummary={latestSummary}
            scoredJobs={scoredJobs}
          />
        )}
        {activeTab === 'health' && (
          <LogsHealthTab latestSummary={latestSummary} onRefresh={fetchConfig} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 px-6 py-4 text-center text-xs text-slate-500 bg-slate-950">
        JobsAlert Autonomous Career Intelligence • Zero-Cost Cloud Architecture (GitHub Actions, Cloudflare Pages, Resend)
      </footer>
    </div>
  );
};
