from django.urls import path
from .views import ProductListView, ProductDetailView

urlpatterns = [
    path('api/v1/products/', ProductListView.as_view(), name='product-list'),
    path('api/v1/products/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
]
