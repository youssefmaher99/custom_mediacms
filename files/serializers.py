from cms import settings
from rest_framework import serializers

from .models import Category, Comment, EncodeProfile, Media, Playlist, Tag

# TODO: put them in a more DRY way


class MediaSerializer(serializers.ModelSerializer):
    playlist_friendly_token = serializers.CharField(read_only=True)

    # to be used in APIs as show related media
    user = serializers.ReadOnlyField(source="user.username")
    url = serializers.SerializerMethodField()
    api_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    author_profile = serializers.SerializerMethodField()
    author_thumbnail = serializers.SerializerMethodField()

    def get_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())

    def get_api_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url(api=True))

    def get_thumbnail_url(self, obj):
        if obj.thumbnail_url:
            return self.context["request"].build_absolute_uri(obj.thumbnail_url)
        else:
            return None

    def get_author_profile(self, obj):
        return self.context["request"].build_absolute_uri(obj.author_profile())

    def get_author_thumbnail(self, obj):
        return self.context["request"].build_absolute_uri(obj.author_thumbnail())

    class Meta:
        model = Media
        read_only_fields = (
            "id",
            "playlist_friendly_token",
            "friendly_token",
            "user",
            "add_date",
            "media_type",
            "state",
            "duration",
            "encoding_status",
            "views",
            "likes",
            "dislikes",
            "reported_times",
            "size",
            "is_reviewed",
            "featured",
        )
        fields = (
            "id",
            "playlist_friendly_token",
            "friendly_token",
            "url",
            "api_url",
            "user",
            "title",
            "description",
            "add_date",
            "views",
            "media_type",
            "state",
            "duration",
            "thumbnail_url",
            "is_reviewed",
            "preview_url",
            "author_name",
            "author_profile",
            "author_thumbnail",
            "encoding_status",
            "views",
            "likes",
            "dislikes",
            "reported_times",
            "featured",
            "user_featured",
            "size",
        )


class SingleMediaSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())

    class Meta:
        model = Media
        read_only_fields = (
            "friendly_token",
            "user",
            "add_date",
            "views",
            "media_type",
            "state",
            "duration",
            "encoding_status",
            "views",
            "likes",
            "dislikes",
            "reported_times",
            "size",
            "video_height",
            "is_reviewed",
        )
        fields = (
            "url",
            "user",
            "title",
            "description",
            "add_date",
            "edit_date",
            "media_type",
            "state",
            "duration",
            "thumbnail_url",
            "poster_url",
            "thumbnail_time",
            "url",
            "sprites_url",
            "preview_url",
            "author_name",
            "author_profile",
            "author_thumbnail",
            "encodings_info",
            "encoding_status",
            "views",
            "likes",
            "dislikes",
            "reported_times",
            "user_featured",
            "original_media_url",
            "size",
            "video_height",
            "enable_comments",
            "categories_info",
            "is_reviewed",
            "edit_url",
            "tags_info",
            "hls_info",
            "license",
            "subtitles_info",
            "ratings_info",
            "add_subtitle_url",
            "allow_download",
        )


class MediaSearchSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    api_url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())

    def get_api_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url(api=True))

    class Meta:
        model = Media
        fields = (
            "title",
            "author_name",
            "author_profile",
            "thumbnail_url",
            "add_date",
            "views",
            "description",
            "friendly_token",
            "duration",
            "url",
            "api_url",
            "media_type",
            "preview_url",
            "categories_info",
        )


class EncodeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncodeProfile
        fields = ("name", "extension", "resolution", "codec", "description")


class CategorySerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")
    # thumbnail_url = serializers.SerializerMethodField()

    # def get_thumbnail_url(self, obj):
    #     if obj.thumbnail_url:
    #         if settings.DEVELOPMENT_MODE:
    #             print("/*/*/*/**/*")
    #             return obj.thumbnail_url
    #         else:
    #             return obj.thumbnail_url
    #     return None

    class Meta:
        model = Category
        fields = (
            "title",
            "description",
            "is_global",
            "media_count",
            "user",
            "thumbnail_url",
        )


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("title", "media_count", "thumbnail_url")


class PlaylistSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")
    cover_image = serializers.SerializerMethodField()
    thumbnail_image = serializers.SerializerMethodField()

    def get_cover_image(self, obj):
        if obj.cover_image:
            if settings.DEVELOPMENT_MODE:
                return "http://localhost" + settings.MEDIA_URL + str(obj.cover_image)
            else:
                return settings.MEDIA_URL + str(obj.cover_image)
        return None
    
    def get_thumbnail_image(self, obj):
        if obj.thumbnail_image:
            if settings.DEVELOPMENT_MODE:
                return "http://localhost" + settings.MEDIA_URL + str(obj.thumbnail_image)
            else:
                return settings.MEDIA_URL + str(obj.thumbnail_image)
        return None

    class Meta:
        model = Playlist
        read_only_fields = ("add_date", "user")
        fields = ("id","add_date", "title", "description", "user", "media_count", "url", "api_url", "thumbnail_url", "category", "cover_image", "friendly_token", "thumbnail_image")


class PlaylistDetailSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")
    cover_image = serializers.SerializerMethodField()
    thumbnail_image = serializers.SerializerMethodField()

    def get_cover_image(self, obj):
        if obj.cover_image:
            if settings.DEVELOPMENT_MODE:
                return "http://localhost" + settings.MEDIA_URL + str(obj.cover_image)
            else:
                return settings.MEDIA_URL + str(obj.cover_image)
        return None
    
    def get_thumbnail_image(self, obj):
        if obj.thumbnail_image:
            if settings.DEVELOPMENT_MODE:
                return "http://localhost" + settings.MEDIA_URL + str(obj.thumbnail_image)
            else:
                return settings.MEDIA_URL + str(obj.thumbnail_image)
        return None

    class Meta:
        model = Playlist
        read_only_fields = ("add_date", "user")
        fields = ("id","title", "add_date", "user_thumbnail_url", "description", "user", "media_count", "url", "thumbnail_url", "category", "cover_image", "friendly_token", "thumbnail_image")


class CommentSerializer(serializers.ModelSerializer):
    author_profile = serializers.ReadOnlyField(source="user.get_absolute_url")
    author_name = serializers.ReadOnlyField(source="user.name")
    author_thumbnail_url = serializers.ReadOnlyField(source="user.thumbnail_url")

    class Meta:
        model = Comment
        read_only_fields = ("add_date", "uid")
        fields = (
            "add_date",
            "text",
            "parent",
            "author_thumbnail_url",
            "author_profile",
            "author_name",
            "media_url",
            "uid",
        )


class FavoritePlaylistSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Playlist
        fields = ("id","add_date", "title", "description", "user", "media_count", "url", "api_url", "thumbnail_url", "category", "cover_image", "friendly_token")
    