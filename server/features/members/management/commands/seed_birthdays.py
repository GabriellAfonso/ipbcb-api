"""Seed fake members with birthdays spread across all 12 months for local testing.

Each entry is (name, gender, day, month, year); any birth part may be None.
"""

from django.core.management.base import BaseCommand

from features.members.models.member import Member


FAKE_MEMBERS: list[tuple[str, str | None, int | None, int | None, int | None]] = [
    ("Ana Silva", "F", 8, 1, 1995),
    ("Bruno Costa", "M", 22, 1, 1988),
    ("Carla Souza", "F", 14, 2, 1990),
    ("Daniel Oliveira", "M", 28, 2, 1985),
    ("Elena Pereira", "F", 5, 3, 1992),
    ("Felipe Santos", "M", 19, 3, 1987),
    ("Gabriela Lima", "F", 2, 4, 1993),
    ("Hugo Almeida", "M", 17, 4, 1991),
    ("Isabela Rocha", "F", 10, 5, 1989),
    ("Joao Ferreira", "M", 25, 5, 1994),
    ("Karen Barbosa", "F", 7, 6, 1986),
    ("Lucas Ribeiro", "M", 21, 6, 1996),
    ("Marina Cardoso", "F", 3, 7, 1990),
    ("Nicolas Araujo", "M", 16, 7, 1988),
    ("Olivia Gomes", "F", 30, 7, 1993),
    ("Pedro Martins", "M", 11, 8, 1985),
    ("Raquel Dias", "F", 24, 8, 1992),
    ("Samuel Nunes", "M", 1, 9, 1987),
    ("Tatiana Campos", "F", 18, 9, 1991),
    ("Vinicius Moreira", "M", 6, 10, 1994),
    ("Wanda Teixeira", "F", 20, 10, 1989),
    ("Xavier Mendes", "M", 9, 11, 1996),
    ("Yasmin Castro", "F", 27, 11, 1986),
    ("Zeca Pinto", "M", 4, 12, 1990),
    ("Amanda Correia", "F", 25, 12, 1988),
    ("Roberto Lopes", None, 12, 3, 1993),
    ("Fernanda Nascimento", "F", 7, 7, 1991),
    ("Gustavo Ramos", "M", 31, 1, 1985),
    ("Juliana Vieira", "F", 15, 6, 1992),
    ("Marcos Azevedo", "M", 18, 12, 1987),
    # Partly known dates (spec 011): only the first of these shows up in birthdays.
    ("Helena Duarte", "F", 14, 8, None),
    ("Otavio Prado", "M", None, None, 1950),
    ("Sonia Reis", "F", None, None, None),
]


class Command(BaseCommand):
    help = "Seed fake members with birthdays for local testing"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove seeded members before creating new ones",
        )

    def handle(self, *args, **options):  # type: ignore[no-untyped-def]
        if options["clear"]:
            deleted, _ = Member.objects.filter(
                name__in=[entry[0] for entry in FAKE_MEMBERS]
            ).delete()
            self.stdout.write(f"Removed {deleted} seeded members.")
            return

        created = 0
        for name, gender, day, month, year in FAKE_MEMBERS:
            _, was_created = Member.objects.get_or_create(
                name=name,
                defaults={
                    "gender": gender,
                    "birth_day": day,
                    "birth_month": month,
                    "birth_year": year,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            f"Created {created} members ({len(FAKE_MEMBERS) - created} already existed)."
        )
