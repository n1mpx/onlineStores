from django.db import models
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

good_image_storage = S3Boto3Storage()


class GoodCategory(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.title


class Good(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(GoodCategory, on_delete=models.CASCADE, related_name='goods')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goods')
    image = models.ImageField(
        upload_to='goods/',
        storage=good_image_storage,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


class GoodImage(models.Model):
    good = models.ForeignKey(Good, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='goods/', storage=S3Boto3Storage())
    thumbnail = models.ImageField(upload_to='goods/thumbs/', storage=S3Boto3Storage(), blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.image and not self.thumbnail:
            try:
                img = Image.open(self.image)
                img = img.convert("RGB")
                img.thumbnail((300, 300))  # размер превью

                thumb_io = BytesIO()
                img.save(thumb_io, format='JPEG', quality=80)

                thumb_name = f"thumb_{self.image.name.split('/')[-1]}"
                self.thumbnail.save(thumb_name, ContentFile(thumb_io.getvalue()), save=False)
            except Exception as e:
                print(f"Ошибка создания превью: {e}")

        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(
        upload_to='payment_logos/',
        storage=S3Boto3Storage(),
        null=True,
        blank=True
    )

    def __str__(self):
        return self.title


class DeliveryMethod(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Recipient(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    address = models.TextField()
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.last_name} {self.first_name}"


class BasketItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='basket_items'
    )
    good = models.ForeignKey('Good', on_delete=models.CASCADE, related_name='basket_items')
    count = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'good'], name='unique_user_good')
        ]

    def __str__(self):
        return f"{self.user} — {self.good.name} x {self.count}"

class Checkout(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checkouts'
    )
    recipient = models.ForeignKey('Recipient', on_delete=models.CASCADE)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.PROTECT)
    delivery_method = models.ForeignKey('DeliveryMethod', on_delete=models.PROTECT)
    payment_total = models.DecimalField(max_digits=10, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    ORDER_STATUS_CHOICES = [
        ('CREATED', 'Создан'),
        ('PAID', 'Оплачен'),
        ('SHIPPED', 'Отправлен'),
        ('DELIVERED', 'Доставлен'),
        ('CANCELLED', 'Отменён'),
    ]

    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='CREATED'
    )

    def __str__(self):
        return f"Checkout #{self.id} by {self.user}"


class CheckoutItem(models.Model):
    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name='items')
    good = models.ForeignKey('Good', on_delete=models.PROTECT)
    count = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.good.name} x {self.count}"


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('ERROR', 'Error'),
    ]

    checkout = models.ForeignKey(Checkout, on_delete=models.CASCADE, related_name='transactions')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    provider_data = models.JSONField(null=True, blank=True)  # ⬅️ обязательно
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transaction #{self.id} - {self.status}"
