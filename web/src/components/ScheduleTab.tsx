import React from 'react';
import { Clock, Info, Mail } from 'lucide-react';
import { AppConfig } from '../types';
import { Section, Toggle, inputClass, labelClass } from './ui';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

const TIMEZONES = [
  ['UTC', 'UTC'],
  ['Africa/Lagos', 'Africa/Lagos (WAT, UTC+1)'],
  ['Europe/London', 'Europe/London (GMT / BST)'],
  ['Europe/Berlin', 'Europe/Berlin (CET / CEST)'],
  ['America/New_York', 'America/New_York (ET)'],
  ['America/Los_Angeles', 'America/Los_Angeles (PT)'],
  ['Asia/Singapore', 'Asia/Singapore (SGT)'],
];

export const ScheduleTab: React.FC<Props> = ({ config, onChange }) => {
  const setSchedule = (patch: Partial<AppConfig['schedule']>) => onChange({ ...config, schedule: { ...config.schedule, ...patch } });
  const setDelivery = (patch: Partial<AppConfig['delivery']>) => onChange({ ...config, delivery: { ...config.delivery, ...patch } });
  const threshold = config.schedule.instant_alert_threshold;

  return (
    <div className="space-y-6">
      <Section
        icon={<Clock className="w-5 h-5 text-blue-400" aria-hidden="true" />}
        title="When alerts run"
        description="Scheduled runs happen at 07:30 and 19:30 UTC. To change that, edit the cron line in .github/workflows/job_alert.yml. Each run sends instant alerts and one digest of everything new."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label htmlFor="schedule-timezone" className={labelClass}>Time zone for dates in emails</label>
            <select id="schedule-timezone" value={config.schedule.timezone} onChange={(e) => setSchedule({ timezone: e.target.value })} className={inputClass}>
              {TIMEZONES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="schedule-threshold" className={labelClass}>
              Instant alert threshold: <span className="text-emerald-400">{threshold.toFixed(1)} / 10</span>
            </label>
            <input
              id="schedule-threshold"
              type="range"
              min={7.5}
              max={10}
              step={0.1}
              value={threshold}
              onChange={(e) => setSchedule({ instant_alert_threshold: parseFloat(e.target.value) })}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
            <p className="text-xs text-slate-500 mt-1">Matches at or above this score get their own email right away.</p>
          </div>
        </div>
      </Section>

      <Section
        icon={<Mail className="w-5 h-5 text-indigo-400" aria-hidden="true" />}
        title="Email delivery"
        description="If a send fails, the matches stay queued and are retried on the next scheduled run."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label htmlFor="delivery-provider" className={labelClass}>Email provider</label>
            <select id="delivery-provider" value={config.delivery.email_provider} onChange={(e) => setDelivery({ email_provider: e.target.value })} className={inputClass}>
              <option value="resend">Resend (3,000 free emails/month)</option>
              <option value="brevo">Brevo (300 free emails/day)</option>
              <option value="sendgrid">SendGrid (100 free emails/day)</option>
              <option value="smtp">SMTP (e.g. Gmail app password)</option>
              <option value="console">Preview only (no email)</option>
            </select>
          </div>
          <div>
            <label htmlFor="delivery-recipient" className={labelClass}>Recipient email</label>
            <input id="delivery-recipient" type="email" value={config.delivery.recipient_email}
              onChange={(e) => setDelivery({ recipient_email: e.target.value })} placeholder="you@example.com" className={inputClass} />
          </div>
          <div>
            <label htmlFor="delivery-from" className={labelClass}>Sender</label>
            <input id="delivery-from" type="text" value={config.delivery.from_email}
              onChange={(e) => setDelivery({ from_email: e.target.value })} placeholder="Job Alerts <alerts@resend.dev>" className={`${inputClass} font-mono text-xs`} />
          </div>
          <div className="space-y-3">
            <Toggle id="delivery-instant" label={`Send instant alerts for matches of ${threshold.toFixed(1)}+`}
              checked={config.delivery.send_instant_alerts} onChange={(send_instant_alerts) => setDelivery({ send_instant_alerts })} />
            <Toggle id="delivery-digest" label="Send the digest (matches of 7.0+)"
              checked={config.delivery.send_daily_digest} onChange={(send_daily_digest) => setDelivery({ send_daily_digest })} />
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-start gap-3 text-xs text-slate-400">
          <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" aria-hidden="true" />
          <div className="space-y-1">
            <div className="font-semibold text-slate-200">Credentials stay out of this file</div>
            <div>
              API keys and the recipient address from <code className="text-indigo-300">.env</code> or GitHub secrets
              (<code className="text-indigo-300">RESEND_API_KEY</code>, <code className="text-indigo-300">CANDIDATE_EMAIL</code>) override these
              settings at runtime and are never written back to <code className="text-indigo-300">config/jobs.yaml</code>.
            </div>
          </div>
        </div>
      </Section>
    </div>
  );
};
