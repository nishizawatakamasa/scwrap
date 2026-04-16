from __future__ import annotations

import random
import re
import time
import unicodedata as ud
from urllib.parse import urljoin

from loguru import logger
from patchright.sync_api import Page as PatchrightPage, ElementHandle as PatchrightElementHandle
from playwright.sync_api import Page as PlaywrightPage, ElementHandle as PlaywrightElementHandle
from selectolax.lexbor import LexborHTMLParser, LexborNode


Page = PatchrightPage | PlaywrightPage
ElementHandle = PatchrightElementHandle | PlaywrightElementHandle


def wrap_page(page: Page) -> _WrappedPage:
    return _WrappedPage(page)

class _PageScoped:
    _page: Page

    def wrap_element(self, elem: ElementHandle | None) -> _WrappedElement:
        return _WrappedElement(self._page, elem)

    def wrap_element_group(self, elems: list[_WrappedElement]) -> _WrappedElementGroup:
        return _WrappedElementGroup(self._page, elems)


def wrap_parser(parser: LexborHTMLParser) -> _WrappedParser:
    return _WrappedParser(parser)

def wrap_node(node: LexborNode | None) -> _WrappedNode:
    return _WrappedNode(node)

def wrap_node_group(nodes: list[_WrappedNode]) -> _WrappedNodeGroup:
    return _WrappedNodeGroup(nodes)


class _WrappedPage(_PageScoped):
    def __init__(self, page: Page) -> None:
        self._page = page

    def css(self, selector: str) -> _WrappedElementGroup:
        elems = self._page.query_selector_all(selector)
        return self.wrap_element_group([self.wrap_element(e) for e in elems])

    def goto(
        self,
        url: str | None,
        try_cnt: int = 3,
        wait_range: tuple[float, float] = (3, 5),
        sleep_after: tuple[float, float] | None = (1, 2),
    ) -> bool:
        if not url:
            return False
        for i in range(try_cnt):
            try:
                if self._page.goto(url) is not None:
                    if sleep_after is not None:
                        time.sleep(random.uniform(*sleep_after))
                    return True
                else:
                    reason = "response is None"
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
            logger.warning(f"[goto] {url} ({i+1}/{try_cnt}) {reason}")
            if i + 1 < try_cnt:
                time.sleep(random.uniform(*wait_range))
        logger.error(f"[goto] giving up: {url}")
        return False

    def wait(self, selector: str, state: str = "attached", timeout: int = 15000) -> _WrappedElement:
        try:
            elem = self._page.wait_for_selector(selector, state=state, timeout=timeout)
            return self.wrap_element(elem)
        except Exception as e:
            logger.warning(f"[wait] {type(e).__name__}: {e} | selector={selector!r} | url={self._page.url}")
            return self.wrap_element(None)


class _WrappedElement(_PageScoped):
    def __init__(self, page: Page, elem: ElementHandle | None) -> None:
        self._page = page
        self._elem = elem

    @property
    def raw(self) -> ElementHandle | None:
        return self._elem
    
    def css(self, selector: str) -> _WrappedElementGroup:
        elems = self._elem.query_selector_all(selector) if self._elem else []
        return self.wrap_element_group([self.wrap_element(e) for e in elems])

    def next(self, selector: str) -> _WrappedElement:
        if self._elem is None:
            return self.wrap_element(None)
        try:
            elem = self._elem.evaluate_handle(
                """(el, sel) => {
                    let cur = el.nextElementSibling;
                    while (cur) {
                        if (cur.matches(sel)) return cur;
                        cur = cur.nextElementSibling;
                    }
                    return null;
                }""",
                selector,
            ).as_element()
            return self.wrap_element(elem)
        except Exception as e:
            logger.error(f"[next] {self._elem} {type(e).__name__}: {e}")
            return self.wrap_element(None)

    @property
    def text(self) -> str | None:
        if self._elem is None:
            return None
        if not (text := self._elem.text_content()):
            return None
        if not (t := text.strip()):
            return None
        return t
        
    def attr(self, attr_name: str) -> str | None:
        if self._elem is None:
            return None
        return a.strip() if (a := self._elem.get_attribute(attr_name)) else None

    @property
    def url(self) -> str | None:
        if not (href := self.attr('href')):
            return None
        if re.search(r'(?i)^(?:#|javascript:|mailto:|tel:|data:)', href):
            return None
        return urljoin(self._page.url, href)

class _WrappedElementGroup(_PageScoped):
    def __init__(self, page: Page, elems: list[_WrappedElement]) -> None:
        self._page = page
        self._elems = elems

    @property
    def raw(self) -> list[_WrappedElement]:
        return self._elems

    @property
    def first(self) -> _WrappedElement:
        return self._elems[0] if self._elems else self.wrap_element(None)

    def grep(self, pattern: str) -> _WrappedElementGroup:
        prog = re.compile(pattern)
        filtered = [
            e for e in self._elems
            if (t := e.text) and prog.search(ud.normalize('NFKC', t))
        ]
        return self.wrap_element_group(filtered)

    @property
    def texts(self) -> list[str | None]:
        return [e.text for e in self._elems]

    def attrs(self, attr_name: str) -> list[str | None]:
        return [e.attr(attr_name) for e in self._elems]

    @property
    def urls(self) -> list[str | None]:
        return [e.url for e in self._elems]


class _WrappedParser:
    def __init__(self, parser: LexborHTMLParser) -> None:
        self._parser = parser

    def css(self, selector: str) -> _WrappedNodeGroup:
        nodes = self._parser.css(selector)
        return wrap_node_group([wrap_node(n) for n in nodes])

class _WrappedNode:
    def __init__(self, node: LexborNode | None) -> None:
        self._node = node

    @property
    def raw(self) -> LexborNode | None:
        return self._node

    def css(self, selector: str) -> _WrappedNodeGroup:
        nodes = self._node.css(selector) if self._node else []
        return wrap_node_group([wrap_node(n) for n in nodes])

    def next(self, selector: str) -> _WrappedNode:
        if self._node is None:
            return wrap_node(None)
        cur = self._node.next
        while cur is not None:
            if cur.is_element_node and cur.css_matches(selector):
                return wrap_node(cur)
            cur = cur.next
        return wrap_node(None)

    @property
    def text(self) -> str | None:
        if self._node is None:
            return None
        return t if (t := self._node.text(strip=True)) else None

    def attr(self, attr_name: str) -> str | None:
        if self._node is None:
            return None
        return a.strip() if (a := self._node.attributes.get(attr_name)) else None

class _WrappedNodeGroup:
    def __init__(self, nodes: list[_WrappedNode]) -> None:
        self._nodes = nodes
    
    @property
    def raw(self) -> list[_WrappedNode]:
        return self._nodes

    @property
    def first(self) -> _WrappedNode:
        return self._nodes[0] if self._nodes else wrap_node(None)

    def grep(self, pattern: str) -> _WrappedNodeGroup:
        prog = re.compile(pattern)
        filtered = [
            n for n in self._nodes
            if (t := n.text) and prog.search(ud.normalize('NFKC', t))
        ]
        return wrap_node_group(filtered)

    @property
    def texts(self) -> list[str | None]:
        return [n.text for n in self._nodes]

    def attrs(self, attr_name: str) -> list[str | None]:
        return [n.attr(attr_name) for n in self._nodes]

