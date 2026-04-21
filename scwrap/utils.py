from __future__ import annotations

import hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, TypeVar

import pandas as pd
from loguru import logger
from selectolax.lexbor import LexborHTMLParser


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_html(path: Path | str) -> LexborHTMLParser | None:
    try:
        return LexborHTMLParser(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"[parse_html] {path} {type(e).__name__}: {e}")
        return None

def from_here(file: str) -> Callable[[str], Path]:
    base = Path(file).resolve().parent
    return lambda path: base / path

def append_csv(path: Path | str, row: dict) -> None:
    p = Path(path)
    try:
        _ensure_parent(p)
        pd.DataFrame([row]).to_csv(
            p,
            mode='a',
            index=False,
            header=True if not p.exists() else p.stat().st_size == 0,
            encoding='utf-8-sig',
        )
    except Exception as e:
        logger.error(f"[append_csv] {path} {row} {type(e).__name__}: {e}")

def write_parquet(path: Path | str, rows: list[dict]) -> None:
    p = Path(path)
    try:
        _ensure_parent(p)
        pd.DataFrame(rows).to_parquet(
            p,
            index=False,
        )
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

def log_to_file(path: Path | str) -> None:
    p = Path(path)
    _ensure_parent(p)
    logger.add(p, level="WARNING", encoding="utf-8")


def pool_map[T, R](
    worker: Callable[[T], R],
    items: Iterable[T],
    workers: int | None = None,
) -> list[R]:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(worker, items))

def glob_paths(dir_path: str | Path, pattern: str = "*.html") -> list[str]:
    """
    ``dir_path`` 直下で ``pattern`` に一致するパスを ``str`` のリストで返す。

    ``str`` にしているのは ``pool_map`` 等のプロセスプールへ渡すとき pickle しやすくするため。
    """
    return [str(p) for p in Path(dir_path).glob(pattern)]
