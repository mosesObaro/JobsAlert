import React, { useState } from 'react';
import { AppConfig } from '../types';
import { Plus, X, Briefcase, CheckCircle2, Star, Ban } from 'lucide-react';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const RoleMatrixTab: React.FC<Props> = ({ config, onChange }) => {
  const [newRole, setNewRole] = useState('');
  const [newMust, setNewMust] = useState('');
  const [newNice, setNewNice] = useState('');
  const [newExcluded, setNewExcluded] = useState('');

  const addRole = () => {
    if (!newRole.trim()) return;
    onChange({
      ...config,
      profile: {
        ...config.profile,
        target_roles: [...config.profile.target_roles, newRole.trim()],
      },
    });
    setNewRole('');
  };

  const removeRole = (idx: number) => {
    onChange({
      ...config,
      profile: {
        ...config.profile,
        target_roles: config.profile.target_roles.filter((_, i) => i !== idx),
      },
    });
  };

  const addSkill = (type: 'must' | 'nice' | 'excluded') => {
    if (type === 'must' && newMust.trim()) {
      onChange({
        ...config,
        filters: { ...config.filters, must_have_skills: [...config.filters.must_have_skills, newMust.trim()] },
      });
      setNewMust('');
    } else if (type === 'nice' && newNice.trim()) {
      onChange({
        ...config,
        filters: { ...config.filters, nice_to_have_skills: [...config.filters.nice_to_have_skills, newNice.trim()] },
      });
      setNewNice('');
    } else if (type === 'excluded' && newExcluded.trim()) {
      onChange({
        ...config,
        filters: { ...config.filters, excluded_terms: [...config.filters.excluded_terms, newExcluded.trim()] },
      });
      setNewExcluded('');
    }
  };

  const removeSkill = (type: 'must' | 'nice' | 'excluded', idx: number) => {
    if (type === 'must') {
      onChange({
        ...config,
        filters: { ...config.filters, must_have_skills: config.filters.must_have_skills.filter((_, i) => i !== idx) },
      });
    } else if (type === 'nice') {
      onChange({
        ...config,
        filters: { ...config.filters, nice_to_have_skills: config.filters.nice_to_have_skills.filter((_, i) => i !== idx) },
      });
    } else if (type === 'excluded') {
      onChange({
        ...config,
        filters: { ...config.filters, excluded_terms: config.filters.excluded_terms.filter((_, i) => i !== idx) },
      });
    }
  };

  return (
    <div className="space-y-8">
      {/* Candidate Name & Target Roles */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Briefcase className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">Target Roles & Titles</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          The scoring engine matches these exact titles or close semantically adjacent roles.
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. Staff Distributed Systems Engineer"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addRole()}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={addRole}
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add Role
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.profile.target_roles.map((role, idx) => (
            <span
              key={idx}
              className="bg-blue-950/60 border border-blue-800/80 text-blue-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              {role}
              <button onClick={() => removeRole(idx)} className="hover:text-red-400">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Must-Have Skills */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <h2 className="text-lg font-bold text-white">Must-Have Skills & Toolchains</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          Postings missing these skills will incur steep score penalties or be filtered out.
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. Go, Kubernetes, Kafka"
            value={newMust}
            onChange={(e) => setNewMust(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSkill('must')}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={() => addSkill('must')}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add Skill
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.filters.must_have_skills.map((skill, idx) => (
            <span
              key={idx}
              className="bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              {skill}
              <button onClick={() => removeSkill('must', idx)} className="hover:text-red-400">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Nice-to-Have Skills */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Star className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-white">Nice-to-Have Skills (Bonus Points)</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          Secondary toolchains that grant score bonuses and trigger 9.0+ immediate alerts.
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. Rust, WebAssembly, Edge AI"
            value={newNice}
            onChange={(e) => setNewNice(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSkill('nice')}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
          <button
            onClick={() => addSkill('nice')}
            className="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add Skill
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.filters.nice_to_have_skills.map((skill, idx) => (
            <span
              key={idx}
              className="bg-amber-950/60 border border-amber-800/80 text-amber-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              {skill}
              <button onClick={() => removeSkill('nice', idx)} className="hover:text-red-400">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Excluded Terms */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Ban className="w-5 h-5 text-red-400" />
          <h2 className="text-lg font-bold text-white">Excluded Terms & Deal-Breakers</h2>
        </div>
        <p className="text-sm text-slate-400 mb-4">
          Any job containing these terms in title or description will be immediately dropped to Score 0.0.
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="e.g. PHP, WordPress, No C2C, Security Clearance"
            value={newExcluded}
            onChange={(e) => setNewExcluded(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSkill('excluded')}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-red-500"
          />
          <button
            onClick={() => addSkill('excluded')}
            className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition"
          >
            <Plus className="w-4 h-4" /> Add Term
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {config.filters.excluded_terms.map((term, idx) => (
            <span
              key={idx}
              className="bg-red-950/60 border border-red-800/80 text-red-200 text-sm font-medium px-3 py-1.5 rounded-lg flex items-center gap-2"
            >
              {term}
              <button onClick={() => removeSkill('excluded', idx)} className="hover:text-red-400">
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
