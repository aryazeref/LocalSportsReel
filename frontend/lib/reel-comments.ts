/**
 * Local-only comments for individual reels. Stable reel IDs include both
 * season and match, then goal-index or whole-match key. Two goals in one
 * match do not accidentally share a comments thread.
 *
 * This is not an authenticated public comment system. Production needs
 * user identity, server-side storage, abuse reports and moderation.
 */
export type ReelComment = {
  id: string;
  author: string;
  body: string;
  createdAt: string;
};
const PREFIX = "localsportsreel:reel-comments:v1:";
export const MAX_REEL_COMMENTS = 50;

export function reelCommentKey(reelId: string): string {
  if (!/^\d{4}:\d+:(?:goal:\d+|match)$/.test(reelId)) throw new Error("Invalid reel ID");
  return PREFIX + reelId;
}

export function parseReelComments(raw: string | null): ReelComment[] {
  if (!raw || raw.length > 120000) return [];
  try {
    const data: unknown = JSON.parse(raw);
    if (!Array.isArray(data)) return [];
    return data.filter((item): item is ReelComment => {
      if (item === null || typeof item !== "object") return false;
      const c = item as Record<string, unknown>;
      return typeof c.id === "string" && c.id.length > 0 && c.id.length <= 80
        && typeof c.author === "string" && c.author.trim().length > 0 && c.author.length <= 40
        && typeof c.body === "string" && c.body.trim().length > 0 && c.body.length <= 500
        && typeof c.createdAt === "string" && !Number.isNaN(Date.parse(c.createdAt)) && c.createdAt.length <= 50;
    }).slice(-MAX_REEL_COMMENTS);
  } catch { return []; }
}

export function readReelComments(reelId: string): ReelComment[] {
  if (typeof window === "undefined") return [];
  try { return parseReelComments(localStorage.getItem(reelCommentKey(reelId))); }
  catch { return []; }
}
export function saveReelComments(reelId: string, comments: ReelComment[]): boolean {
  if (typeof window === "undefined") return false;
  try {
    localStorage.setItem(reelCommentKey(reelId), JSON.stringify(comments.slice(-MAX_REEL_COMMENTS)));
    return true;
  } catch { return false; }
}
