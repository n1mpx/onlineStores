from yookassa import Configuration, Payment
import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied
import uuid
import json

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions, mixins, status, serializers
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser

from .models import GoodCategory, Good, PaymentMethod, DeliveryMethod, Recipient, Checkout, Transaction, BasketItem, \
    CheckoutItem, GoodImage
from .serializers import GoodCategorySerializer, GoodSerializer, PaymentMethodSerializer, DeliveryMethodSerializer, \
    RecipientSerializer, BasketItemSerializer, CheckoutSerializer, TransactionSerializer
from .permission import IsSellerOrAdmin, IsSellerAndOwnerOrReadOnly, IsAdminOnly, IsSellerOnly


Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_yookassa_payment(request):
    user = request.user
    checkout_id = request.data.get('checkout_id')

    try:
        checkout = Checkout.objects.get(id=checkout_id, user=user)
    except Checkout.DoesNotExist:
        return Response({'error': 'Checkout не найден'}, status=404)

    idempotence_key = str(uuid.uuid4())

    payment = Payment.create({
        "amount": {
            "value": str(checkout.payment_total),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "http://localhost:5173/order-success"
        },
        "capture": True,
        "description": f"Оплата заказа #{checkout.id}"
    }, idempotence_key)

    # Сохраняем транзакцию
    Transaction.objects.create(
        checkout=checkout,
        status='PENDING',
        amount=checkout.payment_total,
        provider_data=payment.json()
    )

    return Response({
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url
    })


@csrf_exempt
@api_view(['POST'])
def yookassa_webhook(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        object_data = payload.get('object', {})
        payment_id = object_data.get('id')
        status = object_data.get('status')

        print(f"🔔 Webhook пришёл! payment_id={payment_id}, status={status}")

        if not payment_id:
            return Response({"error": "payment_id отсутствует"}, status=400)

        transaction = Transaction.objects.filter(provider_data__id=payment_id).first()
        if not transaction:
            return Response({"error": "Transaction не найдена"}, status=404)

        # Обновляем статус
        transaction.status = 'SUCCESS' if status == 'succeeded' else 'ERROR'
        transaction.provider_data = object_data
        transaction.save()

        # Обновляем заказ
        if status == 'succeeded':
            checkout = transaction.checkout
            checkout.is_paid = True
            checkout.status = 'PAID'
            checkout.save()

        return Response({"message": "OK"}, status=200)

    except Exception as e:
        print("Ошибка в webhook:", e)
        return Response({"error": str(e)}, status=500)


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


class PublicGoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Good.objects.all()
    serializer_class = GoodSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CustomPagination


class GoodViewSet(viewsets.ModelViewSet):
    serializer_class = GoodSerializer
    permission_classes = [IsSellerOnly, IsSellerAndOwnerOrReadOnly]
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

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def upload_image(self, request, pk=None):
        good = self.get_object()

        if good.seller != request.user:
            return Response({'detail': 'Вы не являетесь владельцем этого товара.'}, status=403)

        if request.user.role not in ['seller', 'admin']:
            return Response({'detail': 'Только продавец может загружать изображения.'}, status=403)

        images = request.FILES.getlist('image')

        if not images:
            return Response({'error': 'Файлы не переданы'}, status=400)

        for img in images:
            GoodImage.objects.create(good=good, image=img)

        return Response({'message': f'{len(images)} изображений загружено'})


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


    def perform_create(self, serializer):
        validated_data = serializer.validated_data
        checkout = validated_data['checkout']
        amount = validated_data['amount']

        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "http://localhost:5173/order-success"
            },
            "capture": True,
            "description": f"Заказ №{checkout.id}",
            "metadata": {
                "checkout_id": checkout.id,
            }
        }, uuid.uuid4().hex)

        # Создаем и сохраняем вручную
        transaction = Transaction.objects.create(
            checkout=checkout,
            amount=amount,
            status='created',
            provider_data=payment.json()
        )

        # ВАЖНО: записываем объект обратно в сериализатор
        serializer.instance = transaction

