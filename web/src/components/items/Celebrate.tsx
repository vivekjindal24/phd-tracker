"use client";

import { useEffect, useRef } from "react";
import { Owl } from "../brand/Owl";
import "./items.css";

const COLORS = ["#a78bda", "#6d4bc3", "#d9ccf2", "#81b29a", "#f2cc8f", "#a8cce8"];
const DURATION_MS = 1500;

/** One confetti burst + the cheering owl, only after the API confirmed an approval.
 *  Hand-rolled canvas, no dependency; nothing at all under prefers-reduced-motion. */
export function Celebrate({ onDone }: { onDone: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const el = canvas.current;
    const ctx = el?.getContext("2d");
    if (reduced || !el || !ctx) {
      const t = setTimeout(onDone, 2500);
      return () => clearTimeout(t);
    }
    const dpr = window.devicePixelRatio || 1;
    el.width = window.innerWidth * dpr;
    el.height = window.innerHeight * dpr;
    ctx.scale(dpr, dpr);
    const parts = Array.from({ length: 140 }, () => ({
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
    const t = setTimeout(onDone, 2600);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(t);
    };
  }, [onDone]);

  return (
    <>
      <canvas ref={canvas} className="confetti" aria-hidden="true" />
      <div className="celebrate clay" role="status">
        <Owl pose="cheering" size={72} />
        <strong>Approved! 🎓</strong>
      </div>
    </>
  );
}
