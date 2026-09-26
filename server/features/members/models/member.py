from django.db import models


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
    birth_date = models.DateField(null=True, blank=True)
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

    def __str__(self) -> str:
        return self.name
