import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyImpactSnapshot, impactSnapshotKey, parseImpactSnapshot, readStoredImpact,
  saveImpactSnapshot, subscribeImpactSnapshots, validImpact,
  type ImpactContext,
} from "../lib/impact-snapshot";
import type { ImpactResponse, Outcome } from "../lib/prediction-types";

class TestStorage implements Storage {
  entries = new Map<string, string>();
  denyRead = false;
  denyWrite = false;
  get length() { return this.entries.size; }
  clear() { this.entries.clear(); }
  key(index: number) { return [...this.entries.keys()][index] ?? null; }
  getItem(key: string) {
    if (this.denyRead) throw new Error("Storage denied");
    return this.entries.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    if (this.denyWrite) throw new Error("Storage quota exceeded");
    this.entries.set(key, value);
  }
  removeItem(key: string) {
    if (this.denyWrite) throw new Error("Storage denied");
    this.entries.delete(key);
  }
}

let browser: EventTarget & { localStorage: TestStorage };
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");

function storageEvent(key: string | null) {
  const event = new Event("storage");
  Object.defineProperty(event, "key", { value: key });
  browser.dispatchEvent(event);
}

beforeEach(() => {
  browser = Object.assign(new EventTarget(), { localStorage: new TestStorage() });
  Object.defineProperty(globalThis, "window", { configurable: true, value: browser });
  const unsubscribe = subscribeImpactSnapshots(() => {});
  storageEvent(null);
  unsubscribe();
});

afterEach(() => {
  if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
  else Reflect.deleteProperty(globalThis, "window");
});

function context(overrides: Partial<ImpactContext> = {}): ImpactContext {
  return {
    apiBase: "https://sports.example.test", season: 2027, gameId: 100,
    homeId: "home", awayId: "away", modelVersion: "model-one", topN: 1,
    ...overrides,
  };
}

function impact(ctx = context()): ImpactResponse {
  const baseline = [
    { team_id: ctx.homeId, name: "Home Club", current_points: 10, expected_points: 20,
      expected_rank: 1.4, top_n_lower: 0.6, top_n_upper: 0.6 },
    { team_id: ctx.awayId, name: "Away Club", current_points: 8, expected_points: 18,
      expected_rank: 1.6, top_n_lower: 0.4, top_n_upper: 0.4 },
  ];
  const outcomes: Outcome[] = ["home_regulation", "home_overtime", "away_overtime", "away_regulation"];
  const awards = [[3, 0], [2, 1], [1, 2], [0, 3]];
  return {
    season: ctx.season, game_id: ctx.gameId, generated_at: "2026-10-24T13:00:00Z",
    standings_updated_at: "2026-10-24T12:59:00Z", model_name: "logistic_total_n40",
    model_version: ctx.modelVersion, forecast_cutoff: "2026-10-24", scope: "regular_season_points",
    warnings: [], limitations: ["Points-only projection"], simulations: 4000, seed: 2026,
    top_n: ctx.topN, remaining_fixtures: 10, max_mc_margin_95: 0.0155, baseline,
    scenarios: outcomes.map((outcome, index) => ({
      outcome, home_points: awards[index][0], away_points: awards[index][1],
      teams: baseline.map((team, teamIndex) => {
        const direction = teamIndex === 0 ? 1 : -1;
        return { ...team, expected_points: team.expected_points + direction,
          expected_rank: team.expected_rank - direction * 0.1,
          top_n_lower: team.top_n_lower + direction * 0.05,
          top_n_upper: team.top_n_upper + direction * 0.05,
          delta_points: direction, delta_rank: -direction * 0.1,
          delta_top_n_lower: direction * 0.05, delta_top_n_upper: direction * 0.05 };
      }),
    })),
  };
}

function envelope(value: ImpactResponse, version = 1) {
  return JSON.stringify({ version, impact: value });
}

