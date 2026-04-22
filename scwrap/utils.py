import csv
import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from loguru import logger
from selectolax.lexbor import LexborHTMLParser
from tqdm import tqdm


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_html(path: Path | str) -> LexborHTMLParser | None:
    """HTML ファイルをパースして :class:`LexborHTMLParser` を返す。

    ``read_bytes`` で読み込み、selectolax にバイト列を直接渡す（Python 側の
    UTF-8 デコードを 1 回省略してパース時間を短縮）。scwrap の ``save_html``
    は UTF-8 固定で書き出すので、scwrap で保存した HTML に対しては安全。
    """
    try:
        return LexborHTMLParser(Path(path).read_bytes())
    except Exception as e:
        logger.error(f"[parse_html] {path} {type(e).__name__}: {e}")
        return None

def from_here(file: str) -> Callable[[str], Path]:
    base = Path(file).resolve().parent
    return lambda path: base / path

def append_csv(path: Path | str, row: dict) -> None:
    """``row`` を 1 行だけ CSV に追記する（ファイルが無ければ作成）。

    Excel 互換のため、**ファイル新規作成時のみ先頭に UTF-8 BOM** を書く
    （``utf-8-sig`` で open）。既存ファイルへの追記では BOM を書かない
    （中途 BOM は不正になるため）。ファイルが新規 / 空ならヘッダ行を書く。
    列順は ``row.keys()`` の順で、2 回目以降のキーずれは検知しない
    （pandas 版と同じ挙動）。
    """
    p = Path(path)
    try:
        _ensure_parent(p)
        need_header = not p.exists() or p.stat().st_size == 0
        encoding = 'utf-8-sig' if need_header else 'utf-8'
        with open(p, mode='a', newline='', encoding=encoding) as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if need_header:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        logger.error(f"[append_csv] {path} {row} {type(e).__name__}: {e}")

def write_parquet(path: Path | str, rows: list[dict]) -> None:
    """``rows`` を Parquet ファイルとして書き出す。

    pyarrow を直接使う（pandas 非依存）。``rows`` が空ならスキップ（警告のみ）。
    列スキーマは各列の最初の non-None 値から推論されるので、**同一キーで型が
    混在するとエラーになる**ことがある点に注意。
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    p = Path(path)
    try:
        if not rows:
            logger.warning(f"[write_parquet] {path} no rows, skipped")
            return
        _ensure_parent(p)
        pq.write_table(pa.Table.from_pylist(rows), p)
    except Exception as e:
        logger.error(f"[write_parquet] {path} {type(e).__name__}: {e}")

def hash_name(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()

def save_html(filepath: Path, html: str) -> bool:
    try:
        _ensure_parent(filepath)
        filepath.write_text(html, encoding="utf-8", errors="replace")
        return True
    except Exception as e:
        logger.error(f"[save_html] {filepath} {type(e).__name__}: {e}")
        return False

def add_log_file(path: Path | str, level: str = "WARNING") -> None:
    """loguru に、指定パスへ書き出すファイルシンクを 1 つ追加する。

    scwrap は内部で loguru を使ってログを出しており、この関数は
    ``logger.add(path, level=level, encoding='utf-8')`` を呼ぶだけの糖衣。
    親ディレクトリが無ければ作成する。既定の stderr シンクはそのまま残るため、
    追加呼び出しで "同時書き出し (tee)" になる。

    凝った構成（rotation / retention / 複数シンクなど）が必要な場合は、本関数を
    使わず ``from loguru import logger`` して ``logger.add(...)`` /
    ``logger.remove(...)`` を直接使うこと。

    同じ path で複数回呼ぶと、同じ行が重複して書かれるので注意。
    """
    p = Path(path)
    _ensure_parent(p)
    logger.add(p, level=level, encoding="utf-8")


class _SafeWorker:
    def __init__(self, fn: Callable) -> None:
        self.fn = fn

    def __call__(self, x):
        try:
            return self.fn(x)
        except Exception as e:
            logger.error(f"[pool_map] {type(e).__name__}: {e}")
            return None


def _auto_chunksize(n: int, workers: int | None) -> int:
    w = workers or os.cpu_count() or 4
    return max(1, min(64, n // (w * 4)))


def pool_map[T, R](
    worker: Callable[[T], R],
    items: Iterable[T],
    workers: int | None = None,
    *,
    progress: bool = True,
    chunksize: int | None = None,
) -> list[R | None]:
    """``worker`` を ``ProcessPoolExecutor`` で並列実行する。

    ワーカー側で例外が出た要素は ``None`` として返す（全体は止めない）。

    ``chunksize`` は 1 回のワーカー送信にまとめる要素数。基本は未指定で OK
    （自動値を採用）。次の場合は ``chunksize=1`` を明示するとよい：

      * 進捗バーを 1 件ずつ細かく進めたい
      * タスクごとの所要時間のばらつきが大きい（重い 1 件がチャンクに閉じ込め
        られると末尾で詰まるため、1 件ずつ配ったほうが全体として早く終わる）
    """
    safe = _SafeWorker(worker)
    if progress:
        item_list = list(items)
        cs = chunksize if chunksize is not None else _auto_chunksize(len(item_list), workers)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            return list(
                tqdm(ex.map(safe, item_list, chunksize=cs), total=len(item_list), unit="file")
            )
    cs = chunksize if chunksize is not None else 1
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(safe, items, chunksize=cs))

def glob_paths(dir_path: str | Path, pattern: str = "*.html") -> list[str]:
    """
    ``dir_path`` 直下で ``pattern`` に一致するパスを ``str`` のリストで返す。

    ``str`` にしているのは ``pool_map`` 等のプロセスプールへ渡すとき pickle しやすくするため。
    """
    return [str(p) for p in Path(dir_path).glob(pattern)]
