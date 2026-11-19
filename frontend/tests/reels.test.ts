import assert from "node:assert/strict";
import test from "node:test";
import type { DiscoveryResponse, DiscoveryGame } from "../lib/liiga-discovery";
import { reelScore, reelsFromGames } from "../lib/reel-feed";
import { approvedReelVideo } from "../lib/reel-media";
import { parseReelComments, reelCommentKey } from "../lib/reel-comments";

function game(id: number, goals: DiscoveryGame["goal_events"]): DiscoveryGame {
  return {
    id, season: 2027, start: "2026-10-21T17:30:00+03:00", status: "finished",
    home_team: { name: "Kärpät", team_id: "1", goals: 4, logo_url: null },
    away_team: { name: "JYP", team_id: "2", goals: 1, logo_url: null },
    city: "Oulu", venue: "Oulun Energia Areena", goal_events: goals,
  };
}
const response: DiscoveryResponse = {
  source: "Liiga Stats API v1", data_mode: "real", season: 2027,
  updated_at: "2026-10-24T10:00:00+00:00", games_in_dataset: 2,
  selected_city: null, cities: ["Oulu"], live: [], upcoming: [],
  recent: [
    game(12, [
      { scorer: "Scorer One", team_side: "home", period: 3, game_time_seconds: 3200, has_video: true },
      { scorer: "Scorer Two", team_side: "away", period: 2, game_time_seconds: 1800, has_video: false },
    ]),
    game(11, []),
  ],
};

test("each real goal gets a distinct reel and clip-specific comment key", () => {
  const reels = reelsFromGames(response);
  assert.deepEqual(reels.map(reel => reel.id), ["2027:12:goal:0", "2027:12:goal:1", "2027:11:match"]);
  assert.equal(reels[0].title, "Scorer One's goal");
  assert.equal(reels[0].kind, "goal");
  assert.equal(reels[0].homeTeam, "Kärpät");
  assert.equal(reelScore(reels[0]), "4–1");
  assert.notEqual(reelCommentKey(reels[0].id), reelCommentKey(reels[1].id));
});

test("a has_video flag is not a license to serve footage", () => {
  const first = reelsFromGames(response)[0];
  assert.equal(response.recent[0].goal_events[0].has_video, true);
  assert.equal(first.videoSrc, null);
  assert.equal(approvedReelVideo(first.id), null);
});

test("missing goal data is a factual match recap, not an invented scorer", () => {
  const match = reelsFromGames(response)[2];
  assert.equal(match.kind, "match");
  assert.equal(match.title, "Kärpät vs JYP");
  assert.equal(match.videoSrc, null);
  assert.deepEqual(reelsFromGames(response, 2).map(item => item.id), [
    "2027:12:goal:0", "2027:12:goal:1",
  ]);
});

test("comment storage only accepts bounded, well-formed plain text", () => {
  const good = [{ id: "comment1", author: "Fan", body: "<script>plain user text</script>",
    createdAt: "2026-10-24T20:00:00.000Z" }];
  assert.deepEqual(parseReelComments(JSON.stringify(good)), good);
  assert.deepEqual(parseReelComments("broken json"), []);
  assert.deepEqual(parseReelComments(JSON.stringify([{ ...good[0], body: "x".repeat(501) }])), []);
  assert.throws(() => reelCommentKey("../../../secret"));
});
