# scwrap

## Overview - 概要

scwrap is a scraping utility library built on Patchright, Playwright, and selectolax.  
scwrap は Patchright / Playwright（`Page` API）と selectolax をベースにしたスクレイピングユーティリティライブラリです。**細かい挙動はプリミティブの組み合わせで組み立てる**前提の薄いラッパーです（「よしなに」な自動修復は置かない方針）。

DOM・パーサのラッパーは **`scwrap`**（`wrap_page` / `wrap_parser` / `wrap_node` / `wrap_node_group` と、Patchright / Playwright 共通の **`Page`** 型エイリアス）から、ブラウザ起動は **`scwrap.browser`**、CSV やログなどの周辺は **`scwrap.utils`** から import します。


## Requirements - 必要条件

- Python 3.12 or higher（`requires-python` は `pyproject.toml` 参照）
- 主要依存: patchright, playwright, selectolax, pyarrow, camoufox, loguru, tqdm（一覧・下限は `pyproject.toml` の `[project.dependencies]`）
- `write_parquet` は **pyarrow** を直接使います（pandas 依存なし）。`append_csv` は stdlib の `csv` で書き出します。出力をデータフレームで扱いたい場合は、ユーザ側で `pandas.read_parquet(...)` / `polars.read_parquet(...)` などを使ってください。
- `pool_map` は既定で **tqdm** で進捗を表示します（`progress=False` で無効化）。tqdm は依存に含まれています。
- ブラウザ: **Patchright / Playwright 用の取得**と、下記のとおり **`patchright_page` は Google Chrome 前提**です。

## Installation - インストール

### pip

```
pip install scwrap
```

### uv (推奨)

```
uv add scwrap
```

