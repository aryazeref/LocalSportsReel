// Contracts shared by the Next.js Fan Companion screen and FastAPI's /api/companion routes.
// Numeric forecasts come exclusively from the existing prediction service.
export type CompanionTeam = { id: string; name: string; city: string };
export type TeamsResponse = {
  season: number;
  source: string;
  as_of: string;
  data_mode: "real";
  teams: CompanionTeam[];
};
export type FactReceipt = {
  id: string;
  label: string;
  value: string;
  source: string;
};
export type CompanionForecast = {
  game_id: number;
  season: number;
  home_team: string;
  away_team: string;
  home_win: number;
  away_win: number;
  model: string;
  warnings: string[];
};
export type CompanionImpact = {
  game_id: number;
  model: string;
  scope: "regular_season_points";
  top_n: number;
  outcomes: {
    outcome: string;
    expected_points: number;
    delta_points: number;
    expected_rank: number;
  }[];
  limitations: string[];
  warnings: string[];
};
export type CompanionReply = {
  kind: "chat" | "brief" | "podcast";
  text: string;
  engine: string;
  verification_status: "verified" | "corrected" | "redacted";
  numbers_checked: number;
  receipts: FactReceipt[];
  team_id: string;
  team_name: string;
  data_source: string;
  data_as_of: string;
  is_mock: boolean;
  forecast: CompanionForecast | null;
  forecast_warning: string | null;
  impact: CompanionImpact | null;
  impact_warning: string | null;
  model_note: string;
};
export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  reply?: CompanionReply;
};
