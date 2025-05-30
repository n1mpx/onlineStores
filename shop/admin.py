from django.contrib import admin
from .models import GoodCategory, Good, PaymentMethod, DeliveryMethod, Recipient, BasketItem, Checkout, CheckoutItem, Transaction


@admin.register(GoodCategory)
class GoodCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'parent']
    search_fields = ['title']
    list_filter = ['parent']


@admin.register(Good)
class GoodAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'category', 'seller']
    list_filter = ['category', 'seller']
    search_fields = ['name', 'description']
    autocomplete_fields = ['category', 'seller']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == 'admin':
            return qs
        return qs.filter(seller=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.seller = request.user
        super().save_model(request, obj, form, change)




@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'description']
    search_fields = ['title']


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ['id', 'title']
    search_fields = ['title']


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'first_name', 'last_name', 'phone']
    search_fields = ['first_name', 'last_name', 'phone', 'user__email']
    list_filter = ['user']


@admin.register(BasketItem)
class BasketItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'good', 'count']
    list_filter = ['user']
    autocomplete_fields = ['user', 'good']


class CheckoutItemInline(admin.TabularInline):
    model = CheckoutItem
    extra = 0


@admin.register(Checkout)
class CheckoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'payment_total', 'created']
    list_filter = ['created', 'payment_method', 'delivery_method']
    inlines = [CheckoutItemInline]
    autocomplete_fields = ['user', 'recipient', 'payment_method', 'delivery_method']
    search_fields = ['user__email', 'recipient__first_name', 'recipient__last_name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'checkout', 'status', 'amount', 'created', 'updated']
    list_filter = ['status']
    autocomplete_fields = ['checkout']
