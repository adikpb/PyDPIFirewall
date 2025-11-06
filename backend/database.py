"""Database operations using SQLModel"""

from datetime import datetime, timedelta
from collections.abc import Iterable
from sqlmodel import SQLModel, create_engine, col, Session, select, func, delete
from .models import RequestLog
from .config import DB_URL
import logging

logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(DB_URL, echo=False)


def init_database():
    """Initialize database with required tables"""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def log_request(
    url: str,
    blocked: bool,
    headers: str | None = None,
    body: str | None = None,
    matched_rule: str | None = None,
):
    """Log a request to the database"""
    try:
        with Session(engine) as session:
            request_log = RequestLog(
                url=url,
                blocked=blocked,
                headers=headers,
                body=body,
                matched_rule=matched_rule,
            )
            session.add(request_log)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to log request: {e}")


def get_metrics() -> tuple[int, int]:
    """Get metrics: total requests and blocked requests"""
    try:
        with Session(engine) as session:
            total_stmt = select(func.count(col(RequestLog.id)))
            total_requests = session.exec(total_stmt).one()

            blocked_stmt = select(func.count(col(RequestLog.id))).where(
                RequestLog.blocked == True
            )
            blocked_requests = session.exec(blocked_stmt).one()

            return total_requests, blocked_requests
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return 0, 0


def get_logs(
    page: int = 1,
    page_size: int = 50,
    blocked: bool | None = None,
    url_contains: str | None = None,
) -> tuple[list[RequestLog], int]:
    """Paginate and filter logs"""
    with Session(engine) as session:
        stmt = select(RequestLog)
        count_stmt = select(func.count(col(RequestLog.id)))
        if blocked is not None:
            stmt = stmt.where(RequestLog.blocked == blocked)
            count_stmt = count_stmt.where(RequestLog.blocked == blocked)
        if url_contains:
            like = f"%{url_contains}%"
            stmt = stmt.where(col(RequestLog.url).like(like))
            count_stmt = count_stmt.where(col(RequestLog.url).like(like))
        total = session.exec(count_stmt).one()
        stmt = (
            stmt.order_by(col(RequestLog.id).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(session.exec(stmt).all())
        return items, total


def get_log_by_id(log_id: int) -> RequestLog | None:
    with Session(engine) as session:
        return session.get(RequestLog, log_id)


def delete_logs(blocked: bool | None = None) -> int:
    with Session(engine) as session:
        if blocked is None:
            # delete all
            stmt = delete(RequestLog)
            deleted = session.exec(stmt).rowcount
            session.commit()
            return deleted
        else:
            # delete by blocked flag
            stmt = delete(RequestLog).where(col(RequestLog.blocked) == blocked)
            deleted = session.exec(stmt).rowcount
            return deleted


def iterate_logs(blocked: bool | None = None) -> Iterable[RequestLog]:
    with Session(engine) as session:
        stmt = select(RequestLog)
        if blocked is not None:
            stmt = stmt.where(RequestLog.blocked == blocked)
        stmt = stmt.order_by(col(RequestLog.id).asc())
        for row in session.exec(stmt):
            yield row


def get_detailed_metrics() -> dict[str, int | dict[str, int]]:
    now = datetime.now()
    one_min_ago = now - timedelta(seconds=60)
    with Session(engine) as session:
        total = session.exec(select(func.count(col(RequestLog.id)))).one()
        blocked = session.exec(
            select(func.count(col(RequestLog.id))).where(RequestLog.blocked == True)
        ).one()
        allowed = total - blocked

        # by_rule
        by_rule_rows = session.exec(
            select(RequestLog.matched_rule, func.count(col(RequestLog.id))).group_by(
                RequestLog.matched_rule
            )
        ).all()
        by_rule = {k if k is not None else "": v for k, v in by_rule_rows}

        # last minute
        last_minute_total = session.exec(
            select(func.count(col(RequestLog.id))).where(
                RequestLog.timestamp >= one_min_ago
            )
        ).one()
        last_minute_blocked = session.exec(
            select(func.count(col(RequestLog.id))).where(
                RequestLog.timestamp >= one_min_ago, RequestLog.blocked == True
            )
        ).one()
        last_minute_allowed = last_minute_total - last_minute_blocked

        return {
            "total": total,
            "blocked": blocked,
            "allowed": allowed,
            "by_rule": by_rule,
            "last_minute": {
                "total": last_minute_total,
                "blocked": last_minute_blocked,
                "allowed": last_minute_allowed,
            },
        }


def reset_metrics():
    with Session(engine) as session:
        stmt = delete(RequestLog)
        _ = session.exec(stmt)
        session.commit()
