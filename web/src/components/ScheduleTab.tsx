import React from 'react';
import { AppConfig } from '../types';
import { Clock, Mail, ShieldCheck, Zap, Info } from 'lucide-react';

interface Props {
  config: AppConfig;
  onChange: (newConfig: AppConfig) => void;
}

export const ScheduleTab: React.FC<Props> = ({ config, onChange }) => {
  return (
    <div className="space-y-8">
      {/* Schedule & Timing */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Clock className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">Alert Schedules & Delivery Timing</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Controls when the automated GitHub Actions runner wakes up to crawl, score, and dispatch emails.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Timezone
            </label>
            <select
              value={config.schedule.timezone}
              onChange={(e) =>
                onChange({
                  ...config,
                  schedule: { ...config.schedule, timezone: e.target.value },
                })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="UTC">UTC (Universal Coordinated Time)</option>
              <option value="America/New_York">America/New_York (EST / EDT)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PST / PDT)</option>
              <option value="Europe/London">Europe/London (GMT / BST)</option>
              <option value="Africa/Lagos">Africa/Lagos (WAT - UTC+1)</option>
              <option value="Europe/Berlin">Europe/Berlin (CET / CEST)</option>
              <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Daily Digest Delivery Time
            </label>
            <input
              type="time"
              value={config.schedule.daily_digest_time}
              onChange={(e) =>
                onChange({
                  ...config,
                  schedule: { ...config.schedule, daily_digest_time: e.target.value },
                })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Weekly Digest Day
            </label>
            <select
              value={config.schedule.weekly_digest_day}
              onChange={(e) =>
                onChange({
                  ...config,
                  schedule: { ...config.schedule, weekly_digest_day: e.target.value },
                })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="Monday">Monday</option>
              <option value="Tuesday">Tuesday</option>
              <option value="Wednesday">Wednesday</option>
              <option value="Thursday">Thursday</option>
              <option value="Friday">Friday</option>
              <option value="Saturday">Saturday</option>
              <option value="Sunday">Sunday</option>
            </select>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Immediate Alert Threshold: <span className="text-emerald-400 font-bold">{config.schedule.instant_alert_threshold.toFixed(1)} / 10</span>
              </label>
            </div>
            <input
              type="range"
              min={8.5}
              max={9.8}
              step={0.1}
              value={config.schedule.instant_alert_threshold}
              onChange={(e) =>
                onChange({
                  ...config,
                  schedule: { ...config.schedule, instant_alert_threshold: parseFloat(e.target.value) },
                })
              }
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
            <p className="text-xs text-slate-500 mt-1">
              Opportunities scoring at or above this threshold trigger an instant alert email without waiting for the daily digest.
            </p>
          </div>
        </div>
      </div>

      {/* Email Delivery Settings */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Mail className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-white">Email Delivery Provider & Credentials</h2>
        </div>
        <p className="text-sm text-slate-400 mb-6">
          Choose your zero-cost email delivery route. Resend provides 3,000 free emails per month with zero SMTP setup.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Email Provider
            </label>
            <select
              value={config.delivery.email_provider}
              onChange={(e) =>
                onChange({
                  ...config,
                  delivery: { ...config.delivery, email_provider: e.target.value },
                })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="resend">Resend (Recommended - 3,000 free/mo)</option>
              <option value="brevo">Brevo / Sendinblue (300 free/day)</option>
              <option value="sendgrid">SendGrid (100 free/day)</option>
              <option value="smtp">Custom SMTP (Gmail App Password, etc.)</option>
              <option value="console">Local Console / Preview Only (No Send)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Recipient Email Address
            </label>
            <input
              type="email"
              value={config.delivery.recipient_email}
              onChange={(e) =>
                onChange({
                  ...config,
                  delivery: { ...config.delivery, recipient_email: e.target.value },
                })
              }
              placeholder="candidate@example.com"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              From Sender String
            </label>
            <input
              type="text"
              value={config.delivery.from_email}
              onChange={(e) =>
                onChange({
                  ...config,
                  delivery: { ...config.delivery, from_email: e.target.value },
                })
              }
              placeholder="Job Intelligence <alerts@resend.dev>"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 font-mono text-xs"
            />
          </div>

          <div className="flex flex-col justify-center space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.delivery.send_instant_alerts}
                onChange={(e) =>
                  onChange({
                    ...config,
                    delivery: { ...config.delivery, send_instant_alerts: e.target.checked },
                  })
                }
                className="w-4 h-4 accent-indigo-500 rounded"
              />
              <span className="text-sm font-medium text-slate-200">
                Dispatch Immediate Alerts for 9.0+ Matches
              </span>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.delivery.send_daily_digest}
                onChange={(e) =>
                  onChange({
                    ...config,
                    delivery: { ...config.delivery, send_daily_digest: e.target.checked },
                  })
                }
                className="w-4 h-4 accent-indigo-500 rounded"
              />
              <span className="text-sm font-medium text-slate-200">
                Send Scheduled Daily Digest (7.0+ Matches)
              </span>
            </label>
          </div>
        </div>

        {/* Free Tier Setup Instructions Banner */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-start gap-3 text-xs text-slate-400">
          <Info className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-slate-200 mb-1">
              Zero-Cost Setup Quick Reference:
            </div>
            <div>
              1. Sign up for a free Resend account at <a href="https://resend.com" target="_blank" rel="noreferrer" className="text-blue-400 underline">resend.com</a>.
            </div>
            <div>
              2. Add your API token as <code className="bg-slate-800 text-indigo-300 px-1 py-0.5 rounded">RESEND_API_KEY</code> in your local <code className="bg-slate-800 text-indigo-300 px-1 py-0.5 rounded">.env</code> file or in your GitHub Repository Secrets.
            </div>
            <div>
              3. By default, Resend allows sending to your account email using <code className="bg-slate-800 text-indigo-300 px-1 py-0.5 rounded">onboarding@resend.dev</code> with zero domain DNS setup!
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
