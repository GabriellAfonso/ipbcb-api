from django.urls import path

from features.doctrine.views import DoctrineDetailView, DoctrineListView

app_name = "doctrine"

urlpatterns = [
    path("api/doctrine/", DoctrineListView.as_view(), name="doctrine-list"),
    path("api/doctrine/<slug:slug>/", DoctrineDetailView.as_view(), name="doctrine-detail"),
]
