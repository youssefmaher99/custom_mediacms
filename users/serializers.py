from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from django.contrib.auth.password_validation import validate_password

from .models import User


class UserSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    api_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())

    def get_api_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url(api=True))

    def get_thumbnail_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.thumbnail_url())

    class Meta:
        model = User
        read_only_fields = (
            "date_added",
            "is_featured",
            "uid",
            "username",
            "advancedUser",
            "is_editor",
            "is_manager",
            "email_is_verified",
        )
        fields = (
            "description",
            "date_added",
            "name",
            "is_featured",
            "thumbnail_url",
            "url",
            "api_url",
            "username",
            "advancedUser",
            "is_editor",
            "is_manager",
            "email_is_verified",
        )


class UserDetailSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    api_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())

    def get_api_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url(api=True))

    def get_thumbnail_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.thumbnail_url())

    class Meta:
        model = User
        read_only_fields = ("date_added", "is_featured", "uid", "username")
        fields = (
            "description",
            "date_added",
            "name",
            "is_featured",
            "thumbnail_url",
            "banner_thumbnail_url",
            "url",
            "username",
            "media_info",
            "api_url",
            "edit_url",
            "default_channel_edit_url",
        )
        extra_kwargs = {"name": {"required": False}}


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=255, required=False)
    username = serializers.CharField(max_length=255, required=False)
    password = serializers.CharField(max_length=128, write_only=True)
    token = serializers.CharField(max_length=255, required=False)

    def validate(self, data):
        email = data.get('email', None)
        username = data.get('username', None)
        password = data.get('password', None)

        if settings.ACCOUNT_AUTHENTICATION_METHOD == 'username' and not username:
            raise serializers.ValidationError('username is required to log in.')
        else:
            username_or_email = username
        if settings.ACCOUNT_AUTHENTICATION_METHOD == 'email' and not email:
            raise serializers.ValidationError('email is required to log in.')
        else:
            username_or_email = email

        if settings.ACCOUNT_AUTHENTICATION_METHOD == 'username_email' and not (username or email):
            raise serializers.ValidationError('username or email is required to log in.')
        else:
            username_or_email = username or email

        if password is None:
            raise serializers.ValidationError('password is required to log in.')

        user = authenticate(username=username_or_email, password=password)

        if user is None:
            raise serializers.ValidationError('User not found.')

        if not user.is_active:
            raise serializers.ValidationError('User has been deactivated.')

        token = Token.objects.filter(user=user).first()
        if not token:
            token = Token.objects.create(user=user)

        return {'email': user.email, 'username': user.username, 'token': token.key}
    


class UserRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    email = serializers.CharField(required=True)
    name = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'name', 'password', 'description', 'title',
                 'location', 'is_featured', 'advancedUser',
                 'media_count', 'allow_contact', 'thumbnail_url',
                 'banner_thumbnail_url', 'email_is_verified', 'playlists_info',
                 'media_info')

    def create(self, validated_data):
        if 'name' not in validated_data:
            validated_data['name'] = validated_data['username']
        user = User.objects.create_user(**validated_data)
        return user

class UserDetailSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    banner_thumbnail_url = serializers.SerializerMethodField()
    email_is_verified = serializers.BooleanField(read_only=True)
    playlists_info = serializers.ReadOnlyField()
    media_info = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'name', 'description', 'title',
                 'location', 'date_added', 'is_featured', 'advancedUser',
                 'media_count', 'allow_contact', 'thumbnail_url',
                 'banner_thumbnail_url', 'email_is_verified', 'playlists_info',
                 'media_info')
        read_only_fields = ('date_added', 'media_count', 'email_is_verified')

    def get_thumbnail_url(self, obj):
        return obj.thumbnail_url()

    def get_banner_thumbnail_url(self, obj):
        return obj.banner_thumbnail_url()