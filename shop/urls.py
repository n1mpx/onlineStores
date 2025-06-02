from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoodCategoryViewSet, GoodViewSet, PaymentMethodViewSet, DeliveryMethodViewSet, RecipientViewSet, \
    BasketItemViewSet, CheckoutViewSet, TransactionViewSet, initiate_yookassa_payment, yookassa_webhook

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
    path('', include(router.urls)),
]

urlpatterns += [
    path('payment/yookassa/initiate/', initiate_yookassa_payment, name='yookassa-initiate'),
    path('payment/yookassa/webhook/', yookassa_webhook, name='yookassa-webhook'),
]