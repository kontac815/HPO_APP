# HPO Normalizer + PubCaseFinder

日本語テキスト（例: 病歴・主訴・経過）から **症状表現を抽出 → HPO ID に正規化 → PubCaseFinder API で疾患をランキング**するアプリケーションです。

## 特徴

- **LLM を安全に使う設計**: 幻覚 ID を抑え、説明可能性を向上
- **RAG による正規化**: HPO 日本語 CSV を知識ベースとして活用
- **人が介入できる UI**: 根拠表示・ハイライト・チェックボックスで取捨選択が可能

## 技術スタック

- **Frontend**: Next.js / React / TypeScript
- **Backend**: Python / FastAPI / LangChain / LangGraph
- **Normalization**: OpenAI Chat + OpenAI Embeddings + FAISS（RAG）
- **Disease ranking**: PubCaseFinder API（DBCLS）

---

## 機能

1. **テキスト入力**: 症状を含む日本語テキストを入力
2. **症状抽出 + HPO 正規化**: ワンクリックで自動処理
3. **ハイライト表示**: 文章中の症状箇所をハイライト（クリックで HPO サイトを新規タブで開く）
4. **抽出結果テーブル**: 根拠テキスト、HPO ID、英語/日本語ラベル、リンクを表示
5. **HPO 選択**: 各行のチェックボックスで予測に使う HPO を選択（デフォルト全選択）
6. **疾患予測**: PubCaseFinder に投げて、疾患ランキング（上位20件）とリンクを表示

---

## アーキテクチャ（データフロー）

1. **入力テキスト** → backend `POST /api/extract`
2. **症状抽出**: LLM が症状を抽出（**否定症状は除外**）
3. **HPO 正規化**: 各症状について
   - OpenAI Embeddings + FAISS で HPO 候補を検索（RAG の retrieval）
   - 候補リストを LLM に渡し「**候補の中から1つだけ選べ**」と制約して HPO ID を確定（**幻覚 ID を抑制**）
4. **UI での確認**: フロントでハイライト/表に表示し、チェックで取捨選択
5. **疾患予測**: 選択された HPO ID のみ backend `POST /api/predict` → PubCaseFinder `pcf_get_ranked_list`

「LLM に自由生成で HP:... を返させない」設計により、信頼性の高い HPO ID 正規化を実現しています。

---

## PubCaseFinder API

### 仕様参照

- Swagger: `https://pubcasefinder.dbcls.jp/api`
- OpenAPI(JSON): `https://pubcasefinder.dbcls.jp/api_spec_json`

### 使用エンドポイント

- `GET https://pubcasefinder.dbcls.jp/api/pcf_get_ranked_list`
  - `target`: `omim` / `orphanet` / `gene`
  - `format`: `json` / `tsv`（本アプリケーションは `json`）
  - `hpo_id`: `HP:0002089,HP:0001998` のようにカンマ区切り

---

## クイックスタート（Docker Compose）

### 前提

- Docker / Docker Compose
- OpenAI API Key（環境変数 `OPENAI_API_KEY`）
- `HPO_depth_ge3.csv`（手元 CSV。`HPO_ID`, `name_en`, `jp_final`, `definition_ja` を使用）

### 1) CSV の配置

`docker-compose.yml` は `HPO_CSV_HOST_PATH`（デフォルト: `../HPO_depth_ge3.csv`）を backend にマウントします。

- デフォルト配置: （このリポジトリの1つ上に）`../HPO_depth_ge3.csv`
- 変更したい場合: `.env` に `HPO_CSV_HOST_PATH=/path/to/HPO_depth_ge3.csv` を設定します

### 2) .env 作成

```bash
cp .env.example .env
```

`.env` の設定項目:

- **必須:**
  - `OPENAI_API_KEY`: OpenAI API キー
- **オプション:**
  - `OPENAI_CHAT_MODEL`: チャットモデル（デフォルト: `gpt-4o-mini`）
  - `OPENAI_EMBED_MODEL`: 埋め込みモデル（デフォルト: `text-embedding-3-small`）
  - `CORS_ORIGINS`: 許可するCORSオリジン（デフォルト: `http://localhost:3000`）
  - `LOG_LEVEL`: ログレベル（デフォルト: `INFO`）
  - `HPO_CSV_HOST_PATH`: （Docker Compose用）ホスト側のHPO CSVファイルのパス（デフォルト: `../HPO_depth_ge3.csv`）
  - `HPO_CSV_PATH`: （ローカル実行用）HPO CSVファイルのパス（デフォルト: `/data/HPO_depth_ge3.csv`）
  - `REBUILD_FAISS_ON_STARTUP`: 起動時にFAISS再構築（デフォルト: `false`）
  - `ALLOW_NO_CANDIDATE_FIT`: 候補に適切なものが無い場合 `hpo_id=null` を許可（デフォルト: `true`）

### 3) 起動

```bash
docker compose up --build
```

```

- **Frontend**: `http://localhost:3000`
- **Backend OpenAPI UI**: `http://localhost:8000/docs`

停止:

```bash
docker compose down
```

---

## 使い方