test("roundtrip retains the complete successful table and all four scenarios", () => {
  const ctx = context(), value = impact(ctx);
  assert.equal(validImpact(value, ctx), true);
  saveImpactSnapshot(ctx, value);
  const raw = readStoredImpact(impactSnapshotKey(ctx));
  assert.deepEqual(parseImpactSnapshot(raw, ctx), value);
  assert.equal(browser.localStorage.getItem(impactSnapshotKey(ctx)), raw);
  assert.equal(emptyImpactSnapshot(), "");
});

test("reconstructed standings retain their cutoff and replay metadata in saved tables", () => {
  const value = impact();
  value.standings_basis = "completed_results_snapshot";
  value.standings_as_of = "2026-10-23T21:00:00Z";
  value.simulated_started_games = 2;
  saveImpactSnapshot(context(), value);
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(context())), context()), value);
});

test("unknown or incomplete reconstructed standings metadata is rejected", () => {
  const missing = { ...impact(), standings_basis: "completed_results_snapshot" };
  assert.equal(validImpact(missing, context()), false);
  assert.equal(validImpact({ ...impact(), standings_basis: "live" }, context()), false);
  for (const metadata of [
    { standings_as_of: "invalid", simulated_started_games: 2 },
    { standings_as_of: "2027-01-01T00:00:00Z", simulated_started_games: 2 },
    { standings_as_of: "2026-10-23T21:00:00Z", simulated_started_games: -1 },
    { standings_as_of: "2026-10-23T21:00:00Z", simulated_started_games: 11 },
  ]) {
    assert.equal(validImpact({ ...missing, ...metadata }, context()), false);
  }
});

test("corrupt JSON, unsupported versions, and missing envelopes are ignored", () => {
  for (const raw of ["{", "null", "[]", "{}", JSON.stringify(impact()), envelope(impact(), 2)]) {
    assert.equal(parseImpactSnapshot(raw, context()), null);
  }
});

test("cache keys isolate API base, season, game, model, target, and both teams", () => {
  const ctx = context();
  const differences: Partial<ImpactContext>[] = [
    { apiBase: "https://other.example.test" }, { season: 2028 }, { gameId: 101 },
    { modelVersion: "model-two" }, { topN: 2 }, { homeId: "different-home" },
    { awayId: "different-away" }, { homeId: "away", awayId: "home" },
  ];
  saveImpactSnapshot(ctx, impact(ctx));
  for (const difference of differences) {
    const other = context(difference);
    assert.notEqual(impactSnapshotKey(other), impactSnapshotKey(ctx));
    assert.equal(readStoredImpact(impactSnapshotKey(other)), "");
    // Responses contain neither API identity nor explicit home/away IDs; the
    // lookup key, rather than the response body, isolates API and reversed sides.
    const reversedSides = difference.homeId === ctx.awayId && difference.awayId === ctx.homeId;
    if (!difference.apiBase && !reversedSides) assert.equal(parseImpactSnapshot(envelope(impact(ctx)), other), null);
  }
});

const invalidMutations: [string, (value: ImpactResponse) => void][] = [
  ["NaN expected points", value => { value.baseline[0].expected_points = NaN; }],
  ["infinite expected rank", value => { value.baseline[0].expected_rank = Infinity; }],
  ["negative current points", value => { value.baseline[0].current_points = -1; }],
  ["rank outside table", value => { value.baseline[0].expected_rank = 3; }],
  ["probability above one", value => { value.baseline[0].top_n_upper = 1.1; }],
  ["reversed probability bounds", value => { value.baseline[0].top_n_lower = 0.8; }],
  ["duplicate baseline team", value => { value.baseline[1] = { ...value.baseline[0] }; }],
  ["missing baseline", value => { value.baseline = []; }],
  ["missing scenario", value => { value.scenarios.pop(); }],
  ["duplicate outcome", value => { value.scenarios[1].outcome = value.scenarios[0].outcome; }],
  ["wrong points award", value => { value.scenarios[0].home_points = 2; }],
  ["missing scenario team", value => { value.scenarios[0].teams.pop(); }],
  ["duplicate scenario team", value => { value.scenarios[0].teams[1] = { ...value.scenarios[0].teams[0] }; }],
  ["unexpected scenario team", value => { value.scenarios[0].teams[0].team_id = "outsider"; }],
  ["invalid scenario delta", value => { value.scenarios[0].teams[0].delta_rank = NaN; }],
  ["invalid calculation timestamp", value => { value.generated_at = "yesterday"; }],
  ["zero simulations", value => { value.simulations = 0; }],
  ["invalid Monte Carlo margin", value => { value.max_mc_margin_95 = Infinity; }],
];

