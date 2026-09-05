import React from 'react';
import { AppConfig } from '../types';
import { Globe, Layers, Check, X, Rss, Terminal, Cpu } from 'lucide-react';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const SourcesTab: React.FC<Props> = ({ config, onChange }) => {
  const updateGreenhouseCompanies = (val: string) => {
    const slugs = val.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    onChange({
      ...config,
      sources: {
        ...config.sources,
        greenhouse: { ...config.sources.greenhouse, companies: slugs },
      },
    });
  };

  const updateLeverCompanies = (val: string) => {
    const slugs = val.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    onChange({
      ...config,
      sources: {
        ...config.sources,
        lever: { ...config.sources.lever, companies: slugs },
      },
    });
  };

  const updateAshbyCompanies = (val: string) => {
    const slugs = val.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    onChange({
      ...config,
      sources: {
        ...config.sources,
        ashby: { ...config.sources.ashby, companies: slugs },
      },
    });
  };

  return (
    <div className="space-y-8">
      {/* Direct ATS Connectors */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Layers className="w-5 h-5 text-emerald-400" />
          <h2 className="text-lg font-bold text-white">Direct ATS Endpoints (100% Free & Verified)</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Query official public ATS boards directly. These jobs have zero recruiter middleman markup and include direct application URLs.
        </p>

        <div className="space-y-6">
          {/* Greenhouse */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                <span className="font-bold text-white">Greenhouse Boards API</span>
                <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                  boards-api.greenhouse.io
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.sources.greenhouse.enabled}
                  onChange={(e) =>
                    onChange({
                      ...config,
                      sources: {
                        ...config.sources,
                        greenhouse: { ...config.sources.greenhouse, enabled: e.target.checked },
                      },
                    })
                  }
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
              </label>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Target Company Slugs (comma separated)
              </label>
              <input
                type="text"
                value={(config.sources.greenhouse.companies || []).join(', ')}
                onChange={(e) => updateGreenhouseCompanies(e.target.value)}
                placeholder="cloudflare, datadog, figma, elastic"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>
          </div>

          {/* Lever */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-400"></span>
                <span className="font-bold text-white">Lever Postings API</span>
                <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                  api.lever.co/v0
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.sources.lever.enabled}
                  onChange={(e) =>
                    onChange({
                      ...config,
                      sources: {
                        ...config.sources,
                        lever: { ...config.sources.lever, enabled: e.target.checked },
                      },
                    })
                  }
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Target Company Slugs (comma separated)
              </label>
              <input
                type="text"
                value={(config.sources.lever.companies || []).join(', ')}
                onChange={(e) => updateLeverCompanies(e.target.value)}
                placeholder="netflix, atlassian, palantir"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          {/* Ashby */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400"></span>
                <span className="font-bold text-white">Ashby Posting API</span>
                <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                  api.ashbyhq.com
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.sources.ashby.enabled}
                  onChange={(e) =>
                    onChange({
                      ...config,
                      sources: {
                        ...config.sources,
                        ashby: { ...config.sources.ashby, enabled: e.target.checked },
                      },
                    })
                  }
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
              </label>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Target Company Slugs (comma separated)
              </label>
              <input
                type="text"
                value={(config.sources.ashby.companies || []).join(', ')}
                onChange={(e) => updateAshbyCompanies(e.target.value)}
                placeholder="linear, ramp, retool, openai"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500 font-mono"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Aggregators & Feeds */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Globe className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white">Aggregators, Remote Boards & Startup Feeds</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          High-volume verified remote feeds with transparent compensation and tech tags.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Remotive */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="font-bold text-white">Remotive API</div>
              <div className="text-xs text-slate-400">Curated global tech remote roles</div>
            </div>
            <input
              type="checkbox"
              checked={config.sources.remotive.enabled}
              onChange={(e) =>
                onChange({
                  ...config,
                  sources: { ...config.sources, remotive: { ...config.sources.remotive, enabled: e.target.checked } },
                })
              }
              className="w-5 h-5 accent-cyan-500 rounded cursor-pointer"
            />
          </div>

          {/* RemoteOK */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="font-bold text-white">RemoteOK API</div>
              <div className="text-xs text-slate-400">Software engineering & high-comp tags</div>
            </div>
            <input
              type="checkbox"
              checked={config.sources.remoteok.enabled}
              onChange={(e) =>
                onChange({
                  ...config,
                  sources: { ...config.sources, remoteok: { ...config.sources.remoteok, enabled: e.target.checked } },
                })
              }
              className="w-5 h-5 accent-cyan-500 rounded cursor-pointer"
            />
          </div>

          {/* Arbeitnow */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="font-bold text-white">Arbeitnow API</div>
              <div className="text-xs text-slate-400">European tech jobs & global remote</div>
            </div>
            <input
              type="checkbox"
              checked={config.sources.arbeitnow.enabled}
              onChange={(e) =>
                onChange({
                  ...config,
                  sources: { ...config.sources, arbeitnow: { ...config.sources.arbeitnow, enabled: e.target.checked } },
                })
              }
              className="w-5 h-5 accent-cyan-500 rounded cursor-pointer"
            />
          </div>

          {/* Jobicy */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="font-bold text-white">Jobicy API</div>
              <div className="text-xs text-slate-400">Remote tech listings with level tags</div>
            </div>
            <input
              type="checkbox"
              checked={config.sources.jobicy.enabled}
              onChange={(e) =>
                onChange({
                  ...config,
                  sources: { ...config.sources, jobicy: { ...config.sources.jobicy, enabled: e.target.checked } },
                })
              }
              className="w-5 h-5 accent-cyan-500 rounded cursor-pointer"
            />
          </div>

          {/* Hacker News */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between md:col-span-2">
            <div>
              <div className="font-bold text-orange-400 flex items-center gap-1.5">
                <Terminal className="w-4 h-4" /> Hacker News "Who is Hiring?" (Algolia API)
              </div>
              <div className="text-xs text-slate-400">
                Parses the monthly Y Combinator & high-growth startup hiring thread. Unlocks unlisted early-stage roles.
              </div>
            </div>
            <input
              type="checkbox"
              checked={config.sources.hackernews.enabled}
              onChange={(e) =>
                onChange({
                  ...config,
                  sources: { ...config.sources, hackernews: { ...config.sources.hackernews, enabled: e.target.checked } },
                })
              }
              className="w-5 h-5 accent-orange-500 rounded cursor-pointer"
            />
          </div>

          {/* Twitter / X */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 md:col-span-2 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-bold text-sky-400 flex items-center gap-1.5">
                  <Globe className="w-4 h-4" /> Twitter / X Job Scout
                </div>
                <div className="text-xs text-slate-400">
                  Scouts hiring tweets, recruitment hashtags, and target company accounts with automated link resolution.
                </div>
              </div>
              <input
                type="checkbox"
                checked={config.sources.twitter?.enabled ?? true}
                onChange={(e) =>
                  onChange({
                    ...config,
                    sources: {
                      ...config.sources,
                      twitter: {
                        ...(config.sources.twitter || { search_queries: [], monitored_accounts: [], max_tweets: 30 }),
                        enabled: e.target.checked,
                      },
                    },
                  })
                }
                className="w-5 h-5 accent-sky-500 rounded cursor-pointer"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Search Queries / Hashtags (comma separated)
                </label>
                <input
                  type="text"
                  value={(config.sources.twitter?.search_queries || []).join(', ')}
                  onChange={(e) => {
                    const queries = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                    onChange({
                      ...config,
                      sources: {
                        ...config.sources,
                        twitter: {
                          ...(config.sources.twitter || { enabled: true, monitored_accounts: [], max_tweets: 30 }),
                          search_queries: queries,
                        },
                      },
                    });
                  }}
                  placeholder="#hiring #remotejobs, remote hiring"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">
                  Monitored Handles (comma separated)
                </label>
                <input
                  type="text"
                  value={(config.sources.twitter?.monitored_accounts || []).join(', ')}
                  onChange={(e) => {
                    const accounts = e.target.value.split(',').map((s) => s.trim().replace('@', '')).filter(Boolean);
                    onChange({
                      ...config,
                      sources: {
                        ...config.sources,
                        twitter: {
                          ...(config.sources.twitter || { enabled: true, search_queries: [], max_tweets: 30 }),
                          monitored_accounts: accounts,
                        },
                      },
                    });
                  }}
                  placeholder="TechJobsAfrica, RemoteJobs, JobbermanOnline"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

