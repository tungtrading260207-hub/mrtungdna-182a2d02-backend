import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from ..config import settings
from ..db import SupabaseClient
from ..rate_limiter import anti_429_delay
from .no_api_scrapers import NoApiScraper
from .antigravity_engine import AntigravityEngine


class AntiTrapShortEngine:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.scraper = NoApiScraper()
        self.ag_engine = AntigravityEngine()

    async def scan(self) -> list[dict]:
        symbols = await self.fetch_symbols()
        signals: list[dict] = []
        
        if not symbols:
            return signals

        # 1. TradingView Pre-filter (No-API) to avoid Binance Rate Limit
        tv_tickers = [f"BINANCE:{s}" for s in symbols]
        tv_data = await self.scraper.scan_tradingview(["crypto"], tv_tickers)
        
        filtered_symbols = []
        if tv_data and "data" in tv_data:
            for item in tv_data["data"]:
                sym = item.get("s", "").replace("BINANCE:", "")
                d = item.get("d", [])
                if len(d) >= 5:
                    mfi = d[4] # MoneyFlow is index 4 based on columns list
                    # Lọc thô MFI > 80
                    if mfi is not None and mfi > 80:
                        filtered_symbols.append(sym)
        else:
            # Fallback if TradingView fails
            filtered_symbols = symbols

        for symbol in filtered_symbols:
            try:
                signal = await self.evaluate_symbol(symbol)
                if signal:
                    signals.append(signal)
            except Exception as exc:
                logging.warning("[AntiTrapShort] Error scanning %s: %s", symbol, exc)

        if signals:
            logging.info("[AntiTrapShort] Writing %d signals to Supabase.", len(signals))
            await self.supabase_client.insert_rows(settings.inverse_short_table, signals)

        return signals

    async def fetch_symbols(self) -> list[str]:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get("https://api.binance.com/api/v3/ticker/24hr")
            response.raise_for_status()
            await anti_429_delay()
            tickers = response.json()[:200]

        filtered = [
            item["symbol"]
            for item in tickers
            if item["symbol"].endswith("USDT") and float(item.get("volume", 0) or 0) >= 2000
        ]
        return filtered[:50]

    async def evaluate_symbol(self, symbol: str) -> dict | None:
        candles_h4 = await self.fetch_klines(symbol, "4h", 80)
        candles_d1 = await self.fetch_klines(symbol, "1d", 90)

        if len(candles_h4) < 30 or len(candles_d1) < 50:
            return None

        vwap = self.compute_vwap(candles_d1)
        last_close = candles_d1[-1]["close"]
        if last_close >= vwap:
            return None

        hma_values = self.compute_hma([c["close"] for c in candles_d1], 21)
        if len(hma_values) < 2 or (hma_values[-1] - hma_values[-2]) > 0:
            return None

        mfi_values = self.compute_mfi(candles_d1)
        if len(mfi_values) < 2 or not (mfi_values[-1] > 80 and mfi_values[-2] > mfi_values[-1]):
            return None

        cvd_signals = self.compute_cvd_divergence(candles_d1)
        if not cvd_signals:
            return None

        fvg_top, fvg_bottom = self.find_nearest_fvg(candles_d1)
        entry, stop_loss, take_profit = self.calculate_targets(last_close, fvg_top, fvg_bottom)
        score = self.compute_setup_score(last_close, vwap, hma_values[-1], mfi_values[-1], cvd_signals)

        # -----------------------------
        # Áp dụng AntigravityEngine
        # -----------------------------
        asset_class = self.ag_engine.classify_asset(symbol)
        side = "SHORT"
        pnl_info = self.ag_engine.calculate_pnl_expected(
            asset_class=asset_class, side=side, entry=entry, sl=stop_loss, tp=take_profit, capital=1000, leverage=10
        )
        
        hma_slope = hma_values[-1] - hma_values[-2] if len(hma_values) >= 2 else 0
        cvd_trend = "DIVERGENCE" if cvd_signals else "DOWNTREND"
        
        status, recommendation = self.ag_engine.generate_realtime_recommendation(
            asset_class=asset_class, side=side, current_price=last_close, entry=entry, 
            hma_slope=hma_slope, cvd_trend=cvd_trend, mfi=mfi_values[-1]
        )

        formatted_notes = f"[{status}] {recommendation}"
        formatted_details = (
            f"Giá dưới Anchored VWAP {round(vwap, 6)}, HMA slope <=0, MFI {round(mfi_values[-1], 1)} đang xuống, "
            f"CVD divergence phát hiện. | PnL: Size={pnl_info['position_size']}, "
            f"SL={pnl_info['pnl_at_sl']}, TP={pnl_info['pnl_at_tp']}, RR={pnl_info['risk_reward_ratio']}"
        )

        return {
            "ticker": symbol,
            "timeframe": "H4/D1",
            "entry_price": round(entry, 6),
            "stop_loss": round(stop_loss, 6),
            "take_profit": round(take_profit, 6),
            "analysis_score": round(score, 1),
            "detected_at": (datetime.now(timezone.utc) + timedelta(hours=7)).isoformat(),
            "trigger_details": formatted_details,
            "source": "AntiTrapShort",
            "notes": formatted_notes,
            "fvg_top": round(fvg_top, 6),
            "fvg_bottom": round(fvg_bottom, 6),
        }

    async def fetch_klines(self, symbol: str, interval: str, limit: int) -> list[dict]:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            response.raise_for_status()
            await anti_429_delay()
            raw = response.json()

        return [
            {
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "quote_volume": float(item[7]),
                "timestamp": int(item[0]),
            }
            for item in raw
        ]

    def compute_vwap(self, candles: list[dict]) -> float:
        total_flow = 0.0
        total_volume = 0.0
        for candle in candles[-50:]:
            typical_price = (candle["high"] + candle["low"] + candle["close"]) / 3.0
            total_flow += typical_price * candle["volume"]
            total_volume += candle["volume"]
        return total_flow / total_volume if total_volume else candles[-1]["close"]

    def compute_ema(self, values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        ema_values = []
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        ema_values.append(ema)
        for price in values[period:]:
            ema = (price - ema) * multiplier + ema
            ema_values.append(ema)
        return ema_values

    def compute_wma(self, values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        result = []
        for i in range(period, len(values) + 1):
            window = values[i - period : i]
            denominator = sum(range(1, period + 1))
            weighted_sum = sum(weight * price for weight, price in zip(range(1, period + 1), window))
            result.append(weighted_sum / denominator)
        return result

    def compute_hma(self, values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        half_length = max(1, period // 2)
        sqrt_length = max(1, int(math.sqrt(period)))
        wma_half = self.compute_wma(values, half_length)
        wma_full = self.compute_wma(values, period)
        diff_series = [2 * half - full for half, full in zip(wma_half[len(wma_half) - len(wma_full) :], wma_full)]
        return self.compute_wma(diff_series, sqrt_length)

    def compute_mfi(self, candles: list[dict]) -> list[float]:
        typical_prices = [((c["high"] + c["low"] + c["close"]) / 3.0) for c in candles]
        positive_flow = 0.0
        negative_flow = 0.0
        mfi_values: list[float] = []

        for i in range(1, len(candles)):
            money_flow = typical_prices[i] * candles[i]["volume"]
            if typical_prices[i] > typical_prices[i - 1]:
                positive_flow += money_flow
            else:
                negative_flow += money_flow

            if i >= 13:
                ratio = positive_flow / negative_flow if negative_flow else positive_flow
                mfi_values.append(100 - 100 / (1 + ratio))

        return mfi_values

    def compute_cvd_divergence(self, candles: list[dict]) -> bool:
        if len(candles) < 5:
            return False

        delta_values = []
        for candle in candles[-5:]:
            delta_values.append((candle["close"] - candle["open"]) * candle["volume"])

        price_move = candles[-1]["close"] - candles[-2]["close"]
        decreasing_delta = delta_values[-1] < delta_values[-2] < delta_values[-3]
        return price_move > 0 and decreasing_delta

    def find_nearest_fvg(self, candles: list[dict]) -> tuple[float, float]:
        for idx in range(len(candles) - 1, 2, -1):
            current = candles[idx]
            prior = candles[idx - 1]
            if current["low"] > prior["high"]:
                return prior["high"], current["low"]
            if current["high"] < prior["low"]:
                return current["high"], prior["low"]

        last = candles[-2]
        return last["high"], last["low"]

    def calculate_targets(self, close: float, fvg_top: float, fvg_bottom: float) -> tuple[float, float, float]:
        entry = min(close * 0.998, fvg_top * 0.998)
        stop_loss = max(fvg_top * 1.02, close * 1.03)
        take_profit = max(close - (stop_loss - entry) * 1.5, fvg_bottom)
        return entry, stop_loss, take_profit

    def compute_setup_score(self, close: float, vwap: float, hma: float, mfi: float, divergence: bool) -> float:
        score = 0.0
        if close < vwap:
            score += 2.5
        if hma <= 0:
            score += 2.0
        if mfi > 80:
            score += 2.0
        if divergence:
            score += 2.0
        return min(score, 10.0)
