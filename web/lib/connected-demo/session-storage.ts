export interface RecoveryMetadata {
  role: "advisor" | "parent";
  csrf: string;
  caseId: string;
  taskId: string | null;
  briefId: string | null;
  cursor: number;
}

const KEY = "night-voyager:m5";

export function saveRecoveryMetadata(value: RecoveryMetadata): void {
  sessionStorage.setItem(KEY, JSON.stringify(value));
}

export function clearRecoveryMetadata(): void {
  sessionStorage.removeItem(KEY);
}

export function loadRecoveryMetadata(): RecoveryMetadata | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<RecoveryMetadata>;
    const keys = Object.keys(value).sort().join(",");
    if (
      keys !== "briefId,caseId,csrf,cursor,role,taskId" ||
      !["advisor", "parent"].includes(String(value.role)) ||
      typeof value.csrf !== "string" ||
      typeof value.caseId !== "string" ||
      !(typeof value.taskId === "string" || value.taskId === null) ||
      !(typeof value.briefId === "string" || value.briefId === null) ||
      !Number.isInteger(value.cursor) ||
      Number(value.cursor) < 0
    ) return null;
    return value as RecoveryMetadata;
  } catch {
    return null;
  }
}
