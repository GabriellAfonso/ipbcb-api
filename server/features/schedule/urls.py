from django.urls import path

from features.schedule.views.schedule import (
    CurrentMonthlyScheduleAPI,
    MonthlySchedulePreviewAPI,
    MonthlyScheduleSaveAPI,
)

urlpatterns = [
    path("api/schedule/current/", CurrentMonthlyScheduleAPI.as_view(), name="schedule_current"),
    path("api/schedule/save/", MonthlyScheduleSaveAPI.as_view(), name="schedule_save"),
    path("api/schedule/generate/", MonthlySchedulePreviewAPI.as_view(), name="generate_schedule"),
]
