const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

export type RequiredDateTone = "neutral" | "attention" | "late";

export type RequiredDateSignal = {
  daysRemaining: number;
  label: string;
  tone: RequiredDateTone;
};

export function elapsedTime(start: string, end = new Date()) {
  const elapsed = Math.max(0, end.getTime() - new Date(start).getTime());
  if (elapsed < MINUTE_MS) return "less than a minute";
  if (elapsed < HOUR_MS) return quantity(Math.floor(elapsed / MINUTE_MS), "minute");
  if (elapsed < DAY_MS) return quantity(Math.floor(elapsed / HOUR_MS), "hour");
  return quantity(Math.floor(elapsed / DAY_MS), "day");
}

export function requiredDateSignal(requiredBy: string, now = new Date()): RequiredDateSignal {
  const [year, month, day] = requiredBy.split("-").map(Number);
  const due = Date.UTC(year, month - 1, day);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const daysRemaining = Math.round((due - today) / DAY_MS);
  if (daysRemaining < 0) {
    const elapsed = Math.abs(daysRemaining);
    return {
      daysRemaining,
      label: `Required date passed by ${quantity(elapsed, "day")}`,
      tone: "late",
    };
  }
  if (daysRemaining === 0) return { daysRemaining, label: "Required today", tone: "attention" };
  if (daysRemaining === 1) return { daysRemaining, label: "Required tomorrow", tone: "attention" };
  return {
    daysRemaining,
    label: `Required in ${quantity(daysRemaining, "day")}`,
    tone: daysRemaining <= 3 ? "attention" : "neutral",
  };
}

function quantity(value: number, unit: string) {
  return `${value} ${unit}${value === 1 ? "" : "s"}`;
}
