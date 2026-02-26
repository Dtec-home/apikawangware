"""
Local Development Seeder
========================
Creates test data for local development and QA.

Usage:
    python manage.py seed_local_data            # seed everything
    python manage.py seed_local_data --reset    # wipe existing seed data first

What gets created
-----------------
Categories   : Tithe, Offering, Building Fund, Missions
Members+Users: 6 accounts covering every role
Contributions: 18 records (mix of statuses, entry types, dates)
C2B Txns     : 6 records (3 processed, 2 unmatched, 1 failed)

OTP / SMS in local dev
----------------------
Because DEBUG=True and MOBITECH_API_KEY is not set, the SMSService
automatically falls back to console-only output. You will see:

    📱 OTP for 254700000001: 123456

in your Django server terminal whenever you call requestOtp().
The OTP code is also returned inside the GraphQL response as `otpCode`.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from contributions.models import Contribution, ContributionCategory, CategoryAdmin
from members.models import Member
from members.roles import UserRole, RoleType
from mpesa.models import C2BTransaction


# ─── Seed constants ────────────────────────────────────────────────────────────

CATEGORIES = [
    {"name": "Tithe",         "code": "TITHE",  "description": "Monthly tithe contributions"},
    {"name": "Offering",      "code": "OFFER",  "description": "Regular weekly offering"},
    {"name": "Building Fund", "code": "BUILD",  "description": "Church construction & renovation"},
    {"name": "Missions",      "code": "MISS",   "description": "Local and international missions"},
]

# phone → member data + role
MEMBERS = [
    {
        "phone": "254700000001",
        "first_name": "Alice",
        "last_name": "Admin",
        "email": "alice.admin@church.local",
        "member_number": "SDA-001",
        "role": RoleType.ADMIN,
    },
    {
        "phone": "254700000002",
        "first_name": "Trevor",
        "last_name": "Treasurer",
        "email": "trevor@church.local",
        "member_number": "SDA-002",
        "role": RoleType.TREASURER,
    },
    {
        "phone": "254700000003",
        "first_name": "Paul",
        "last_name": "Pastor",
        "email": "pastor.paul@church.local",
        "member_number": "SDA-003",
        "role": RoleType.PASTOR,
    },
    {
        "phone": "254700000004",
        "first_name": "Carol",
        "last_name": "Category",
        "email": None,
        "member_number": "SDA-004",
        "role": RoleType.MEMBER,          # role=member; gets category-admin separately
        "category_admin_of": "TITHE",     # only sees Tithe contributions
    },
    {
        "phone": "254700000005",
        "first_name": "Mary",
        "last_name": "Member",
        "email": None,
        "member_number": "SDA-005",
        "role": RoleType.MEMBER,
    },
    {
        "phone": "254700000006",
        "first_name": "John",
        "last_name": "Mwangi",
        "email": "john.m@church.local",
        "member_number": "SDA-006",
        "role": RoleType.MEMBER,
    },
]

# ─── C2B seeds (trans_id must be globally unique) ─────────────────────────────

C2B_TRANSACTIONS = [
    # 3 processed (auto-matched)
    {
        "trans_id": "SEED_C2B_001",
        "msisdn": "254700000005",  # Mary
        "first_name": "MARY", "middle_name": "", "last_name": "MEMBER",
        "trans_amount": Decimal("2000.00"),
        "bill_ref_number": "TITHE",
        "status": "processed",
        "matched_category_code": "TITHE",
        "match_method": "exact",
        "days_ago": 3,
    },
    {
        "trans_id": "SEED_C2B_002",
        "msisdn": "254700000006",  # John
        "first_name": "JOHN", "middle_name": "", "last_name": "MWANGI",
        "trans_amount": Decimal("500.00"),
        "bill_ref_number": "OFFER",
        "status": "processed",
        "matched_category_code": "OFFER",
        "match_method": "exact",
        "days_ago": 7,
    },
    {
        "trans_id": "SEED_C2B_003",
        "msisdn": "254700000005",  # Mary
        "first_name": "MARY", "middle_name": "", "last_name": "MEMBER",
        "trans_amount": Decimal("1500.00"),
        "bill_ref_number": "BUILD",
        "status": "processed",
        "matched_category_code": "BUILD",
        "match_method": "fuzzy",
        "days_ago": 10,
    },
    # 2 unmatched — these need manual resolution in the admin UI
    {
        "trans_id": "SEED_C2B_004",
        "msisdn": "254700000006",  # John
        "first_name": "JOHN", "middle_name": "", "last_name": "MWANGI",
        "trans_amount": Decimal("3000.00"),
        "bill_ref_number": "TITHES",   # typo — not matched to TITHE
        "status": "unmatched",
        "matched_category_code": "",
        "match_method": "",
        "days_ago": 1,
    },
    {
        "trans_id": "SEED_C2B_005",
        "msisdn": "254711999888",  # unknown phone — also tests member-not-found case
        "first_name": "UNKNOWN", "middle_name": "", "last_name": "PERSON",
        "trans_amount": Decimal("800.00"),
        "bill_ref_number": "XMAS",     # completely unknown reference
        "status": "unmatched",
        "matched_category_code": "",
        "match_method": "",
        "days_ago": 2,
    },
    # 1 failed
    {
        "trans_id": "SEED_C2B_006",
        "msisdn": "254700000005",  # Mary
        "first_name": "MARY", "middle_name": "", "last_name": "MEMBER",
        "trans_amount": Decimal("100.00"),
        "bill_ref_number": "OFFER",
        "status": "failed",
        "matched_category_code": "",
        "match_method": "",
        "days_ago": 5,
    },
]


class Command(BaseCommand):
    help = "Seed local development data (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded data before re-seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        self.stdout.write("\n" + "═" * 60)
        self.stdout.write("  Church Funds System — Local Dev Seeder")
        self.stdout.write("═" * 60)

        cats = self._seed_categories()
        members, users = self._seed_members(cats)
        self._seed_contributions(members, cats)
        self._seed_c2b_transactions()

        self._print_summary(members, users)

    # ─── reset ─────────────────────────────────────────────────────────────────

    def _reset(self):
        self.stdout.write(self.style.WARNING("Resetting previously seeded data..."))

        phones = [m["phone"] for m in MEMBERS]
        seed_trans_ids = [t["trans_id"] for t in C2B_TRANSACTIONS]

        C2BTransaction.objects.filter(trans_id__in=seed_trans_ids).delete()

        # Delete contributions made by seed members
        seed_members = Member.objects.filter(phone_number__in=phones)
        Contribution.objects.filter(member__in=seed_members).delete()

        # Delete category admins for seed members
        CategoryAdmin.objects.filter(member__in=seed_members).delete()

        # Delete user roles and users
        for m in seed_members:
            if m.user:
                UserRole.objects.filter(user=m.user).delete()
                m.user.delete()

        seed_members.delete()
        self.stdout.write(self.style.SUCCESS("Reset complete.\n"))

    # ─── categories ────────────────────────────────────────────────────────────

    def _seed_categories(self):
        self.stdout.write("\n📂 Categories")
        cat_objects = {}
        for cat_data in CATEGORIES:
            cat, created = ContributionCategory.objects.get_or_create(
                code=cat_data["code"],
                defaults={
                    "name": cat_data["name"],
                    "description": cat_data["description"],
                    "is_active": True,
                },
            )
            status = "created" if created else "exists"
            self.stdout.write(f"   [{status}] {cat.name} ({cat.code})")
            cat_objects[cat.code] = cat
        return cat_objects

    # ─── members + users + roles ───────────────────────────────────────────────

    def _seed_members(self, cats):
        self.stdout.write("\n👥 Members / Users / Roles")
        member_objects = {}
        user_objects = {}

        for data in MEMBERS:
            # Member
            member, m_created = Member.objects.get_or_create(
                phone_number=data["phone"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "email": data.get("email"),
                    "member_number": data["member_number"],
                    "is_active": True,
                },
            )

            # Django User
            user, u_created = User.objects.get_or_create(
                username=data["phone"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "email": data.get("email") or "",
                },
            )
            if u_created:
                user.set_unusable_password()
                user.save(update_fields=["password"])

            # Link
            if member.user != user:
                member.user = user
                member.save(update_fields=["user"])

            # Role
            role_val = data["role"].value
            user_role, r_created = UserRole.objects.get_or_create(
                user=user,
                role=role_val,
                defaults={"is_active": True},
            )
            if not r_created and not user_role.is_active:
                user_role.is_active = True
                user_role.save(update_fields=["is_active"])

            # Category admin (if specified)
            cat_admin_code = data.get("category_admin_of")
            if cat_admin_code and cat_admin_code in cats:
                _, ca_created = CategoryAdmin.objects.get_or_create(
                    member=member,
                    category=cats[cat_admin_code],
                    defaults={"is_active": True},
                )
                if ca_created:
                    self.stdout.write(
                        f"   [cat-admin] {member.full_name} → {cat_admin_code}"
                    )

            m_status = "created" if m_created else "exists"
            self.stdout.write(
                f"   [{m_status}] {member.full_name} | {data['phone']} | role={role_val}"
            )
            member_objects[data["phone"]] = member
            user_objects[data["phone"]] = user

        return member_objects, user_objects

    # ─── contributions ─────────────────────────────────────────────────────────

    def _seed_contributions(self, members, cats):
        self.stdout.write("\n💰 Contributions")

        now = timezone.now()

        CONTRIBS = [
            # Alice — admin, various entry types
            ("254700000001", "TITHE",  Decimal("5000"), "completed", "mpesa",    0,   "MPA_SEED001"),
            ("254700000001", "OFFER",  Decimal("1000"), "completed", "envelope", 7,   None),
            # Trevor — treasurer
            ("254700000002", "TITHE",  Decimal("4000"), "completed", "mpesa",    3,   "MPA_SEED002"),
            ("254700000002", "BUILD",  Decimal("2000"), "completed", "manual",   14,  "RCP-001"),
            # Paul — pastor
            ("254700000003", "OFFER",  Decimal("500"),  "completed", "cash",     2,   None),
            ("254700000003", "MISS",   Decimal("1000"), "completed", "mpesa",    10,  "MPA_SEED003"),
            # Carol — category admin (Tithe only in her filtered view)
            ("254700000004", "TITHE",  Decimal("3000"), "completed", "mpesa",    1,   "MPA_SEED004"),
            ("254700000004", "OFFER",  Decimal("500"),  "completed", "cash",     5,   None),
            # Mary — regular member
            ("254700000005", "TITHE",  Decimal("2500"), "completed", "mpesa",    4,   "MPA_SEED005"),
            ("254700000005", "BUILD",  Decimal("500"),  "completed", "manual",   9,   "RCP-002"),
            ("254700000005", "MISS",   Decimal("200"),  "completed", "cash",     20,  None),
            ("254700000005", "TITHE",  Decimal("2500"), "pending",   "mpesa",    0,   None),
            # John — regular member
            ("254700000006", "OFFER",  Decimal("800"),  "completed", "mpesa",    6,   "MPA_SEED006"),
            ("254700000006", "TITHE",  Decimal("3200"), "completed", "mpesa",    13,  "MPA_SEED007"),
            ("254700000006", "BUILD",  Decimal("1000"), "failed",    "mpesa",    8,   None),
            ("254700000006", "OFFER",  Decimal("600"),  "pending",   "mpesa",    0,   None),
            # A couple of historical records for richer reports
            ("254700000001", "TITHE",  Decimal("5000"), "completed", "mpesa",    35,  "MPA_SEED008"),
            ("254700000005", "OFFER",  Decimal("300"),  "completed", "cash",     28,  None),
        ]

        created_count = 0
        for phone, cat_code, amount, status, etype, days_ago, receipt_no in CONTRIBS:
            member = members.get(phone)
            cat = cats.get(cat_code)
            if not member or not cat:
                continue

            tx_date = now - timedelta(days=days_ago)

            # Use receipt number as idempotency key where present
            qs = Contribution.objects.filter(
                member=member,
                category=cat,
                amount=amount,
                entry_type=etype,
                transaction_date__date=tx_date.date(),
            )
            if qs.exists():
                continue

            Contribution.objects.create(
                member=member,
                category=cat,
                amount=amount,
                status=status,
                entry_type=etype,
                transaction_date=tx_date,
                manual_receipt_number=receipt_no,
                contribution_group_id=uuid.uuid4(),
                notes="Seeded for local development",
            )
            created_count += 1

        self.stdout.write(f"   {created_count} new contribution(s) created")

    # ─── C2B transactions ──────────────────────────────────────────────────────

    def _seed_c2b_transactions(self):
        self.stdout.write("\n📲 C2B (Pay Bill) Transactions")
        now = timezone.now()

        created_count = 0
        for data in C2B_TRANSACTIONS:
            _, created = C2BTransaction.objects.get_or_create(
                trans_id=data["trans_id"],
                defaults={
                    "trans_time": now - timedelta(days=data["days_ago"]),
                    "trans_amount": data["trans_amount"],
                    "business_short_code": "400200",  # dummy paybill
                    "bill_ref_number": data["bill_ref_number"],
                    "msisdn": data["msisdn"],
                    "first_name": data["first_name"],
                    "middle_name": data["middle_name"],
                    "last_name": data["last_name"],
                    "status": data["status"],
                    "validation_result": "accepted",
                    "matched_category_code": data["matched_category_code"],
                    "match_method": data["match_method"],
                },
            )
            if created:
                created_count += 1
                flag = (
                    "⚠ UNMATCHED — resolve in admin"
                    if data["status"] == "unmatched"
                    else ""
                )
                self.stdout.write(
                    f"   [{data['status']:10s}] {data['trans_id']}  "
                    f"KES {data['trans_amount']:>8}  ref={data['bill_ref_number']}  {flag}"
                )
            else:
                self.stdout.write(f"   [exists    ] {data['trans_id']}")

        self.stdout.write(f"   {created_count} new C2B record(s) created")

    # ─── summary table ─────────────────────────────────────────────────────────

    def _print_summary(self, members, users):
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write("  TEST ACCOUNTS  (OTP will print to this console)")
        self.stdout.write("═" * 60)
        self.stdout.write(
            f"  {'Phone':<16} {'Name':<22} {'Role / Notes'}"
        )
        self.stdout.write("  " + "─" * 56)

        role_labels = {
            "254700000001": "admin          → full access",
            "254700000002": "treasurer      → full access",
            "254700000003": "pastor         → full access",
            "254700000004": "member + category-admin (Tithe only)",
            "254700000005": "member         → own contributions only",
            "254700000006": "member         → own contributions only",
        }
        for data in MEMBERS:
            phone = data["phone"]
            member = members.get(phone)
            if not member:
                continue
            label = role_labels.get(phone, "")
            self.stdout.write(f"  {phone:<16} {member.full_name:<22} {label}")

        self.stdout.write("═" * 60)
        self.stdout.write("\n  HOW TO LOGIN")
        self.stdout.write("  ─────────────────────────────────────────────────────")
        self.stdout.write("  1. Call requestOtp(phoneNumber: \"254700000001\")")
        self.stdout.write("  2. OTP appears in THIS terminal (server console)")
        self.stdout.write("     AND is returned as otpCode in the GraphQL response")
        self.stdout.write("     (only in DEBUG mode)")
        self.stdout.write("  3. Call verifyOtp(phoneNumber: ..., otpCode: ...)")
        self.stdout.write("  4. Use the returned accessToken as Bearer token")
        self.stdout.write("\n  RECEIPT / SMS OUTPUT")
        self.stdout.write("  ─────────────────────────────────────────────────────")
        self.stdout.write("  All SMS (OTP + receipts) print to this console when")
        self.stdout.write("  DEBUG=True and MOBITECH_API_KEY is not set.")
        self.stdout.write("\n  C2B TEST")
        self.stdout.write("  ─────────────────────────────────────────────────────")
        self.stdout.write("  2 UNMATCHED C2B transactions are seeded.")
        self.stdout.write("  Go to Admin → C2B / Pay Bill to resolve them.")
        self.stdout.write("  Note: SEED_C2B_005 has an unknown phone — resolving")
        self.stdout.write("  it will return 'Member not found' (expected).\n")
