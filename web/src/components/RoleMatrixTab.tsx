import React from 'react';
import { Ban, Briefcase, CheckCircle2, Star } from 'lucide-react';
import { AppConfig } from '../types';
import { Notice, Section, TagInput } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const RoleMatrixTab: React.FC<Props> = ({ config, onChange }) => {
  const setProfile = (patch: Partial<AppConfig['profile']>) => onChange({ ...config, profile: { ...config.profile, ...patch } });
  const setFilters = (patch: Partial<AppConfig['filters']>) => onChange({ ...config, filters: { ...config.filters, ...patch } });
  const specCount = config.job_specs.length;

  return (
    <div className="space-y-6">
      {specCount > 0 && (
        <Notice
          kind="info"
          message={`These are defaults. You have ${specCount} job spec${specCount === 1 ? '' : 's'}: each one uses its own roles and skills, and falls back to these only where its fields are empty. Edit specs in the Job Specs tab. Excluded terms here always apply.`}
        />
      )}

      <Section
        icon={<Briefcase className="w-5 h-5 text-blue-400" aria-hidden="true" />}
        title="Target roles"
        description="Titles are matched as whole words, so short keywords like “HR” don't match inside other words."
      >
        <TagInput
          id="default-target-roles"
          label="Target roles & titles"
          values={config.profile.target_roles}
          onChange={(target_roles) => setProfile({ target_roles })}
          placeholder="e.g. HR Business Partner"
          addLabel="Add role"
        />
      </Section>

      <Section
        icon={<CheckCircle2 className="w-5 h-5 text-emerald-400" aria-hidden="true" />}
        title="Must-have skills"
        description="Postings missing these skills score lower."
      >
        <TagInput
          id="default-must-have"
          label="Must-have skills"
          tone="emerald"
          values={config.filters.must_have_skills}
          onChange={(must_have_skills) => setFilters({ must_have_skills })}
          placeholder="e.g. Recruitment, Onboarding"
          addLabel="Add skill"
        />
      </Section>

      <Section
        icon={<Star className="w-5 h-5 text-amber-400" aria-hidden="true" />}
        title="Nice-to-have skills"
        description="Secondary skills that add bonus points."
      >
        <TagInput
          id="default-nice-to-have"
          label="Nice-to-have skills"
          tone="amber"
          values={config.filters.nice_to_have_skills}
          onChange={(nice_to_have_skills) => setFilters({ nice_to_have_skills })}
          placeholder="e.g. BambooHR, Workday"
          addLabel="Add skill"
        />
      </Section>

      <Section
        icon={<Ban className="w-5 h-5 text-red-400" aria-hidden="true" />}
        title="Excluded terms"
        description="Any posting with one of these terms in its title or description scores 0. Applies to every job spec."
      >
        <TagInput
          id="default-excluded-terms"
          label="Excluded terms"
          tone="red"
          values={config.filters.excluded_terms}
          onChange={(excluded_terms) => setFilters({ excluded_terms })}
          placeholder="e.g. US Citizen Only, Security Clearance"
          addLabel="Add term"
        />
      </Section>
    </div>
  );
};
