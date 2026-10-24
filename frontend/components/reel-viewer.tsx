"use client";

import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import Link from "next/link";
import type { Reel } from "../lib/reel-feed";
import { reelScore } from "../lib/reel-feed";
import {
  MAX_REEL_COMMENTS, type ReelComment, readReelComments, saveReelComments,
} from "../lib/reel-comments";
import styles from "./reel-viewer.module.css";

type Props = { reels: Reel[] };
const MAX_BYTES = 100 * 1024 * 1024;
const VIDEO_TYPES = new Set(["video/mp4", "video/webm"]);

function localDate(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium", timeZone: "Europe/Helsinki",
  }).format(date);
}

/** Every goal has a different browser-local comments thread. */
function ReelComments({ reel }: { reel: Reel }) {
  const [comments, setComments] = useState<ReelComment[]>(() => readReelComments(reel.id));
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [warning, setWarning] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const author = name.trim(), body = message.trim();
    if (!author || !body || author.length > 40 || body.length > 500) return;
    const updated = [...comments, {
      id: crypto.randomUUID(), author, body, createdAt: new Date().toISOString(),
    }].slice(-MAX_REEL_COMMENTS);
    setComments(updated);
    setWarning(saveReelComments(reel.id, updated) ? "" : "Browser storage is unavailable. This comment won't be saved.");
    setMessage("");
  }

  return <aside className={styles.comments} aria-label={"Comments for " + reel.title}>
    <div className={styles.commentsHeader}>
      <span className={styles.eyebrow}>FAN REACTIONS</span>
      <h3>Comments <small>({comments.length})</small></h3>
      <p>Talk about this specific goal or match.</p>
    </div>
    <div className={styles.commentList} aria-live="polite">
      {comments.length === 0 ? <p className={styles.noComments}>
        No comments on this device yet. What did you think of this moment?
      </p> : [...comments].reverse().map(item => <article className={styles.comment} key={item.id}>
        <div className={styles.commentTop}>
          <strong>{item.author}</strong>
          <time dateTime={item.createdAt}>{localDate(item.createdAt)}</time>
        </div>
        <p>{item.body}</p>
      </article>)}
    </div>
    <form onSubmit={submit} className={styles.commentForm}>
      <label htmlFor={"reel-name-" + reel.id}>Display name</label>
      <input id={"reel-name-" + reel.id} autoComplete="nickname" maxLength={40} required
        value={name} placeholder="Your name"
        onChange={event => setName(event.target.value)} />
      <label htmlFor={"reel-text-" + reel.id}>Your reaction</label>
      <textarea id={"reel-text-" + reel.id} rows={3} maxLength={500} required
        value={message} placeholder="What a goal! …"
        onChange={event => setMessage(event.target.value)} />
      <div className={styles.submitRow}>
        <span>{message.length}/500</span>
        <button type="submit" disabled={!name.trim() || !message.trim()}>Post locally ↗</button>
      </div>
      {warning && <p role="alert" className={styles.warning}>{warning}</p>}
    </form>
    <p className={styles.privateNote}>
      <strong>Demo discussion:</strong> Comments are saved only in this browser,
      not visible to other fans. Public comments require accounts and moderation.
    </p>
  </aside>;
}

/**
 * One active reel at a time prevents every video from auto-playing.
 *
 * Users can select a local 30–60-second MP4/WebM to preview the layout.
 * File bytes never leave the browser and are discarded when the component
 * unmounts or the preview is replaced. Production video must be licensed.
 */
