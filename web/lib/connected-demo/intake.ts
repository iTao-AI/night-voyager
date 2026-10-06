export function isIntakeMonth(value: unknown): value is string {
  return typeof value === "string" && /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value)
    && Number(value.slice(0, 4)) > 0;
}
