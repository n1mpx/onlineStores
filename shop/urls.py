from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoodCategoryViewSet, GoodViewSet, PaymentMethodViewSet, DeliveryMethodViewSet, RecipientViewSet, \
    BasketItemViewSet, CheckoutViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'good-categories', GoodCategoryViewSet, basename='good-category')
router.register(r'goods', GoodViewSet, basename='good')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'delivery-methods', DeliveryMethodViewSet, basename='delivery-method')
router.register(r'recipients', RecipientViewSet, basename='recipient')
router.register(r'me/basket-items', BasketItemViewSet, basename='basket-item')
router.register(r'checkouts', CheckoutViewSet, basename='checkout')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
