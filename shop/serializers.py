from rest_framework import serializers
from .models import GoodCategory, Good, GoodImage, PaymentMethod, DeliveryMethod, Recipient, BasketItem, Checkout, \
    CheckoutItem, Transaction
import json
from rest_framework import serializers



class GoodCategorySerializer(serializers.ModelSerializer):
    parentId = serializers.PrimaryKeyRelatedField(
        source='parent', queryset=GoodCategory.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = GoodCategory
        fields = ['id', 'title', 'description', 'parentId']


class GoodImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and hasattr(obj.thumbnail, 'url'):
            return request.build_absolute_uri(obj.thumbnail.url) if request else obj.thumbnail.url
        return None

    class Meta:
        model = GoodImage
        fields = ['id', 'image', 'thumbnail']
class GoodImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoodImage
        fields = ['id', 'image', 'thumbnail']


class GoodSerializer(serializers.ModelSerializer):
    categoryId = serializers.PrimaryKeyRelatedField(
        source='category', queryset=GoodCategory.objects.all()
    )
    sellerId = serializers.PrimaryKeyRelatedField(
        source='seller', read_only=True
    )
    images = serializers.SerializerMethodField()

    def get_images(self, obj):
        request = self.context.get('request')
        serializer = GoodImageSerializer(obj.images.all(), many=True, context={'request': request})
        return serializer.data

    class Meta:
        model = Good
        fields = [
            'id', 'name', 'description', 'price',
            'categoryId', 'sellerId', 'images'
        ]



class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'title', 'description', 'logo']


class DeliveryMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryMethod
        fields = ['id', 'title', 'description']


class RecipientSerializer(serializers.ModelSerializer):
    userId = serializers.PrimaryKeyRelatedField(source='user', read_only=True)

    class Meta:
        model = Recipient
        fields = [
            'id', 'userId', 'first_name', 'last_name',
            'middle_name', 'address', 'zip_code', 'phone'
        ]


class GoodNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Good
        fields = ['id', 'name', 'price', 'description']


class BasketItemSerializer(serializers.ModelSerializer):
    goodId = serializers.PrimaryKeyRelatedField(
        source='good', queryset=Good.objects.all()
    )
    good = GoodNestedSerializer(read_only=True)

    class Meta:
        model = BasketItem
        fields = ['id', 'goodId', 'good', 'count']


class CheckoutItemSerializer(serializers.ModelSerializer):
    goodId = serializers.PrimaryKeyRelatedField(source='good', read_only=True)

    class Meta:
        model = CheckoutItem
        fields = ['goodId', 'count']


class CheckoutSerializer(serializers.ModelSerializer):
    recipientId = serializers.PrimaryKeyRelatedField(source='recipient', queryset=Recipient.objects.all())
    paymentMethodId = serializers.PrimaryKeyRelatedField(source='payment_method', queryset=PaymentMethod.objects.all())
    deliveryMethodId = serializers.PrimaryKeyRelatedField(source='delivery_method', queryset=DeliveryMethod.objects.all())
    items = CheckoutItemSerializer(many=True, read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Checkout
        fields = [
            'id', 'user', 'recipientId',
            'paymentMethodId', 'deliveryMethodId',
            'payment_total', 'created', 'items', 'status'
        ]
        read_only_fields = ['user', 'created', 'is_paid', 'status']

class TransactionSerializer(serializers.ModelSerializer):
    checkoutId = serializers.PrimaryKeyRelatedField(source='checkout', queryset=Checkout.objects.all())
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'created', 'updated', 'status', 'amount',
            'checkoutId', 'provider_data', 'payment_url'
        ]

    def get_payment_url(self, obj):
        if not obj.provider_data:
            return None
        try:
            data = json.loads(obj.provider_data) if isinstance(obj.provider_data, str) else obj.provider_data
            return data.get('confirmation', {}).get('confirmation_url')  # ⬅️ исправлено
        except Exception:
            return None

