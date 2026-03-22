import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.core.config import settings
from app.models.stock import CompanyProfile, Event, FinancialSummary, PriceDaily


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class SQLiteRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS company_profile (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    exchange TEXT,
                    market TEXT,
                    industry TEXT,
                    area TEXT,
                    list_date TEXT,
                    status TEXT,
                    website TEXT,
                    chairman TEXT,
                    manager TEXT,
                    employees INTEGER,
                    main_business TEXT,
                    business_scope TEXT,
                    source TEXT NOT NULL,
                    dedupe_key TEXT,
                    source_priority INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event (
                    event_id TEXT PRIMARY KEY,
                    dedupe_key TEXT,
                    ticker TEXT NOT NULL,
                    event_date TEXT,
                    title TEXT NOT NULL,
                    raw_title TEXT,
                    event_type TEXT,
                    category TEXT,
                    sentiment TEXT,
                    source_type TEXT,
                    source TEXT NOT NULL,
                    source_priority INTEGER NOT NULL DEFAULT 0,
                    url TEXT,
                    summary TEXT,
                    importance TEXT,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_event_ticker_date ON event (ticker, event_date DESC);

                CREATE TABLE IF NOT EXISTS financial_summary (
                    record_id TEXT PRIMARY KEY,
                    dedupe_key TEXT,
                    ticker TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    announcement_date TEXT,
                    report_type TEXT,
                    revenue REAL,
                    revenue_yoy REAL,
                    net_profit REAL,
                    net_profit_yoy REAL,
                    eps REAL,
                    roe REAL,
                    gross_margin REAL,
                    source TEXT NOT NULL,
                    source_priority INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_financial_ticker_date ON financial_summary (ticker, report_date DESC);

                CREATE TABLE IF NOT EXISTS price_daily (
                    ticker TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    dedupe_key TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    change_pct REAL,
                    turnover_rate REAL,
                    source TEXT NOT NULL,
                    source_priority INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, trade_date)
                );
                CREATE INDEX IF NOT EXISTS idx_price_ticker_date ON price_daily (ticker, trade_date DESC);

                CREATE TABLE IF NOT EXISTS sync_state (
                    dataset TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    last_synced_at TEXT,
                    last_success_at TEXT,
                    last_error_at TEXT,
                    last_error_message TEXT,
                    records_written INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER,
                    PRIMARY KEY (dataset, ticker)
                );
                """
            )
        with self.connect() as connection:
            try:
                connection.execute("ALTER TABLE event ADD COLUMN importance TEXT")
            except sqlite3.OperationalError:
                pass
            for statement in (
                "ALTER TABLE company_profile ADD COLUMN dedupe_key TEXT",
                "ALTER TABLE company_profile ADD COLUMN source_priority INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE event ADD COLUMN dedupe_key TEXT",
                "ALTER TABLE event ADD COLUMN raw_title TEXT",
                "ALTER TABLE event ADD COLUMN event_type TEXT",
                "ALTER TABLE event ADD COLUMN sentiment TEXT",
                "ALTER TABLE event ADD COLUMN source_type TEXT",
                "ALTER TABLE event ADD COLUMN source_priority INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE financial_summary ADD COLUMN dedupe_key TEXT",
                "ALTER TABLE financial_summary ADD COLUMN source_priority INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE price_daily ADD COLUMN dedupe_key TEXT",
                "ALTER TABLE price_daily ADD COLUMN source_priority INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE sync_state ADD COLUMN last_synced_at TEXT",
                "ALTER TABLE sync_state ADD COLUMN last_success_at TEXT",
                "ALTER TABLE sync_state ADD COLUMN last_error_at TEXT",
                "ALTER TABLE sync_state ADD COLUMN last_error_message TEXT",
                "ALTER TABLE sync_state ADD COLUMN records_written INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE sync_state ADD COLUMN duration_ms INTEGER",
                "CREATE INDEX IF NOT EXISTS idx_event_dedupe_key ON event (ticker, dedupe_key)",
            ):
                try:
                    connection.execute(statement)
                except sqlite3.OperationalError:
                    pass

    def ping(self) -> bool:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return True

    def upsert_company_profile(self, profile: CompanyProfile) -> CompanyProfile:
        payload = profile.model_dump()
        payload["updated_at"] = payload["updated_at"] or _utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO company_profile (
                    ticker, name, exchange, market, industry, area, list_date, status,
                    website, chairman, manager, employees, main_business, business_scope,
                    source, dedupe_key, source_priority, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    exchange=excluded.exchange,
                    market=excluded.market,
                    industry=excluded.industry,
                    area=excluded.area,
                    list_date=excluded.list_date,
                    status=excluded.status,
                    website=excluded.website,
                    chairman=excluded.chairman,
                    manager=excluded.manager,
                    employees=excluded.employees,
                    main_business=excluded.main_business,
                    business_scope=excluded.business_scope,
                    source=excluded.source,
                    dedupe_key=excluded.dedupe_key,
                    source_priority=excluded.source_priority,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                (
                    payload["ticker"],
                    payload["name"],
                    payload["exchange"],
                    payload["market"],
                    payload["industry"],
                    payload["area"],
                    payload["list_date"],
                    payload["status"],
                    payload["website"],
                    payload["chairman"],
                    payload["manager"],
                    payload["employees"],
                    payload["main_business"],
                    payload["business_scope"],
                    payload["source"],
                    payload.get("dedupe_key"),
                    payload.get("source_priority", 0),
                    json.dumps(payload["raw"], ensure_ascii=False),
                    payload["updated_at"],
                ),
            )
        self.mark_synced("company_profile", profile.ticker, payload["updated_at"])
        return profile.model_copy(update={"updated_at": payload["updated_at"]})

    def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM company_profile WHERE ticker = ?", (ticker,)).fetchone()
        return self._company_from_row(row) if row else None

    def upsert_events(self, ticker: str, events: list[Event]) -> list[Event]:
        synced_at = _utc_now()
        with self.connect() as connection:
            for event in events:
                payload = event.model_dump()
                payload["updated_at"] = synced_at
                connection.execute(
                    """
                    INSERT INTO event (
                        event_id, dedupe_key, ticker, event_date, title, raw_title, event_type,
                        category, sentiment, source_type, source, source_priority, url, summary,
                        importance, raw_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        dedupe_key=excluded.dedupe_key,
                        ticker=excluded.ticker,
                        event_date=excluded.event_date,
                        title=excluded.title,
                        raw_title=excluded.raw_title,
                        event_type=excluded.event_type,
                        category=excluded.category,
                        sentiment=excluded.sentiment,
                        source_type=excluded.source_type,
                        source=excluded.source,
                        source_priority=excluded.source_priority,
                        url=excluded.url,
                        summary=excluded.summary,
                        importance=excluded.importance,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        payload["event_id"],
                        payload.get("dedupe_key"),
                        payload["ticker"],
                        payload["event_date"],
                        payload["title"],
                        payload.get("raw_title"),
                        payload.get("event_type"),
                        payload["category"],
                        payload.get("sentiment"),
                        payload.get("source_type"),
                        payload["source"],
                        payload.get("source_priority", 0),
                        payload["url"],
                        payload["summary"],
                        payload.get("importance"),
                        json.dumps(payload["raw"], ensure_ascii=False),
                        payload["updated_at"],
                    ),
                )
        self.mark_synced("event", ticker, synced_at)
        return [event.model_copy(update={"updated_at": synced_at}) for event in events]

    def replace_events(self, ticker: str, events: list[Event]) -> list[Event]:
        synced_at = _utc_now()
        with self.connect() as connection:
            connection.execute("DELETE FROM event WHERE ticker = ?", (ticker,))
            for event in events:
                payload = event.model_dump()
                payload["updated_at"] = synced_at
                connection.execute(
                    """
                    INSERT INTO event (
                        event_id, dedupe_key, ticker, event_date, title, raw_title, event_type,
                        category, sentiment, source_type, source, source_priority, url, summary,
                        importance, raw_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["event_id"],
                        payload.get("dedupe_key"),
                        payload["ticker"],
                        payload["event_date"],
                        payload["title"],
                        payload.get("raw_title"),
                        payload.get("event_type"),
                        payload["category"],
                        payload.get("sentiment"),
                        payload.get("source_type"),
                        payload["source"],
                        payload.get("source_priority", 0),
                        payload["url"],
                        payload["summary"],
                        payload.get("importance"),
                        json.dumps(payload["raw"], ensure_ascii=False),
                        payload["updated_at"],
                    ),
                )
        self.mark_synced("event", ticker, synced_at)
        return [event.model_copy(update={"updated_at": synced_at}) for event in events]

    def list_events(self, ticker: str, limit: int = 20) -> list[Event]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM event
                WHERE ticker = ?
                ORDER BY COALESCE(event_date, '') DESC, updated_at DESC
                LIMIT ?
                """,
                (ticker, limit),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def upsert_financial_summaries(self, ticker: str, items: list[FinancialSummary]) -> list[FinancialSummary]:
        synced_at = _utc_now()
        with self.connect() as connection:
            for item in items:
                payload = item.model_dump()
                payload["updated_at"] = synced_at
                connection.execute(
                    """
                    INSERT INTO financial_summary (
                        record_id, dedupe_key, ticker, report_date, announcement_date, report_type,
                        revenue, revenue_yoy, net_profit, net_profit_yoy, eps, roe,
                        gross_margin, source, source_priority, raw_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_id) DO UPDATE SET
                        dedupe_key=excluded.dedupe_key,
                        ticker=excluded.ticker,
                        report_date=excluded.report_date,
                        announcement_date=excluded.announcement_date,
                        report_type=excluded.report_type,
                        revenue=excluded.revenue,
                        revenue_yoy=excluded.revenue_yoy,
                        net_profit=excluded.net_profit,
                        net_profit_yoy=excluded.net_profit_yoy,
                        eps=excluded.eps,
                        roe=excluded.roe,
                        gross_margin=excluded.gross_margin,
                        source=excluded.source,
                        source_priority=excluded.source_priority,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        payload["record_id"],
                        payload.get("dedupe_key"),
                        payload["ticker"],
                        payload["report_date"],
                        payload["announcement_date"],
                        payload["report_type"],
                        payload["revenue"],
                        payload["revenue_yoy"],
                        payload["net_profit"],
                        payload["net_profit_yoy"],
                        payload["eps"],
                        payload["roe"],
                        payload["gross_margin"],
                        payload["source"],
                        payload.get("source_priority", 0),
                        json.dumps(payload["raw"], ensure_ascii=False),
                        payload["updated_at"],
                    ),
                )
        self.mark_synced("financial_summary", ticker, synced_at)
        return [item.model_copy(update={"updated_at": synced_at}) for item in items]

    def list_financial_summaries(self, ticker: str, limit: int = 8) -> list[FinancialSummary]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM financial_summary
                WHERE ticker = ?
                ORDER BY report_date DESC
                LIMIT ?
                """,
                (ticker, limit),
            ).fetchall()
        return [self._financial_from_row(row) for row in rows]

    def upsert_prices(self, ticker: str, prices: list[PriceDaily]) -> list[PriceDaily]:
        synced_at = _utc_now()
        with self.connect() as connection:
            for price in prices:
                payload = price.model_dump()
                payload["updated_at"] = synced_at
                connection.execute(
                    """
                    INSERT INTO price_daily (
                        ticker, trade_date, dedupe_key, open, high, low, close, volume, amount,
                        change_pct, turnover_rate, source, source_priority, raw_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, trade_date) DO UPDATE SET
                        dedupe_key=excluded.dedupe_key,
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        volume=excluded.volume,
                        amount=excluded.amount,
                        change_pct=excluded.change_pct,
                        turnover_rate=excluded.turnover_rate,
                        source=excluded.source,
                        source_priority=excluded.source_priority,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        payload["ticker"],
                        payload["trade_date"],
                        payload.get("dedupe_key"),
                        payload["open"],
                        payload["high"],
                        payload["low"],
                        payload["close"],
                        payload["volume"],
                        payload["amount"],
                        payload["change_pct"],
                        payload["turnover_rate"],
                        payload["source"],
                        payload.get("source_priority", 0),
                        json.dumps(payload["raw"], ensure_ascii=False),
                        payload["updated_at"],
                    ),
                )
        self.mark_synced("price_daily", ticker, synced_at)
        return [price.model_copy(update={"updated_at": synced_at}) for price in prices]

    def list_prices(
        self,
        ticker: str,
        limit: int = 60,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[PriceDaily]:
        clauses = ["ticker = ?"]
        params: list[object] = [ticker]
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)
        params.append(limit)
        query = f"""
            SELECT * FROM price_daily
            WHERE {' AND '.join(clauses)}
            ORDER BY trade_date DESC
            LIMIT ?
        """
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._price_from_row(row) for row in rows]

    def mark_synced(self, dataset: str, ticker: str, synced_at: str) -> None:
        self.record_sync_result(dataset, ticker, synced_at, success=True)

    def record_sync_result(
        self,
        dataset: str,
        ticker: str,
        synced_at: str,
        *,
        success: bool,
        error_message: str | None = None,
        records_written: int = 0,
        duration_ms: int | None = None,
    ) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT synced_at, last_synced_at, last_success_at, last_error_at, last_error_message, records_written, duration_ms
                FROM sync_state
                WHERE dataset = ? AND ticker = ?
                """,
                (dataset, ticker),
            ).fetchone()
            last_success_at = synced_at if success else (existing["last_success_at"] if existing else None)
            last_error_at = None if success else synced_at
            last_error_message = None if success else error_message
            connection.execute(
                """
                INSERT INTO sync_state (
                    dataset, ticker, synced_at, last_synced_at, last_success_at,
                    last_error_at, last_error_message, records_written, duration_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset, ticker) DO UPDATE SET
                    synced_at=excluded.synced_at,
                    last_synced_at=excluded.last_synced_at,
                    last_success_at=excluded.last_success_at,
                    last_error_at=excluded.last_error_at,
                    last_error_message=excluded.last_error_message,
                    records_written=excluded.records_written,
                    duration_ms=excluded.duration_ms
                """,
                (
                    dataset,
                    ticker,
                    synced_at,
                    synced_at,
                    last_success_at,
                    last_error_at,
                    last_error_message,
                    records_written,
                    duration_ms,
                ),
            )

    def get_last_synced_at(self, dataset: str, ticker: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(last_synced_at, synced_at) AS last_synced_at FROM sync_state WHERE dataset = ? AND ticker = ?",
                (dataset, ticker),
            ).fetchone()
        return row["last_synced_at"] if row else None

    def get_sync_state(self, dataset: str, ticker: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT dataset, ticker, synced_at, last_synced_at, last_success_at, last_error_at,
                       last_error_message, records_written, duration_ms
                FROM sync_state
                WHERE dataset = ? AND ticker = ?
                """,
                (dataset, ticker),
            ).fetchone()
        return self._sync_state_from_row(row) if row else None

    def list_sync_state(self, ticker: str | None = None) -> list[dict]:
        query = """
            SELECT dataset, ticker, synced_at, last_synced_at, last_success_at, last_error_at,
                   last_error_message, records_written, duration_ms
            FROM sync_state
        """
        params: tuple[object, ...] = ()
        if ticker:
            query += " WHERE ticker = ?"
            params = (ticker,)
        query += " ORDER BY ticker ASC, dataset ASC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._sync_state_from_row(row) for row in rows]

    def _company_from_row(self, row: sqlite3.Row) -> CompanyProfile:
        return CompanyProfile(
            ticker=row["ticker"],
            name=row["name"],
            exchange=row["exchange"],
            market=row["market"],
            industry=row["industry"],
            area=row["area"],
            list_date=row["list_date"],
            status=row["status"],
            website=row["website"],
            chairman=row["chairman"],
            manager=row["manager"],
            employees=row["employees"],
            main_business=row["main_business"],
            business_scope=row["business_scope"],
            source=row["source"],
            dedupe_key=row["dedupe_key"] or row["ticker"],
            source_priority=row["source_priority"],
            updated_at=row["updated_at"],
            raw=json.loads(row["raw_json"]),
        )

    def _event_from_row(self, row: sqlite3.Row) -> Event:
        return Event(
            event_id=row["event_id"],
            dedupe_key=row["dedupe_key"] or row["event_id"],
            ticker=row["ticker"],
            event_date=row["event_date"],
            title=row["title"],
            raw_title=row["raw_title"] or row["title"],
            event_type=row["event_type"],
            category=row["category"],
            sentiment=row["sentiment"],
            source_type=row["source_type"],
            source=row["source"],
            source_priority=row["source_priority"],
            url=row["url"],
            source_url=row["url"],
            summary=row["summary"],
            importance=row["importance"],
            updated_at=row["updated_at"],
            raw=json.loads(row["raw_json"]),
        )

    def _financial_from_row(self, row: sqlite3.Row) -> FinancialSummary:
        return FinancialSummary(
            record_id=row["record_id"],
            dedupe_key=row["dedupe_key"] or row["record_id"],
            ticker=row["ticker"],
            report_date=row["report_date"],
            announcement_date=row["announcement_date"],
            report_type=row["report_type"],
            revenue=row["revenue"],
            revenue_yoy=row["revenue_yoy"],
            net_profit=row["net_profit"],
            net_profit_yoy=row["net_profit_yoy"],
            eps=row["eps"],
            roe=row["roe"],
            gross_margin=row["gross_margin"],
            source=row["source"],
            source_priority=row["source_priority"],
            updated_at=row["updated_at"],
            raw=json.loads(row["raw_json"]),
        )

    def _price_from_row(self, row: sqlite3.Row) -> PriceDaily:
        return PriceDaily(
            ticker=row["ticker"],
            trade_date=row["trade_date"],
            dedupe_key=row["dedupe_key"] or f"{row['ticker']}:{row['trade_date']}",
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            amount=row["amount"],
            change_pct=row["change_pct"],
            turnover_rate=row["turnover_rate"],
            source=row["source"],
            source_priority=row["source_priority"],
            updated_at=row["updated_at"],
            raw=json.loads(row["raw_json"]),
        )

    def _sync_state_from_row(self, row: sqlite3.Row) -> dict:
        last_synced_at = row["last_synced_at"] or row["synced_at"]
        last_success_at = row["last_success_at"] or row["synced_at"]
        last_error_at = row["last_error_at"]
        if last_error_at and not last_success_at:
            status = "failed"
        elif last_error_at and last_success_at and last_error_at >= last_success_at:
            status = "failed"
        elif last_error_at and last_success_at:
            status = "partial"
        else:
            status = "ok"
        return {
            "dataset": row["dataset"],
            "ticker": row["ticker"],
            "status": status,
            "synced_at": row["synced_at"],
            "last_synced_at": last_synced_at,
            "last_success_at": last_success_at,
            "last_error_at": last_error_at,
            "last_error_message": row["last_error_message"],
            "records_written": row["records_written"],
            "duration_ms": row["duration_ms"],
        }


_repository: SQLiteRepository | None = None


def get_repository() -> SQLiteRepository:
    global _repository
    if _repository is None:
        _repository = SQLiteRepository(settings.sqlite_db_path)
    return _repository


def init_db() -> None:
    get_repository().init_db()
