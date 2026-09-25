# x-jev-gate

**TypeSafe Jev（System One）に「出してよいか」を確率で聞ける、X下書き用の判定CLI。**

A small public gate for X drafts: Layer A hard-blocks secret-looking strings locally, then Layer B asks [TypeSafe Jev](https://docs.typesafe.ai) defined Noul questions and exits non-zero when scores miss thresholds.

- Jev **writes nothing, posts nothing, publishes nothing** — judgment only.
- No long LLM critique. Cheap, fast, explainable Noul scores.
- Sibling of [`grok-bot-jev`](https://github.com/Bodila51/grok-bot-jev) (Grok Bot router). This package is **post-gate specialized**.

## 使い方（動画）

約54秒の解説（日本語 UI / コマンドはそのまま英語）。

GitHub のリポジトリ内プレビューは大きな MP4 を再生できないことがあるので、**ページ上では GIF**、本編は **Release の MP4** を使う。

![x-jev-gate 使い方プレビュー](docs/media/x-jev-gate-howto.gif)

**[▶ 本編 MP4（1080p・無音）を開く](https://github.com/hrtaym1114-github/x-jev-gate/releases/download/v0.1.0/x-jev-gate-howto.mp4)**  
ストーリーボード: [strip](docs/media/x-jev-gate-howto-strip.png) · [Release v0.1.0](https://github.com/hrtaym1114-github/x-jev-gate/releases/tag/v0.1.0)

### 4ステップ

1. **Install** — `pip install git+https://github.com/hrtaym1114-github/x-jev-gate.git`
2. **API key** — `export TYPESAFE_API_KEY=...`（shell / secret manager のみ。コミット禁止）
3. **Run** — `x-jev-gate --text '...'` またはファイル / stdin
4. **結果** — **PASS**（Noul スコアがしきい値以上 → exit 0）/ **BLOCK**（Layer A 秘密検知やしきい値割れ → exit 1）

キー無しのスモーク: `x-jev-gate --dry-run-offline --text 'smoke test body'`  
※ 自動投稿はしません。判定のみです。

## What is Jev?

Jev（TypeSafe System One）は、定義済みの yes/no（Noul）質問に対して確率スコアを返す安い判断層です。生成モデルに長文批評させる代わりに、「ペルソナに刺さるか」「フックがあるか」「公開してよいか」などを数値で返し、しきい値で gate します。

## Install

```bash
# from GitHub (recommended for users)
pip install git+https://github.com/hrtaym1114-github/x-jev-gate.git

# editable (recommended while developing)
pip install -e ".[dev]"
# or with uv
uv pip install -e ".[dev]"
```

Requires Python ≥ 3.10 and a TypeSafe API key for live judgment.

```bash
export TYPESAFE_API_KEY=...   # secret manager / shell env only
# このツールは vault の秘密ファイルを読みません
```

Never commit the key. The CLI never logs `TYPESAFE_API_KEY`.

## Usage

```bash
# file
x-jev-gate examples/pass.txt --profile manufacturing-it

# inline text
x-jev-gate --text "16GBノートで測った結果…" --json

# stdin
cat draft.txt | x-jev-gate --stdin --strict

# vault markdown (## 投稿文 fenced block)
x-jev-gate path/to/draft.md --format vault-md

# CI smoke without network
x-jev-gate --dry-run-offline --text "smoke test body"

# measurement period: always exit 0, still print scores
x-jev-gate draft.txt --shadow --json
```

### Profiles

| Profile | Reader |
|---------|--------|
| `manufacturing-it` (default) | 製造業IT・16GB閉域ノートの固定ペルソナ（ops `PRIMARY_READER` を移植） |
| `generic-tech` | もう少し広い hands-on 技術者 |

Override thresholds with `--threshold-file thresholds.yaml`.

### Noul questions (v0.1)

| ID | Default threshold |
|----|-------------------|
| `persona_attraction` | 0.65 |
| `hook_strength` | 0.65 |
| `memorability` | 0.65 |
| `reader_value` | 0.65 |
| `evidence_quality` | 0.60 |
| `message_clarity` | 0.60 |
| `source_connection` | 0.60 |
| `safe_to_publish` | 0.70 |

`safe_to_publish` は勤務先リーク・他者攻撃・機密っぽさを意味で見る Jev 質問です。正規表現側（Layer A）は鍵・パス漏洩など機械的なものだけに縮小しています。

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | pass（または `--shadow`） |
| `1` | Layer A hard block、または Jev しきい値割れ |
| `2` | Jev 利用不可（キー無し・API障害）。**既定は fail closed** |

`--allow-offline-soft` を付けると、利用不可時に警告のみで exit 0 にできます（非推奨）。

## Architecture

```
入力（下書き）
  ├─ Layer A  Hard fail-closed（ローカル）
  │     APIキー様 / password= / /Users/ パス
  │     → hit なら即 exit 1（Jev を呼ばない）
  ├─ Layer B  Jev System One（TYPESAFE_API_KEY）
  │     複数 Noul → しきい値比較
  └─ Layer C  人間可读要約 + --json
```

## Relation to grok-bot-jev

| | grok-bot-jev | x-jev-gate |
|--|--------------|------------|
| Role | Grok Bot 作業ルーター | X下書きゲート |
| Actions | reuse_cache / stop_retry / … | pass / block |
| Shared | TypeSafe `system_one` + env key only | same |

## Non-goals

- 長文の添削生成（それは LLM）
- 自動投稿・X への書き込み
- grok-bot-jev ルーター全体の再発明

## License

MIT © 歩 原田
