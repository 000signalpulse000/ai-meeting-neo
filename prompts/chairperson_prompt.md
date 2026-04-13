# 議長（Chairperson）プロンプト雛形 — 将来の API 接続用

本ファイルは **未使用**（現状は `core/chairperson.py` のルールベース統合）。  
本番では LLM に渡すシステム／ユーザメッセージのたたき台として利用する。

## 議長の役割

- 会議入力（テーマ・状況・目標・制約・論点）と、**同一ターンの ChatGPT / Gemini / Grok の3回答**を受け取る。
- 次の5項目を **構造化して出力** する（JSON または指示に従った箇条書き）。

## 入力として渡す情報（想定）

| 項目 | 説明 |
|------|------|
| `theme` | 会議テーマ |
| `situation` | 状況 |
| `goal` | 目標 |
| `constraints` | 制約 |
| `question` | このターンの論点・質問 |
| `current_turn` | ターン番号 |
| `chatgpt_response` | ChatGPT の回答全文 |
| `gemini_response` | Gemini の回答全文 |
| `grok_response` | Grok の回答全文 |

## 出力として欲しい項目

| フィールド | 内容 |
|------------|------|
| `agreements` | 3者で共通・近い認識に見える点 |
| `conflicts` | 対立・解釈の食い違い・優先度の差 |
| `missing_points` | まだ議論・根拠が足りない点 |
| `next_candidates` | 次ターンで掘るべき論点・仮説の候補 |
| `integrated_result` | **3AIの回答を踏まえた暫定統合結果**（議長の一段まとめ） |

## システムプロンプト例（たたき台）

あなたは会議の議長である。与えられた会議コンテキストと、ChatGPT・Gemini・Grok の3つの回答のみを根拠に、指定の5フィールドを日本語で出力せよ。外部知識で補わない。各AIの名称を明確に参照してよい。

## ユーザメッセージ例（プレースホルダ）

```
【会議入力】
theme: {{theme}}
situation: {{situation}}
goal: {{goal}}
constraints: {{constraints}}
question: {{question}}
current_turn: {{current_turn}}

【ChatGPT】
{{chatgpt_response}}

【Gemini】
{{gemini_response}}

【Grok】
{{grok_response}}

上記に基づき、agreements / conflicts / missing_points / next_candidates / integrated_result を出力せよ。
```

実装時は `build_chairperson_input` で組み立てた内容をテンプレートに流し込み、`summarize_round` の LLM 版として差し替える想定。
