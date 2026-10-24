import assert from "node:assert/strict";
import { test } from "node:test";
import {
  activateDemoPremium,
  ENTITLEMENTS_STORAGE_KEY,
  FREE_ENTITLEMENTS,
  getEntitlementsSnapshot,
  getServerEntitlementsSnapshot,
  hasReportAccess,
  parseEntitlements,
  purchaseDemoReport,
  readPersistedEntitlements,
  reportId,
  resetDemoPurchases,
} from "../lib/entitlements";

function withMemoryStorage(run: (storage: Storage) => void) {
  const values = new Map<string, string>();
  const storage = {
    getItem(key: string) { return values.get(key) ?? null; },
    setItem(key: string, value: string) { values.set(key, value); },
  } as Storage;
  Object.defineProperty(globalThis, "window", { configurable: true, value: { localStorage: storage } });
  resetDemoPurchases();
  try {
    run(storage);
  } finally {
    resetDemoPurchases();
    Reflect.deleteProperty(globalThis, "window");
  }
}

test("Free access keeps advanced reports locked", () => {
  const free = parseEntitlements(null);
  assert.equal(free.plan, "free");
  assert.equal(hasReportAccess(free, reportId(2027, 501)), false);
});

test("an individual unlock grants only that season and match", () => {
  withMemoryStorage(() => {
    const selected = reportId(2027, 501);
    purchaseDemoReport(selected);
    const current = getEntitlementsSnapshot();
    assert.equal(hasReportAccess(current, selected), true);
    assert.equal(hasReportAccess(current, reportId(2027, 502)), false);
    assert.equal(hasReportAccess(current, reportId(2028, 501)), false);
  });
});

test("Premium grants access to multiple reports", () => {
  withMemoryStorage(() => {
    activateDemoPremium();
    const premium = getEntitlementsSnapshot();
    assert.equal(premium.plan, "premium");
    assert.equal(hasReportAccess(premium, reportId(2027, 501)), true);
    assert.equal(hasReportAccess(premium, reportId(2027, 502)), true);
  });
});

test("a purchased report persists in localStorage for the next page load", () => {
  withMemoryStorage(storage => {
    const id = reportId(2027, 501);
    purchaseDemoReport(id);
    const reloaded = readPersistedEntitlements(storage);
    assert.equal(storage.getItem(ENTITLEMENTS_STORAGE_KEY) !== null, true);
    assert.equal(hasReportAccess(reloaded, id), true);
  });
});

test("reset returns the demo account to Free and removes report access", () => {
  withMemoryStorage(() => {
    const id = reportId(2027, 501);
    purchaseDemoReport(id);
    resetDemoPurchases();
    const reset = getEntitlementsSnapshot();
    assert.equal(reset.plan, "free");
    assert.deepEqual(reset.purchasedReportIds, []);
    assert.equal(hasReportAccess(reset, id), false);
  });
});

test("invalid or corrupted entitlement data safely falls back to Free", () => {
  assert.deepEqual(parseEntitlements("not json"), FREE_ENTITLEMENTS);
  assert.deepEqual(parseEntitlements(JSON.stringify({ version: 2, plan: "premium", purchasedReportIds: [] })), FREE_ENTITLEMENTS);
  assert.deepEqual(parseEntitlements(JSON.stringify({ version: 1, plan: "free", purchasedReportIds: ["not-a-match"] })), FREE_ENTITLEMENTS);
  assert.deepEqual(readPersistedEntitlements({ getItem() { throw new Error("blocked"); }, setItem() {} }), FREE_ENTITLEMENTS);
});

test("server rendering does not read browser storage", () => {
  assert.equal(readPersistedEntitlements(null), FREE_ENTITLEMENTS);
  assert.equal(getServerEntitlementsSnapshot(), FREE_ENTITLEMENTS);
});
