"use client";

import { useSyncExternalStore } from "react";
import { getEntitlementsSnapshot, getServerEntitlementsSnapshot, subscribeEntitlements } from "./entitlements";

/**
 * Shared client hook keeps pricing and predictions in sync across tabs.
 * The server snapshot always starts as Free; persisted access is read after
 * hydration by useSyncExternalStore, so localStorage never changes server HTML.
 */
export function useEntitlements() {
  return useSyncExternalStore(subscribeEntitlements, getEntitlementsSnapshot, getServerEntitlementsSnapshot);
}
