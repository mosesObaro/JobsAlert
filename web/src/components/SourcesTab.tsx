import React, { useState } from 'react';
import { Globe, Layers, Plus, Rss, Terminal, Trash2 } from 'lucide-react';
import { AppConfig, SourceSubConfig } from '../types';
import { safeUrl } from '../format';
import { Section, TagInput, Toggle, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

type AtsKey = 'greenhouse' | 'lever' | 'ashby';
type BoardKey = 'remotive' | 'remoteok' | 'arbeitnow' | 'jobicy';

const ATS: { key: AtsKey; name: string; host: string; example: string }[] = [
  { key: 'greenhouse', name: 'Greenhouse', host: 'boards-api.greenhouse.io', example: 'cloudflare, datadog' },
  { key: 'lever', name: 'Lever', host: 'api.lever.co', example: 'netflix, palantir' },
  { key: 'ashby', name: 'Ashby', host: 'api.ashbyhq.com', example: 'linear, ramp' },
];

const BOARDS: { key: BoardKey; name: string; description: string }[] = [
  { key: 'remotive', name: 'Remotive', description: 'Curated remote roles by category' },
  { key: 'remoteok', name: 'RemoteOK', description: 'Remote roles across tech and operations' },
  { key: 'arbeitnow', name: 'Arbeitnow', description: 'European and global remote roles' },
  { key: 'jobicy', name: 'Jobicy', description: 'Remote roles with salary and level data' },
];

export const SourcesTab: React.FC<Props> = ({ config, onChange }) => {
  const [feedName, setFeedName] = useState('');
  const [feedUrl, setFeedUrl] = useState('');
  const sources = config.sources;

  const setSource = <K extends keyof AppConfig['sources']>(key: K, value: AppConfig['sources'][K]) =>
    onChange({ ...config, sources: { ...sources, [key]: value } });
  const patchSub = (key: AtsKey | BoardKey | 'hackernews', patch: Partial<SourceSubConfig>) =>
    setSource(key, { ...sources[key], ...patch });

  const addFeed = () => {
    const url = safeUrl(feedUrl.trim());
    if (!feedName.trim() || !url) return;
    setSource('rss_feeds', [...sources.rss_feeds, { name: feedName.trim(), url, enabled: true }]);
    setFeedName('');
    setFeedUrl('');
  };

  return (
    <div className="space-y-6">
      <Section
        icon={<Layers className="w-5 h-5 text-emerald-400" aria-hidden="true" />}
        title="Company job boards (ATS)"
        description="Public job boards of specific companies. Use each company's board slug, e.g. boards.greenhouse.io/<slug>. A slug that doesn't exist shows up as degraded in Logs & Health."
      >
        {ATS.map((ats) => (
          <div key={ats.key} className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Toggle
                id={`source-${ats.key}`}
                label={`${ats.name} (${ats.host})`}
                checked={sources[ats.key].enabled}
                onChange={(enabled) => patchSub(ats.key, { enabled })}
              />
            </div>
            <div>
              <label htmlFor={`source-${ats.key}-companies`} className={labelClass}>Company slugs (comma separated)</label>
              <input
                id={`source-${ats.key}-companies`}
                type="text"
                value={sources[ats.key].companies.join(', ')}
                onChange={(e) =>
                  patchSub(ats.key, { companies: e.target.value.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean) })
                }
                placeholder={ats.example}
                className={`${inputClass} font-mono text-xs`}
              />
            </div>
          </div>
        ))}
      </Section>

      <Section
        icon={<Globe className="w-5 h-5 text-cyan-400" aria-hidden="true" />}
        title="Remote job boards & community sources"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {BOARDS.map((board) => (
            <div key={board.key} className="bg-slate-950 border border-slate-800 rounded-xl p-4">
              <Toggle
                id={`source-${board.key}`}
                label={board.name}
                description={board.description}
                checked={sources[board.key].enabled}
                onChange={(enabled) => patchSub(board.key, { enabled })}
              />
            </div>
          ))}

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 md:col-span-2 space-y-3">
            <div className="flex items-center gap-2 text-orange-400 font-bold text-sm">
              <Terminal className="w-4 h-4" aria-hidden="true" /> Hacker News “Who is hiring?”
            </div>
            <Toggle
              id="source-hackernews"
              label="Read the monthly hiring threads"
              description="Top-level comments from the latest threads posted by the whoishiring account."
              checked={sources.hackernews.enabled}
              onChange={(enabled) => patchSub('hackernews', { enabled })}
            />
            <div className="max-w-xs">
              <label htmlFor="source-hackernews-threads" className={labelClass}>Monthly threads to read</label>
              <input
                id="source-hackernews-threads"
                type="number"
                min={1}
                max={3}
                value={sources.hackernews.limit_stories}
                onChange={(e) => patchSub('hackernews', { limit_stories: Math.max(1, parseInt(e.target.value, 10) || 1) })}
                className={inputClass}
              />
            </div>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 md:col-span-2 space-y-3">
            <Toggle
              id="source-twitter"
              label="Twitter / X hiring posts"
              description="Uses public mirrors that are often unavailable; empty results show as degraded in Logs & Health."
              checked={sources.twitter.enabled}
              onChange={(enabled) => setSource('twitter', { ...sources.twitter, enabled })}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <TagInput
                id="twitter-queries"
                label="Search queries / hashtags"
                values={sources.twitter.search_queries}
                onChange={(search_queries) => setSource('twitter', { ...sources.twitter, search_queries })}
                placeholder="#hiring #remotejobs"
              />
              <TagInput
                id="twitter-accounts"
                label="Accounts to monitor"
                values={sources.twitter.monitored_accounts}
                onChange={(accounts) =>
                  setSource('twitter', { ...sources.twitter, monitored_accounts: accounts.map((a) => a.replace(/^@/, '')) })
                }
                placeholder="JobbermanOnline"
              />
            </div>
          </div>
        </div>
      </Section>

      <Section
        icon={<Rss className="w-5 h-5 text-amber-400" aria-hidden="true" />}
        title="RSS / Atom feeds"
        description="Careers feeds from companies or job boards (RSS 2.0 or Atom)."
      >
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[160px]">
            <label htmlFor="feed-name" className={labelClass}>Name</label>
            <input id="feed-name" type="text" value={feedName} onChange={(e) => setFeedName(e.target.value)} placeholder="e.g. Acme Careers" className={inputClass} />
          </div>
          <div className="flex-[2] min-w-[220px]">
            <label htmlFor="feed-url" className={labelClass}>Feed URL</label>
            <input id="feed-url" type="url" value={feedUrl} onChange={(e) => setFeedUrl(e.target.value)} placeholder="https://…/jobs.rss" className={inputClass} />
          </div>
          <button type="button" onClick={addFeed}
            className="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1">
            <Plus className="w-4 h-4" aria-hidden="true" /> Add feed
          </button>
        </div>
        {sources.rss_feeds.length > 0 && (
          <ul className="space-y-2" aria-label="RSS feeds">
            {sources.rss_feeds.map((feed, index) => (
              <li key={`${feed.url}-${index}`} className="bg-slate-950 border border-slate-800 rounded-lg p-3 flex items-center justify-between gap-3">
                <Toggle
                  id={`feed-${index}`}
                  label={feed.name}
                  description={feed.url}
                  checked={feed.enabled}
                  onChange={(enabled) =>
                    setSource('rss_feeds', sources.rss_feeds.map((f, i) => (i === index ? { ...f, enabled } : f)))
                  }
                />
                <button type="button" aria-label={`Remove feed ${feed.name}`} title={`Remove ${feed.name}`}
                  onClick={() => setSource('rss_feeds', sources.rss_feeds.filter((_, i) => i !== index))}
                  className="text-slate-500 hover:text-red-400 p-1 rounded">
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
};
