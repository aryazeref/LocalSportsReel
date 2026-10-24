import type { ImpactResponse, Projection } from "./prediction-types";

export type ImpactContext = {
  apiBase: string; season: number; gameId: number; homeId: string; awayId: string;
  modelVersion: string; topN: number;
};

const PREFIX = "localsportsreel:impact:v1:";
const INDEX = "localsportsreel:impact-index:v1";
const CHANGE = "localsportsreel:impact-saved";
const LIMIT = 20;
const memory = new Map<string, string>();
const outcomes = ["home_regulation", "home_overtime", "away_overtime", "away_regulation"];
const awards = [[3, 0], [2, 1], [1, 2], [0, 3]];

export function impactSnapshotKey(context: ImpactContext): string {
  return PREFIX + JSON.stringify([context.apiBase, context.season, context.gameId,
    context.homeId, context.awayId, context.modelVersion, context.topN]);
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function integer(value: unknown, minimum: number): value is number {
  return finite(value) && Number.isInteger(value) && value >= minimum;
}
function timestamp(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}
function projection(value: unknown, teamCount: number): value is Projection {
  return object(value) && typeof value.team_id === "string" && Boolean(value.team_id)
    && typeof value.name === "string" && integer(value.current_points, 0)
    && finite(value.expected_points) && value.expected_points >= 0
    && finite(value.expected_rank) && value.expected_rank >= 1 && value.expected_rank <= teamCount
    && finite(value.top_n_lower) && finite(value.top_n_upper)
    && value.top_n_lower >= 0 && value.top_n_upper <= 1 && value.top_n_lower <= value.top_n_upper;
}

// Persisted browser data is untrusted. Check the complete table before allowing
// it to replace an unavailable response, including all four scenarios and teams.
export function validImpact(value: unknown, context: ImpactContext): value is ImpactResponse {
  if (!object(value) || value.season !== context.season || value.game_id !== context.gameId
    || value.top_n !== context.topN || value.model_version !== context.modelVersion
    || value.scope !== "regular_season_points" || typeof value.model_name !== "string"
    || !timestamp(value.generated_at) || !timestamp(value.standings_updated_at)
    || !timestamp(value.forecast_cutoff) || !strings(value.warnings) || !strings(value.limitations)
    || !integer(value.simulations, 1) || !integer(value.seed, 0) || !integer(value.remaining_fixtures, 1)
    || !finite(value.max_mc_margin_95) || value.max_mc_margin_95 < 0 || value.max_mc_margin_95 > 1
    || !Array.isArray(value.baseline) || !value.baseline.length || !Array.isArray(value.scenarios)
    || value.scenarios.length !== 4 || context.topN < 1 || context.topN > value.baseline.length) return false;
  const baseline = value.baseline;
  const scenarios = value.scenarios;
  if (!baseline.every(team => projection(team, baseline.length))) return false;
  const ids = new Set(baseline.map(team => team.team_id));
  if (ids.size !== baseline.length || !ids.has(context.homeId) || !ids.has(context.awayId)) return false;
  return outcomes.every((outcome, index) => {
    const matches = scenarios.filter((scenario: unknown) => object(scenario) && scenario.outcome === outcome);
    if (matches.length !== 1) return false;
    const scenario = matches[0];
    if (scenario.home_points !== awards[index][0] || scenario.away_points !== awards[index][1]
      || !Array.isArray(scenario.teams) || scenario.teams.length !== ids.size) return false;
    const scenarioIds = new Set<string>();
    return scenario.teams.every((team: unknown) => {
      if (!projection(team, ids.size) || !ids.has(team.team_id) || scenarioIds.has(team.team_id)) return false;
      scenarioIds.add(team.team_id);
      return ["delta_points", "delta_rank", "delta_top_n_lower", "delta_top_n_upper"]
        .every(field => finite((team as unknown as Record<string, unknown>)[field]));
    });
  });
}

export function parseImpactSnapshot(raw: string, context: ImpactContext): ImpactResponse | null {
  try {
    const value: unknown = JSON.parse(raw);
    return object(value) && value.version === 1 && validImpact(value.impact, context) ? value.impact : null;
  } catch { return null; }
}

function remember(key: string, value: string) {
  memory.delete(key);
  memory.set(key, value);
  if (memory.size > LIMIT) memory.delete(memory.keys().next().value!);
}

export function readStoredImpact(key: string): string {
  if (!key || typeof window === "undefined") return "";
  const cached = memory.get(key);
  if (cached !== undefined) return cached;
  try {
    const raw = window.localStorage.getItem(key) ?? "";
    if (raw) remember(key, raw);
    return raw;
  } catch { return ""; }
}

export function saveImpactSnapshot(context: ImpactContext, impact: ImpactResponse): void {
  if (!validImpact(impact, context) || typeof window === "undefined") return;
  const key = impactSnapshotKey(context);
  const raw = JSON.stringify({ version: 1, impact });
  remember(key, raw);
  try {
    const index: unknown = JSON.parse(window.localStorage.getItem(INDEX) ?? "[]");
    const previous = Array.isArray(index) ? index.filter((item): item is string =>
      typeof item === "string" && item.startsWith(PREFIX) && item !== key) : [];
    const keys = [...new Set([...previous, key])];
    for (const old of keys.slice(0, -LIMIT)) window.localStorage.removeItem(old);
    window.localStorage.setItem(key, raw);
    window.localStorage.setItem(INDEX, JSON.stringify(keys.slice(-LIMIT)));
  } catch { /* Quota, corrupt index, or denied storage: retain the in-memory copy. */ }
  window.dispatchEvent(new Event(CHANGE));
}

export function emptyImpactSnapshot(): string { return ""; }

export function subscribeImpactSnapshots(onChange: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key !== null && !event.key.startsWith(PREFIX)) return;
    if (event.key === null) memory.clear();
    else memory.delete(event.key);
    onChange();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(CHANGE, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CHANGE, onChange);
  };
}
