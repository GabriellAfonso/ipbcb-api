from django.urls import path

from features.sunday_school.views.manage import (
    SundaySchoolManageLessonDetailView,
    SundaySchoolManageLessonsView,
    SundaySchoolManageOrderView,
    SundaySchoolManageYearDetailView,
    SundaySchoolManageYearsView,
)
from features.sunday_school.views.public import SundaySchoolIndexView, SundaySchoolLessonView

app_name = "sunday_school"

# Panel routes live under ``manage/`` so a public path can never serve a draft (research R-09).
urlpatterns = [
    path("api/sunday-school/", SundaySchoolIndexView.as_view(), name="index"),
    path(
        "api/sunday-school/lessons/<int:lesson_id>/",
        SundaySchoolLessonView.as_view(),
        name="lesson",
    ),
    path(
        "api/sunday-school/manage/lessons/",
        SundaySchoolManageLessonsView.as_view(),
        name="manage-lessons",
    ),
    path(
        "api/sunday-school/manage/lessons/order/",
        SundaySchoolManageOrderView.as_view(),
        name="manage-lessons-order",
    ),
    path(
        "api/sunday-school/manage/lessons/<int:lesson_id>/",
        SundaySchoolManageLessonDetailView.as_view(),
        name="manage-lesson-detail",
    ),
    path(
        "api/sunday-school/manage/years/",
        SundaySchoolManageYearsView.as_view(),
        name="manage-years",
    ),
    path(
        "api/sunday-school/manage/years/<int:year>/",
        SundaySchoolManageYearDetailView.as_view(),
        name="manage-year-detail",
    ),
]
