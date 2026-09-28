from django.db import models
from django.db.models import Q


class MemberStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name_plural = "Member Statuses"


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class Ministry(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name_plural = "Ministries"


class Member(models.Model):
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
    ]

    name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255, blank=True, default="")
    last_name = models.CharField(max_length=255, blank=True, default="")
    # Split so a partly known birth date is stored as exactly what is known: day and month
    # always together, year independent. No placeholder year (year 0001 used to mean
    # "unknown"), and a known year no longer needs a fake birthday (spec 011).
    birth_day = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_month = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)

    status = models.ForeignKey(MemberStatus, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    ministries = models.ManyToManyField(Ministry, blank=True)

    baptism_date = models.DateField(null=True, blank=True)
    # Means "valid profile", not "attends church". Only valid profiles appear in the
    # regular member list and birthdays; leaders see every record (specs/members/spec.md).
    is_active = models.BooleanField(default=True)
    # Leader-only (the media rule for members/ allows leaders alone, spec 009) and separate
    # from Profile.photo. Written through MemberPhotoStorage under a random name, never
    # through FieldFile.save, so the row update stays inside the history transaction.
    photo = models.ImageField(upload_to="members/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # The Django admin writes Member without the service; these checks reach it through
        # validate_constraints(), so it cannot store half a birthday either. Calendar, future
        # and baptism rules stay in features/members/domain/member_dates.py.
        constraints = [
            models.CheckConstraint(
                condition=Q(birth_day__isnull=True, birth_month__isnull=True)
                | Q(birth_day__isnull=False, birth_month__isnull=False),
                name="member_birth_day_month_together",
            ),
            models.CheckConstraint(
                condition=Q(birth_day__isnull=True) | Q(birth_day__gte=1, birth_day__lte=31),
                name="member_birth_day_range",
            ),
            models.CheckConstraint(
                condition=Q(birth_month__isnull=True) | Q(birth_month__gte=1, birth_month__lte=12),
                name="member_birth_month_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name
