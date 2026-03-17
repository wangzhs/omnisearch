import os
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.normalizers.stock import format_compact_date, normalize_ticker_input


class AKShareCollector:
    source = "akshare"

    def fetch_daily_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized = normalize_ticker_input(ticker)
        symbol = normalized.split(".", maxsplit=1)[0]
        end = end_date or date.today().isoformat()
        start = start_date or (date.today() - timedelta(days=max(limit * 2, 120))).isoformat()

        try:
            with _without_proxy_env():
                records = self._fetch_hist_from_eastmoney(
                    symbol=symbol,
                    start_date=format_compact_date(start),
                    end_date=format_compact_date(end),
                )
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch daily prices from AKShare for {normalized}: {exc}") from exc

        return list(reversed(records[-limit:]))

    def _fetch_hist_from_eastmoney(self, symbol: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
        market_code = "1" if symbol.startswith("6") else "0"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "101",
            "fqt": "0",
            "secid": f"{market_code}.{symbol}",
            "beg": start_date,
            "end": end_date,
        }
        session = requests.Session()
        session.trust_env = False
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
                "Referer": f"https://quote.eastmoney.com/{market_code}.{symbol}.html",
                "Accept": "application/json, text/plain, */*",
            }
        )
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.4,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        session.mount("http://", HTTPAdapter(max_retries=retry))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        klines = ((payload.get("data") or {}).get("klines")) or []
        if not klines:
            return []

        rows: list[dict[str, Any]] = []
        for item in klines:
            parts = item.split(",")
            if len(parts) < 11:
                continue
            rows.append(
                {
                    "日期": parts[0],
                    "股票代码": symbol,
                    "开盘": parts[1],
                    "收盘": parts[2],
                    "最高": parts[3],
                    "最低": parts[4],
                    "成交量": parts[5],
                    "成交额": parts[6],
                    "振幅": parts[7],
                    "涨跌幅": parts[8],
                    "涨跌额": parts[9],
                    "换手率": parts[10],
                }
            )
        return rows


@contextmanager
def _without_proxy_env() -> Iterator[None]:
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    original = {key: os.environ.get(key) for key in proxy_keys}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
