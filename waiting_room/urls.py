from django.urls import path

from . import views

app_name = "waiting_room"

urlpatterns = [
    path("join/", views.JoinView.as_view(), name="join"),
    path("leave/", views.LeaveView.as_view(), name="leave"),
]
