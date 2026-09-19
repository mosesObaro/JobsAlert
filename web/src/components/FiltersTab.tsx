import React from 'react';
import { Award, DollarSign, MapPin, Scale } from 'lucide-react';
import { AppConfig, ScoringWeights } from '../types';
import { Notice, Section, TagInput, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

const WEIGHTS: { key: keyof ScoringWeights; label: string; min: number; max: number }[] = [
  { key: 'title_and_stack', label: 'Title & core skills', min: 10, max: 70 },
  { key: 'location_remote', label: 'Location & remote eligibility', min: 5, max: 50 },
  { key: 'compensation', label: 'Compensation fit', min: 5, max: 40 },
  { key: 'company_priority', label: 'Company watchlist', min: 5, max: 40 },
  { key: 'recency_urgency', label: 'Recency (first 24h)', min: 5, max: 30 },
];

export const FiltersTab: React.FC<Props> = ({ config, onChange }) => {
  const setProfile = (patch: Partial<AppConfig['profile']>) => onChange({ ...config, profile: { ...config.profile, ...patch } });
  const weights = config.scoring_weights;
  const totalWeight = WEIGHTS.reduce((sum, w) => sum + weights[w.key], 0);

  return (
    <div className="space-y-6">
      {config.job_specs.length > 0 && (
        <Notice
          kind="info"
          message="Experience, salary floor and locations here are defaults; a job spec's own values take priority. Scoring weights apply to every spec that doesn't set its own."
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Section icon={<Award className="w-5 h-5 text-indigo-400" aria-hidden="true" />} title="Candidate & experience">
          <div className="space-y-4">
            <div>
              <label htmlFor="candidate-name" className={labelClass}>Candidate name / label</label>
              <input
                id="candidate-name"
                type="text"
                value={config.profile.candidate_name}
                onChange={(e) => setProfile({ candidate_name: e.target.value })}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="experience-years" className={labelClass}>
                Relevant experience: <span className="text-indigo-300">{config.profile.experience_years} years</span>
              </label>
              <input
                id="experience-years"
                type="range"
                min={0}
                max={20}
                step={1}
                value={config.profile.experience_years}
                onChange={(e) => setProfile({ experience_years: parseInt(e.target.value, 10) })}
                className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                With 5+ years (or a senior spec), junior, intern and graduate titles are excluded.
              </p>
            </div>
          </div>
        </Section>

        <Section icon={<DollarSign className="w-5 h-5 text-amber-400" aria-hidden="true" />} title="Salary floor">
          <div className="space-y-3">
            <div>
              <label htmlFor="salary-floor" className={labelClass}>Minimum base salary (USD per year)</label>
              <input
                id="salary-floor"
                type="number"
                min={0}
                step={1000}
                value={config.profile.salary_floor_usd}
                onChange={(e) => setProfile({ salary_floor_usd: parseFloat(e.target.value) || 0 })}
                className={`${inputClass} font-mono`}
              />
            </div>
            <p className="text-xs text-slate-400">
              Salaries in other currencies and periods (e.g. ₦ per month) are converted to annual USD using the rates in
              <code className="mx-1 text-slate-300">fx_rates_to_usd</code>. Unlisted pay scores neutrally.
            </p>
          </div>
        </Section>
      </div>

      <Section
        icon={<MapPin className="w-5 h-5 text-emerald-400" aria-hidden="true" />}
        title="Preferred locations"
        description="Include your country (e.g. Nigeria) so remote roles restricted to other countries are recognised and scored down."
      >
        <TagInput
          id="preferred-locations"
          label="Preferred locations"
          tone="emerald"
          values={config.profile.preferred_locations}
          onChange={(preferred_locations) => setProfile({ preferred_locations })}
          placeholder="e.g. Remote, Worldwide, Nigeria, Africa"
          addLabel="Add location"
        />
      </Section>

      <Section
        icon={<Scale className="w-5 h-5 text-blue-400" aria-hidden="true" />}
        title="Scoring weights"
        description="How much each factor contributes to the 0–10 score."
        actions={
          <span
            className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
              totalWeight === 100 ? 'bg-emerald-950 text-emerald-300 border-emerald-800' : 'bg-amber-950 text-amber-300 border-amber-800'
            }`}
          >
            Total: {totalWeight}%
          </span>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {WEIGHTS.map((w) => (
            <div key={w.key}>
              <label htmlFor={`weight-${w.key}`} className="flex justify-between text-xs font-semibold text-slate-300 mb-1">
                <span>{w.label}</span>
                <span className="text-blue-400">{weights[w.key]}%</span>
              </label>
              <input
                id={`weight-${w.key}`}
                type="range"
                min={w.min}
                max={w.max}
                step={5}
                value={weights[w.key]}
                onChange={(e) =>
                  onChange({ ...config, scoring_weights: { ...weights, [w.key]: parseFloat(e.target.value) } })
                }
                className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
};
