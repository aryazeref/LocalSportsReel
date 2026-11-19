"use client";

/* eslint-disable @next/next/no-img-element -- User-selected local blob previews cannot use Next image optimization. */

import { useEffect, useRef, useState } from "react";
import type { FormEvent, ChangeEvent } from "react";
import {
  MAX_FAN_COMMENTS, type FanComment, readFanComments, writeFanComments,
} from "../lib/fan-zone";
import styles from "./match-fan-zone.module.css";

type Props = {
  season: number;
  gameId: number;
  homeTeam: string;
  awayTeam: string;
};

type LocalPhoto = { id: string; url: string; name: string };
const MAX_PHOTOS = 4;
const MAX_IMAGE_BYTES = 3 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function friendlyTime(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Helsinki",
  }).format(new Date(value));
}

/**
 * This is a PRIVATE, local-only interaction prototype.
 *
 * Comments are stored only in localStorage on the current browser; they do not
 * reach other fans. Photos use temporary blob URLs, never leave the browser,
 * and are discarded on unmount/reload. Real posting needs auth, database,
 * consent, uploads, moderation, abuse protection and privacy controls.
 */
export default function MatchFanZone({ season, gameId, homeTeam, awayTeam }: Props) {
  // This component mounts only after a user expands a match card. The lazy
  // initializer safely reads browser storage without an SSR hydration mismatch.
  const [comments, setComments] = useState<FanComment[]>(() => readFanComments(season, gameId));
  const [author, setAuthor] = useState("");
  const [message, setMessage] = useState("");
  const [storageWarning, setStorageWarning] = useState(false);
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const [photoError, setPhotoError] = useState("");
  const photoUrls = useRef<string[]>([]);

  useEffect(() => {
    const urls = photoUrls.current;
    return () => urls.forEach(url => URL.revokeObjectURL(url));
  }, []);

  function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanAuthor = author.trim();
    const cleanMessage = message.trim();
    if (!cleanAuthor || !cleanMessage || cleanAuthor.length > 40 || cleanMessage.length > 500) return;
    const comment: FanComment = {
      id: globalThis.crypto?.randomUUID?.() ?? String(Date.now()),
      author: cleanAuthor,
      message: cleanMessage,
      createdAt: new Date().toISOString(),
    };
    const updated = [...comments, comment].slice(-MAX_FAN_COMMENTS);
    setComments(updated);
    setStorageWarning(!writeFanComments(season, gameId, updated));
    setMessage("");
  }

  function addPhoto(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    setPhotoError("");
    if (!files.length) return;
    const available = MAX_PHOTOS - photos.length;
    if (files.length > available) {
      setPhotoError("Only " + MAX_PHOTOS + " preview photos per match are supported.");
      return;
    }
    if (files.some(file => !ALLOWED_TYPES.has(file.type) || file.size > MAX_IMAGE_BYTES || file.size === 0)) {
      setPhotoError("Choose JPEG, PNG or WebP images up to 3 MB each.");
      return;
    }
    const added = files.map(file => {
      const url = URL.createObjectURL(file);
      photoUrls.current.push(url);
      return { id: url, url, name: file.name.slice(0, 80) };
    });
    setPhotos(current => [...current, ...added]);
  }

  function removePhoto(photo: LocalPhoto) {
    setPhotos(current => current.filter(item => item.id !== photo.id));
    photoUrls.current = photoUrls.current.filter(url => url !== photo.url);
    URL.revokeObjectURL(photo.url);
  }

  return (
    <section className={styles.zone} aria-label={"Fan Zone for " + homeTeam + " versus " + awayTeam}>
      <div className={styles.intro}>
        <div>
          <span className={styles.eyebrow}>MATCHDAY COMMUNITY</span>
          <h3>Fan Zone</h3>
          <p>Share a reaction or preview a matchday photo.</p>
        </div>
        <span className={styles.demoBadge}>LOCAL DEMO</span>
      </div>

      <p className={styles.notice}>
        This is a private prototype, not a public discussion. Comments stay in this browser;
        photos are temporary previews and disappear when this panel closes. No one else sees them.
      </p>

      <div className={styles.columns}>
        <section aria-label="Match comments">
          <h4>Match discussion <span>({comments.length})</span></h4>
          <form className={styles.form} onSubmit={submitComment}>
            <label htmlFor={"fan-name-" + season + "-" + gameId}>Display name</label>
            <input id={"fan-name-" + season + "-" + gameId} type="text" value={author}
              onChange={event => setAuthor(event.target.value)} maxLength={40}
              placeholder="Your display name" autoComplete="nickname" required />
            <label htmlFor={"fan-comment-" + season + "-" + gameId}>Your comment</label>
            <textarea id={"fan-comment-" + season + "-" + gameId} value={message}
              onChange={event => setMessage(event.target.value)} maxLength={500}
              rows={3} placeholder="What do you think about this matchup?" required />
            <div className={styles.formFooter}>
              <span>{message.length}/500</span>
              <button type="submit" disabled={!author.trim() || !message.trim()}>Add local comment</button>
            </div>
          </form>
          {storageWarning && <p className={styles.warning} role="alert">
            Browser storage is unavailable. This comment will disappear when the panel closes.
          </p>}
          {comments.length === 0 ? (
            <p className={styles.empty}>No comments on this device yet. Start the conversation.</p>
          ) : (
            <ol className={styles.comments}>
              {[...comments].reverse().map(comment => (
                <li key={comment.id} className={styles.comment}>
                  <div className={styles.commentHeading}>
                    <strong>{comment.author}</strong>
                    <time dateTime={comment.createdAt}>{friendlyTime(comment.createdAt)}</time>
                  </div>
                  <p>{comment.message}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
        <section aria-label="Fan photo wall">
          <h4>Fan Wall <span>({photos.length}/{MAX_PHOTOS})</span></h4>
          <p className={styles.help}>Choose a stadium selfie, crowd photo or fan moment.
            Previews are never uploaded or published.</p>
          <label className={styles.upload}>
            <span aria-hidden="true">＋</span> Preview your photos
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple
              onChange={addPhoto} disabled={photos.length >= MAX_PHOTOS} />
          </label>
          {photoError && <p className={styles.warning} role="alert">{photoError}</p>}
          {photos.length === 0 ? (
            <div className={styles.photoEmpty}>Your local photo previews will appear here.</div>
          ) : (
            <ul className={styles.gallery}>
              {photos.map(photo => (
                <li key={photo.id}>
                  <img src={photo.url} alt={"Local preview: " + photo.name} />
                  <button type="button" onClick={() => removePhoto(photo)}
                    aria-label={"Remove preview " + photo.name}>Remove</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}