export default function ReelViewer({ reels }: Props) {
  const [selectedId, setSelectedId] = useState(reels[0]?.id || "");
  const activeIndex = Math.max(0, reels.findIndex(item => item.id === selectedId));
  const active = reels[activeIndex];
  const [preview, setPreview] = useState<{ reelId: string; url: string } | null>(null);
  const [videoError, setVideoError] = useState("");
  const blobUrl = useRef<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => { if (blobUrl.current) URL.revokeObjectURL(blobUrl.current); };
  }, []);

  if (!active) return <p className={styles.empty}>No recent goal or match reels are available yet.</p>;

  function choose(next: number) {
    const target = reels[Math.max(0, Math.min(reels.length - 1, next))];
    if (!target) return;
    setSelectedId(target.id);
    setVideoError("");
  }

  function onKeyboard(event: KeyboardEvent<HTMLElement>) {
    const tag = (event.target as HTMLElement).tagName;
    if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "VIDEO"].includes(tag)) return;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      choose(activeIndex + 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      choose(activeIndex - 1);
    }
  }

  function addPreview(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!VIDEO_TYPES.has(file.type) || file.size === 0 || file.size > MAX_BYTES) {
      setVideoError("Use an MP4 or WebM clip up to 100 MB.");
      return;
    }
    if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
    const url = URL.createObjectURL(file);
    blobUrl.current = url;
    setVideoError("");
    setPreview({ reelId: active.id, url });
  }

  function validateDuration(event: React.SyntheticEvent<HTMLVideoElement>) {
    if (!(preview?.reelId === active.id)) return;
    const duration = event.currentTarget.duration;
    if (!Number.isFinite(duration) || duration < 30 || duration > 60) {
      setVideoError("Please choose a 30–60-second video. This preview doesn't trim files.");
      setPreview(null);
      if (blobUrl.current) {
        URL.revokeObjectURL(blobUrl.current);
        blobUrl.current = null;
      }
    }
  }

  const videoSrc = preview?.reelId === active.id ? preview.url : active.videoSrc;
  return <section className={styles.reels} aria-label="Hockey reel player" onKeyDown={onKeyboard}>
    <div className={styles.toolbar}>
      <div>
        <span className={styles.eyebrow}>REAL MATCH MOMENTS</span>
        <h2>Pick a reel<span>.</span></h2>
      </div>
      <p>Clip {activeIndex + 1} of {reels.length}</p>
    </div>
    <div className={styles.content}>
      <nav className={styles.playlist} aria-label="Available match reels">
        {reels.map((reel, index) => <button key={reel.id} type="button"
          className={styles.playlistItem + (reel.id === active.id ? " " + styles.activeItem : "")}
          aria-current={reel.id === active.id ? "true" : undefined}
          onClick={() => choose(index)}>
          <span className={styles.index}>{String(index + 1).padStart(2, "0")}</span>
          <span className={styles.playlistText}>
            <strong>{reel.title}</strong>
            <small>{reel.homeTeam} – {reel.awayTeam} · {reelScore(reel)}</small>
          </span>
          <span className={styles.mediaSymbol} aria-label={reel.videoSrc ? "Clip available" : "Video not connected"}>
            {reel.videoSrc ? "▶" : "○"}
          </span>
        </button>)}
      </nav>
      <div className={styles.stage}>
        <div className={styles.portrait}>
          <div className={styles.videoArea}>
            {videoSrc ? <video key={videoSrc} className={styles.video} src={videoSrc}
              controls playsInline preload="metadata" onLoadedMetadata={validateDuration}
              aria-label={"Reel video: " + active.title}>
              Your browser does not support video playback.
            </video> : <div className={styles.videoEmpty}>
              <div className={styles.rinkLines} aria-hidden="true" />
              <span className={styles.hockeyIcon} aria-hidden="true">🏒</span>
              <strong>Highlight clip not connected</strong>
              <p>Real Liiga goal information is ready. Play a rights-cleared clip here when one is available.</p>
              <label className={styles.previewUpload}>
                Preview your own 30–60s video
                <input ref={fileInput} type="file" accept="video/mp4,video/webm"
                  onChange={addPreview} aria-label="Choose a local 30 to 60 second demo video" />
              </label>
              <small>Your video stays on this device. It is not uploaded.</small>
            </div>}
          </div>
          <div className={styles.videoOverlay}>
            <span className={styles.clipTag}>{active.kind === "goal" ? "GOAL MOMENT" : "MATCH RECAP"}</span>
            <h3>{active.title}</h3>
            <p>{active.subtitle}</p>
            <div className={styles.scorePill}>{active.homeTeam} <strong>{reelScore(active)}</strong> {active.awayTeam}</div>
          </div>
        </div>
        <div className={styles.controls}>
          <button type="button" disabled={activeIndex === 0} onClick={() => choose(activeIndex - 1)}>↑ Previous</button>
          <span>{localDate(active.start)} · {active.city || "City unavailable"}</span>
          <button type="button" disabled={activeIndex === reels.length - 1}
            onClick={() => choose(activeIndex + 1)}>Next ↓</button>
        </div>
        {videoSrc && <button className={styles.replaceClip} type="button"
          onClick={() => { setVideoError(""); fileInput.current?.click(); }}>
          {preview?.reelId === active.id ? "Change local preview" : "Preview another local clip"}
        </button>}
        {videoSrc && <input className={styles.hiddenInput} ref={fileInput}
          type="file" accept="video/mp4,video/webm" onChange={addPreview}
          aria-label="Choose a different local 30 to 60 second video"/>}
        {videoError && <p role="alert" className={styles.warning}>{videoError}</p>}
        <div className={styles.moreLinks}>
          <Link href="/liiga">Match centre &amp; Fan Zone ↗</Link>
          <Link href="/predictions">Explore predictions ↗</Link>
        </div>
        <p className={styles.clipNotice}>
          Only rights-approved clips can be published. Liiga event data does not automatically
          grant footage rights. This demo does not upload user-selected videos.
        </p>
      </div>
      <ReelComments key={active.id} reel={active} />
    </div>
  </section>;
}
