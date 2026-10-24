// These shapes reflect the Pydantic API models in backend/app/models.py.
// TypeScript catches mistakes during development; Python validates at runtime.
export type Fact = { id: string; text: string; source_id: string };

export type Moment = {
  id: string;
  city: string;
  happened_at: string;
  sport: string;
  league: string;
  team: string;
  athlete: string;
  title: string;
  moment_type: string;
  score: string;
  excitement: number;
  distance_km: number;
  relevance_score: number;
  source_label: string;
  facts: Fact[];
  demo: boolean;
  video_url: string | null;
  video_authorized: boolean;
};

export type FeedResponse = {
  selected_city: string;
  radius_km: number;
  total: number;
  demo_data: boolean;
  moments: Moment[];
};

export type Story = {
  moment_id: string;
  headline: string;
  narration: string;
  evidence: Fact[];
  mode: "template" | "llm_draft";
  publication_status: "demo_only" | "review_required";
  disclaimer: string;
};
