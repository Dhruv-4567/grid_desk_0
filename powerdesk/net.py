"""HTTP plumbing shared by news and official sources: retries, timeouts, size cap, parallel fetch."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, TypeVar

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HTTP_TIMEOUT, HTTP_WORKERS, MAX_DOWNLOAD_BYTES, USER_AGENT

log = logging.getLogger(__name__)
T = TypeVar("T")
R = TypeVar("R")


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET"}))
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=HTTP_WORKERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.8"})
    return session


def download(session: Any, url: str) -> bytes:
    """GET a URL with a timeout and a 5 MB cap. Raises on any failure; callers catch."""
    with session.get(url, timeout=HTTP_TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        chunks, size = [], 0
        for chunk in resp.iter_content(64 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise ValueError("response larger than 5 MB")
            chunks.append(chunk)
    return b"".join(chunks)


def run_all(
    jobs: Iterable[T],
    worker: Callable[[Any, T], R],
    session: Any = None,
) -> list[R]:
    """Run worker(session, job) for every job in parallel, sharing one session. Order is preserved.

    The worker itself must catch its own errors; this only manages threads and the session.
    """
    jobs = list(jobs)
    if not jobs:
        return []
    own = session is None
    session = session or make_session()
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(HTTP_WORKERS, len(jobs)))) as pool:
            return list(pool.map(lambda job: worker(session, job), jobs))
    finally:
        if own:
            try:
                session.close()
            except Exception:  # closing must never be the thing that fails
                log.debug("session close failed", exc_info=True)
