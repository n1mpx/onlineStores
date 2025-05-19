from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailCode, User
from .serializers import EmailSerializer
from rest_framework import status
from django.core.exceptions import ValidationError

import traceback


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user, created = User.objects.get_or_create(email=email)

                EmailCode.objects.filter(email=email).delete()
                email_code = EmailCode.objects.create(email=email)
                email_code.generate_code()

                send_mail(
                    'Ваш одноразовый код',
                    f'Ваш код: {email_code.code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                print(f'Ваш код: {email_code.code}')

                return Response({"message": "Код отправлен на email."}, status=status.HTTP_200_OK)


            except Exception as e:

                print("Произошла ошибка:")

                traceback.print_exc()  # Покажет полный стек трейс

                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        try:
            email_code = EmailCode.objects.get(email=email, code=code)
        except EmailCode.DoesNotExist:
            return Response({"error": "Неверный код."}, status=status.HTTP_400_BAD_REQUEST)

        if not email_code.is_valid():
            return Response({"error": "Код истёк."}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(email=email)
        if created:
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        return Response({
            "access": str(access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_200_OK)
