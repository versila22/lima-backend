import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./tests/test.db")

from app.database import Base, get_db
from app.main import app
from app.middleware.activity_tracker import ActivityTrackerMiddleware
from app.models.activity_log import ActivityLog
from app.models.alignment import Alignment, AlignmentAssignment, AlignmentEvent
from app.models.commission import Commission, MemberCommission
from app.models.event import Event
from app.models.member import Member
from app.models.member_season import MemberSeason
from app.models.season import Season
from app.models.show_plan import ShowPlan
from app.models.venue import Venue
from app.utils.security import create_access_token, hash_password

TEST_DB_PATH = Path("/data/.openclaw/workspace/lima/backend/tests/test.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

engine = create_async_engine(
    TEST_DATABASE_URL,
    future=True,
    echo=False,
    connect_args={"timeout": 30},
)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db
app.state.limiter.enabled = False
import app.database as app_database
app_database.AsyncSessionLocal = TestingSessionLocal

ActivityTrackerMiddleware.enabled = False


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    async with TestingSessionLocal() as session:
        for model in [
            ActivityLog,
            AlignmentAssignment,
            AlignmentEvent,
            Alignment,
            ShowPlan,
            Event,
            MemberCommission,
            Commission,
            MemberSeason,
            Venue,
            Member,
            Season,
        ]:
            await session.execute(delete(model))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_data():
    async with TestingSessionLocal() as session:
        admin = Member(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            app_role="admin",
            is_active=True,
            password_hash=hash_password("Admin1234!"),
        )
        regular = Member(
            email="member@example.com",
            first_name="Regular",
            last_name="User",
            app_role="member",
            is_active=True,
            password_hash=hash_password("Member1234!"),
        )
        inactive = Member(
            email="inactive@example.com",
            first_name="Inactive",
            last_name="User",
            app_role="member",
            is_active=False,
            password_hash=hash_password("Inactive1234!"),
        )
        pending = Member(
            email="pending@example.com",
            first_name="Pending",
            last_name="Activation",
            app_role="member",
            is_active=False,
            activation_token="activate-token",
            activation_expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        )
        reset_member = Member(
            email="reset@example.com",
            first_name="Reset",
            last_name="User",
            app_role="member",
            is_active=True,
            password_hash=hash_password("OldPassword123!"),
        )
        expired_pending = Member(
            email="expired@example.com",
            first_name="Expired",
            last_name="Activation",
            app_role="member",
            is_active=False,
            activation_token="expired-activate-token",
            activation_expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        )

        current_season = Season(
            name="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
            is_current=True,
        )
        old_season = Season(
            name="2024-2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
            is_current=False,
        )
        venue = Venue(name="Maison de quartier", city="Angers", is_home=True)
        hidden_venue = Venue(name="Lieu secret", city="Cholet", is_home=False)

        session.add_all([
            admin,
            regular,
            inactive,
            pending,
            reset_member,
            expired_pending,
            current_season,
            old_season,
            venue,
            hidden_venue,
        ])
        await session.flush()

        session.add_all([
            MemberSeason(
                member_id=regular.id,
                season_id=current_season.id,
                player_status="M",
                asso_role="trésorier",
            ),
            MemberSeason(
                member_id=regular.id,
                season_id=old_season.id,
                player_status="C",
                asso_role="secrétaire",
            ),
            MemberSeason(member_id=admin.id, season_id=current_season.id, player_status="A"),
        ])

        public_event = Event(
            season_id=current_season.id,
            venue_id=venue.id,
            title="Match public",
            event_type="match",
            start_at=datetime(2026, 2, 10, 20, 0),
            end_at=datetime(2026, 2, 10, 22, 0),
            visibility="all",
        )
        admin_event = Event(
            season_id=current_season.id,
            venue_id=hidden_venue.id,
            title="Réunion CA",
            event_type="other",
            start_at=datetime(2026, 2, 11, 18, 0),
            visibility="admin",
        )
        other_season_event = Event(
            season_id=old_season.id,
            venue_id=venue.id,
            title="Ancien cabaret",
            event_type="cabaret",
            start_at=datetime(2025, 2, 10, 20, 0),
            visibility="all",
        )
        session.add_all([public_event, admin_event, other_season_event])
        await session.flush()

        draft_alignment = Alignment(
            season_id=current_season.id,
            name="Grille brouillon",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            status="draft",
            created_by=admin.id,
        )
        published_alignment = Alignment(
            season_id=current_season.id,
            name="Grille publiée",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            status="published",
            created_by=admin.id,
        )
        commission = Commission(code="COM", name="Communication")
        session.add_all([draft_alignment, published_alignment, commission])
        await session.flush()

        session.add_all([
            AlignmentEvent(alignment_id=draft_alignment.id, event_id=public_event.id, sort_order=0),
            AlignmentEvent(alignment_id=published_alignment.id, event_id=public_event.id, sort_order=0),
        ])

        session.add(
            MemberCommission(
                member_id=regular.id,
                commission_id=commission.id,
                season_id=current_season.id,
            )
        )

        session.add(
            ShowPlan(
                event_id=public_event.id,
                created_by=admin.id,
                title="Plan match",
                show_type="match",
                config={"teams": 2},
            )
        )

        await session.commit()

        regular_token = create_access_token(str(regular.id), extra_claims={"role": "member"})
        admin_token = create_access_token(str(admin.id), extra_claims={"role": "admin"})

        return {
            "admin": admin,
            "regular": regular,
            "inactive": inactive,
            "pending": pending,
            "reset_member": reset_member,
            "expired_pending": expired_pending,
            "current_season": current_season,
            "old_season": old_season,
            "venue": venue,
            "hidden_venue": hidden_venue,
            "public_event": public_event,
            "admin_event": admin_event,
            "other_season_event": other_season_event,
            "draft_alignment": draft_alignment,
            "published_alignment": published_alignment,
            "commission": commission,
            "admin_token": admin_token,
            "regular_token": regular_token,
        }


@pytest_asyncio.fixture
async def auth_client(client, seeded_data):
    client.headers.update({"Authorization": f"Bearer {seeded_data['admin_token']}"})
    yield client
    client.headers.pop("Authorization", None)


@pytest_asyncio.fixture
async def regular_client(client, seeded_data):
    client.headers.update({"Authorization": f"Bearer {seeded_data['regular_token']}"})
    yield client
    client.headers.pop("Authorization", None)
