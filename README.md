# log-fooot

nginx の COMBINED アクセスログを IP ごとに解析し、サイト内の画面遷移をカードと線で可視化するコマンドラインツールです。

## 機能

1. **サイトクロール**  
   指定した Web サイトをクロールし、URL 一覧と画面構成（パス・タイトル）を取得します。

2. **ログ解析**  
   nginx の COMBINED 形式のアクセスログをパースし、IP ごとにリクエスト時系列を構築します。

3. **可視化**  
   ページをカードとして表示し、ログから得られた「どの IP がどの順でページを見たか」を線で繋いだ HTML を出力します。

## 必要環境

- Python 3.9+
- （クロール時）対象サイトへの HTTP アクセス

## インストール

```bash
git clone https://github.com/YOUR_USERNAME/log-fooot.git
cd log-fooot
pip install -r requirements.txt
# または
pip install -e .
```

## 使い方

### 基本（クロール + ログ解析 + 可視化）

```bash
# サイトをクロールし、ログを解析して結果を output_dir に出力
python -m log_fooot \
  --base-url "https://example.com" \
  --log-path /var/log/nginx/access.log \
  --output-dir ./result
```

### オプション

| オプション | 説明 | 例 |
|-----------|------|-----|
| `--base-url` | クロール対象のベース URL | `https://example.com` |
| `--log-path` | nginx COMBINED ログファイルのパス | `/var/log/nginx/access.log` |
| `--output-dir` | 解析結果（JSON・HTML）を書き出すディレクトリ | `./result` |
| `--crawl-only` | クロールのみ実行し、sitemap を出力 | - |
| `--analyze-only` | 既存の sitemap を使いログ解析のみ | - |
| `--sitemap` | 既存 sitemap JSON のパス（`--analyze-only` 時） | `./result/sitemap.json` |
| `--max-pages` | クロールする最大ページ数（既定: 500） | `100` |
| `--session-gap-minutes` | 同一 IP でこの分数以上空いたら別セッション（既定: 30） | `15` |
| `--exclude-ips` | 集計から除外する IP を列挙したファイル（.txt または .csv） | `./exclude.csv` |
| `--output-sitemap` | sitemap の出力ファイル名またはパス | `sitemap.json` / `./out/sitemap.json` |
| `--output-sessions` | sessions の出力ファイル名またはパス | `sessions.json` |
| `--output-report` | レポート HTML の出力ファイル名またはパス | `report.html` / `/var/www/report.html` |
| `--lang` | レポートの表示言語（`en` / `ja`、既定: `en`） | `ja` |

- **出力ファイル名**: `--output-sitemap` / `--output-sessions` / `--output-report` でそれぞれの書き出し先を指定できます。ファイル名だけの場合は `--output-dir` の下に、パス（`/` や `\` を含む）の場合はそのパスに出力します。
- **除外 IP**: 未指定でも `--output-dir` に `exclude_ips.csv` があれば自動で読み込み、その IP はセッション集計に含めません。レポートの左サイドバーで除外一覧の確認・追加・CSV 取り込み・ダウンロードができます。

### 出力ファイル

- `sitemap.json` … クロールで得た URL 一覧・パス・タイトル
- `sessions.json` … IP 別のアクセス時系列・遷移パス
- `report.html` … カード＋遷移の線で可視化したレポート（ブラウザで開く）
- `exclude_ips.csv` … （任意）レポートでエクスポートした除外 IP をここに保存すると、次回から自動で読み込まれる

## ログ形式

nginx の **combined** 形式を想定しています。

```
log_format combined '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent"';
```

## サンプル

同梱の `sample_access.log` は nginx COMBINED 形式のサンプルです。sitemap を用意したうえで解析のみ試す例:

```bash
# 事前に result/sitemap.json を用意している場合
python -m log_fooot --analyze-only --log-path ./sample_access.log --output-dir ./result --sitemap ./result/sitemap.json
# result/report.html をブラウザで開く
```

### 大きなサンプルで試す（20 画面・15000 行）

```bash
# 20 画面の sitemap と 15000 行のログを生成
python scripts/generate_sample_log.py
# レポート生成
python -m log_fooot --analyze-only --log-path ./sample_access.log --output-dir ./result --sitemap ./result/sitemap.json
```

- `result/sitemap.json` は 20 画面用にあらかじめ用意済みです。
- `scripts/generate_sample_log.py` を実行すると `sample_access.log` が 15000 行で上書きされます。

## ライセンス

MIT License（[LICENSE](LICENSE)）
