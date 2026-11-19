/**
 * Demo-only access rules for the freemium MVP.
 *
 * This browser store keeps UI state consistent between pricing and predictions.
 * It is intentionally not a security boundary: a production service must check
 * account entitlements on the backend before returning paid report data.
 */
export const ENTITLEMENTS_STORAGE_KEY = "localsportsreel.demo-entitlements.v1";

export type DemoPlan = "free" | "premium";

export type DemoEntitlements = {
  version: 1;
  plan: DemoPlan;
  purchasedReportIds: string[];
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const FREE_ENTITLEMENTS: DemoEntitlements = Object.freeze({
  version: 1,
  plan: "free",
  purchasedReportIds: Object.freeze([]) as unknown as string[],
});

const listeners = new Set<() => void>();
let snapshot: DemoEntitlements = FREE_ENTITLEMENTS;
let initialized = false;

/** A match ID includes the season so future season changes cannot collide. */
export function reportId(season: number, gameId: number): string {
  return `${season}:${gameId}`;
}

/** Validate persisted values before using them; malformed data safely becomes Free. */
export function parseEntitlements(raw: string | null): DemoEntitlements {
  if (!raw) return FREE_ENTITLEMENTS;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return FREE_ENTITLEMENTS;
    const value = parsed as Partial<DemoEntitlements>;
    if (value.version !== 1 || (value.plan !== "free" && value.plan !== "premium")
      || !Array.isArray(value.purchasedReportIds)
      || !value.purchasedReportIds.every(id => typeof id === "string" && /^\d{4}:\d+$/.test(id))) {
      return FREE_ENTITLEMENTS;
    }
    return {
      version: 1,
      plan: value.plan,
      purchasedReportIds: [...new Set(value.purchasedReportIds)],
    };
  } catch {
    return FREE_ENTITLEMENTS;
  }
}

/** Storage access is optional and wrapped because browsers can block localStorage. */
function browserStorage(): StorageLike | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readPersistedEntitlements(storage: StorageLike | null): DemoEntitlements {
  if (!storage) return FREE_ENTITLEMENTS;
  try {
    return parseEntitlements(storage.getItem(ENTITLEMENTS_STORAGE_KEY));
  } catch {
    return FREE_ENTITLEMENTS;
  }
}

function emitChange() {
  for (const listener of listeners) listener();
}

function write(next: DemoEntitlements) {
  snapshot = next;
  initialized = true;
  try {
    browserStorage()?.setItem(ENTITLEMENTS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // The purchase remains available for this page session if persistence is blocked.
  }
  emitChange();
}

/** Client snapshot used by useSyncExternalStore after hydration. */
export function getEntitlementsSnapshot(): DemoEntitlements {
  if (!initialized) {
    snapshot = readPersistedEntitlements(browserStorage());
    initialized = true;
  }
  return snapshot;
}

/** Stable Free snapshot for server rendering; this prevents storage hydration mismatches. */
export function getServerEntitlementsSnapshot(): DemoEntitlements {
  return FREE_ENTITLEMENTS;
}

export function subscribeEntitlements(listener: () => void): () => void {
  listeners.add(listener);
  const storage = browserStorage();
  const onStorage = (event: StorageEvent) => {
    if (event.key !== ENTITLEMENTS_STORAGE_KEY && event.key !== null) return;
    snapshot = readPersistedEntitlements(storage);
    initialized = true;
    emitChange();
  };
  if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

export function hasReportAccess(entitlements: DemoEntitlements, id: string): boolean {
  return entitlements.plan === "premium" || entitlements.purchasedReportIds.includes(id);
}

/** Grant a single report in the demo store; backend authorization replaces this later. */
export function purchaseDemoReport(id: string) {
  if (!/^\d{4}:\d+$/.test(id)) return;
  const current = getEntitlementsSnapshot();
  if (current.purchasedReportIds.includes(id) || current.plan === "premium") return;
  write({ ...current, purchasedReportIds: [...current.purchasedReportIds, id] });
}

/** Activate the simulated unlimited tier. No payment or recurring billing occurs. */
export function activateDemoPremium() {
  write({ ...getEntitlementsSnapshot(), plan: "premium" });
}

/** Clear the demo plan and all match unlocks so each tier can be tried again. */
export function resetDemoPurchases() {
  write(FREE_ENTITLEMENTS);
}
