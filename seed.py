#!/usr/bin/env python3
"""
Seed script for LIMA database.

Creates realistic data:
  - 1 saison courante 2025-2026
  - 1 admin + 8 membres fictifs
  - 5 lieux
  - 5 commissions
  - 10 événements
  - 1 grille d'alignement (Trimestre 1)
  - Affectations joueurs

Run:
    python seed.py
    # Or with a custom DATABASE_URL:
    DATABASE_URL=postgresql+asyncpg://... python seed.py
"""

import asyncio
import sys
import os

# Ensure app is importable from the script location
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models.alignment import Alignment, AlignmentAssignment, AlignmentEvent
from app.models.commission import Commission, MemberCommission
from app.models.event import Event
from app.models.member import Member
from app.models.member_season import MemberSeason
from app.models.season import Season
from app.models.venue import Venue
from app.utils.security import generate_secure_token, hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMMISSIONS = [
    {"code": "comspec", "name": "Commission Spectacles", "description": "Organisation des spectacles et soirées cabaret"},
    {"code": "comprog", "name": "Commission Programme", "description": "Planification du calendrier et des matchs"},
    {"code": "comform", "name": "Commission Formation", "description": "Coordination des entraînements et formations"},
    {"code": "comadh", "name": "Commission Adhésion", "description": "Gestion des adhésions et inscriptions HelloAsso"},
    {"code": "comcom", "name": "Commission Communication", "description": "Réseaux sociaux, affiches et relations presse"},
]

VENUES = [
    {
        "name": "Le Welsh",
        "address": "3 rue de la Roe",
        "city": "Angers",
        "contact_info": "Sophie Martin — 06 12 34 56 78",
        "is_home": True,
    },
    {
        "name": "Salle Giffard",
        "address": "Rue Giffard",
        "city": "Angers",
        "contact_info": "Mairie d'Angers — 02 41 05 40 00",
        "is_home": True,
    },
    {
        "name": "Le Germoir",
        "address": "14 rue Boisnet",
        "city": "Angers",
        "contact_info": "Pierre Dupont — 06 98 76 54 32",
        "is_home": True,
    },
    {
        "name": "Digital Village",
        "address": "8 rue du Mail",
        "city": "Angers",
        "contact_info": "hello@digitalvillage.fr",
        "is_home": True,
    },
    {
        "name": "Salle des fêtes Chantenay",
        "address": "Place Aristide Briand",
        "city": "Nantes",
        "contact_info": "Ville de Nantes — 02 40 41 90 00",
        "is_home": False,
    },
]

MEMBERS_DATA = [
    {
        "email": "admin@lima-impro.fr",
        "first_name": "Alexandre",
        "last_name": "Bertrand",
        "phone": "06 11 22 33 44",
        "app_role": "admin",
        "password": "Admin1234!",
        "player_status": "M",
        "player_fee": Decimal("160.00"),
        "asso_role": "co_president",
    },
    {
        "email": "marie.leroy@exemple.fr",
        "first_name": "Marie",
        "last_name": "Leroy",
        "phone": "06 22 33 44 55",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "M",
        "player_fee": Decimal("160.00"),
        "asso_role": "co_treasurer",
    },
    {
        "email": "thomas.martin@exemple.fr",
        "first_name": "Thomas",
        "last_name": "Martin",
        "phone": "06 33 44 55 66",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "C",
        "player_fee": Decimal("75.00"),
        "asso_role": None,
    },
    {
        "email": "sophie.dubois@exemple.fr",
        "first_name": "Sophie",
        "last_name": "Dubois",
        "phone": "06 44 55 66 77",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "M",
        "player_fee": Decimal("160.00"),
        "asso_role": "secretary",
    },
    {
        "email": "lucas.petit@exemple.fr",
        "first_name": "Lucas",
        "last_name": "Petit",
        "phone": "06 55 66 77 88",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "L",
        "player_fee": Decimal("40.00"),
        "asso_role": None,
    },
    {
        "email": "claire.moreau@exemple.fr",
        "first_name": "Claire",
        "last_name": "Moreau",
        "phone": "06 66 77 88 99",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "C",
        "player_fee": Decimal("75.00"),
        "asso_role": "ca_member",
    },
    {
        "email": "julien.bernard@exemple.fr",
        "first_name": "Julien",
        "last_name": "Bernard",
        "phone": "06 77 88 99 00",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "M",
        "player_fee": Decimal("160.00"),
        "asso_role": "coach",
    },
    {
        "email": "emma.richard@exemple.fr",
        "first_name": "Emma",
        "last_name": "Richard",
        "phone": "06 88 99 00 11",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "A",
        "player_fee": None,
        "asso_role": None,
    },
    {
        "email": "paul.durand@exemple.fr",
        "first_name": "Paul",
        "last_name": "Durand",
        "phone": "06 99 00 11 22",
        "app_role": "member",
        "password": "Password1!",
        "player_status": "M",
        "player_fee": Decimal("160.00"),
        "asso_role": None,
    },
]


