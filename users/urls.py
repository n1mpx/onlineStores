from django.urls import path
from .views import LoginView, ConfirmView, MeView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('confirm/', ConfirmView.as_view(), name='confirm'),
    path('me/', MeView.as_view()),  # <-- вот это обязательно

]
