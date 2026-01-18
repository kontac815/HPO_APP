import React from 'react';

import type { NormalizedSymptom } from "./types";

type SpanMark = {
  start: number;
  end: number;
  href?: string;
  title?: string;
};

function chooseNonOverlapping(spans: SpanMark[]): SpanMark[] {
  const sorted = [...spans].sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return (b.end - b.start) - (a.end - a.start);
  });

  const out: SpanMark[] = [];
  let cursor = 0;
  for (const s of sorted) {
    if (s.end <= s.start) continue;
    if (s.start < cursor) continue;
    out.push(s);
    cursor = s.end;
  }
  return out;
}

export function HighlightedText({
  text,
  symptoms
}: {
  text: string;
  symptoms: NormalizedSymptom[];
}) {
  const flat: SpanMark[] = symptoms.flatMap((s) => {
    const title = s.hpo_id ? `${s.label_ja ?? ""} (${s.hpo_id})` : "未確定（No Candidate Fit）";
    return s.spans.map((sp) => ({
      start: sp.start,
      end: sp.end,
      href: s.hpo_url ?? undefined,
      title
    }));
  });

  const spans = chooseNonOverlapping(flat);

  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const sp of spans) {
    if (cursor < sp.start) {
      parts.push(<span key={`t-${cursor}`}>{text.slice(cursor, sp.start)}</span>);
    }
    const chunk = text.slice(sp.start, sp.end);
    parts.push(
      sp.href ? (
        <a
          key={`m-${sp.start}-${sp.end}`}
          href={sp.href}
          target="_blank"
          rel="noreferrer"
          title={sp.title}
        >
          <mark>{chunk}</mark>
        </a>
      ) : (
        <mark key={`m-${sp.start}-${sp.end}`} title={sp.title}>
          {chunk}
        </mark>
      )
    );
    cursor = sp.end;
  }
  if (cursor < text.length) {
    parts.push(<span key={`t-end`}>{text.slice(cursor)}</span>);
  }

  return <div className="whitespace-pre-wrap text-sm leading-8">{parts}</div>;
}
