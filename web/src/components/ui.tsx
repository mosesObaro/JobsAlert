import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Info, Plus, X } from 'lucide-react';

type Tone = 'blue' | 'emerald' | 'amber' | 'red' | 'slate';

const TONES: Record<Tone, { chip: string; button: string; focus: string }> = {
  blue: { chip: 'bg-blue-950/60 border-blue-800/80 text-blue-200', button: 'bg-blue-600 hover:bg-blue-500', focus: 'focus:border-blue-500' },
  emerald: { chip: 'bg-emerald-950/60 border-emerald-800/80 text-emerald-200', button: 'bg-emerald-600 hover:bg-emerald-500', focus: 'focus:border-emerald-500' },
  amber: { chip: 'bg-amber-950/60 border-amber-800/80 text-amber-200', button: 'bg-amber-600 hover:bg-amber-500', focus: 'focus:border-amber-500' },
  red: { chip: 'bg-red-950/60 border-red-800/80 text-red-200', button: 'bg-red-600 hover:bg-red-500', focus: 'focus:border-red-500' },
  slate: { chip: 'bg-slate-800 border-slate-700 text-slate-200', button: 'bg-slate-700 hover:bg-slate-600', focus: 'focus:border-slate-400' },
};

interface TagInputProps {
  id: string;
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  description?: string;
  tone?: Tone;
  addLabel?: string;
}

/** A list of short text values edited as removable chips. */
export const TagInput: React.FC<TagInputProps> = ({
  id,
  label,
  values,
  onChange,
  placeholder,
  description,
  tone = 'blue',
  addLabel = 'Add',
}) => {
  const [draft, setDraft] = useState('');
  const styles = TONES[tone];

  const add = () => {
    const value = draft.trim();
    if (value && !values.some((existing) => existing.toLowerCase() === value.toLowerCase())) {
      onChange([...values, value]);
    }
    setDraft('');
  };

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
        {label}
      </label>
      {description && <p className="text-xs text-slate-400">{description}</p>}
      <div className="flex gap-2">
        <input
          id={id}
          type="text"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add();
            }
          }}
          className={`flex-1 min-w-0 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none ${styles.focus}`}
        />
        <button
          type="button"
          onClick={add}
          className={`${styles.button} text-white px-3 py-2 rounded-lg text-sm font-semibold flex items-center gap-1 transition`}
        >
          <Plus className="w-4 h-4" aria-hidden="true" /> {addLabel}
        </button>
      </div>
      {values.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label={label}>
          {values.map((value, index) => (
            <li
              key={`${value}-${index}`}
              className={`${styles.chip} border text-sm font-medium pl-3 pr-1.5 py-1 rounded-lg flex items-center gap-1.5`}
            >
              {value}
              <button
                type="button"
                aria-label={`Remove ${value}`}
                title={`Remove ${value}`}
                onClick={() => onChange(values.filter((_, i) => i !== index))}
                className="p-0.5 rounded hover:text-red-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

interface NoticeProps {
  kind: 'error' | 'success' | 'info';
  message: string;
  onClose?: () => void;
}

export const Notice: React.FC<NoticeProps> = ({ kind, message, onClose }) => {
  const styles = {
    error: 'bg-red-950/70 border-red-800 text-red-200',
    success: 'bg-emerald-950/70 border-emerald-800 text-emerald-200',
    info: 'bg-slate-900 border-slate-700 text-slate-300',
  }[kind];
  const Icon = kind === 'error' ? AlertTriangle : kind === 'success' ? CheckCircle2 : Info;
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`border rounded-lg px-4 py-3 text-sm flex items-start gap-3 ${styles}`}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
      <span className="flex-1 whitespace-pre-line">{message}</span>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Dismiss message" className="p-0.5 rounded hover:text-white">
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
};

interface ToggleProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
}

export const Toggle: React.FC<ToggleProps> = ({ id, label, checked, onChange, description }) => (
  <div className="flex items-start gap-3">
    <input
      id={id}
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="mt-0.5 w-4 h-4 accent-blue-500 rounded cursor-pointer"
    />
    <label htmlFor={id} className="cursor-pointer">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      {description && <span className="block text-xs text-slate-400 mt-0.5">{description}</span>}
    </label>
  </div>
);

interface SectionProps {
  icon: React.ReactNode;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export const Section: React.FC<SectionProps> = ({ icon, title, description, actions, children }) => (
  <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-lg font-bold text-white">{title}</h2>
        </div>
        {description && <p className="text-sm text-slate-400 mt-1">{description}</p>}
      </div>
      {actions}
    </div>
    {children}
  </section>
);

export const inputClass =
  'w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500';
export const labelClass = 'block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5';
