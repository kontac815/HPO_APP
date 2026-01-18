export type TextSpan = {
  start: number;
  end: number;
  text: string;
};

export type NormalizedSymptom = {
  symptom: string;
  spans: TextSpan[];
  evidence: string;
  hpo_id: string | null;
  label_en: string | null;
  label_ja: string | null;
  hpo_url: string | null;
};

export type ExtractResponse = {
  text: string;
  symptoms: NormalizedSymptom[];
};

export type DiseasePrediction = {
  id: string;
  rank: number | null;
  score: number | null;
  disease_name_en: string | null;
  disease_name_ja: string | null;
  disease_url: string | null;
  matched_hpo_ids: string[];
};

export type PredictResponse = {
  target: "omim" | "orphanet" | "gene";
  hpo_ids: string[];
  predictions: DiseasePrediction[];
};