def make_dt(year: int, month: int, day: int, hour: int = 20, minute: int = 30) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Main seeding function
# ---------------------------------------------------------------------------

async def seed(db: AsyncSession) -> None:
    print("🌱 Démarrage du seeding LIMA...")

    # ---- Season ----
    season_result = await db.execute(select(Season).where(Season.name == "2025-2026"))
    season = season_result.scalar_one_or_none()
    if season is None:
        season = Season(
            name="2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 8, 31),
            is_current=True,
        )
        db.add(season)
        await db.flush()
        print(f"  ✅ Saison créée: {season.name}")
    else:
        print(f"  ⏭  Saison déjà existante: {season.name}")

    # ---- Commissions ----
    commission_objects = {}
    for c_data in COMMISSIONS:
        result = await db.execute(
            select(Commission).where(Commission.code == c_data["code"])
        )
        comm = result.scalar_one_or_none()
        if comm is None:
            comm = Commission(**c_data)
            db.add(comm)
            await db.flush()
            print(f"  ✅ Commission créée: {comm.name}")
        commission_objects[comm.code] = comm

    # ---- Venues ----
    venue_objects = {}
    for v_data in VENUES:
        result = await db.execute(
            select(Venue).where(Venue.name == v_data["name"])
        )
        venue = result.scalar_one_or_none()
        if venue is None:
            venue = Venue(**v_data)
            db.add(venue)
            await db.flush()
            print(f"  ✅ Lieu créé: {venue.name}")
        venue_objects[venue.name] = venue

    # ---- Members ----
    member_objects = {}
    for m_data in MEMBERS_DATA:
        result = await db.execute(
            select(Member).where(Member.email == m_data["email"])
        )
        member = result.scalar_one_or_none()
        if member is None:
            member = Member(
                email=m_data["email"],
                first_name=m_data["first_name"],
                last_name=m_data["last_name"],
                phone=m_data["phone"],
                app_role=m_data["app_role"],
                password_hash=hash_password(m_data["password"]),
                is_active=True,
            )
            db.add(member)
            await db.flush()
            print(f"  ✅ Membre créé: {member.full_name} ({member.email})")
        else:
            print(f"  ⏭  Membre existant: {member.full_name}")
        member_objects[member.email] = member

        # member_season
        ms_result = await db.execute(
            select(MemberSeason).where(
                MemberSeason.member_id == member.id,
                MemberSeason.season_id == season.id,
            )
        )
        if ms_result.scalar_one_or_none() is None:
            ms = MemberSeason(
                member_id=member.id,
                season_id=season.id,
                player_status=m_data["player_status"],
                membership_fee=Decimal("20.00"),
                player_fee=m_data.get("player_fee"),
                asso_role=m_data.get("asso_role"),
            )
            db.add(ms)
            await db.flush()

    # ---- Commission assignments ----
    admin_member = member_objects["admin@lima-impro.fr"]
    for code, comm in commission_objects.items():
        mc_result = await db.execute(
            select(MemberCommission).where(
                MemberCommission.member_id == admin_member.id,
                MemberCommission.commission_id == comm.id,
                MemberCommission.season_id == season.id,
            )
        )
        if mc_result.scalar_one_or_none() is None:
            db.add(MemberCommission(
                member_id=admin_member.id,
                commission_id=comm.id,
                season_id=season.id,
            ))
    await db.flush()

    # ---- Events ----
    welsh_venue = venue_objects.get("Le Welsh")
    giffard_venue = venue_objects.get("Salle Giffard")
    germoir_venue = venue_objects.get("Le Germoir")
    nantes_venue = venue_objects.get("Salle des fêtes Chantenay")

    events_data = [
        {
            "title": "Entraînement Match — Ouverture de saison",
            "event_type": "training_show",
            "start_at": make_dt(2025, 9, 10, 20, 0),
            "venue_id": giffard_venue.id if giffard_venue else None,
            "visibility": "match",
        },
        {
            "title": "Entraînement Loisir — Accueil nouveaux",
            "event_type": "training_leisure",
            "start_at": make_dt(2025, 9, 17, 19, 30),
            "venue_id": germoir_venue.id if germoir_venue else None,
            "visibility": "all",
        },
        {
            "title": "WELSH #1 — Matchs internes",
            "event_type": "welsh",
            "start_at": make_dt(2025, 10, 3, 20, 30),
            "end_at": make_dt(2025, 10, 3, 23, 0),
            "venue_id": welsh_venue.id if welsh_venue else None,
            "visibility": "all",
        },
        {
            "title": "Match MPT vs CITO (Nantes)",
            "event_type": "match",
            "start_at": make_dt(2025, 10, 18, 20, 30),
            "is_away": True,
            "away_city": "Nantes",
            "away_opponent": "CITO",
            "venue_id": nantes_venue.id if nantes_venue else None,
            "visibility": "match",
        },
        {
            "title": "Cabaret Automne — Soirée Halloween",
            "event_type": "cabaret",
            "start_at": make_dt(2025, 10, 25, 20, 30),
            "end_at": make_dt(2025, 10, 25, 23, 30),
            "venue_id": giffard_venue.id if giffard_venue else None,
            "visibility": "all",
        },
        {
            "title": "Formation Clôture de scène",
            "event_type": "formation",
            "start_at": make_dt(2025, 11, 8, 10, 0),
            "end_at": make_dt(2025, 11, 8, 17, 0),
            "venue_id": germoir_venue.id if germoir_venue else None,
            "visibility": "all",
        },
        {
            "title": "WELSH #2 — Matchs thématiques",
            "event_type": "welsh",
            "start_at": make_dt(2025, 11, 21, 20, 30),
            "venue_id": welsh_venue.id if welsh_venue else None,
            "visibility": "all",
        },
        {
            "title": "Assemblée Générale 2025",
            "event_type": "ag",
            "start_at": make_dt(2025, 12, 5, 18, 30),
            "venue_id": germoir_venue.id if germoir_venue else None,
            "visibility": "all",
        },
        {
            "title": "Cabaret Hiver — Spécial Noël",
            "event_type": "cabaret",
            "start_at": make_dt(2025, 12, 13, 20, 30),
            "end_at": make_dt(2025, 12, 13, 23, 30),
            "venue_id": giffard_venue.id if giffard_venue else None,
            "visibility": "all",
        },
        {
            "title": "Match vs Le Minou (Paris) — Tournoi National",
            "event_type": "match",
            "start_at": make_dt(2026, 1, 17, 20, 0),
            "is_away": True,
            "away_city": "Paris",
            "away_opponent": "Le Minou",
            "visibility": "match",
        },
    ]

    event_objects = []
    for e_data in events_data:
        result = await db.execute(
            select(Event).where(
                Event.title == e_data["title"],
                Event.season_id == season.id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            event = Event(season_id=season.id, **e_data)
            db.add(event)
            await db.flush()
            print(f"  ✅ Événement créé: {event.title}")
        event_objects.append(event)

    # ---- Alignment — Trimestre 1 ----
    align_result = await db.execute(
        select(Alignment).where(
            Alignment.name == "Trimestre 1 — 2025-2026",
            Alignment.season_id == season.id,
        )
    )
    alignment = align_result.scalar_one_or_none()
    if alignment is None:
        alignment = Alignment(
            season_id=season.id,
            name="Trimestre 1 — 2025-2026",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 31),
            status="published",
            created_by=admin_member.id,
        )
        db.add(alignment)
        await db.flush()
        print(f"  ✅ Alignement créé: {alignment.name}")

        # Add first 5 events to alignment
        for i, ev in enumerate(event_objects[:5]):
            ae_result = await db.execute(
                select(AlignmentEvent).where(
                    AlignmentEvent.alignment_id == alignment.id,
                    AlignmentEvent.event_id == ev.id,
                )
            )
            if ae_result.scalar_one_or_none() is None:
                db.add(AlignmentEvent(
                    alignment_id=alignment.id,
                    event_id=ev.id,
                    sort_order=i,
                ))
        await db.flush()

        # Assignments: assign match players to Welsh #1 (index 2)
        welsh_event = event_objects[2]
        match_players = [
            m for email, m in member_objects.items()
            if any(
                d["email"] == email and d["player_status"] == "M"
                for d in MEMBERS_DATA
            )
        ]
        cabaret_players = [
            m for email, m in member_objects.items()
            if any(
                d["email"] == email and d["player_status"] == "C"
                for d in MEMBERS_DATA
            )
        ]

        roles_cycle = ["JR", "JR", "DJ", "MJ_MC", "AR"]
        for idx, player in enumerate(match_players[:5]):
            role = roles_cycle[idx % len(roles_cycle)]
            dup = await db.execute(
                select(AlignmentAssignment).where(
                    AlignmentAssignment.alignment_id == alignment.id,
                    AlignmentAssignment.event_id == welsh_event.id,
                    AlignmentAssignment.member_id == player.id,
                )
            )
            if dup.scalar_one_or_none() is None:
                db.add(AlignmentAssignment(
                    alignment_id=alignment.id,
                    event_id=welsh_event.id,
                    member_id=player.id,
                    role=role,
                ))
        await db.flush()
        print(f"  ✅ Affectations ajoutées au WELSH #1")

    await db.commit()
    print("\n✅ Seeding terminé avec succès !")
    print(f"   Admin: admin@lima-impro.fr / Admin1234!")
    print(f"   Membres: 8 membres avec mdp Password1!")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    database_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    engine = create_async_engine(database_url, echo=False)

    # Create tables if they don't exist (useful for fresh dev DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
