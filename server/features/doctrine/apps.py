from django.apps import AppConfig


class DoctrineConfig(AppConfig):
    # No startup validation: the documents live in the database and are validated by the data
    # migration that loads them (specs/027-doctrine-database R-05).
    name = "features.doctrine"
