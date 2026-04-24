from django.urls import path
from apps.merchants.views import RegisterView, MeView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="merchant-register"),
    path("me/", MeView.as_view(), name="merchant-me"),
]
