import React, { useState } from 'react';
import { AppConfig } from '../types';
import { Sliders, DollarSign, MapPin, Award, Scale, Plus, X } from 'lucide-react';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const FiltersTab: React.FC<Props> = ({ config, onChange }) => {
  const [newLocation, setNewLocation] = useState('');

  const addLocation = () => {
    if (!newLocation.trim()) return;
    onChange({
      ...config,
      profile: {
        ...config.profile,
        preferred_locations: [...config.profile.preferred_locations, newLocation.trim()],
      },
    });
    setNewLocation('');
  };

  const removeLocation = (idx: number) => {
    onChange({
      ...config,
      profile: {
        ...config.profile,
        preferred_locations: config.profile.preferred_locations.filter((_, i) => i !== idx),
      },
    });
  };

  const totalWeight =
    config.scoring_weights.title_and_stack +
    config.scoring_weights.location_remote +
    config.scoring_weights.compensation +
    config.scoring_weights.company_priority +
    config.scoring_weights.recency_urgency;

  return (
    <div className="space-y-8">
      {/* Candidate Seniority & Salary Floor */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Candidate Profile Details */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Award className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-white">Seniority & Experience</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Candidate Name / Label
              </label>
              <input
                type="text"
                value={config.profile.candidate_name}
                onChange={(e) =>
                  onChange({
                    ...config,
                    profile: { ...config.profile, candidate_name: e.target.value },
                  })
                }
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Relevant Experience: <span className="text-indigo-300 font-bold">{config.profile.experience_years} Years</span>
                </label>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                step={1}
                value={config.profile.experience_years}
                onChange={(e) =>
                  onChange({
                    ...config,
                    profile: { ...config.profile, experience_years: parseInt(e.target.value) },
                  })
                }
                className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                Candidates with 5+ years automatically exclude entry/junior and internship postings.
              </p>
            </div>
          </div>
        </div>

        {/* Salary Floor */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-bold text-white">Compensation Transparency & Floor</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Minimum Acceptable Base Salary (USD / year)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2 text-slate-400 font-semibold">$</span>
                <input
                  type="number"
                  step={5000}
                  value={config.profile.salary_floor_usd}
                  onChange={(e) =>
                    onChange({
                      ...config,
                      profile: { ...config.profile, salary_floor_usd: parseFloat(e.target.value) || 0 },
                    })
                  }
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-4 py-2 text-sm text-white font-mono focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-xs text-slate-400 space-y-1">
              <div className="text-amber-300 font-semibold">Compensation Scoring Rules:</div>
              <div>• <strong>Above floor:</strong> Full score + "Why You Match" bonus badge.</div>
              <div>• <strong>Unlisted salary:</strong> Neutral score (unpenalized).</div>
              <div>• <strong>Sub-floor postings:</strong> Significant score penalties applied.</div>
            </div>
          </div>
        </div>
      </div>

      {/* Preferred Locations & Geographies */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="w-5 h-5 text-emerald-400" />
          <h2 className="text-lg font-bold text-white">Preferred Locations & Remote Scope</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          The engine prioritizes "Worldwide Remote", validates country boundaries, and matches preferred local tech hubs.
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. Remote, Worldwide, United States, United Kingdom, Lagos, Nigeria"
            value={newLocation}
            onChange={(e) => setNewLocation(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addLocation()}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={addLocation}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add Location
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.profile.preferred_locations.map((loc, idx) => (
            <span
              key={idx}
              className="bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              📍 {loc}
              <button onClick={() => removeLocation(idx)} className="hover:text-red-400">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Granular Scoring Weights Sliders */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Relevance Scoring Weight Distribution</h2>
          </div>
          <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${totalWeight === 100 ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-amber-950 text-amber-300 border border-amber-800'}`}>
            Total: {totalWeight}%
          </span>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Fine-tune how much each evaluation vector influences the final 0–10 score.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
              <span>Title & Core Stack</span>
              <span className="text-blue-400">{config.scoring_weights.title_and_stack}%</span>
            </div>
            <input
              type="range"
              min={10}
              max={70}
              step={5}
              value={config.scoring_weights.title_and_stack}
              onChange={(e) =>
                onChange({
                  ...config,
                  scoring_weights: { ...config.scoring_weights, title_and_stack: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
              <span>Location & Remote Policy</span>
              <span className="text-blue-400">{config.scoring_weights.location_remote}%</span>
            </div>
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              value={config.scoring_weights.location_remote}
              onChange={(e) =>
                onChange({
                  ...config,
                  scoring_weights: { ...config.scoring_weights, location_remote: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
              <span>Compensation Fit</span>
              <span className="text-blue-400">{config.scoring_weights.compensation}%</span>
            </div>
            <input
              type="range"
              min={5}
              max={40}
              step={5}
              value={config.scoring_weights.compensation}
              onChange={(e) =>
                onChange({
                  ...config,
                  scoring_weights: { ...config.scoring_weights, compensation: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
              <span>Company Priority Watchlist</span>
              <span className="text-blue-400">{config.scoring_weights.company_priority}%</span>
            </div>
            <input
              type="range"
              min={5}
              max={40}
              step={5}
              value={config.scoring_weights.company_priority}
              onChange={(e) =>
                onChange({
                  ...config,
                  scoring_weights: { ...config.scoring_weights, company_priority: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
              <span>Recency & Urgency (24h advantage)</span>
              <span className="text-blue-400">{config.scoring_weights.recency_urgency}%</span>
            </div>
            <input
              type="range"
              min={5}
              max={30}
              step={5}
              value={config.scoring_weights.recency_urgency}
              onChange={(e) =>
                onChange({
                  ...config,
                  scoring_weights: { ...config.scoring_weights, recency_urgency: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