for (const [name, mutate] of invalidMutations) {
  test(`invalid snapshot is rejected: ${name}`, () => {
    const value = impact(); mutate(value);
    assert.equal(validImpact(value, context()), false);
    assert.equal(parseImpactSnapshot(envelope(value), context()), null);
    saveImpactSnapshot(context(), value);
    assert.equal(readStoredImpact(impactSnapshotKey(context())), "");
  });
}

test("denied reads and writes retain the new snapshot in memory", () => {
  browser.localStorage.denyRead = true;
  browser.localStorage.denyWrite = true;
  assert.equal(readStoredImpact(impactSnapshotKey(context())), "");
  assert.doesNotThrow(() => saveImpactSnapshot(context(), impact()));
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(context())), context()), impact());
});

test("quota failure after reading the index does not lose the in-memory snapshot", () => {
  browser.localStorage.denyWrite = true;
  saveImpactSnapshot(context(), impact());
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(context())), context()), impact());
});

test("storage reads restore a validated table after in-memory invalidation", () => {
  const ctx = context();
  browser.localStorage.setItem(impactSnapshotKey(ctx), envelope(impact(ctx)));
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(ctx)), ctx), impact(ctx));
});

test("saving more than twenty snapshots evicts the oldest memory and storage entry", () => {
  for (let gameId = 100; gameId <= 120; gameId++) {
    const ctx = context({ gameId }); saveImpactSnapshot(ctx, impact(ctx));
  }
  assert.equal(readStoredImpact(impactSnapshotKey(context({ gameId: 100 }))), "");
  assert.equal(browser.localStorage.getItem(impactSnapshotKey(context({ gameId: 100 }))), null);
  for (let gameId = 101; gameId <= 120; gameId++) {
    const ctx = context({ gameId });
    assert.ok(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(ctx)), ctx));
  }
});

test("saving an existing snapshot refreshes it without consuming an extra slot", () => {
  const ctx = context(); saveImpactSnapshot(ctx, impact(ctx));
  const updated = impact(ctx); updated.generated_at = "2026-10-24T13:05:00Z";
  saveImpactSnapshot(ctx, updated);
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(impactSnapshotKey(ctx)), ctx), updated);
  assert.equal([...browser.localStorage.entries.keys()].filter(key => key.startsWith("localsportsreel:impact:v1:")).length, 1);
});

test("same-tab saves and other-tab storage changes notify subscribers", () => {
  let changes = 0;
  const unsubscribe = subscribeImpactSnapshots(() => { changes++; });
  const ctx = context(), key = impactSnapshotKey(ctx);
  saveImpactSnapshot(ctx, impact(ctx));
  assert.equal(changes, 1);
  const updated = impact(ctx); updated.generated_at = "2026-10-24T13:10:00Z";
  browser.localStorage.setItem(key, envelope(updated));
  storageEvent(key);
  assert.equal(changes, 2);
  assert.deepEqual(parseImpactSnapshot(readStoredImpact(key), ctx), updated);
  storageEvent("unrelated-key"); assert.equal(changes, 2);
  browser.localStorage.clear(); storageEvent(null);
  assert.equal(changes, 3); assert.equal(readStoredImpact(key), "");
  unsubscribe();
  storageEvent(key); assert.equal(changes, 3);
});
