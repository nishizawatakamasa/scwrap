# scwrap/parallel.py
"""
ローカルHTML抽出の並列化を支援する汎用部品。
ドメインロジックは一切含まず、呼び出し側で抽出関数を定義するだけ。
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")  # 入力型 (例: strパス)
R = TypeVar("R")  # 出力型 (例: dict)


def run_parallel(
    items: Iterable[T],
    worker: Callable[[T], R],
    workers: int | None = None,
) -> list[R]:
    """
    リストの各アイテムを並列実行する汎用関数。

    Args:
        items: 並列処理対象のリスト (例: HTMLファイルパスリスト)
        worker: 各アイテムを処理する関数。トップレベル関数推奨。
               pickle問題回避のため、引数はstr/tuple/intのみに。
        workers: ワーカー数。Noneならmin(8, len(items))

    Returns:
        全workerの結果リスト (失敗時は呼び出し側でNoneフィルタ)

    なぜProcessPoolExecutorか:
    - CPU-boundなselectolax parseが速くなる
    - ThreadPoolよりGIL回避で真の並列
    """
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(worker, items))


def html_files(dir_path: str | Path) -> list[str]:
    """
    ディレクトリ内の全*.htmlパスをstrリストで返す。

    Args:
        dir_path: HTML保存ディレクトリ

    Returns:
        [str, str, ...] パスリスト。strにすることで
        プロセス間受け渡しでPath pickle問題を回避。

    pickle安全:
    - Pathオブジェクトをstr化
    - globのみで軽量
    """
    return [str(p) for p in Path(dir_path).glob("*.html")]