// Contracts shared by the Next.js Fan Companion screen and FastAPI's /api/companion routes.
// Numeric forecasts come exclusively from the existing prediction service.
export type CompanionAiStatus = {
  available: boolean;
  provider: string | null;
  message: string;
};
export type CompanionTeam = { id: string; name: string; city: string };
export type CompanionSuggestion = { label: string; question: string };
export type CompanionLocalAction =
  | { tool: "set_alert"; team_id: string; season: number; threshold: number | null }
  | { tool: "save_prediction"; team_id: string; season: number;
      game_id: string; home_team: string; away_team: string;
      home_goals: number; away_goals: number };

export type TeamsResponse = {
  season: number;
  source: string;
  as_of: string;
  data_mode: "real";
  teams: CompanionTeam[];
  suggestions?: CompanionSuggestion[];
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
  generation_mode: "ai" | "offline" | "fallback";
  mode_message: string;
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
  suggestions?: CompanionSuggestion[];
  action?: CompanionLocalAction | null;
};
export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  reply?: CompanionReply;
};
