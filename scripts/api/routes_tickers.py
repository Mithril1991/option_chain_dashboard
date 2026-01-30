"""Routes for per-ticker knowledge base endpoints."""

from datetime import datetime, timezone
from pathlib import Path as PathlibPath
from typing import Optional, Dict, Any

from fastapi import APIRouter, Path, HTTPException
from pydantic import BaseModel, Field

from functions.util.logging_setup import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ThesisResponse(BaseModel):
    """Response model for thesis/risks/notes content."""

    ticker: str = Field(..., description="Stock ticker symbol")
    file_type: str = Field(..., description="File type: 'thesis', 'risks', or 'notes'")
    content: str = Field(..., description="Markdown file content")
    last_updated: Optional[str] = Field(None, description="File last modified timestamp")
    timestamp: str = Field(..., description="UTC ISO 8601 response timestamp")


def get_utc_iso_timestamp() -> str:
    """Get current UTC time in ISO 8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_tickers_dir() -> PathlibPath:
    """Get path to tickers/ directory containing per-ticker knowledge base."""
    project_root = PathlibPath(__file__).resolve().parents[2]
    return project_root / "tickers"


def load_thesis_file(ticker: str, file_type: str) -> Optional[str]:
    """Load thesis/risks/notes markdown file for a ticker."""
    try:
        valid_types = {"thesis": "theses.md", "risks": "risks.md", "notes": "notes.md"}
        if file_type not in valid_types:
            logger.warning(f"Invalid file type requested: {file_type}")
            return None

        ticker_clean = str(ticker).upper().replace("..", "").replace("/", "").replace("\\", "")
        if not ticker_clean or len(ticker_clean) > 10:
            logger.warning(f"Invalid ticker requested: {ticker}")
            return None

        tickers_dir = get_tickers_dir()
        file_path = tickers_dir / ticker_clean / valid_types[file_type]

        if not file_path.exists():
            logger.debug(f"Thesis file not found: {file_path}")
            return None

        with open(file_path, "r") as f:
            content = f.read()
            logger.debug(f"Loaded thesis file for {ticker_clean}/{file_type}: {len(content)} bytes")
            return content

    except Exception as e:
        logger.error(f"Failed to load thesis file for {ticker}/{file_type}: {e}")
        return None


@router.get("/tickers/{ticker}/thesis", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_thesis(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get investment thesis for a ticker."""
    try:
        content = load_thesis_file(ticker, "thesis")

        if not content:
            logger.info(f"Thesis not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Thesis not found for ticker '{ticker}'. Create tickers/{ticker}/theses.md to add.",
            )

        logger.debug(f"Retrieved thesis for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="thesis",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thesis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get thesis: {e}")


@router.get("/tickers/{ticker}/risks", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_risks(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get known risks for a ticker."""
    try:
        content = load_thesis_file(ticker, "risks")

        if not content:
            logger.info(f"Risks not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Risks not found for ticker '{ticker}'. Create tickers/{ticker}/risks.md to add.",
            )

        logger.debug(f"Retrieved risks for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="risks",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get risks for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get risks: {e}")


@router.get("/tickers/{ticker}/notes", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_notes(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get trading notes and observations for a ticker."""
    try:
        content = load_thesis_file(ticker, "notes")

        if not content:
            logger.info(f"Notes not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Notes not found for ticker '{ticker}'. Create tickers/{ticker}/notes.md to add.",
            )

        logger.debug(f"Retrieved notes for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="notes",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notes for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notes: {e}")


@router.get("/tickers/list", tags=["Theses"])
async def list_tickers() -> Dict[str, Any]:
    """List all available tickers with their knowledge base files."""
    try:
        tickers_dir = get_tickers_dir()

        if not tickers_dir.exists():
            logger.warning(f"Tickers directory not found: {tickers_dir}")
            return {
                "tickers": [],
                "total_count": 0,
                "timestamp": get_utc_iso_timestamp(),
            }

        tickers = []
        for ticker_dir in sorted(tickers_dir.iterdir()):
            if ticker_dir.is_dir():
                ticker_name = ticker_dir.name.upper()
                tickers.append(
                    {
                        "ticker": ticker_name,
                        "has_thesis": (ticker_dir / "theses.md").exists(),
                        "has_risks": (ticker_dir / "risks.md").exists(),
                        "has_notes": (ticker_dir / "notes.md").exists(),
                    }
                )

        logger.debug(f"Listed {len(tickers)} tickers from knowledge base")
        return {
            "tickers": tickers,
            "total_count": len(tickers),
            "timestamp": get_utc_iso_timestamp(),
        }

    except Exception as e:
        logger.error(f"Failed to list tickers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tickers: {e}")
