/**
 * /api/liiga/discover is sourced from the same Liiga snapshot as /liiga.
 * Unlike the older demo /api/feed, Liiga records contain real match facts,
 * not fictional athletes, nearby distances, or authorized reel video URLs.
 */
export type DiscoveryTeam = {
  name: string;
  team_id: string | null;
  goals: number | null;
  logo_url: string | null;
};
export type DiscoveryGoal = {
  team_side: "home" | "away";
  scorer: string;
  period: number | null;
  game_time_seconds: number | null;
  has_video: boolean;
};
export type DiscoveryGame = {
  id: number;
  season: number;
  start: string;
  status: "upcoming" | "live" | "finished" | "cancelled";
  home_team: DiscoveryTeam;
  away_team: DiscoveryTeam;
  venue: string | null;
  city: string | null;
  goal_events: DiscoveryGoal[];
};
export type DiscoveryResponse = {
  source: "Liiga Stats API v1";
  data_mode: "real";
  season: number;
  updated_at: string;
  games_in_dataset: number;
  selected_city: string | null;
  cities: string[];
  live: DiscoveryGame[];
  recent: DiscoveryGame[];
  upcoming: DiscoveryGame[];
};
export function isDiscoveryResponse(value: unknown): value is DiscoveryResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Partial<DiscoveryResponse>;
  return response.data_mode === "real"
    && typeof response.season === "number"
    && typeof response.updated_at === "string"
    && Array.isArray(response.cities)
    && response.cities.every(city => typeof city === "string")
    && ["live", "recent", "upcoming"].every(key =>
      Array.isArray(response[key as "live" | "recent" | "upcoming"])
      && (response[key as "live" | "recent" | "upcoming"] ?? []).every(game =>
        typeof game.id === "number"
        && typeof game.start === "string"
        && typeof game.home_team?.name === "string"
        && typeof game.away_team?.name === "string"));
}
