from typing import Any

import requests

from app.core.config import settings
from app.normalizers.stock import get_cninfo_exchange_code, normalize_ticker_input


class CNInfoCollector:
    source = "cninfo"

    def fetch_events(self, ticker: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = normalize_ticker_input(ticker)
        symbol, market = normalized.split(".", maxsplit=1)
        payload = {
            "pageNum": 1,
            "pageSize": limit,
            "column": "szse" if market == "SZ" else "sse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{symbol},{get_cninfo_exchange_code(market)}",
            "searchkey": "",
            "secid": f"{symbol},{get_cninfo_exchange_code(market)}",
            "category": "",
            "trade": "",
            "seDate": "",
            "sortName": "time",
            "sortType": "desc",
            "isHLtitle": "true",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": settings.user_agent,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.cninfo.com.cn/",
        }

        try:
            response = requests.post(
                settings.cninfo_announcements_url,
                data=payload,
                headers=headers,
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch announcements from CNInfo for {normalized}: {exc}") from exc

        data = response.json()
        announcements = data.get("announcements", [])
        if not isinstance(announcements, list):
            return []
        return announcements[:limit]
