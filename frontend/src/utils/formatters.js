/**
 * Formatting utilities for Indian Currency (INR) and Indian Standard Time (IST).
 * Complies with AGENTS.md requirements:
 * - Indian number grouping: ₹1,00,000.00
 * - Asia/Kolkata timezone representation
 */

/**
 * Formats a number or Decimal string into Indian currency representation.
 * Example: 150000.5 -> "₹1,50,000.50"
 */
export function formatINR(amount, includeSymbol = true) {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return includeSymbol ? '₹0.00' : '0.00';
  }

  const num = Number(amount);
  const isNegative = num < 0;
  const absNum = Math.abs(num);

  // Format using Indian locale (en-IN)
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absNum);

  const sign = isNegative ? '-' : '';
  const prefix = includeSymbol ? '₹' : '';

  return `${sign}${prefix}${formatted}`;
}

/**
 * Formats an ISO UTC date string into IST (Asia/Kolkata) readable format.
 * Example: "2026-11-07T06:30:00Z" -> "07 Nov 2026, 12:00 PM"
 */
export function formatISTDateTime(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

/**
 * Formats date only in IST (Asia/Kolkata) readable format.
 * Example: "2026-11-07T06:30:00Z" -> "07 Nov 2026"
 */
export function formatISTDate(isoString) {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}
