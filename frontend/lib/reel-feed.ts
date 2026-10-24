/**
 * Adapt real Liiga match/goal metadata into a reel queue.
 *
 * Video rights and video files are a separate layer. A goal marker or a
 * provider's "has_video" boolean is NOT permission to re-publish the clip.
 */
import type { DiscoveryGame, DiscoveryResponse } from "./liiga-discovery";
import { approvedReelVideo } from "./reel-media";

export type Reel = {
  id: string;
  gameId: number;
  season: number;
  start: string;
  city: string | null;
  venue: string | null;
  homeTeam: string;
  awayTeam: string;
  homeGoals: number | null;
  awayGoals: number | null;
  kind: "goal" | "match";
  title: string;
  subtitle: string;
  videoSrc: string | null;
};

export function reelsFromGames(response: DiscoveryResponse, maxReels = 18): Reel[] {
  const all: Reel[] = [];
  // Prefer recent completed match goals. A recent finished match without
  // goal-level data gets a factual match recap placeholder, NOT a made-up goal.
  for (const game of response.recent) {
    const common = {
      gameId: game.id, season: game.season, start: game.start, city: game.city,
      venue: game.venue, homeTeam: game.home_team.name, awayTeam: game.away_team.name,
      homeGoals: game.home_team.goals, awayGoals: game.away_team.goals,
    };
    const goals = game.goal_events
      .map((goal, index) => ({ goal, index }))
      .filter(({ goal }) => goal.scorer.trim() && goal.scorer !== "Unknown scorer")
      .sort((a, b) => (b.goal.game_time_seconds ?? -1) - (a.goal.game_time_seconds ?? -1))
      .slice(0, 4);
    if (goals.length) {
      for (const { goal, index } of goals) {
        const id = game.season + ":" + game.id + ":goal:" + index;
        const team = goal.team_side === "home" ? game.home_team.name : game.away_team.name;
        all.push({
          ...common, id, kind: "goal", title: goal.scorer + "'s goal",
          subtitle: team + " · " + game.home_team.name + " vs " + game.away_team.name,
          videoSrc: approvedReelVideo(id),
        });
      }
    } else {
      const id = game.season + ":" + game.id + ":match";
      all.push({
        ...common, id, kind: "match",
        title: game.home_team.name + " vs " + game.away_team.name,
        subtitle: "Match recap · Final score",
        videoSrc: approvedReelVideo(id),
      });
    }
  }
  return all.slice(0, Math.max(0, Math.min(40, maxReels)));
}

export function reelScore(reel: Reel): string {
  return reel.homeGoals == null || reel.awayGoals == null
    ? "Final score unavailable" : reel.homeGoals + "–" + reel.awayGoals;
}
