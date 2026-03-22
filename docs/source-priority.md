# Source Priority

Current source priority rules prefer authoritative structured sources over fallback discovery sources.

Priority map:

- `tushare`: 100
- `cninfo`: 100
- `akshare`: 90
- `exchange_search`: 60
- `fallback`: 10
- `derived`: 0

## How It Is Used

- company profile prefers `tushare`
- financial summary prefers `tushare`
- daily prices prefer `akshare`, then fall back to `tushare`
- events prefer `cninfo`, then use `exchange_search` when direct disclosure fetch is empty or unavailable
- event dedupe keeps the higher-priority source when two normalized events share the same `dedupe_key`