1. `http://localhost:3000` を開く
2. テキストを入力して「症状抽出 + HPO正規化」を実行
3. 抽出結果テーブルのチェックを必要に応じて変更（デフォルト全選択）
4. 「選択HPOで疾患予測」を実行

---

## 実装のポイント

### 1) RAG による “候補の閉集合化” で幻覚 ID を抑制

LLM に「HPO ID を自由に生成」させると、存在しない `HP:...` を出すリスクがあります。
本実装では「検索（retrieval）で候補を絞り、その候補集合の中から LLM に **選択** させる」方式を採用し、ID の暴走を抑えています。

### 2) 人間が介入できる UI（説明可能性）

以下を用意し、「モデルの出力をそのまま信じない」形を実現しています：

- 根拠テキスト（evidence）
- ハイライト（本文上の出現箇所）
- チェックボックスで "予測に使うHPO" を制御

### 3) LangGraph で抽出→正規化をワークフロー化

単なる関数呼び出しの羅列ではなく、状態遷移（extract → normalize）として実装し、将来の拡張（評価ノード、分岐、再試行）を入れやすい設計にしています。

---

## コード案内

### Backend

- **API**: [backend/app/main.py](backend/app/main.py)
- **設定**: [backend/app/config.py](backend/app/config.py)
- **症状抽出 + HPO 正規化フロー**: [backend/app/graph.py](backend/app/graph.py)
- **HPO CSV → Embeddings → FAISS**: [backend/app/hpo_store.py](backend/app/hpo_store.py)
- **PubCaseFinder 呼び出し**: [backend/app/pubcasefinder.py](backend/app/pubcasefinder.py)

### Frontend

- **UI**: [frontend/src/app/page.tsx](frontend/src/app/page.tsx)
- **ハイライト**: [frontend/src/lib/highlight.tsx](frontend/src/lib/highlight.tsx)
- **Backend プロキシ**: [frontend/src/app/api/extract/route.ts](frontend/src/app/api/extract/route.ts), [frontend/src/app/api/predict/route.ts](frontend/src/app/api/predict/route.ts)

---

## 環境変数（Backend）

### 必須

- `OPENAI_API_KEY`: OpenAI API キー

### 任意

- `OPENAI_CHAT_MODEL`: チャットモデル（デフォルト: `gpt-4o-mini`）
- `OPENAI_EMBED_MODEL`: 埋め込みモデル（デフォルト: `text-embedding-3-small`）
- `REBUILD_FAISS_ON_STARTUP`: 起動時に FAISS インデックスを作り直す（デフォルト: `false`）
  - `true` の場合、embeddings 再計算で時間/コスト増

---

## 初回起動について（Embeddings 構築）

初回起動時は `HPO_depth_ge3.csv` の全行を **OpenAI Embeddings でベクトル化**して FAISS インデックスを作成するため、時間がかかります。
2回目以降は `./backend/storage` に保存した FAISS を再利用するため、高速に起動します。

### 注意事項

- Backend は先に起動しますが、FAISS 準備が終わるまで `POST /api/extract` が `503` を返すことがあります
- `GET http://localhost:8000/health` の `store_ready` が `true` になるまでお待ちください

---

## FAISS インデックスの事前生成（任意）

初回起動の待ち時間を減らしたい場合、事前に FAISS インデックスのみを作成できます。

```bash
docker compose --profile init run --rm backend_init
```

既存のインデックスを作り直す場合:

```bash
docker compose --profile init run --rm backend_init python -m app.build_faiss --rebuild
```

---

## 仕様上の制限事項

- 入力は日本語のみを想定
- 否定症状（例: 「発熱なし」）は除外される
- 同一語が文章内に複数回出る場合は全てハイライトされるが、抽出結果は重複を1行にまとめる
- 症状スパンは LLM 出力が不正確な場合があるため、サーバ側で全文検索により補正される場合がある
- 疾患ランキングは上位20件のみ表示（PubCaseFinder が大量件数を返す場合があるため）

---

## トラブルシューティング

### 1) `OPENAI_API_KEY is missing`

`.env` の `OPENAI_API_KEY` が未設定です。

```bash
cat .env
```

### 2) 初回起動が遅い、または終わらない

- Embeddings 生成中の可能性があります（CSVサイズと回線に依存）
- この間 backend は起動しますが、`/api/extract` は `503`（初期化中）を返すことがあります
- 状態確認: `curl http://localhost:8000/health`（`store_ready` が `true` になるまで待つ）
- 途中で停止した場合は `REBUILD_FAISS_ON_STARTUP=true` で作り直すことも可能ですが、コストが増加します

### 3) CSV が見つからない（FileNotFoundError）

`.env` の `HPO_CSV_HOST_PATH`（ホスト側パス）が正しいか確認してください。

- `HPO_CSV_HOST_PATH` は **ディレクトリではなくCSVファイルのパス**を指定する必要があります

### 4) 疾患予測が空になる

- チェックを全て外していないか確認してください
- 症状抽出で HPO が付与されなかった可能性があります（入力文を変更してみてください）

---

## セキュリティ・注意事項

- 入力テキストは OpenAI API に送信されます（個人情報・機微情報の取り扱いには十分注意してください）
- 本アプリケーションは診断を目的とした医療機器ではありません（研究・学習・プロトタイピング用途を想定）
