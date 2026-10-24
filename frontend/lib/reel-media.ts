/**
 * Curated rights-approved video references, never scraped from Liiga API.
 *
 * Add an entry ONLY when you own the clip or have explicit permission to
 * publish it in this website. Put MP4/WebM assets in frontend/public/reels/
 * and document permission/source outside this code. Use exact stable reel
 * IDs shown in /api/liiga/discover goal and match events.
 *
 * Example only (no default or fake video is shipped):
 *   "2027:12345:goal:0": "/reels/approved-goal.webm"
 *
 * This mapping is deliberately empty until rights-cleared footage exists.
 * Avoid linking to provider videoClipUrl merely because it was exposed.
 */
const approved: Record<string, string> = {};

export function approvedReelVideo(reelId: string): string | null {
  const url = approved[reelId];
  // Reject external media, path traversal and untrusted URL schemes.
  if (!url || !/^\/reels\/[a-zA-Z0-9_/-]+\.(mp4|webm)$/.test(url) || url.includes(".."))
    return null;
  return url;
}
