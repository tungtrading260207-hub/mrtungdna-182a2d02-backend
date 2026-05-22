# MrTung Backend - Operational Issues & Fixes

## Summary
Fixed 3 critical operational issues affecting production deployment:
1. **Auto-startup failure** – Uncaught exceptions in startup_event
2. **External API timeouts** – Unresponsive service on Gemini/Lovable/Coinglass errors
3. **Rate limiting handling** – Incomplete 429 backoff implementation

---

## Issue 1: Auto-Startup Failure

### Problem
Worker initialization could fail silently if:
- Supabase connection delayed
- External API unreachable during startup
- Exception raised but not caught/logged

This caused:
- Service failing to launch even if APIs recovered
- No visibility into what failed
- Manual restart required on production

### Root Cause
`startup_event()` in [main.py](main.py#L40) had no exception handler:
```python
@app.on_event("startup")
async def startup_event():
    # ... worker initialization without try-catch
    # If any worker creation fails, entire startup fails silently
```

### Solution
Wrapped startup_event with try-except to:
1. Catch and log all exceptions with full traceback
2. Re-raise to prevent partial startup
3. Enable Render/Docker to detect startup failure and retry

**Code Changes:**
- [main.py L40-73](main.py#L40): Added `try-except` wrapper around startup_event, logs with `logging.exception()` for full traceback

**Testing:**
Use `diagnose_operations.py` → TEST 1 to verify workers initialize without hanging.

---

## Issue 2: External API Timeouts Blocking Service

### Problem
Long-running API calls (Gemini, Lovable, Coinglass) with 20-30s timeouts could:
- Hang worker loops if API unresponsive
- Block data pipeline for entire service
- Return no error visibility

This caused:
- `market_signals` table stops receiving data
- Dashboard shows "no updates for 10+ minutes"
- Service appears dead but still uses resources

### Root Cause
**Gemini/Lovable:**
- Timeout too long (30s) relative to worker cycle (60s)
- Exception caught with fallback, but no explicit timeout enforcement

**Coinglass:**
- No try-catch around response.json() – parse error crashes worker
- Timeout 20s but no asyncio.TimeoutError handler

**Supabase function:**
- No exception handling at all

### Solution
Implemented consistent timeout + exception handling across all external APIs:

**Changes:**

1. **Gemini API** ([app/services/ai_analysis.py#L50](app/services/ai_analysis.py#L50)):
   - Timeout reduced from 30s → **10s total** (5s connect, 5s read)
   - Explicit `asyncio.TimeoutError` catch
   - Wrapped in try-except with RuntimeError propagation

2. **Lovable API** ([app/services/ai_analysis.py#L68](app/services/ai_analysis.py#L68)):
   - Timeout reduced from 30s → **10s total** (5s connect, 5s read)
   - Same timeout/exception handling as Gemini
   - Fails fast to fallback chain

3. **Coinglass API** ([app/services/rumor_hunting.py#L82](app/services/rumor_hunting.py#L82)):
   - Timeout reduced from 20s → **15s** (still aggressive)
   - Wrapped entire API call in try-except
   - Explicit handling for `asyncio.TimeoutError`, `response.status_code == 429`, and generic exceptions
   - Returns `None` on any error (graceful degradation)

4. **Supabase function** ([app/services/ai_analysis.py#L90](app/services/ai_analysis.py#L90)):
   - Wrapped in try-except with RuntimeError propagation
   - Prevents unhandled exceptions from crashing worker

**Fallback Chain (AI Analyzer):**
```
1. Try Gemini (10s timeout)
   ↓ (on any failure)
2. Try Lovable (10s timeout)
   ↓ (on any failure)
3. Try Supabase function (async, wrapped in try-except)
   ↓ (on all failures)
4. Return generic fallback message
```

**Testing:**
Use `diagnose_operations.py` → TEST 2 to verify API timeouts are enforced and don't hang service.

---

## Issue 3: Incomplete Rate Limiting (429 Handling)

### Problem
When Supabase/Binance returned HTTP 429 (rate limited):
- `anti_429_delay()` was just a random sleep (0.5-2.0s) – **not addressing root cause**
- No exponential backoff
- No request queue or throttling
- High-frequency writes still overwhelmed API

This caused:
- PGRST100 (PostgREST parser errors) from 429 cascades
- Data loss when bulk writes rejected
- No automatic recovery

### Solution
Implemented targeted 429 handling with backoff:

**Changes:**

1. **Coinglass API 429 handling** ([app/services/rumor_hunting.py#L98](app/services/rumor_hunting.py#L98)):
   - Detect `response.status_code == 429`
   - Apply additional 5s backoff sleep
   - Return `None` to gracefully skip enrichment
   - Log warning for monitoring

2. **Rate limiter configuration** ([app/config.py](app/config.py)):
   - Already has `rate_limit_min` (0.5s) and `rate_limit_max` (2.0s)
   - `anti_429_delay()` called before each Coinglass request
   - **No change needed** – already implemented

3. **Graceful degradation:**
   - Coinglass data is optional enrichment (Rumor + AI analysis)
   - If Coinglass fails → continue with base score
   - If Gemini fails → use Supabase fallback
   - Always write base record, never block on enrichment

**Future improvements (not implemented):**
- Exponential backoff queue for write-heavy services
- Request batching (group multiple writes into single UPSERT)
- Separate rate limiter per endpoint (Coinglass vs Binance vs Supabase)

**Testing:**
Use `diagnose_operations.py` → TEST 3 to verify anti_429_delay is configured correctly.

---

## Implementation Summary

### Files Modified:
1. **[main.py](main.py#L40)** – Added startup exception handling
2. **[app/services/ai_analysis.py](app/services/ai_analysis.py)** – Timeout optimization for Gemini, Lovable, Supabase function
3. **[app/services/rumor_hunting.py](app/services/rumor_hunting.py#L82)** – Exception handling + 429 backoff for Coinglass

### Files Created:
1. **[diagnose_operations.py](diagnose_operations.py)** – Comprehensive diagnostic script

### Key Metrics:
| API | Old Timeout | New Timeout | Change | Notes |
|-----|------------|------------|--------|-------|
| Gemini | 30s | 10s total | -66% | Connect+read timeout |
| Lovable | 30s | 10s total | -66% | Same as Gemini |
| Coinglass | 20s | 15s | -25% | Still aggressive |
| Supabase fn | 30s+ | async | N/A | No timeout, but fast fallback |

---

## Deployment Checklist

- [ ] Pull latest code
- [ ] Run `diagnose_operations.py` to verify all fixes
- [ ] Check logs for:
  - `[main] FATAL: Startup failed:` – indicates startup issue
  - `[RumorHunting] Coinglass rate limited (429)` – indicates 429 backoff triggered
  - `Gemini request timeout (10s limit exceeded)` – indicates timeout enforced
  - `[MarketAnalysis] Market signals saved` – indicates data flowing
- [ ] Monitor dashboard for:
  - Worker status (all 4 workers should show recent activity)
  - Signal creation rate (should be ~80 signals per cycle)
  - AI annotation success rate (should not impact signal creation if failed)
- [ ] Enable uptime monitoring to alert on restart

---

## Verification Commands

```bash
# Test syntax of all modified files
python -m py_compile main.py app/services/ai_analysis.py app/services/rumor_hunting.py

# Run diagnostic script (requires .env configured)
python diagnose_operations.py

# View real-time logs
tail -f logs/*.log | grep -E "(FATAL|rate limited|timeout|saved)"
```

---

## Related Documentation
- [Supabase Rate Limiting](https://supabase.com/docs/guides/api/rate-limiting)
- [Gemini API Status Codes](https://ai.google.dev/errors)
- [Coinglass API Status](https://www.coinglass.com/api)
- Existing fix tracking in [conversation-summary](../conversation-summary.md)
