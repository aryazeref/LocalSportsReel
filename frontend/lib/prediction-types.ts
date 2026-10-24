export type Outcome = "home_regulation" | "home_overtime" | "away_overtime" | "away_regulation";

export type ForecastTeam = { team_id: string; name: string };

export type Forecast = {
  game_id: number;
  season: number;
  start: string;
  home_team: ForecastTeam;
  away_team: ForecastTeam;
  probabilities: Record<Outcome, number> & { home_win: number; away_win: number };
  features: {
    names: string[];
    values: number[];
    home_history: number;
    away_history: number;
    cold_start: boolean;
    history_cutoff: string | null;
  };
  warnings: string[];
};

export type ModelMetric = {
  name: string;
  display_name?: string;
  log_loss: number;
  brier: number;
  final_winner_accuracy: number;
  selected?: boolean;
  window?: number;
  feature_set?: string;
  calibration_bins?: {
    lower: number;
    upper: number;
    count: number;
    predicted: number | null;
    observed: number | null;
  }[];
};

export type SeasonEvaluation = {
  season: number;
  start?: string;
  end?: string;
  count?: number;
  selected_model?: string;
  validation?: { start?: string; end?: string; count?: number };
  metrics?: ModelMetric[];
};

export type Evaluation = {
  selected_model?: string;
  feature_set?: string;
  window?: number;
  k?: number | null;
  validation?: { start?: string; end?: string; count?: number; candidates?: ModelMetric[] };
  test?: {
    start?: string;
    end?: string;
    count?: number;
    season?: number;
    seasons?: number[];
    kind?: string;
    independent_blind?: boolean;
    used_for_selection?: boolean;
    metrics?: ModelMetric[];
    per_season?: SeasonEvaluation[];
  };
  limitations?: string[];
  calibration_bins?: unknown[];
};

export type PredictionsResponse = {
  season: number;
  source: string;
  data_updated_at: string;
  generated_at: string;
  model: {
    name: string;
    model_version: string;
    display_name: string;
    feature_set?: string;
    window?: number;
    training_cutoff?: string;
    training_matches?: number;
    training_seasons?: number[];
    trained_at?: string;
  };
  evaluation: Evaluation;
  warnings: string[];
  fixtures: Forecast[];
};

export type Projection = {
  team_id: string;
  name: string;
  current_points: number;
  expected_points: number;
  expected_rank: number;
  top_n_lower: number;
  top_n_upper: number;
};

export type ScenarioProjection = Projection & {
  delta_points: number;
  delta_rank: number;
  delta_top_n_lower: number;
  delta_top_n_upper: number;
};

export type ImpactScenario = {
  outcome: Outcome;
  home_points: number;
  away_points: number;
  teams: ScenarioProjection[];
};

export type ImpactResponse = {
  season: number;
  game_id: number;
  generated_at: string;
  standings_updated_at: string;
  standings_basis?: "official" | "completed_results_snapshot";
  standings_as_of?: string | null;
  simulated_started_games?: number;
  model_name: string;
  model_version: string;
  forecast_cutoff: string;
  scope: "regular_season_points";
  warnings: string[];
  simulations: number;
  seed: number;
  top_n: number;
  remaining_fixtures: number;
  max_mc_margin_95: number;
  baseline: Projection[];
  scenarios: ImpactScenario[];
  limitations: string[];
};
