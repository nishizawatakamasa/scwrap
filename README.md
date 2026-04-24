# scwrap

## Overview - 概要


- ブラウザ: **Patchright / Playwright 用の取得**と、下記のとおり **`patchright_page` は Google Chrome 前提**です。

## Installation - インストール



### uv (推奨)

```
uv add scwrap
```

Playwright / Patchright が使うブラウザバイナリは別途取得してください。  
加えて **`patchright_page()` は `channel='chrome'` で起動するため、マシンに [Google Chrome](https://www.google.com/chrome/) がインストールされている必要があります**（Chromium のみの環境では起動に失敗することがあります）。

### Patchright（Chromium 等）



#### uv (推奨)

```
uv run patchright install chromium
```

### Camoufox（Firefox）



#### uv (推奨)

```
uv run camoufox fetch
```

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
        th_idx = p.css('th').indexed()
        append_csv(fh('csv/scrape.csv'), {
            'URL': page.url,
            '教室名': p.css_first('h1 .text01').text,
            '住所': p.css_first('.item .mapText').text,
            '電話番号': p.css_first('.item .phoneNumber').text,
            'HP': th_idx.regex_first(r'ホームページ').next('td').css_first('a').url,
            '営業時間': th_idx.regex_first(r'営業時間').next('td').text,
            '定休日': th_idx.regex_first(r'定休日').next('td').text,
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
    dt_idx = p.css('dt').indexed()
    results.append({
        'URL': p.url,
        'file_name': file_path.name,
        '教室名': p.css_first('h1 .text02').text,
        '住所': p.css_first('.item .mapText').text,
        '所在地': dt_idx.regex_first(r'所在地').next('dd').text,
        '交通': dt_idx.regex_first(r'交通').next('dd').text,
        '物件番号': dt_idx.regex_first(r'物件番号').next('dd').text,
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
    dt_idx = p.css('dt').indexed()
    return {
        'URL': p.url,
        'file_name': Path(file_path).name,
        '教室名': p.css_first('h1 .text02').text,
        '住所': p.css_first('.item .mapText').text,
        '所在地': dt_idx.regex_first(r'所在地').next('dd').text,
        '交通': dt_idx.regex_first(r'交通').next('dd').text,
        '価格': dt_idx.regex_first(r'価格').next('dd').text,
        '設備・条件': dt_idx.regex_first(r'設備').next('dd').text,
        '備考': dt_idx.regex_first(r'備考').next('dd').text,
    }

if __name__ == '__main__':
    main()
```

## License - ライセンス

[MIT](./LICENSE)
