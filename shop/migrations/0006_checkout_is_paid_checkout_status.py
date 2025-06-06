# Generated by Django 5.2 on 2025-06-02 19:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0005_good_seller_alter_paymentmethod_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="checkout",
            name="is_paid",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="checkout",
            name="status",
            field=models.CharField(
                choices=[
                    ("CREATED", "Создан"),
                    ("PAID", "Оплачен"),
                    ("SHIPPED", "Отправлен"),
                    ("DELIVERED", "Доставлен"),
                    ("CANCELLED", "Отменён"),
                ],
                default="CREATED",
                max_length=20,
            ),
        ),
    ]
