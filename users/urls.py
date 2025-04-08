from django.urls import path
from .views import LoginView, ConfirmView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('confirm/', ConfirmView.as_view(), name='confirm'),
]
