# scwrap

## Overview - 概要

scwrap is a scraping utility library built on Patchright, Playwright, and selectolax.  
scwrap は Patchright / Playwright（`Page` API）と selectolax をベースにしたスクレイピングユーティリティライブラリです。**細かい挙動はプリミティブの組み合わせで組み立てる**前提の薄いラッパーです（「よしなに」な自動修復は置かない方針）。

DOM・パーサのラッパーは **`scwrap`**（`wrap_page` / `wrap_parser` などのファクトリー）から、ブラウザ起動は **`scwrap.browser`**、CSV やログなどの周辺は **`scwrap.utils`** から import します。


## Requirements - 必要条件

- Python 3.12 or higher（`requires-python` は `pyproject.toml` 参照）
- 主要依存: patchright, playwright, selectolax, pandas, pyarrow, camoufox, loguru（一覧・下限は `pyproject.toml` の `[project.dependencies]`）
- `write_parquet` は **pandas + pyarrow**（`pyarrow` は依存に含まれる）。別エンジンに切り替える場合のみ `fastparquet` などが必要になることがあります。
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

ブラウザ側は `wrap_page(page)` が起点です。`goto`・`wait`・`css` などはこの戻り値に対して呼びます。要素が複数なら `css(...)` はグループを返し、先頭だけなら `.first`、正規表現で絞り込みは `.grep(pattern)`、相対 URL の解決には `.urls`（単一は `.url`）を使います。テキストや生の要素は `.text` / `.raw` プロパティです。

静的 HTML（selectolax）側は `wrap_parser(parser)` から `css` / `grep` / `text` など（ノードは `wrap_node` 系）。クラス実装は非公開で、**コンストラクトは常にこれらのファクトリー経由**にしてください。

### `scwrap.browser`

- **`patchright_page()`** … コンテキストマネージャ。Patchright で **Google Chrome**（`channel='chrome'`）を起動し、**毎回クリーンな `BrowserContext`** の `Page` を `with` に渡す（永続プロファイルは使わない）。`headless=False`・`no_viewport=True` などは固定。

- **`camoufox_page(locale=...)`** … Camoufox（Firefox）で `Page` を開く。  
  _例:_ `with camoufox_page(locale='en-US,en') as page:`  
  デフォルトの `locale` は `'ja-JP,ja'`。`headless=False`・`humanize=True` は固定。

ウィンドウ最大化が必要なら、コードではなく **ブラウザ上で手動**してください（起動引数に依存させない）。

### `scwrap.utils`

`log_to_file`・`from_here`・`parse_html`・`append_csv`・`write_parquet`・`save_html`・`hash_name`・`random_sleep` など（各関数は `scwrap/utils.py` を参照）。`log_to_file` はログファイルの **親ディレクトリが無いと失敗**するので、必要なら先に `Path.mkdir` するか、`save_html` のように親を作る処理を挟んでください。


## Basic Usage - 基本的な使い方

```python
from scwrap import wrap_page
from scwrap.browser import patchright_page
from scwrap.utils import log_to_file, append_csv, from_here, random_sleep

fh = from_here(__file__)
log_to_file(fh('log/scraping.log'))

with patchright_page() as page:
    p = wrap_page(page)
    p.goto('https://www.foobarbaz1.jp')

    pref_urls = p.css('li.item > ul > li > a').urls

    classroom_urls = []
    for i, url in enumerate(pref_urls, 1):
        print(f'pref_urls {i}/{len(pref_urls)}')
        if not url or not p.goto(url):
            continue
        random_sleep(1, 2)
        classroom_urls.extend(p.css('.school-area h4 a').urls)

    for i, url in enumerate(classroom_urls, 1):
        print(f'classroom_urls {i}/{len(classroom_urls)}')
        if not p.goto(url):
            continue
        random_sleep(1, 2)
        append_csv(fh('csv/out.csv'), {
            'URL': page.url,
            '教室名': p.css('h1 .text01').first.text,
            '住所': p.css('.item .mapText').first.text,
            '電話番号': p.css('.item .phoneNumber').first.text,
            'HP': p.css('th').grep('ホームページ').first.next('td').css('a').first.url,
        })
```

## Save HTML while scraping - スクレイピングしながらHTMLを保存する

```python
from scwrap import wrap_page
from scwrap.browser import camoufox_page
from scwrap.utils import log_to_file, append_csv, from_here, hash_name, random_sleep, save_html

fh = from_here(__file__)
log_to_file(fh('log/scraping.log'))

with camoufox_page() as page:
    ctx = {}
    p = wrap_page(page)
    p.goto('https://www.foobarbaz1.jp')

    ctx['アイテムURLs'] = p.css('ul.items > li > a').urls

    for i, url in enumerate(ctx['アイテムURLs'], 1):
        print(f"アイテムURLs {i}/{len(ctx['アイテムURLs'])}")
        if not p.goto(url):
            continue
        random_sleep(1, 2)
        if p.wait('#logo', timeout=10000).raw is None:
            continue
        file_name = f'{hash_name(url)}.html'
        if not save_html(fh('html') / file_name, page.content()):
            continue
        append_csv(fh('outurlhtml.csv'), {
            'URL': url,
            'HTML': file_name,
        })
```

## Scrape from local HTML files - 保存済みHTMLからスクレイピングしてParquetに出力する

```python
import pandas as pd

from scwrap import wrap_parser
from scwrap.utils import log_to_file, from_here, parse_html, write_parquet

fh = from_here(__file__)
log_to_file(fh('log/scraping.log'))

df = pd.read_csv(fh('outurlhtml.csv'))
results = []
for i, (url, path) in enumerate(zip(df['URL'], df['HTML']), 1):
    print(f'outhtml {i}/{len(df)}')
    if not (parser := parse_html(fh('html') / path)):
        continue
    p = wrap_parser(parser)
    results.append({
        'URL': url,
        '教室名': p.css('h1 .text02').first.text,
        '住所': p.css('.item .mapText').first.text,
        '所在地': p.css('dt').grep(r'所在地').first.next('dd').text,
    })
write_parquet(fh('outhtml.parquet'), results)
```

## License - ライセンス

[MIT](./LICENSE)
