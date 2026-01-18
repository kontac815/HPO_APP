"use client";

import React, { useMemo, useState } from "react";

import { HighlightedText } from "../lib/highlight";
import type { DiseasePrediction, ExtractResponse, NormalizedSymptom, PredictResponse } from "../lib/types";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  try {
    const r = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!r.ok) {
      const contentType = r.headers.get("content-type") ?? "";
      if (contentType.includes("application/json")) {
        const j = (await r.json().catch(() => null)) as unknown;
        const detail =
          j && typeof j === "object" && "detail" in j ? String((j as { detail: unknown }).detail ?? "") : "";
        if (detail) throw new Error(detail);
      }

      const msg = await r.text();
      console.error(`API Error [${path}]:`, msg);
      throw new Error(msg || `リクエストに失敗しました (HTTP ${r.status})`);
    }
    return r.json() as Promise<T>;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("ネットワークエラーが発生しました。接続を確認してください。");
    }
    throw error;
  }
}

export default function Page() {
  const [input, setInput] = useState<string>(
    "3歳男児。数日前から発熱と咳が続く。昨日から食欲低下。発熱はあるが嘔吐はない。発熱が続く。"
  );
  const [loadingExtract, setLoadingExtract] = useState(false);
  const [loadingPredict, setLoadingPredict] = useState(false);
  const [extract, setExtract] = useState<ExtractResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [predictions, setPredictions] = useState<DiseasePrediction[]>([]);

  const allSelectedHpoIds = useMemo(() => {
    if (!extract) return [];
    const ids: string[] = [];
    for (const s of extract.symptoms) {
      const key = `${s.symptom}@@${s.hpo_id ?? "null"}`;
      if (checked[key] && s.hpo_id) ids.push(s.hpo_id);
    }
    return Array.from(new Set(ids));
  }, [checked, extract]);

  async function onExtract() {
    setError("");
    setPredictions([]);
    setLoadingExtract(true);
    try {
      const data = await postJson<ExtractResponse>("/api/extract", { text: input });
      setExtract(data);

      const next: Record<string, boolean> = {};
      for (const s of data.symptoms) {
        next[`${s.symptom}@@${s.hpo_id ?? "null"}`] = !!s.hpo_id;
      }
      setChecked(next);
    } catch (e) {
      setExtract(null);
      setChecked({});
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingExtract(false);
    }
  }

  async function onPredict() {
    if (!extract) return;
    setError("");
    setLoadingPredict(true);
    try {
      const data = await postJson<PredictResponse>("/api/predict", {
        hpo_ids: allSelectedHpoIds,
        target: "omim",
        limit: 20
      });
      setPredictions(data.predictions);
    } catch (e) {
      setPredictions([]);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingPredict(false);
    }
  }

  function toggleAll(value: boolean) {
    if (!extract) return;
    const next: Record<string, boolean> = {};
    for (const s of extract.symptoms) {
      next[`${s.symptom}@@${s.hpo_id ?? "null"}`] = value && !!s.hpo_id;
    }
    setChecked(next);
  }

  const symptoms: NormalizedSymptom[] = extract?.symptoms ?? [];

  return (
    <main className="mx-auto w-full max-w-[1100px] px-4 py-7 pb-16">
      <section className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="m-0 text-xl font-semibold">HPO 正規化 → PubCaseFinder 疾患予測</h1>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
              日本語テキストから症状を抽出し、HPO IDへ正規化してから PubCaseFinder API に投入して疾患をランキングします。
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-slate-300">
            <span>否定症状は除外</span>
            <span className="opacity-60">・</span>
            <span>HPOは選択式</span>
          </div>
        </div>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="mt-4 w-full min-h-[140px] resize-y rounded-xl border border-white/10 bg-black/25 p-3 text-sm leading-relaxed text-slate-100 outline-none placeholder:text-slate-400 focus:border-sky-300/60 focus:ring-2 focus:ring-sky-400/20"
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            onClick={onExtract}
            disabled={loadingExtract || !input.trim()}
            className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-sky-400/15 px-4 py-2.5 text-sm font-semibold text-slate-100 transition-colors hover:bg-sky-400/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loadingExtract ? "抽出中..." : "症状抽出 + HPO正規化"}
          </button>
          <span className="text-sm text-slate-300">
            OpenAI APIキーは <code className="rounded bg-white/10 px-1 py-0.5">OPENAI_API_KEY</code>。RAG(埋め込み)は{" "}
            <code className="rounded bg-white/10 px-1 py-0.5">HPO_depth_ge3.csv</code> を使います。
          </span>
        </div>

        {error ? <p className="mt-2.5 whitespace-pre-wrap font-semibold text-red-300">{error}</p> : null}
      </section>

      {extract ? (
        <div className="mt-4 space-y-4">
          <section className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
            <h2 className="m-0 mb-2.5 text-base font-semibold">ハイライト（クリックでHPOを開く）</h2>
            <HighlightedText text={extract.text} symptoms={symptoms} />
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="m-0 text-base font-semibold">抽出結果（チェックしたHPOだけで予測）</h2>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => toggleAll(true)}
                  disabled={loadingExtract}
                  className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-100 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  全選択
                </button>
                <button
                  onClick={() => toggleAll(false)}
                  disabled={loadingExtract}
                  className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-100 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  全解除
                </button>
              </div>
            </div>

            <div className="mt-1.5 text-sm text-slate-300">
              行は「症状（重複は1つ）」。本文の同一語はすべてハイライトされます。
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead className="text-slate-300">
                  <tr className="border-b border-white/10">
                    <th className="p-2 text-left font-semibold">使用</th>
                    <th className="p-2 text-left font-semibold">根拠テキスト</th>
                    <th className="p-2 text-left font-semibold">HPO ID</th>
                    <th className="p-2 text-left font-semibold">英語ラベル</th>
                    <th className="p-2 text-left font-semibold">日本語ラベル</th>
                    <th className="p-2 text-left font-semibold">リンク</th>
                  </tr>
                </thead>
                <tbody className="text-slate-100">
                  {symptoms.map((s) => {
                    const key = `${s.symptom}@@${s.hpo_id ?? "null"}`;
                    const hasHpo = !!s.hpo_id && !!s.hpo_url;
                    return (
                      <tr key={key} className="border-b border-white/10">
                        <td className="p-2 align-top">
                          <input
                            type="checkbox"
                            checked={!!checked[key]}
                            disabled={!s.hpo_id}
                            onChange={(e) => setChecked((prev) => ({ ...prev, [key]: e.target.checked }))}
                            className="h-4 w-4 accent-sky-400 disabled:opacity-50"
                          />
                        </td>
                        <td className="max-w-[360px] whitespace-pre-wrap p-2 align-top text-slate-100">{s.evidence}</td>
                        <td className="p-2 align-top">
                          {hasHpo ? (
                            <a href={s.hpo_url!} target="_blank" rel="noreferrer">
                              {s.hpo_id}
                            </a>
                          ) : (
                            <span className="text-slate-300">未確定</span>
                          )}
                        </td>
                        <td className="p-2 align-top text-slate-100">{s.label_en ?? "-"}</td>
                        <td className="p-2 align-top text-slate-100">{s.label_ja ?? "-"}</td>
                        <td className="p-2 align-top">
                          {hasHpo ? (
                            <a href={s.hpo_url!} target="_blank" rel="noreferrer">
                              {s.hpo_url}
                            </a>
                          ) : (
                            <span className="text-slate-300">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {symptoms.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="p-3 text-slate-300">
                        症状が抽出されませんでした（または全て否定症状として除外されました）。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={onPredict}
                disabled={loadingPredict || allSelectedHpoIds.length === 0}
                className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-emerald-300/15 px-4 py-2.5 text-sm font-semibold text-slate-100 transition-colors hover:bg-emerald-300/25 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loadingPredict ? "予測中..." : `選択HPOで疾患予測（${allSelectedHpoIds.length}件）`}
              </button>
              <span className="text-sm text-slate-300">
                PubCaseFinder:{" "}
                <code className="rounded bg-white/10 px-1 py-0.5">pcf_get_ranked_list</code> (target=omim, format=json)
              </span>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
            <h2 className="m-0 mb-2.5 text-base font-semibold">予測された疾患（上位20件）</h2>
            {predictions.length === 0 ? (
              <div className="text-sm text-slate-300">まだ予測していません。</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead className="text-slate-300">
                    <tr className="border-b border-white/10">
                      <th className="p-2 text-left font-semibold">Rank</th>
                      <th className="p-2 text-left font-semibold">Score</th>
                      <th className="p-2 text-left font-semibold">疾患名（日本語）</th>
                      <th className="p-2 text-left font-semibold">疾患名（英語）</th>
                      <th className="p-2 text-left font-semibold">ID</th>
                      <th className="p-2 text-left font-semibold">リンク</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-100">
                    {predictions.map((p) => (
                      <tr key={`${p.id}-${p.rank ?? "x"}`} className="border-b border-white/10">
                        <td className="p-2 align-top">{p.rank ?? "-"}</td>
                        <td className="p-2 align-top">{p.score?.toFixed(4) ?? "-"}</td>
                        <td className="p-2 align-top">{p.disease_name_ja ?? "-"}</td>
                        <td className="p-2 align-top">{p.disease_name_en ?? "-"}</td>
                        <td className="p-2 align-top">{p.id}</td>
                        <td className="p-2 align-top">
                          {p.disease_url ? (
                            <a href={p.disease_url} target="_blank" rel="noreferrer">
                              {p.disease_url}
                            </a>
                          ) : (
                            <span className="text-slate-300">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : null}
    </main>
  );
}
