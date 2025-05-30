from rest_framework import viewsets, permissions, mixins, status, serializers
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import (
    GoodCategory, Good, PaymentMethod, DeliveryMethod,
    Recipient, Checkout, Transaction, BasketItem, CheckoutItem
)

from .serializers import (
    GoodCategorySerializer, GoodSerializer, PaymentMethodSerializer,
    DeliveryMethodSerializer, RecipientSerializer, BasketItemSerializer,
    CheckoutSerializer, TransactionSerializer
)

from .permission import IsSellerOrAdmin, IsSellerAndOwnerOrReadOnly, IsAdminOnly


class CustomPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        return Response({
            'totalCount': self.page.paginator.count,
            'nextPage': self.get_next_link(),
            'prevPage': self.get_previous_link(),
            'items': data
        })


# --- Категории ---
class GoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = GoodCategory.objects.all()
    serializer_class = GoodCategorySerializer
    pagination_class = CustomPagination


# --- Публичный каталог товаров ---
class PublicGoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Good.objects.all()
    serializer_class = GoodSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CustomPagination


# --- Товары продавца ---
class GoodViewSet(viewsets.ModelViewSet):
    serializer_class = GoodSerializer
    permission_classes = [permissions.IsAuthenticated, IsSellerAndOwnerOrReadOnly]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        print(self.request.user, self.request.user.is_staff)
        if user.is_staff:
            return Good.objects.all()
        return Good.objects.filter(seller=user)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if not self.request.user.is_staff and obj.seller != self.request.user:
            raise PermissionDenied("Вы не можете получить доступ к чужому товару.")
        return obj


# --- Методы оплаты ---
class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminOnly()]
        return [permissions.AllowAny()]


# --- Методы доставки ---
class DeliveryMethodViewSet(viewsets.ModelViewSet):
    queryset = DeliveryMethod.objects.all()
    serializer_class = DeliveryMethodSerializer
    pagination_class = CustomPagination


# --- Получатели (для заказов) ---
class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.seller == request.user


class RecipientViewSet(viewsets.ModelViewSet):
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Recipient.objects.all()
        return Recipient.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# --- Корзина пользователя ---
class BasketItemViewSet(viewsets.ModelViewSet):
    serializer_class = BasketItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BasketItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        good = serializer.validated_data['good']
        count = serializer.validated_data['count']
        user = self.request.user

        if count <= 0:
            raise serializers.ValidationError("Количество должно быть больше 0.")

        existing = BasketItem.objects.filter(user=user, good=good).first()
        if existing:
            existing.count += count
            existing.save()
            raise serializers.ValidationError("Товар уже был в корзине — количество обновлено.")

        serializer.save(user=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        good = serializer.validated_data['good']
        count = serializer.validated_data['count']
        user = request.user

        existing = BasketItem.objects.filter(user=user, good=good).first()
        if existing:
            existing.count += count
            existing.save()
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if 'count' in request.data:
            count = int(request.data['count'])
            if count <= 0:
                instance.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            instance.count = count
            instance.save()
            return Response(self.get_serializer(instance).data)
        return super().update(request, *args, **kwargs)


# --- Оформление заказа ---
class CheckoutViewSet(viewsets.ModelViewSet):
    queryset = Checkout.objects.all()
    serializer_class = CheckoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Checkout.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        basket_items = BasketItem.objects.filter(user=user)

        if not basket_items.exists():
            raise serializers.ValidationError("Корзина пуста")

        total = sum(item.good.price * item.count for item in basket_items)
        checkout = serializer.save(user=user, payment_total=total)

        # Переносим товары из корзины в чекаут
        for item in basket_items:
            CheckoutItem.objects.create(
                checkout=checkout,
                good=item.good,
                count=item.count
            )

        # Очищаем корзину
        basket_items.delete()


# --- Транзакции пользователя ---
class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(checkout__user=self.request.user)
