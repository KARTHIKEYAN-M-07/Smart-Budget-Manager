import { describe, it, expect } from 'vitest';
import { formatINR, formatISTDate, formatISTDateTime } from '../utils/formatters';

describe('formatINR', () => {
  it('formats small amounts with 2 decimal places', () => {
    expect(formatINR(150)).toBe('₹150.00');
    expect(formatINR('150.50')).toBe('₹150.50');
  });

  it('formats Indian number grouping correctly (₹1,00,000)', () => {
    expect(formatINR(100000)).toBe('₹1,00,000.00');
    expect(formatINR(1234567.89)).toBe('₹12,34,567.89');
  });

  it('handles negative amounts', () => {
    expect(formatINR(-2500)).toBe('-₹2,500.00');
  });

  it('handles zero, null, and undefined values safely', () => {
    expect(formatINR(0)).toBe('₹0.00');
    expect(formatINR(null)).toBe('₹0.00');
    expect(formatINR(undefined)).toBe('₹0.00');
    expect(formatINR('invalid')).toBe('₹0.00');
  });

  it('supports omitting currency symbol', () => {
    expect(formatINR(100000, false)).toBe('1,00,000.00');
  });
});

describe('formatISTDate & formatISTDateTime', () => {
  it('formats ISO dates correctly into IST', () => {
    const iso = '2026-11-07T06:30:00Z'; // 12:00 PM IST
    const dateFormatted = formatISTDate(iso);
    expect(dateFormatted).toContain('2026');
    expect(dateFormatted).toContain('Nov');

    const dtFormatted = formatISTDateTime(iso);
    expect(dtFormatted).toContain('2026');
    expect(dtFormatted).toContain('PM');
  });

  it('handles null and undefined dates gracefully', () => {
    expect(formatISTDate(null)).toBe('-');
    expect(formatISTDateTime(undefined)).toBe('-');
  });
});
