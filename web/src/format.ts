const SYMBOLS: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', NGN: '₦', INR: '₹' };
const PERIOD_SUFFIX: Record<string, string> = { hourly: '/hr', daily: '/day', weekly: '/wk', monthly: '/mo' };

export function formatMoney(amount: number, currency = 'USD'): string {
  const code = (currency || 'USD').toUpperCase();
  const number = amount.toLocaleString('en-US', { maximumFractionDigits: amount >= 100 ? 0 : 2 });
  const symbol = SYMBOLS[code];
  return symbol ? `${symbol}${number}` : `${code} ${number}`;
}

export function formatSalary(
  min: number | null | undefined,
  max: number | null | undefined,
  currency = 'USD',
  period = 'yearly',
): string {
  const low = min ?? max;
  const high = max ?? min;
  if (low == null || high == null) return '';
  const range = low === high ? formatMoney(high, currency) : `${formatMoney(low, currency)} – ${formatMoney(high, currency)}`;
  return `${range}${PERIOD_SUFFIX[period] ?? ''}`;
}

/** Returns the URL only when it is an http(s) link, so data from job boards can't inject script URLs. */
export function safeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}

export function humanize(value: string | null | undefined): string {
  return (value ?? '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/** Parses a number input; blank (or invalid) becomes null. */
export function parseOptionalNumber(value: string): number | null {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
