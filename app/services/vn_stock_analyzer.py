import asyncio
import logging
from datetime import datetime, timezone
from typing import ClassVar
from httpx import AsyncClient
from pydantic import BaseModel, Field
from ..config import settings
from ..db import SupabaseClient
from core.validator import DataValidator
from core.schemas.stock_schema import VNStockProfile
from .vn_stock_source import VNStockSource


class VNStockProfilePayload(BaseModel):
    """Payload container for VN stock profile"""
    symbol: str
    net_flow: float | int = Field(default=0)
    flow_data: dict = Field(default_factory=dict)
    snapshot_date: str
    analyzed_at: str
    
    model_config = {"extra": "ignore"}


class VNStockAnalyzer:
    """Chuyên tìm kiếm và phân tích chứng khoán Việt Nam"""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.vn_source = VNStockSource()
        
    async def scan(self) -> list[dict]:
        """Fetch VN stock data từ API hoặc fallback scraper"""
        records: list[dict] = []
        
        # Lấy top 50 mã cổ phiếu VN nổi bật từ market snapshot
        snapshot = await self.vn_source.fetch_market_snapshot()
        if not snapshot:
            logging.warning("[VNStockAnalyzer] VN Stock market snapshot unavailable, skipping")
            return records
        
        # Extract top symbols từ snapshot
        symbols = self._extract_top_symbols(snapshot)
        if not symbols:
            logging.warning("[VNStockAnalyzer] No VN stock symbols found in snapshot")
            return records
        
        logging.info(f"[VNStockAnalyzer] Analyzing {len(symbols)} VN stock symbols")
        
        # Fetch dữ liệu từng symbol
        for symbol in symbols[:50]:  # Giới hạn 50 mã
            try:
                flow_data = await self.vn_source.fetch_symbol_flow(symbol)
                if flow_data:
                    record = self.build_profile_record(symbol, flow_data, snapshot)
                    records.append(record)
            except Exception as exc:
                logging.warning(f"[VNStockAnalyzer] Failed to fetch {symbol}: {exc}")
        
        # Validate và push lên Supabase
        if records:
            validated_records, validation_errors = DataValidator.validate_many(VNStockProfile, records)
            if validation_errors:
                logging.warning(f"[VNStockAnalyzer] Dropped {len(validation_errors)} invalid records")
            
            if validated_records:
                logging.info(f"[VNStockAnalyzer] Writing {len(validated_records)} VN stock profiles")
                await self.supabase_client.insert_rows("vn_stock_profiles", validated_records)
            else:
                logging.warning("[VNStockAnalyzer] No valid VN stock profiles to write")
        
        return records
    
    def _extract_top_symbols(self, snapshot: dict) -> list[str]:
        """Extract top VN stock symbols từ market snapshot"""
        try:
            # Nếu snapshot là list hoặc có field top_symbols
            if isinstance(snapshot, list):
                return [item.get("symbol") or item.get("ticker") for item in snapshot[:50] if item.get("symbol") or item.get("ticker")]
            
            # Nếu snapshot là dict với key tên thị trường
            for key in ["top_symbols", "symbols", "tickers", "data"]:
                if key in snapshot:
                    data = snapshot[key]
                    if isinstance(data, list):
                        return [item.get("symbol") or item.get("ticker") for item in data[:50]]
                    if isinstance(data, dict):
                        return list(data.keys())[:50]
            
            # Fallback: return empty nếu không tìm được
            return []
        except Exception as e:
            logging.warning(f"[VNStockAnalyzer] Failed to extract symbols: {e}")
            return []
    
    def build_profile_record(self, symbol: str, flow_data: dict, snapshot: dict) -> dict:
        """Build profile record cho một mã cổ phiếu"""
        timestamp = datetime.now(timezone.utc)
        timestamp_iso = timestamp.isoformat()
        
        # Lấy dữ liệu flow
        net_flow = flow_data.get("netFlow") or flow_data.get("flow") or 0
        source_name = flow_data.get("source") or settings.vn_stock_source or "DNS"
        
        return {
            "id": f"vn_{symbol}_{timestamp_iso[:10]}",  # Unique per day
            "symbol": symbol,
            "source": source_name,
            "payload": {
                "symbol": symbol,
                "net_flow": float(net_flow) if net_flow else 0.0,
                "flow_data": flow_data,
                "snapshot_date": timestamp_iso[:10],
                "analyzed_at": timestamp_iso,
            },
            "updated_at": timestamp,  # datetime object, not string
        }
