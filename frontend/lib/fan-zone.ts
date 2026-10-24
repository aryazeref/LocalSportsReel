/**
 * Fan Zone demo persistence.
 *
 * Each discussion is keyed by (ending season, Liiga game ID). Liiga can reuse
 * numeric game IDs between seasons, so using only game ID would mix discussions.
 * This is deliberately browser-local: it is NOT a multi-user comment service.
 */
export type FanComment = {
  id: string;
  author: string;
  message: string;
  createdAt: string;
};

export const MAX_FAN_COMMENTS = 40;
const PREFIX = "localsportsreel:fan-zone:comments:v1";

export function fanCommentsKey(season: number, gameId: number): string {
  if (!Number.isSafeInteger(season) || season < 2000 || !Number.isSafeInteger(gameId) || gameId < 0) {
    throw new Error("A valid season and game ID are required.");
  }
  return PREFIX + ":" + season + ":" + gameId;
}

/** Treat localStorage like untrusted input: users/extensions can modify it. */
export function parseFanComments(raw: string | null): FanComment[] {
  if (!raw || raw.length > 250_000) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is FanComment => {
      if (!item || typeof item !== "object") return false;
      const value = item as Record<string, unknown>;
      return typeof value.id === "string" && value.id.length > 0 && value.id.length <= 100
        && typeof value.author === "string" && value.author.trim().length > 0 && value.author.length <= 40
        && typeof value.message === "string" && value.message.trim().length > 0 && value.message.length <= 500
        && typeof value.createdAt === "string" && value.createdAt.length <= 50
        && !Number.isNaN(Date.parse(value.createdAt));
    }).slice(-MAX_FAN_COMMENTS);
  } catch {
    return [];
  }
}

export function readFanComments(season: number, gameId: number): FanComment[] {
  if (typeof window === "undefined") return [];
  try {
    return parseFanComments(window.localStorage.getItem(fanCommentsKey(season, gameId)));
  } catch {
    // Browsers may disable storage, or private-mode quotas may be exhausted.
    return [];
  }
}

export function writeFanComments(season: number, gameId: number, comments: FanComment[]): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(fanCommentsKey(season, gameId),
      JSON.stringify(comments.slice(-MAX_FAN_COMMENTS)));
    return true;
  } catch {
    return false;
  }
}
