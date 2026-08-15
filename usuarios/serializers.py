from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password

Usuario = get_user_model()

class PasswordUsuarioMixin:
    def validate(self, data):
        password = data.get('password')
        password2 = data.get('password2')

        if self.instance is None and (not password or not password2):
            raise serializers.ValidationError({"password": "Debes ingresar y confirmar la contraseña."})

        if password or password2:
            if not password or not password2 or password != password2:
                raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})

            candidate = self.instance or Usuario(
                username=data.get('username', ''),
                email=data.get('email', ''),
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})

        if 'email' in data:
            data['email'] = data['email'].strip().lower()
            try:
                validate_email(data['email'])
            except ValidationError:
                raise serializers.ValidationError({"email": "Ingrese un correo electrónico válido."})
            email_en_uso = Usuario.objects.filter(email__iexact=data['email'])
            if self.instance is not None:
                email_en_uso = email_en_uso.exclude(pk=self.instance.pk)
            if email_en_uso.exists():
                raise serializers.ValidationError({"email": "Este correo electrónico ya está registrado."})

        return data

    def _update_usuario(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('password2', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class RegistroUsuarioSerializer(PasswordUsuarioMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = Usuario
        fields = [
            'rut', 'username', 'first_name', 'last_name',
            'email', 'telefono', 'password', 'password2'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }

    def create(self, validated_data):
        validated_data.pop('password2', None)
        validated_data['is_active'] = False
        validated_data['is_staff'] = False
        validated_data['is_superuser'] = False
        validated_data['email_confirmado'] = False
        return Usuario.objects.create_user(**validated_data)


class AdminUsuarioSerializer(PasswordUsuarioMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    is_staff = serializers.BooleanField(required=False)

    class Meta:
        model = Usuario
        fields = [
            'rut', 'username', 'first_name', 'last_name',
            'email', 'telefono', 'is_staff', 'password', 'password2'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }

    def create(self, validated_data):
        validated_data.pop('password2', None)
        validated_data.setdefault('is_active', True)
        validated_data.setdefault('email_confirmado', True)
        return Usuario.objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        return self._update_usuario(instance, validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            data['user'] = user
            return data
        raise serializers.ValidationError("Credenciales inválidas o cuenta inactiva")


class UsuarioListaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'id', 'rut', 'username', 'first_name', 'last_name',
            'email', 'telefono', 'is_staff', 'is_active', 'email_confirmado'
        ]
