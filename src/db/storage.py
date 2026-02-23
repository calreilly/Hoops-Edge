"""
Phase 1 - Week 4: Knowledge Representation & Storage
- SQLite (sqlite_utils): bets ledger, bankroll, team stats
- LanceDB: vector embeddings for news/injury context (seeded for Phase 2 RAG)
"""
import json
import uuid
import sqlite_utils
import lancedb
from lancedb.pydantic import LanceModel, Vector
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

from src.models.schemas import BetRecommendation, TeamStats

VECTOR_DIM = 384
_embedding_model = None


def get_embedding_model():
    """Lazy-load SentenceTransformer only when vector search is needed (Phase 2)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for vector search. "
                "Run: pip install sentence-transformers"
            )
    return _embedding_model


# ─── LanceDB Schema ───────────────────────────────────────────────────────────

class NewsChunk(LanceModel):
    """A chunk of news/injury text for vector search (used in Phase 2 RAG)."""
    chunk_id: str
    vector: Vector(VECTOR_DIM)
    text: str
    team: str        # team the article refers to
    source: str      # e.g. 'ESPN', 'Twitter', 'manual'
    created_at: str  # ISO timestamp


# ─── SQLite Storage ────────────────────────────────────────────────────────────

class BetLedger:
    """
    Manages two SQLite tables:
      - bets: every recommendation the agent makes
      - bankroll: running balance and unit size
      - team_stats: historical team performance data
    """

    def __init__(self, db_path: str = "data/hoops_edge.db"):
        self.db = sqlite_utils.Database(db_path)
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.db["bets"].create({
            "id": str,
            "game_id": str,
            "home_team": str,
            "away_team": str,
            "game_time": str,
            "bet_type": str,
            "side": str,
            "line": float,
            "american_odds": int,
            "projected_prob": float,
            "implied_prob": float,
            "expected_value": float,
            "recommended_units": float,
            "is_recommended": int,   # SQLite has no bool; 0/1
            "summary": str,
            "reasoning": str,        # JSON-serialized CoT steps
            "status": str,           # 'pending', 'approved', 'rejected', 'settled'
            "result": str,           # 'win', 'loss', 'push', null
            "profit_loss": float,    # units won/lost after settlement
            "created_at": str,
        }, pk="id", if_not_exists=True)

        self.db["bankroll"].create({
            "id": int,
            "balance_units": float,
            "unit_dollar_value": float,
            "updated_at": str,
        }, pk="id", if_not_exists=True)

        self.db["team_stats"].create({
            "team_id": str,
            "team_name": str,
            "record": str,
            "offensive_efficiency": float,
            "defensive_efficiency": float,
            "pace": float,
            "three_point_rate": float,
            "ats_record": str,
            "conference": str,
            "last_updated": str,
        }, pk="team_id", if_not_exists=True)

        # Seed bankroll if empty
        if not list(self.db["bankroll"].rows):
            self.db["bankroll"].insert({
                "id": 1,
                "balance_units": 100.0,
                "unit_dollar_value": 10.0,
                "updated_at": datetime.utcnow().isoformat(),
            })

    # ── Bets ──────────────────────────────────────────────────────────────────

    def save_recommendation(self, rec: BetRecommendation) -> str:
        """Persist a BetRecommendation to the bets ledger."""
        bet_id = str(uuid.uuid4())
        row = {
            "id": bet_id,
            "game_id": rec.game_id,
            "home_team": rec.home_team,
            "away_team": rec.away_team,
            "game_time": rec.game_time.isoformat(),
            "bet_type": rec.bet_type.value,
            "side": rec.side.value,
            "line": rec.line,
            "american_odds": rec.american_odds,
            "projected_prob": rec.ev_analysis.projected_win_probability,
            "implied_prob": rec.ev_analysis.implied_probability,
            "expected_value": rec.ev_analysis.expected_value,
            "recommended_units": rec.recommended_units,
            "is_recommended": int(rec.is_recommended),
            "summary": rec.summary,
            "reasoning": json.dumps(rec.ev_analysis.reasoning_steps),
            "status": "pending",
            "result": None,
            "profit_loss": None,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.db["bets"].insert(row)
        return bet_id

    def approve_bet(self, bet_id: str):
        """Human-in-the-loop: mark a bet as approved (Week 11 prep)."""
        self.db["bets"].update(bet_id, {"status": "approved"})

    def reject_bet(self, bet_id: str):
        self.db["bets"].update(bet_id, {"status": "rejected"})

    def settle_bet(self, bet_id: str, result: str, profit_loss: float):
        """Settle a bet ('win'/'loss'/'push') and update bankroll."""
        self.db["bets"].update(bet_id, {
            "status": "settled",
            "result": result,
            "profit_loss": profit_loss,
        })
        row = list(self.db["bankroll"].rows)[0]
        new_balance = row["balance_units"] + profit_loss
        self.db["bankroll"].update(1, {
            "balance_units": new_balance,
            "updated_at": datetime.utcnow().isoformat(),
        })

    def get_pending_bets(self) -> list:
        return list(self.db["bets"].rows_where("status = ?", ["pending"]))

    def get_approved_bets(self) -> list:
        return list(self.db["bets"].rows_where("status = ?", ["approved"]))

    def get_bankroll(self) -> dict:
        return list(self.db["bankroll"].rows)[0]

    # ── Team Stats ────────────────────────────────────────────────────────────

    def upsert_team_stats(self, stats: TeamStats):
        row = stats.model_dump()
        row["last_updated"] = (
            stats.last_updated.isoformat() if stats.last_updated
            else datetime.utcnow().isoformat()
        )
        self.db["team_stats"].upsert(row, pk="team_id")

    def get_team_stats(self, team_id: str) -> Optional[dict]:
        rows = list(self.db["team_stats"].rows_where("team_id = ?", [team_id]))
        return rows[0] if rows else None

    def get_all_team_stats(self) -> list:
        return list(self.db["team_stats"].rows)


# ─── LanceDB News/Injury Store ─────────────────────────────────────────────────

class NewsVectorStore:
    """
    Stores and retrieves news/injury snippets as vector embeddings.
    Foundation for Phase 2 RAG pipeline.
    """

    def __init__(self, uri: str = "data/lancedb"):
        self.db = lancedb.connect(uri)
        self.table_name = "news_chunks"
        self._table = None
        self._init_table()

    def _init_table(self):
        self.db.create_table(self.table_name, schema=NewsChunk, exist_ok=True)

    @property
    def table(self):
        if self._table is None:
            self._table = self.db.open_table(self.table_name)
        return self._table

    def add_articles(self, texts: List[str], teams: List[str], sources: List[str]):
        """Embed and store news articles."""
        model = get_embedding_model()
        embeddings = model.encode(texts)
        rows = []
        for i, text in enumerate(texts):
            rows.append({
                "chunk_id": str(uuid.uuid4()),
                "vector": embeddings[i].tolist(),
                "text": text,
                "team": teams[i] if i < len(teams) else "unknown",
                "source": sources[i] if i < len(sources) else "unknown",
                "created_at": datetime.utcnow().isoformat(),
            })
        self.table.add(rows)

    def search(self, query: str, team_filter: Optional[str] = None, limit: int = 5) -> list:
        """Semantic search for news relevant to a team or matchup."""
        model = get_embedding_model()
        vec = model.encode([query])[0].tolist()
        results = self.table.search(vec).limit(limit).to_list()
        if team_filter:
            results = [r for r in results if r["team"].lower() == team_filter.lower()]
        return results
