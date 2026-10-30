"use client";

import { useEffect, useRef } from "react";
import { Owl } from "./brand/Owl";
import "./celebrate.css";

const COLORS = ["#a78bda", "#6d4bc3", "#d9ccf2", "#81b29a", "#f2cc8f", "#a8cce8"];
const DURATION_MS = 1500;
const FULL_PARTS = 140;
const SMALL_PARTS = 45;

/** True only the first time this browser asks for `key` — a celebration fires once per event. */
export function firstTime(key: string): boolean {
  try {
    if (localStorage.getItem(`anveshan.celebrated.${key}`)) return false;
    localStorage.setItem(`anveshan.celebrated.${key}`, "1");
    return true;
  } catch {
    return false; // storage blocked: skip the celebration rather than repeat it
  }
}

/** One confetti burst, only after the API confirmed the event. With a message it is the full
 *  burst plus the cheering owl; without, a small burst (a mid-chain approve).
 *  Hand-rolled canvas, no dependency; no confetti under prefers-reduced-motion. */
export function Celebrate({ message, onDone }: { message?: string; onDone: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  // A ref, so a parent re-render (a fresh onDone) does not restart the burst.
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    const finish = () => done.current();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const el = canvas.current;
    const ctx = el?.getContext("2d");
    if (reduced || !el || !ctx) {
      const t = setTimeout(finish, 2500);
      return () => clearTimeout(t);
    }
    const dpr = window.devicePixelRatio || 1;
    el.width = window.innerWidth * dpr;
    el.height = window.innerHeight * dpr;
    ctx.scale(dpr, dpr);
    const parts = Array.from({ length: message ? FULL_PARTS : SMALL_PARTS }, () => ({
      x: window.innerWidth / 2 + (Math.random() - 0.5) * 160,
      y: window.innerHeight * 0.55,
      vx: (Math.random() - 0.5) * 14,
      vy: -Math.random() * 16 - 6,
      r: Math.random() * 6 + 4,
      c: COLORS[Math.floor(Math.random() * COLORS.length)] ?? COLORS[0]!,
      a: Math.random() * 6,
      va: (Math.random() - 0.5) * 0.3,
    }));
    const start = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      const life = (now - start) / DURATION_MS;
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      if (life >= 1) return;
      ctx.globalAlpha = 1 - life * life;
      for (const p of parts) {
        p.vy += 0.45;
        p.x += p.vx;
        p.y += p.vy;
        p.a += p.va;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.a);
        ctx.fillStyle = p.c;
        ctx.beginPath();
        ctx.roundRect(-p.r, -p.r / 2, p.r * 2, p.r, p.r / 2);
        ctx.fill();
        ctx.restore();
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    const t = setTimeout(finish, message ? 2600 : DURATION_MS);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(t);
    };
  }, [message]);

  return (
    <>
      <canvas ref={canvas} className="confetti" aria-hidden="true" />
      {message && (
        <div className="celebrate clay" role="status">
          <Owl pose="cheering" size={72} />
          <strong>{message}</strong>
        </div>
      )}
    </>
  );
}
