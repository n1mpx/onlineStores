from rest_framework import viewsets, permissions, mixins, status, serializers
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from .models import GoodCategory, Good, PaymentMethod, DeliveryMethod, Recipient, Checkout, Transaction, BasketItem, \
    CheckoutItem
from .serializers import GoodCategorySerializer, GoodSerializer, PaymentMethodSerializer, DeliveryMethodSerializer, \
    RecipientSerializer, BasketItemSerializer, CheckoutSerializer, TransactionSerializer
from .permission import IsSellerOrAdmin, IsSellerAndOwnerOrReadOnly, IsAdminOnly


class CustomPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        return Response({
            'totalCount': self.page.paginator.count,
            'nextPage': self.get_next_link(),
            'prevage': self.get_previous_link(),
            'items': data
        })


class GoodCategoryViewSet(viewsets.ModelViewSet):
    queryset = GoodCategory.objects.all()
    serializer_class = GoodCategorySerializer
    pagination_class = CustomPagination


class GoodViewSet(viewsets.ModelViewSet):
    queryset = Good.objects.all()
    serializer_class = GoodSerializer
    permission_classes = [IsSellerAndOwnerOrReadOnly]
    pagination_class = CustomPagination

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def get_queryset(self):
        return Good.objects.all()


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsAdminOnly()]
        return [permissions.AllowAny()]


class DeliveryMethodViewSet(viewsets.ModelViewSet):
    queryset = DeliveryMethod.objects.all()
    serializer_class = DeliveryMethodSerializer
    pagination_class = CustomPagination


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.user == request.user


class RecipientViewSet(viewsets.ModelViewSet):
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        # Админ видит всё, пользователь — только своё
        if self.request.user.is_staff:
            return Recipient.objects.all()
        return Recipient.objects.filter(user=self.request.user)


class BasketItemViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = BasketItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Корзина — без пагинации

    def get_queryset(self):
        return BasketItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Если товар уже в корзине — обновляем count
        existing = BasketItem.objects.filter(user=self.request.user, good=serializer.validated_data['good']).first()
        if existing:
            existing.count += serializer.validated_data['count']
            existing.save()
            self.existing_instance = existing
        else:
            serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        if hasattr(self, 'existing_instance'):
            return Response(BasketItemSerializer(self.existing_instance).data, status=200)

        return Response(serializer.data, status=201)


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

        # Копируем корзину в чекаут
        for item in basket_items:
            CheckoutItem.objects.create(
                checkout=checkout,
                good=item.good,
                count=item.count
            )

        # Очищаем корзину
        basket_items.delete()


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(checkout__user=self.request.user)