# ai-meeting-neo

自律会議ループの**コアエンジン**（CLI・JSON 保存）です。  
**AI-Meeting-Hub**（会議室 UI）とは別リポジトリで、対話型 AI 3 体の会議 → 総監督 → 実行計画（ファイル生成まで）を担います。

## AI-Meeting-Hub との違い

| 項目 | AI-Meeting-Hub | ai-meeting-neo（本プロジェクト） |
|------|----------------|----------------------------------|
| 役割 | 表示・入力・履歴・比較などの UI | 会議ループ・ターン管理・JSON 永続化・総監督・実行プロンプト生成 |
| API | （既存） | 会議エージェントはスタブまたはローカル実装可 |

## 実装範囲

- テーマ入力（`data/input.json`）
- 会議ターン（既定 `max_turns=6`）→ 最終ターン後 **`paused_for_supervisor`**
- **`python main.py --supervisor`** … `supervisor_output.json`（ルールベース解析）
- **`python main.py --plan-execution`** … `execution_plan.json`（`tasks` 内包）と `prompts/execution_prompt_*.md`
- **`python main.py --auto`** … 上記を安全に連続（**ファイル生成のみ**。コマンド実行・デプロイはしない）
- DB なし、**JSON ファイルのみ**

### 状態（`status`）

| 値 | 意味 |
|----|------|
| `running` | 会議進行中 |
| `paused_for_supervisor` | ターン上限到達。総監督フェーズ待ち |
| `approved_for_execution` | 総監督が承認（ルール上 `approve`） |
| `needs_revision` | 再検討が必要 |
| `completed` | 実行計画まで生成済み |
| `on_hold` | 保留 |

## 実行方法

プロジェクトルートで:

```bash
python main.py
```

| オプション | 動作 |
|------------|------|
| （なし） / `--run-once` | 会議を **1 ターン** だけ実行 |
| `--run-batch` | `max_turns` まで連続し **`paused_for_supervisor`** まで進める |
| `--supervisor` | 総監督フェーズ（`paused_for_supervisor` 時）→ `supervisor_output.json` |
| `--plan-execution` | 実行計画フェーズ（`approved_for_execution` 時）→ plan / tasks / prompts |
| `--auto` | バッチ → 総監督 → 実行計画を順に実行（**セーフモード既定**） |

データディレクトリは環境変数 `DATA_DIR` または `config/settings.py` の `data/`。

### JSON の文字エンコーディング

- `data/` 以下の JSON は **UTF-8（BOM 許容: utf-8-sig）** で読み書きします（`storage/repository.py`）。
- PowerShell で表示が崩れる場合はファイル内容を優先し、例:  
  `Get-Content .\data\meeting_state.json -Encoding UTF8`

## セーフモード（既定）

- 本ツールは **JSON / Markdown の生成のみ**です（**実行準備モード**。ディスパッチ・シェル・API 送信なし）。
- プランナー出力（`execution_plan` に含まれる `tasks` / 各プロンプト）は **提案（proposal / draft）のみ**で、実行命令ではありません。
- `safe_mode` は **`meeting_state.json` に永続**されます（既定 `true`）。環境変数 `SAFE_MODE` で `config/settings.py` の既定に影響。
- Cursor / OpenClaw / ChatGPT 向けプロンプトは **`prompts/` に書き出すだけ**で、**自動実行・本番変更・デプロイは行いません**。

### 保存順序と atomic 書き込み

- 各フェーズで **詳細アーティファクト（turns / supervisor_* / execution_* / prompts）を先に** temp 書き込み → 検証 → **atomic rename** してから、**最後に `meeting_state.json`** を更新します。
- 正規データには **`session_id` と `schema_version`** を含みます（`meeting_state` は最新の正規状態へのライトウェイトなポインタ）。

### 起動時整合性チェック

- 既定で **残存 `run.lock`**、**残存 `*.tmp*`**、**session_id の不一致**は **エラーで停止**します（不完全な temp からの自動再開はしません）。
- 旧形式（`schema_version` / `session_id` 欠落）は **警告のみ**（次回保存で更新されます）。
- **ERROR は常に検出し、存在時は必ず終了**します。警告の表示だけ省略する場合: `python main.py --skip-integrity-warnings`

## データファイル

| ファイル | 内容 |
|----------|------|
| `data/input.json` | 会議入力 |
| `data/turns.json` | 各ターンの 3AI と `chair_summary` |
| `data/meeting_state.json` | 会議状態 |
| `data/supervisor_input.json` | 総監督への入力スナップショット |
| `data/supervisor_output.json` | 総監督フェーズの出力（`--supervisor`） |
| `data/execution_plan.json` | 実行計画と `tasks` 配列（`--plan-execution`） |

初回からやり直す場合は `current_turn`・`status`・`turns.json` を適宜リセットしてください。

## ライセンス

プロジェクトにライセンスが未設定の場合は、利用前にリポジトリ管理者に確認してください。
