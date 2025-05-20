from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSellerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['seller', 'admin']


class IsSellerAndOwnerOrReadOnly(BasePermission):
    """
    Разрешает:
    - Просмотр всем
    - Редактирование только продавцу и только своих товаров
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return request.user.is_authenticated and request.user.role == 'seller'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        return obj.seller == request.user


class IsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'