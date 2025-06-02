from yookassa import Configuration, Payment
import requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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
from .permission import IsSellerOrAdmin, IsSellerAndOwnerOrReadOnly, IsAdminOnly


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

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def upload_image(self, request, pk=None):
        good = self.get_object()

        if good.seller != request.user:
            return Response({'detail': 'Вы не являетесь владельцем этого товара.'}, status=403)

        if request.user.role != 'seller':
            return Response({'detail': 'Только продавец может загружать изображения.'}, status=403)

        images = request.FILES.getlist('image')

        if not images:
            return Response({'error': 'Файлы не переданы'}, status=400)

        for img in images:
            GoodImage.objects.create(good=good, image=img)

        return Response({'message': f'{len(images)} изображений загружено'})


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