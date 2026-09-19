import React from 'react';
import { Copy, ListChecks, Plus, Trash2 } from 'lucide-react';
import { AppConfig, JobSpec } from '../types';
import { parseOptionalNumber } from '../format';
import { Notice, Section, TagInput, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

const emptySpec = (name: string): JobSpec => ({
  name,
  keywords: [],
  target_roles: [],
  seniority: null,
  experience_years: null,
  technologies: [],
  must_have_skills: [],
  nice_to_have_skills: [],
  employment_type: null,
  remote: null,
  preferred_locations: [],
  salary_floor_usd: null,
  excluded_terms: [],
  excluded_companies: [],
  scoring_weights: null,
});

const inherits = (list: string[], fallback: string[]) =>
  list.length === 0 && fallback.length > 0 ? `Empty: uses the defaults (${fallback.slice(0, 3).join(', ')}${fallback.length > 3 ? '…' : ''}).` : undefined;

export const JobSpecsTab: React.FC<Props> = ({ config, onChange }) => {
  const specs = config.job_specs;
  const setSpecs = (job_specs: JobSpec[]) => onChange({ ...config, job_specs });
  const update = (index: number, patch: Partial<JobSpec>) =>
    setSpecs(specs.map((spec, i) => (i === index ? { ...spec, ...patch } : spec)));

  const addSpec = () => setSpecs([...specs, emptySpec(`Job spec ${specs.length + 1}`)]);
  const duplicate = (index: number) => {
    const copy: JobSpec = { ...specs[index], name: `${specs[index].name} (copy)` };
    setSpecs([...specs.slice(0, index + 1), copy, ...specs.slice(index + 1)]);
  };
  const remove = (index: number) => {
    if (window.confirm(`Delete the job spec “${specs[index].name}”? Save to apply.`)) {
      setSpecs(specs.filter((_, i) => i !== index));
    }
  };

  return (
    <div className="space-y-6">
      <Notice
        kind="info"
        message="Every posting is scored against each job spec, and the digest groups matches by spec. Empty fields inherit the defaults from the Roles & Skills and Filters tabs; excluded terms and companies from those tabs always apply."
      />

      {specs.length === 0 && (
        <Notice kind="info" message="No job specs yet: postings are scored against your defaults as a single spec." />
      )}

      {specs.map((spec, index) => {
        const id = (field: string) => `spec-${index}-${field}`;
        return (
          <Section
            key={index}
            icon={<ListChecks className="w-5 h-5 text-blue-400" aria-hidden="true" />}
            title={spec.name || `Job spec ${index + 1}`}
            actions={
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => duplicate(index)}
                  className="text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-lg flex items-center gap-1"
                >
                  <Copy className="w-3.5 h-3.5" aria-hidden="true" /> Duplicate
                </button>
                <button
                  type="button"
                  onClick={() => remove(index)}
                  className="text-xs text-red-300 bg-red-950/60 hover:bg-red-900/80 border border-red-800 px-3 py-1.5 rounded-lg flex items-center gap-1"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden="true" /> Delete
                </button>
              </div>
            }
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label htmlFor={id('name')} className={labelClass}>Name (shown as a section in the digest)</label>
                <input id={id('name')} type="text" value={spec.name} onChange={(e) => update(index, { name: e.target.value })} className={inputClass} />
              </div>

              <TagInput id={id('roles')} label="Target roles" values={spec.target_roles}
                onChange={(target_roles) => update(index, { target_roles })} placeholder="e.g. HR Generalist"
                description={inherits([...spec.target_roles, ...spec.keywords], config.profile.target_roles)} />
              <TagInput id={id('keywords')} label="Title keywords" values={spec.keywords}
                onChange={(keywords) => update(index, { keywords })} placeholder="e.g. Recruiter, People Operations"
                description="Matched as whole words in titles, like target roles." />

              <TagInput id={id('must')} label="Must-have skills" tone="emerald" values={spec.must_have_skills}
                onChange={(must_have_skills) => update(index, { must_have_skills })} placeholder="e.g. Recruitment"
                description={inherits([...spec.must_have_skills, ...spec.technologies], config.filters.must_have_skills)} />
              <TagInput id={id('tech')} label="Technologies (also required)" tone="emerald" values={spec.technologies}
                onChange={(technologies) => update(index, { technologies })} placeholder="e.g. SQL, Swift" />

              <TagInput id={id('nice')} label="Nice-to-have skills" tone="amber" values={spec.nice_to_have_skills}
                onChange={(nice_to_have_skills) => update(index, { nice_to_have_skills })} placeholder="e.g. Workday"
                description={inherits(spec.nice_to_have_skills, config.filters.nice_to_have_skills)} />
              <TagInput id={id('locations')} label="Preferred locations" tone="emerald" values={spec.preferred_locations}
                onChange={(preferred_locations) => update(index, { preferred_locations })} placeholder="e.g. Nigeria, Worldwide"
                description={inherits(spec.preferred_locations, config.profile.preferred_locations)} />

              <div>
                <label htmlFor={id('seniority')} className={labelClass}>Seniority</label>
                <select id={id('seniority')} value={spec.seniority ?? ''} className={inputClass}
                  onChange={(e) => update(index, { seniority: e.target.value || null })}>
                  <option value="">Any (decided by experience)</option>
                  <option value="junior">Junior / entry level</option>
                  <option value="mid">Mid level</option>
                  <option value="senior">Senior</option>
                  <option value="lead">Lead / staff</option>
                </select>
              </div>
              <div>
                <label htmlFor={id('experience')} className={labelClass}>Experience (years)</label>
                <input id={id('experience')} type="number" min={0} max={40} className={inputClass}
                  value={spec.experience_years ?? ''} placeholder={`Default: ${config.profile.experience_years}`}
                  onChange={(e) => update(index, { experience_years: parseOptionalNumber(e.target.value) })} />
              </div>
              <div>
                <label htmlFor={id('employment')} className={labelClass}>Employment type</label>
                <select id={id('employment')} value={spec.employment_type ?? ''} className={inputClass}
                  onChange={(e) => update(index, { employment_type: e.target.value || null })}>
                  <option value="">Any</option>
                  <option value="full_time">Full-time</option>
                  <option value="contract">Contract / freelance</option>
                  <option value="part_time">Part-time</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
              <div>
                <label htmlFor={id('remote')} className={labelClass}>Remote</label>
                <select id={id('remote')} className={inputClass}
                  value={spec.remote === null ? '' : spec.remote ? 'yes' : 'no'}
                  onChange={(e) => update(index, { remote: e.target.value === '' ? null : e.target.value === 'yes' })}>
                  <option value="">No preference</option>
                  <option value="yes">Remote roles preferred</option>
                  <option value="no">On-site / hybrid is fine</option>
                </select>
              </div>
              <div>
                <label htmlFor={id('salary')} className={labelClass}>Salary floor (USD per year)</label>
                <input id={id('salary')} type="number" min={0} step={1000} className={`${inputClass} font-mono`}
                  value={spec.salary_floor_usd ?? ''} placeholder={`Default: ${config.profile.salary_floor_usd}`}
                  onChange={(e) => update(index, { salary_floor_usd: parseOptionalNumber(e.target.value) })} />
              </div>

              <TagInput id={id('excluded-terms')} label="Extra excluded terms" tone="red" values={spec.excluded_terms}
                onChange={(excluded_terms) => update(index, { excluded_terms })} placeholder="e.g. On-Site Only" />
              <TagInput id={id('excluded-companies')} label="Extra excluded companies" tone="red" values={spec.excluded_companies}
                onChange={(excluded_companies) => update(index, { excluded_companies })} placeholder="e.g. Staffing Co" />
            </div>
          </Section>
        );
      })}

      <button
        type="button"
        onClick={addSpec}
        className="w-full border-2 border-dashed border-slate-700 hover:border-blue-500 text-slate-300 hover:text-white rounded-xl py-4 text-sm font-semibold flex items-center justify-center gap-2 transition"
      >
        <Plus className="w-4 h-4" aria-hidden="true" /> Add job spec
      </button>
    </div>
  );
};
