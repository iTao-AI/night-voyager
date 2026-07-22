import { getPresentationCopy } from "./catalog";
import type { PresentationLocale } from "./locales";

function cnyMinorValue(minor: unknown, currency: unknown): string | null {
  if (
    currency !== "CNY"
    || typeof minor !== "number"
    || !Number.isSafeInteger(minor)
    || minor < 0
  ) {
    return null;
  }
  const exact = BigInt(minor);
  const units = (exact / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const remainder = exact % 100n;
  return remainder === 0n
    ? units
    : `${units}.${remainder.toString().padStart(2, "0")}`;
}

function moneyPrefix(locale: PresentationLocale): string {
  return locale === "zh-CN" ? "¥" : "CNY ";
}

export function formatCnyMinor(
  locale: PresentationLocale,
  minor: unknown,
  currency: unknown,
): string {
  const value = cnyMinorValue(minor, currency);
  return value === null
    ? getPresentationCopy(locale, "statusUnavailable")
    : `${moneyPrefix(locale)}${value}`;
}

export function formatCnyRange(
  locale: PresentationLocale,
  minimumMinor: unknown,
  maximumMinor: unknown,
  currency: unknown,
): string {
  const minimum = cnyMinorValue(minimumMinor, currency);
  const maximum = cnyMinorValue(maximumMinor, currency);
  if (
    minimum === null
    || maximum === null
    || typeof minimumMinor !== "number"
    || typeof maximumMinor !== "number"
    || minimumMinor > maximumMinor
  ) {
    return getPresentationCopy(locale, "statusUnavailable");
  }
  return `${moneyPrefix(locale)}${minimum}–${maximum}`;
}

export function formatIsoDate(locale: PresentationLocale, value: unknown): string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return getPresentationCopy(locale, "statusUnavailable");
  }
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
  ) {
    return getPresentationCopy(locale, "statusUnavailable");
  }
  if (locale === "zh-CN") return `${year}年${month}月${day}日`;
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ] as const;
  return `${months[month - 1]} ${day}, ${year}`;
}
