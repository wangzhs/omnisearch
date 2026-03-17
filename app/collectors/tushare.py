from typing import Any

from app.core.config import settings
from app.normalizers.stock import normalize_ticker_input


class TushareCollector:
    source = "tushare"

    def __init__(self) -> None:
        self._client = None

    def fetch_company_profile(self, ticker: str) -> dict[str, Any] | None:
        normalized = normalize_ticker_input(ticker)
        client = self._get_client()
        basic = self._fetch_stock_basic(client, normalized)
        company = self._fetch_stock_company(client, normalized)
        if not basic and not company:
            return None
        return {
            "basic": basic or {},
            "company": company or {},
            "ticker": normalized,
        }

    def fetch_financial_summaries(self, ticker: str, limit: int = 8) -> list[dict[str, Any]]:
        normalized = normalize_ticker_input(ticker)
        client = self._get_client()
        try:
            income = self._call_api(
                client,
                "income",
                params={"ts_code": normalized},
                fields="ts_code,ann_date,end_date,report_type,total_revenue,revenue,n_income,basic_eps",
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch income statement from Tushare for {normalized}: {exc}") from exc

        indicator_records: dict[str, dict[str, Any]] = {}
        try:
            indicators = self._call_api(
                client,
                "fina_indicator",
                params={"ts_code": normalized},
                fields="ts_code,ann_date,end_date,q_sales_yoy,q_dtprofit_yoy,roe,grossprofit_margin",
            )
            for item in indicators:
                end_date = item.get("end_date")
                if end_date:
                    indicator_records[end_date] = item
        except Exception:
            indicator_records = {}

        if not income:
            return []

        records = []
        for item in income[:limit]:
            end_date = item.get("end_date")
            merged = dict(item)
            if end_date and end_date in indicator_records:
                merged.update(indicator_records[end_date])
            records.append(merged)
        return records

    def fetch_daily_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized = normalize_ticker_input(ticker)
        client = self._get_client()
        params = {"ts_code": normalized}
        if start_date:
            params["start_date"] = start_date.replace("-", "")
        if end_date:
            params["end_date"] = end_date.replace("-", "")

        try:
            daily_rows = self._call_api(
                client,
                "daily",
                params=params,
                fields="ts_code,trade_date,open,high,low,close,vol,amount,pct_chg",
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch daily prices from Tushare for {normalized}: {exc}") from exc

        turnover_by_date: dict[str, Any] = {}
        try:
            basic_rows = self._call_api(
                client,
                "daily_basic",
                params=params,
                fields="ts_code,trade_date,turnover_rate",
            )
            turnover_by_date = {item["trade_date"]: item.get("turnover_rate") for item in basic_rows if item.get("trade_date")}
        except Exception:
            turnover_by_date = {}

        results: list[dict[str, Any]] = []
        for item in daily_rows[:limit]:
            trade_date = item.get("trade_date")
            results.append(
                {
                    "trade_date": trade_date,
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "close": item.get("close"),
                    "volume": item.get("vol"),
                    "amount": item.get("amount"),
                    "change_pct": item.get("pct_chg"),
                    "turnover_rate": turnover_by_date.get(trade_date),
                    "source": "tushare",
                    "ts_code": normalized,
                }
            )
        return list(reversed(results))

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not settings.tushare_token:
            raise RuntimeError("TUSHARE_TOKEN is not configured.")

        try:
            import tushare as ts
            from tushare.pro import client as tushare_client
        except ImportError as exc:
            raise RuntimeError("Tushare is not installed. Add it to the environment to collect financial data.") from exc

        if settings.tushare_base_url:
            tushare_client.DataApi._DataApi__http_url = settings.tushare_base_url

        ts.set_token(settings.tushare_token)
        self._client = ts.pro_api(settings.tushare_token)
        return self._client

    def _fetch_stock_basic(self, client, ticker: str) -> dict[str, Any] | None:
        rows = self._call_api(
            client,
            "stock_basic",
            params={"ts_code": ticker},
            fields="ts_code,symbol,name,area,industry,market,list_status,list_date",
        )
        if not rows:
            return None
        return rows[0]

    def _fetch_stock_company(self, client, ticker: str) -> dict[str, Any] | None:
        exchange = "SSE" if ticker.endswith(".SH") else "SZSE"
        rows = self._call_api(
            client,
            "stock_company",
            params={"exchange": exchange},
            fields="ts_code,chairman,manager,secretary,reg_capital,setup_date,province,city,website,employees,main_business,business_scope",
        )
        if not rows:
            return None
        for row in rows:
            if row.get("ts_code") == ticker:
                return row
        return None

    def _call_api(self, client, api_name: str, params: dict[str, Any], fields: str) -> list[dict[str, Any]]:
        try:
            frame = getattr(client, api_name)(fields=fields, **params)
        except Exception as exc:
            raise RuntimeError(f"Tushare API call failed for {api_name}: {exc}") from exc
        if frame is None or getattr(frame, "empty", True):
            return []
        return frame.to_dict(orient="records")