Playwright / Patchright が使うブラウザバイナリは別途取得してください。  
加えて **`patchright_page()` は `channel='chrome'` で起動するため、マシンに [Google Chrome](https://www.google.com/chrome/) がインストールされている必要があります**（Chromium のみの環境では起動に失敗することがあります）。

### Patchright（Chromium 等）

#### pip

```
python -m patchright install chromium
```

#### uv (推奨)

```
uv run patchright install chromium
```

### Camoufox（Firefox）

#### pip

```
camoufox fetch
```

#### uv (推奨)

```
uv run camoufox fetch
```

## メソッド

### `scwrap`（ラッパー）

ブラウザ側は `wrap_page(page)` が起点です。`goto`・`wait`・`css_first` / `css` などはこの戻り値に対して呼びます。`goto` は失敗時に最大 `try_cnt` 回まで再試行し、試行間は `wait_range`（秒の乱数範囲）で待ちます。成功したあとは既定で `sleep_after`（秒の乱数範囲、デフォルト `(1, 2)`）で待機します。待機を無効にする場合は `sleep_after=None` を渡してください。セレクタで 1 件は `css_first('...')`、複数は `css('...')`（グループ）。先頭 1 件だけなら `.one`、正規表現で絞り込みは `.grep(pattern)`（グループ）や `.grep_first(pattern)`（最初の 1 件だけ）。マッチ対象のテキストは NFKC 正規化（パターンも Python の `re` と同様）。同じグループに何度も正規表現を当てるときは `.indexed()` してから `.grep` / `.grep_first` すると、`text` の取り直しが 1 回で済む（ブラウザ側では IPC も抑えられる）。相対 URL の解決には `.urls`（要素 1 つは `.url` プロパティ）を使います。兄弟方向に進むのは `next('...')`（ブラウザ側は `nextElementSibling` と `matches` を使いテキストノードを挟んでも要素兄弟だけを辿る／Lexbor 側はリンクを進めつつ要素ノードのみ `css_matches`）。親要素がヒットしない場合でも `css_first` はクラッシュせず、`None` を包んだラッパーを返します。`.text` と `attr(...)` は DOM に近い文字列を返し、ラッパーでは strip しません（空や欠如は `None`）。`.url` / `.urls` だけ `href` を trim してから `urljoin` し、 `#` や `javascript:` 等は採用しません。`html()` は `with_url` / `with_saved_at` で、HTML 先頭に `<meta name="scwrap:url">` や `<meta name="scwrap:saved_at">` を挿入できます。Playwright のハンドルは `.raw` です。

`wrap_parser(parser)` では `css_first` / `css` のほか、保存 HTML に挿入した meta を読み取る **`url`** / **`saved_at`** プロパティがあります。公開 API はすべてファクトリーと型エイリアスだけで、**コンストラクタは使わず** `wrap_page` / `wrap_parser` / `wrap_node` など経由にしてください。

### `scwrap.browser`

- **`patchright_page()`** … コンテキストマネージャ。Patchright で **Google Chrome**（`channel='chrome'`）を起動し、**毎回クリーンな `BrowserContext`** の `Page` を `with` に渡す（永続プロファイルは使わない）。`headless=False` などは固定。

- **`camoufox_page()`** … Camoufox（Firefox）で `Page` を開く。  
  _例:_ `with camoufox_page() as page:`  
  `headless=False`・`humanize=True` は固定。

ウィンドウ最大化が必要なら、コードではなく **ブラウザ上で手動**してください（起動引数に依存させない）。

### `scwrap.utils`

`add_log_file`・`from_here`・`parse_html`・`append_csv`・`write_parquet`・`save_html`・`hash_name`・`pool_map`・`glob_paths` など（各関数は `scwrap/utils.py` を参照）。`append_csv`・`write_parquet`・`save_html`・`add_log_file` は、出力先ファイルの **親ディレクトリが無ければ作成**します（読み取り専用の `parse_html` などは対象外）。

なお scwrap は内部で [loguru](https://github.com/Delgan/loguru) を使ってログを出します。`add_log_file(path, level="WARNING")` は `logger.add(path, level=..., encoding='utf-8')` を呼ぶだけの糖衣で、既定の stderr 出力に**追加**でファイルへも書き出すようになります（既定シンクを置き換えるのではなく tee する形）。不要なら呼ばなくてよく、rotation / retention や複数シンクなど凝った構成が必要なら `from loguru import logger` して `logger.add(...)` / `logger.remove(...)` を直接使ってください。


## Basic Usage - 基本的な使い方

```python
from scwrap import wrap_page
from scwrap.browser import patchright_page
from scwrap.utils import add_log_file, append_csv, from_here

fh = from_here(__file__)
add_log_file(fh('log/scraping.log'))

with patchright_page() as page:
    p = wrap_page(page)

    p.goto('https://www.foobarbaz1.jp')
    pref_urls = p.css('li.item > ul > li > a').urls

    classroom_urls = []
    for i, url in enumerate(pref_urls, 1):
        print(f'pref_urls {i}/{len(pref_urls)}')
        if not p.goto(url):
            append_csv(fh('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        classroom_urls.extend(p.css('.school-area h4 a').urls)

    for i, url in enumerate(classroom_urls, 1):
        print(f'classroom_urls {i}/{len(classroom_urls)}')
        if not p.goto(url):
            append_csv(fh('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        ths = p.css('th').indexed()
        append_csv(fh('csv/scrape.csv'), {
            'URL': page.url,
            '教室名': p.css_first('h1 .text01').text,
            '住所': p.css_first('.item .mapText').text,
            '電話番号': p.css_first('.item .phoneNumber').text,
            'HP': ths.grep_first(r'ホームページ').next('td').css_first('a').url,
            '営業時間': ths.grep_first(r'営業時間').next('td').text,
            '定休日': ths.grep_first(r'定休日').next('td').text,
        })
```

## Save HTML while scraping - スクレイピングしながらHTMLを保存する

```python
from scwrap import wrap_page
from scwrap.browser import camoufox_page
from scwrap.utils import add_log_file, append_csv, from_here, hash_name, save_html

fh = from_here(__file__)
add_log_file(fh('log/scraping.log'))

with camoufox_page() as page:
    p = wrap_page(page)

    p.goto('https://www.foobarbaz1.jp')
    item_urls = p.css('ul.items > li > a').urls

    for i, url in enumerate(item_urls, 1):
        print(f'item_urls {i}/{len(item_urls)}')
        if not p.goto(url):
            append_csv(fh('csv/failed.csv'), {'url': url, 'reason': 'goto'})
            continue
        file_name = f'{hash_name(url)}.html'
        if not save_html(fh('html') / file_name, p.html(with_url=True)):
            append_csv(fh('csv/failed.csv'), {'url': url, 'reason': 'save_html'})
            continue
```

## Scrape from local HTML files - 保存済みHTMLからスクレイピングしてParquetに出力する

```python
from scwrap import wrap_parser
from scwrap.utils import add_log_file, from_here, parse_html, write_parquet

fh = from_here(__file__)
add_log_file(fh('log/scraping.log'))

results = []
for i, file_path in enumerate(fh('html').glob('*.html')):
    print(f'html {i}')
    if not (parser := parse_html(file_path)):
        continue
    p = wrap_parser(parser)
    dts = p.css('dt').indexed()
    results.append({
        'URL': p.url,
        'file_name': file_path.name,
        '教室名': p.css_first('h1 .text02').text,
        '住所': p.css_first('.item .mapText').text,
        '所在地': dts.grep_first(r'所在地').next('dd').text,
        '交通': dts.grep_first(r'交通').next('dd').text,
        '物件番号': dts.grep_first(r'物件番号').next('dd').text,
    })
write_parquet(fh('parquet/extract.parquet'), results)
```

## 保存済みHTMLからスクレイピングしてParquetに出力する(並列処理)

```python
from pathlib import Path

from scwrap import wrap_parser
from scwrap.utils import from_here, glob_paths, parse_html, pool_map, write_parquet

def main():
    fh = from_here(__file__)
    html_paths = glob_paths(fh('html'), '*.html')
    results = [r for r in pool_map(extract, html_paths) if r]
    write_parquet(fh('parquet/extract.parquet'), results)

def extract(file_path: str) -> dict | None:
    if not (parser := parse_html(file_path)):
        return None
    p = wrap_parser(parser)
    # 同じ dt 群から項目を複数取るときは indexed() で text を一度だけ切り出す
    dts = p.css('dt').indexed()
    return {
        'URL': p.url,
        'file_name': Path(file_path).name,
        '教室名': p.css_first('h1 .text02').text,
        '住所': p.css_first('.item .mapText').text,
        '所在地': dts.grep_first(r'所在地').next('dd').text,
        '交通': dts.grep_first(r'交通').next('dd').text,
        '価格': dts.grep_first(r'価格').next('dd').text,
        '設備・条件': dts.grep_first(r'設備').next('dd').text,
        '備考': dts.grep_first(r'備考').next('dd').text,
    }

if __name__ == '__main__':
    main()
```

## License - ライセンス

[MIT](./LICENSE)
