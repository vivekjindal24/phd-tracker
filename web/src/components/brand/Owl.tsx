"use client";

import { useId } from "react";
import "./owl.css";

export type OwlPose = "idle" | "reading" | "sleeping" | "cheering" | "empty";

/** The Anveshan mascot (DESIGN_SYSTEM.md §2). Decorative unless `label` is given. */
export function Owl({
  pose = "idle",
  size = 160,
  label,
}: {
  pose?: OwlPose;
  size?: number;
  label?: string;
}) {
  const id = useId().replace(/:/g, "");
  const body = `owl-body-${id}`;
  const soft = `owl-soft-${id}`;
  const wingsUp = pose === "cheering";
  const eyesClosed = pose === "sleeping";
  return (
    <svg
      className={`owl owl-${pose}`}
      viewBox="0 0 200 220"
      width={size}
      height={size * 1.1}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <radialGradient id={body} cx="35%" cy="28%" r="80%">
          <stop offset="0" stopColor="#fff" stopOpacity=".45" />
          <stop offset=".45" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".18" />
        </radialGradient>
        <radialGradient id={soft} cx="35%" cy="30%" r="75%">
          <stop offset="0" stopColor="#fff" stopOpacity=".55" />
          <stop offset=".6" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".12" />
        </radialGradient>
      </defs>
      <ellipse cx="100" cy="210" rx="58" ry="8" fill="#000" opacity=".12" />
      <g className="owl-bob">
        <ellipse cx="80" cy="200" rx="13" ry="7" fill="var(--owl-beak)" />
        <ellipse cx="120" cy="200" rx="13" ry="7" fill="var(--owl-beak)" />
        {wingsUp ? (
          <g>
            {[
              [34, -35],
              [166, 35],
            ].map(([cx, deg]) => (
              <g key={cx} transform={`rotate(${deg} ${cx} 92)`}>
                <ellipse cx={cx} cy="92" rx="18" ry="38" fill="var(--owl-body)" />
                <ellipse cx={cx} cy="92" rx="18" ry="38" fill={`url(#${soft})`} />
              </g>
            ))}
          </g>
        ) : (
          <g>
            {[
              [42, 12],
              [158, -12],
            ].map(([cx, deg]) => (
              <g key={cx} transform={`rotate(${deg} ${cx} 140)`}>
                <ellipse cx={cx} cy="140" rx="20" ry="38" fill="var(--owl-body)" />
                <ellipse cx={cx} cy="140" rx="20" ry="38" fill={`url(#${soft})`} />
              </g>
            ))}
          </g>
        )}
        <ellipse cx="100" cy="128" rx="64" ry="74" fill="var(--owl-body)" />
        <ellipse cx="100" cy="128" rx="64" ry="74" fill={`url(#${body})`} />
        <ellipse cx="100" cy="150" rx="40" ry="44" fill="var(--owl-belly)" />
        <ellipse cx="100" cy="150" rx="40" ry="44" fill={`url(#${soft})`} />
        <path
          d="M86 140q7 6 14 0q7 6 14 0M80 158q10 7 20 0q10 7 20 0M88 176q6 5 12 0q6 5 12 0"
          fill="none"
          stroke="var(--owl-body)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity=".7"
        />
        <circle cx="76" cy="100" r="24" fill="#fff8f0" />
        <circle cx="124" cy="100" r="24" fill="#fff8f0" />
        <circle cx="76" cy="100" r="24" fill={`url(#${soft})`} />
        <circle cx="124" cy="100" r="24" fill={`url(#${soft})`} />
        {eyesClosed ? (
          <g fill="none" stroke="#3d2c2e" strokeWidth="4" strokeLinecap="round">
            <path d="M64 104q12 9 24 0" />
            <path d="M112 104q12 9 24 0" />
          </g>
        ) : (
          <g className="owl-pupils">
            <circle cx="79" cy="102" r="11" fill="#3d2c2e" />
            <circle cx="121" cy="102" r="11" fill="#3d2c2e" />
            <circle cx="83" cy="97" r="4" fill="#fff" />
            <circle cx="125" cy="97" r="4" fill="#fff" />
          </g>
        )}
        <circle cx="58" cy="122" r="7" fill="#f4a28c" opacity=".65" />
        <circle cx="142" cy="122" r="7" fill="#f4a28c" opacity=".65" />
        <path d="M92 116q8 18 16 0q-8-5-16 0z" fill="var(--owl-beak)" />
        {pose === "reading" && (
          <g>
            <path d="M58 168q42-14 42 4q0-18 42-4v30q-42-12-42 4q0-16-42-4z" fill="#a78bda" />
            <path d="M100 172v32" stroke="#3d2c2e" strokeWidth="2" opacity=".4" />
            <path
              d="M58 168q42-14 42 4q0-18 42-4v30q-42-12-42 4q0-16-42-4z"
              fill={`url(#${soft})`}
            />
          </g>
        )}
        <path d="M100 30l64 20-64 20-64-20z" fill="var(--owl-cap)" />
        <path d="M70 60v14q30 14 60 0V60l-30 10z" fill="var(--owl-cap)" />
        <path d="M100 30l64 20-64 20-64-20z" fill={`url(#${soft})`} opacity=".7" />
        <path d="M100 50L152 56v26" fill="none" stroke="#f2cc8f" strokeWidth="3" strokeLinecap="round" />
        <ellipse cx="152" cy="86" rx="6" ry="9" fill="#f2cc8f" />
        <circle cx="100" cy="50" r="5" fill="#f2cc8f" />
      </g>
      {eyesClosed && (
        <g className="owl-zzz" fontFamily="Georgia, serif" fontWeight="700" fill="var(--ink-soft)">
          <text x="150" y="40" fontSize="18">z</text>
          <text x="162" y="24" fontSize="14">z</text>
          <text x="172" y="10" fontSize="11">z</text>
        </g>
      )}
    </svg>
  );
}

/** The owl-face logo mark; the same drawing ships as app/icon.svg (favicon). */
export function OwlMark({ size = 42 }: { size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <circle cx="32" cy="32" r="30" fill="var(--butter)" />
      <ellipse cx="32" cy="38" rx="19" ry="17" fill="var(--owl-body)" />
      <circle cx="25" cy="36" r="7" fill="#fff8f0" />
      <circle cx="39" cy="36" r="7" fill="#fff8f0" />
      <circle cx="26" cy="37" r="3.4" fill="#3d2c2e" />
      <circle cx="38" cy="37" r="3.4" fill="#3d2c2e" />
      <path d="M30 42q2 5 4 0z" fill="var(--owl-beak)" />
      <path d="M32 12l20 6-20 6-20-6z" fill="var(--owl-cap)" />
      <path d="M23 21v4q9 4 18 0v-4l-9 3z" fill="var(--owl-cap)" />
      <path d="M32 18l15 2v8" fill="none" stroke="#f2cc8f" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
