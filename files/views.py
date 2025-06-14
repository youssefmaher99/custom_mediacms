from collections import Counter
from datetime import datetime, timedelta, timezone
import os
from random import SystemRandom
from django.forms import IntegerField
from rest_framework.authentication import BasicAuthentication
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, render
from drf_yasg import openapi as openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FileUploadParser, FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from django.views.generic import FormView
from actions.models import USER_MEDIA_ACTIONS, MediaAction
from cms.custom_pagination import FastPaginationWithoutCount
from cms.permissions import IsAuthorizedToAdd, IsAuthorizedToAddComment, IsUserOrEditor, user_allowed_to_upload
from users.models import User
from django.http import JsonResponse
from django.core.files.storage import default_storage
from .forms import ContactForm, MediaForm, SubtitleForm
from .frontend_translations import translate_string
from .helpers import clean_query, get_alphanumeric_only, produce_ffmpeg_commands
from .methods import (
    check_comment_for_mention,
    get_user_or_session,
    is_mediacms_editor,
    is_mediacms_manager,
    list_tasks,
    notify_user_on_comment,
    show_recommended_media,
    show_related_media,
    update_user_ratings,
)
from .models import Category, Comment, EncodeProfile, Encoding, Media, Playlist, PlaylistMedia, Tag, UserEvents
from .serializers import (
    CategorySerializer,
    CommentSerializer,
    EncodeProfileSerializer,
    FavoritePlaylistSerializer,
    MediaSearchSerializer,
    MediaSerializer,
    PlaylistDetailSerializer,
    PlaylistSerializer,
    SingleMediaSerializer,
    TagSerializer,
)
from .stop_words import STOP_WORDS
from .tasks import save_user_action, store_user_events
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Subquery, OuterRef
from django.db.models import Count, Case, When, IntegerField
from collections import Counter
from random import SystemRandom
from django.db.models import Sum

VALID_USER_ACTIONS = [action for action, name in USER_MEDIA_ACTIONS]
MAX_FILE_SIZE = 10 * 1024 * 1024


def about(request):
    """About view"""

    context = {}
    return render(request, "cms/about.html", context)


def setlanguage(request):
    """Set Language view"""

    context = {}
    return render(request, "cms/set_language.html", context)


@login_required
def add_subtitle(request):
    """Add subtitle view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()
    if not media:
        return HttpResponseRedirect("/")

    if not (request.user == media.user or is_mediacms_editor(request.user) or is_mediacms_manager(request.user)):
        return HttpResponseRedirect("/")

    if request.method == "POST":
        form = SubtitleForm(media, request.POST, request.FILES)
        if form.is_valid():
            subtitle = form.save()
            messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, "Subtitle was added"))

            return HttpResponseRedirect(subtitle.media.get_absolute_url())
    else:
        form = SubtitleForm(media_item=media)
    return render(request, "cms/add_subtitle.html", {"form": form})


def categories(request):
    """List categories view"""

    context = {}
    return render(request, "cms/categories.html", context)


def contact(request):
    """Contact view"""

    context = {}
    if request.method == "GET":
        form = ContactForm(request.user)
        context["form"] = form

    else:
        form = ContactForm(request.user, request.POST)
        if form.is_valid():
            if request.user.is_authenticated:
                from_email = request.user.email
                name = request.user.name
            else:
                from_email = request.POST.get("from_email")
                name = request.POST.get("name")
            message = request.POST.get("message")

            title = "[{}] - Contact form message received".format(settings.PORTAL_NAME)

            msg = """
You have received a message through the contact form\n
Sender name: %s
Sender email: %s\n
\n %s
""" % (
                name,
                from_email,
                message,
            )
            email = EmailMessage(
                title,
                msg,
                settings.DEFAULT_FROM_EMAIL,
                settings.ADMIN_EMAIL_LIST,
                reply_to=[from_email],
            )
            email.send(fail_silently=True)
            success_msg = "Message was sent! Thanks for contacting"
            context["success_msg"] = success_msg

    return render(request, "cms/contact.html", context)


def history(request):
    """Show personal history view"""

    context = {}
    return render(request, "cms/history.html", context)


@login_required
def edit_media(request):
    """Edit a media view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")
    media = Media.objects.filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    if not (request.user == media.user or is_mediacms_editor(request.user) or is_mediacms_manager(request.user)):
        return HttpResponseRedirect("/")
    if request.method == "POST":
        form = MediaForm(request.user, request.POST, request.FILES, instance=media)
        if form.is_valid():
            media = form.save()
            for tag in media.tags.all():
                media.tags.remove(tag)
            if form.cleaned_data.get("new_tags"):
                for tag in form.cleaned_data.get("new_tags").split(","):
                    tag = get_alphanumeric_only(tag)
                    tag = tag[:99]
                    if tag:
                        try:
                            tag = Tag.objects.get(title=tag)
                        except Tag.DoesNotExist:
                            tag = Tag.objects.create(title=tag, user=request.user)
                        if tag not in media.tags.all():
                            media.tags.add(tag)
            messages.add_message(request, messages.INFO, translate_string(request.LANGUAGE_CODE, "Media was edited"))
            return HttpResponseRedirect(media.get_absolute_url())
    else:
        form = MediaForm(request.user, instance=media)
    return render(
        request,
        "cms/edit_media.html",
        {"form": form, "add_subtitle_url": media.add_subtitle_url},
    )


def embed_media(request):
    """Embed media view"""

    friendly_token = request.GET.get("m", "").strip()
    if not friendly_token:
        return HttpResponseRedirect("/")

    media = Media.objects.values("title").filter(friendly_token=friendly_token).first()

    if not media:
        return HttpResponseRedirect("/")

    context = {}
    context["media"] = friendly_token
    return render(request, "cms/embed.html", context)


def featured_media(request):
    """List featured media view"""

    context = {}
    return render(request, "cms/featured-media.html", context)


def index(request):
    """Index view"""

    context = {}
    return render(request, "cms/index.html", context)


def latest_media(request):
    """List latest media view"""

    context = {}
    return render(request, "cms/latest-media.html", context)


def liked_media(request):
    """List user's liked media view"""

    context = {}
    return render(request, "cms/liked_media.html", context)


@login_required
def manage_users(request):
    """List users management view"""

    context = {}
    return render(request, "cms/manage_users.html", context)


@login_required
def manage_media(request):
    """List media management view"""

    context = {}
    return render(request, "cms/manage_media.html", context)


@login_required
def manage_comments(request):
    """List comments management view"""

    context = {}
    return render(request, "cms/manage_comments.html", context)


def members(request):
    """List members view"""

    context = {}
    return render(request, "cms/members.html", context)


def recommended_media(request):
    """List recommended media view"""

    context = {}
    return render(request, "cms/recommended-media.html", context)


def search(request):
    """Search view"""

    context = {}
    RSS_URL = f"/rss{request.environ.get('REQUEST_URI')}"
    context["RSS_URL"] = RSS_URL
    return render(request, "cms/search.html", context)


def statistics(request):
    """Statistics view"""

    context = {}
    return render(request, "cms/statistics.html", context)


def sitemap(request):
    """Sitemap"""

    context = {}
    context["media"] = list(Media.objects.filter(Q(listable=True)).order_by("-add_date"))
    context["playlists"] = list(Playlist.objects.filter().order_by("-add_date"))
    context["users"] = list(User.objects.filter())
    return render(request, "sitemap.xml", context, content_type="application/xml")


def tags(request):
    """List tags view"""

    context = {}
    return render(request, "cms/tags.html", context)


def tos(request):
    """Terms of service view"""

    context = {}
    return render(request, "cms/tos.html", context)


def upload_media(request):
    """Upload media view"""

    from allauth.account.forms import LoginForm

    form = LoginForm()
    context = {}
    context["form"] = form
    context["can_add"] = user_allowed_to_upload(request)
    can_upload_exp = settings.CANNOT_ADD_MEDIA_MESSAGE
    context["can_upload_exp"] = can_upload_exp

    return render(request, "cms/add-media.html", context)


def view_media(request):
    """View media view"""

    friendly_token = request.GET.get("m", "").strip()
    context = {}
    media = Media.objects.filter(friendly_token=friendly_token).first()
    if not media:
        context["media"] = None
        return render(request, "cms/media.html", context)

    user_or_session = get_user_or_session(request)
    save_user_action.delay(user_or_session, friendly_token=friendly_token, action="watch")
    context = {}
    context["media"] = friendly_token
    context["media_object"] = media

    context["CAN_DELETE_MEDIA"] = False
    context["CAN_EDIT_MEDIA"] = False
    context["CAN_DELETE_COMMENTS"] = False

    if request.user.is_authenticated:
        if (media.user.id == request.user.id) or is_mediacms_editor(request.user) or is_mediacms_manager(request.user):
            context["CAN_DELETE_MEDIA"] = True
            context["CAN_EDIT_MEDIA"] = True
            context["CAN_DELETE_COMMENTS"] = True
    return render(request, "cms/media.html", context)


def view_playlist(request, friendly_token):
    """View playlist view"""

    try:
        playlist = Playlist.objects.get(friendly_token=friendly_token)
    except BaseException:
        playlist = None

    context = {}
    context["playlist"] = playlist
    return render(request, "cms/playlist.html", context)


@method_decorator(csrf_exempt, name='dispatch')
class SimpleUploadView(FormView):
    authentication_classes = [BasicAuthentication]
    permission_classes = (IsAuthorizedToAdd)

    def dispatch(self, request, *args, **kwargs):
        # Authenticate using DRF's authentication classes
        user_auth_tuple = BasicAuthentication().authenticate(request)
        if user_auth_tuple is not None:
            request.user, request.auth = user_auth_tuple
        
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, friendly_token, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)

        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        if uploaded_file.size > MAX_FILE_SIZE:
            return JsonResponse({
                'success': False,
                'error': 'File too large'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

        if file_ext not in allowed_extensions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid file type'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Save file
            file_path = default_storage.save(
                f'cover/{uploaded_file.name}',
                uploaded_file
            )
            Playlist.objects.filter(friendly_token=friendly_token).update(cover_image=file_path)

            return JsonResponse({
                'success': True,
                'file_url': default_storage.url(file_path)
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class PlaylistThumbnailUploadView(FormView):
    authentication_classes = [BasicAuthentication]
    permission_classes = (IsAuthorizedToAdd)

    def dispatch(self, request, *args, **kwargs):
        # Authenticate using DRF's authentication classes
        user_auth_tuple = BasicAuthentication().authenticate(request)
        if user_auth_tuple is not None:
            request.user, request.auth = user_auth_tuple
        
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, friendly_token, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)

        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        if uploaded_file.size > MAX_FILE_SIZE:
            return JsonResponse({
                'success': False,
                'error': 'File too large'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

        if file_ext not in allowed_extensions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid file type'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Save file
            file_path = default_storage.save(
                f'playlist_thumbnail/{uploaded_file.name}',
                uploaded_file
            )
            Playlist.objects.filter(friendly_token=friendly_token).update(thumbnail_image=file_path)            

            return JsonResponse({
                'success': True,
                'file_url': default_storage.url(file_path)
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MediaList(APIView):
    """Media listings views"""

    permission_classes = (IsAuthorizedToAdd,)
    parser_classes = (MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='page', type=openapi.TYPE_INTEGER, in_=openapi.IN_QUERY, description='Page number'),
            openapi.Parameter(name='author', type=openapi.TYPE_STRING, in_=openapi.IN_QUERY, description='username'),
            openapi.Parameter(name='show', type=openapi.TYPE_STRING, in_=openapi.IN_QUERY, description='show', enum=['recommended', 'featured', 'latest']),
        ],
        tags=['Media'],
        operation_summary='List Media',
        operation_description='Lists all media',
        responses={200: MediaSerializer(many=True)},
    )
    def get(self, request, format=None):
        # Show media
        params = self.request.query_params
        show_param = params.get("show", "")

        author_param = params.get("author", "").strip()
        if author_param:
            user_queryset = User.objects.all()
            user = get_object_or_404(user_queryset, username=author_param)
        if show_param == "recommended":
            pagination_class = FastPaginationWithoutCount
            media = show_recommended_media(request, limit=50)
        else:
            pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
            if author_param:
                # in case request.user is the user here, show
                # all media independant of state
                if self.request.user == user:
                    basic_query = Q(user=user)
                else:
                    basic_query = Q(listable=True, user=user)
            else:
                # base listings should show safe content
                basic_query = Q(listable=True)

            if show_param == "featured":
                media = Media.objects.filter(basic_query, featured=True)
            else:
                media = Media.objects.filter(basic_query).order_by("-add_date")

        paginator = pagination_class()

        if show_param != "recommended":
            media = media.prefetch_related("user")
        page = paginator.paginate_queryset(media, request)

        serializer = MediaSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name="media_file", in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="media_file"),
            openapi.Parameter(name="description", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="description"),
            openapi.Parameter(name="title", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="title"),
        ],
        tags=['Media'],
        operation_summary='Add new Media',
        operation_description='Adds a new media, for authenticated users',
        responses={201: openapi.Response('response description', MediaSerializer), 401: 'bad request'},
    )
    def post(self, request, format=None):
        # Add new media
        serializer = MediaSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            media_file = request.data["media_file"]
            serializer.save(user=request.user, media_file=media_file)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class MediaRandomList(APIView):
    """Media listings views"""

    permission_classes = (IsAuthorizedToAdd,)
    parser_classes = (MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='page', type=openapi.TYPE_INTEGER, in_=openapi.IN_QUERY, description='Page number'),
            openapi.Parameter(name='author', type=openapi.TYPE_STRING, in_=openapi.IN_QUERY, description='username'),
            openapi.Parameter(name='show', type=openapi.TYPE_STRING, in_=openapi.IN_QUERY, description='show', enum=['recommended', 'featured', 'latest']),
        ],
        tags=['Media'],
        operation_summary='List Media',
        operation_description='Lists all media',
        responses={200: MediaSerializer(many=True)},
    )
    def get(self, request, format=None):

        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

        basic_query = Q(listable=True)

        # Add playlist info in the initial query
        media = Media.objects.filter(basic_query).prefetch_related('playlist_set')
        paginator = pagination_class()

        # Get playlist info before pagination and randomization
        media = media.annotate(
            playlist_friendly_token=Subquery(
                Playlist.objects.filter(media=OuterRef('pk')).values('friendly_token')[:1]
            ),
        )
        page = paginator.paginate_queryset(media, request)
        secure_random = SystemRandom()
        randomized_page = secure_random.sample(list(page), len(page))

        serializer = MediaSerializer(randomized_page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class MediaDetail(APIView):
    """
    Retrieve, update or delete a media instance.
    """

    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsUserOrEditor)
    parser_classes = (MultiPartParser, FormParser, FileUploadParser)

    def get_object(self, friendly_token, password=None):
        try:
            media = Media.objects.select_related("user").prefetch_related("encodings__profile").get(friendly_token=friendly_token)

            # this need be explicitly called, and will call
            # has_object_permission() after has_permission has succeeded
            self.check_object_permissions(self.request, media)

            if media.state == "private" and not (self.request.user == media.user or is_mediacms_editor(self.request.user)):
                if (not password) or (not media.password) or (password != media.password):
                    return Response(
                        {"detail": "media is private"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
            return media
        except PermissionDenied:
            return Response({"detail": "bad permissions"}, status=status.HTTP_401_UNAUTHORIZED)
        except BaseException:
            return Response(
                {"detail": "media file does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='friendly_token', type=openapi.TYPE_STRING, in_=openapi.IN_PATH, description='unique identifier', required=True),
        ],
        tags=['Media'],
        operation_summary='Get information for Media',
        operation_description='Get information for a media',
        responses={200: SingleMediaSerializer(), 400: 'bad request'},
    )
    def get(self, request, friendly_token, format=None):
        # Get media details
        password = request.GET.get("password") 
        media = self.get_object(friendly_token, password=password)
        if isinstance(media, Response):
            return media
        serializer = SingleMediaSerializer(media, context={"request": request})
        if media.state == "private":
            related_media = []
        else:
            related_media = show_related_media(media, request=request, limit=100)
            related_media_serializer = MediaSerializer(related_media, many=True, context={"request": request})
            related_media = related_media_serializer.data
        ret = serializer.data

        # update rattings info with user specific ratings
        # eg user has already rated for this media
        # this only affects user rating and only if enabled
        if settings.ALLOW_RATINGS and ret.get("ratings_info") and not request.user.is_anonymous:
            ret["ratings_info"] = update_user_ratings(request.user, media, ret.get("ratings_info"))

        ret["related_media"] = related_media

        first_playlist = media.playlist_set.values('friendly_token', 'id').first()
        if first_playlist:
            ret['playlist_friendly_token'] = first_playlist['friendly_token']

        
        # if admin or AnonymousUser serve without saving anything
        if request.user.is_authenticated and not request.user.is_superuser:
            playlist_category =Playlist.objects.get(friendly_token=first_playlist["friendly_token"]).category_id
            event = {"user_id":request.user.id, "media_id":media.id, "visit_time":datetime.now(), "category":playlist_category}
            store_user_events.delay(event)
            user_or_session = get_user_or_session(request)
            save_user_action.delay(user_or_session, friendly_token=friendly_token, action="watch")
        return Response(ret)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='friendly_token', type=openapi.TYPE_STRING, in_=openapi.IN_PATH, description='unique identifier', required=True),
            openapi.Parameter(name='type', type=openapi.TYPE_STRING, in_=openapi.IN_FORM, description='action to perform', enum=['encode', 'review']),
            openapi.Parameter(
                name='encoding_profiles',
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING),
                in_=openapi.IN_FORM,
                description='if action to perform is encode, need to specify list of ids of encoding profiles',
            ),
            openapi.Parameter(name='result', type=openapi.TYPE_BOOLEAN, in_=openapi.IN_FORM, description='if action is review, this is the result (True for reviewed, False for not reviewed)'),
        ],
        tags=['Media'],
        operation_summary='Run action on Media',
        operation_description='Actions for a media, for MediaCMS editors and managers',
        responses={201: 'action created', 400: 'bad request'},
        operation_id='media_manager_actions',
    )
    def post(self, request, friendly_token, format=None):
        """superuser actions
        Available only to MediaCMS editors and managers

        Action is a POST variable, review and encode are implemented
        """

        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media

        if not (is_mediacms_editor(request.user) or is_mediacms_manager(request.user)):
            return Response({"detail": "not allowed"}, status=status.HTTP_400_BAD_REQUEST)

        action = request.data.get("type")
        profiles_list = request.data.get("encoding_profiles")
        result = request.data.get("result", True)
        if action == "encode":
            # Create encoding tasks for specific profiles
            valid_profiles = []
            if profiles_list:
                if isinstance(profiles_list, list):
                    for p in profiles_list:
                        p = EncodeProfile.objects.filter(id=p).first()
                        if p:
                            valid_profiles.append(p)
                elif isinstance(profiles_list, str):
                    try:
                        p = EncodeProfile.objects.filter(id=int(profiles_list)).first()
                        valid_profiles.append(p)
                    except ValueError:
                        return Response(
                            {"detail": "encoding_profiles must be int or list of ints of valid encode profiles"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            media.encode(profiles=valid_profiles)
            return Response({"detail": "media will be encoded"}, status=status.HTTP_201_CREATED)
        elif action == "review":
            if result:
                media.is_reviewed = True
            elif result is False:
                media.is_reviewed = False
            media.save(update_fields=["is_reviewed"])
            return Response({"detail": "media reviewed set"}, status=status.HTTP_201_CREATED)
        return Response(
            {"detail": "not valid action or no action specified"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name="description", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="description"),
            openapi.Parameter(name="title", in_=openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, description="title"),
            openapi.Parameter(name="media_file", in_=openapi.IN_FORM, type=openapi.TYPE_FILE, required=False, description="media_file"),
        ],
        tags=['Media'],
        operation_summary='Update Media',
        operation_description='Update a Media, for Media uploader',
        responses={201: openapi.Response('response description', MediaSerializer), 401: 'bad request'},
    )
    def put(self, request, friendly_token, format=None):
        # Update a media object
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media
        serializer = MediaSerializer(media, data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            # no need to update the media file itself, only the metadata
            # if request.data.get('media_file'):
            #    media_file = request.data["media_file"]
            #    serializer.save(user=request.user, media_file=media_file)
            # else:
            #    serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='friendly_token', type=openapi.TYPE_STRING, in_=openapi.IN_PATH, description='unique identifier', required=True),
        ],
        tags=['Media'],
        operation_summary='Delete Media',
        operation_description='Delete a Media, for MediaCMS editors and managers',
        responses={
            204: 'no content',
        },
    )
    def delete(self, request, friendly_token, format=None):
        # Delete a media object
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MediaAnalytics(APIView):
    permission_classes = (permissions.IsAdminUser,)
    
    def get(self, request, format=None):
        # Get all media with their titles and view counts
        media_analytics = Media.objects.values('title', 'views').order_by('-views')
        
        # Format the data as a list of dictionaries
        analytics_data = [
            {
                'title': media['title'],
                'views': media['views']
            }
            for media in media_analytics
        ]
        
        return Response({
            'media_analytics': analytics_data,
            'total_media_count': len(analytics_data)
        })
    
class PlaylistAnalytics(APIView):
    permission_classes = (permissions.IsAdminUser,)
    
    def get(self, request, format=None):
        # Get all playlists with their total media views
        playlist_analytics = Playlist.objects.annotate(
            total_views=Sum('playlistmedia__media__views')
        ).values('title', 'total_views').order_by('-total_views')
        
        # Format the data as a list of dictionaries
        analytics_data = [
            {
                'playlist_title': playlist['title'],
                'total_views': playlist['total_views'] or 0  # Handle None values
            }
            for playlist in playlist_analytics
        ]
        
        return Response({
            'playlist_analytics': analytics_data,
            'total_playlists_count': len(analytics_data)
        })


class MediaActions(APIView):
    """
    Retrieve, update or delete a media action instance.
    """

    permission_classes = (permissions.AllowAny,)
    parser_classes = (JSONParser,)

    def get_object(self, friendly_token):
        try:
            media = Media.objects.select_related("user").prefetch_related("encodings__profile").get(friendly_token=friendly_token)
            if media.state == "private" and self.request.user != media.user:
                return Response({"detail": "media is private"}, status=status.HTTP_400_BAD_REQUEST)
            return media
        except PermissionDenied:
            return Response({"detail": "bad permissions"}, status=status.HTTP_400_BAD_REQUEST)
        except BaseException:
            return Response(
                {"detail": "media file does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def get(self, request, friendly_token, format=None):
        # show date and reason for each time media was reported
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media

        ret = {}
        reported = MediaAction.objects.filter(media=media, action="report")
        ret["reported"] = []
        for rep in reported:
            item = {"reported_date": rep.action_date, "reason": rep.extra_info}
            ret["reported"].append(item)

        return Response(ret, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def post(self, request, friendly_token, format=None):
        # perform like/dislike/report actions
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media

        action = request.data.get("type")
        extra = request.data.get("extra_info")
        if request.user.is_anonymous:
            # there is a list of allowed actions for
            # anonymous users, specified in settings
            if action not in settings.ALLOW_ANONYMOUS_ACTIONS:
                return Response(
                    {"detail": "action allowed on logged in users only"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if action:
            user_or_session = get_user_or_session(request)
            save_user_action.delay(
                user_or_session,
                friendly_token=media.friendly_token,
                action=action,
                extra_info=extra,
            )

            return Response({"detail": "action received"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"detail": "no action specified"}, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def delete(self, request, friendly_token, format=None):
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media

        if not request.user.is_superuser:
            return Response({"detail": "not allowed"}, status=status.HTTP_400_BAD_REQUEST)

        action = request.data.get("type")
        if action:
            if action == "report":  # delete reported actions
                MediaAction.objects.filter(media=media, action="report").delete()
                media.reported_times = 0
                media.save(update_fields=["reported_times"])
                return Response(
                    {"detail": "reset reported times counter"},
                    status=status.HTTP_201_CREATED,
                )
        else:
            return Response({"detail": "no action specified"}, status=status.HTTP_400_BAD_REQUEST)


class MediaSearch(APIView):
    """
    Retrieve results for searc
    Only GET is implemented here
    """

    parser_classes = (JSONParser,)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Search'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def get(self, request, format=None):
        params = self.request.query_params
        query = params.get("q", "").strip().lower()
        category = params.get("c", "").strip()
        tag = params.get("t", "").strip()

        ordering = params.get("ordering", "").strip()
        sort_by = params.get("sort_by", "").strip()
        media_type = params.get("media_type", "").strip()

        author = params.get("author", "").strip()
        upload_date = params.get('upload_date', '').strip()

        sort_by_options = ["title", "add_date", "edit_date", "views", "likes"]
        if sort_by not in sort_by_options:
            sort_by = "add_date"
        if ordering == "asc":
            ordering = ""
        else:
            ordering = "-"

        if media_type not in ["video", "image", "audio", "pdf"]:
            media_type = None

        if not (query or category or tag):
            ret = {}
            return Response(ret, status=status.HTTP_200_OK)

        media = Media.objects.filter(state="public", is_reviewed=True)

        if query:
            # move this processing to a prepare_query function
            query = clean_query(query)
            q_parts = [q_part.rstrip("y") for q_part in query.split() if q_part not in STOP_WORDS]
            if q_parts:
                query = SearchQuery(q_parts[0] + ":*", search_type="raw")
                for part in q_parts[1:]:
                    query &= SearchQuery(part + ":*", search_type="raw")
            else:
                query = None
        if query:
            media = media.filter(search=query)

        if tag:
            media = media.filter(tags__title=tag)

        if category:
            media = media.filter(category__title__contains=category)

        if media_type:
            media = media.filter(media_type=media_type)

        if author:
            media = media.filter(user__username=author)

        if upload_date:
            gte = None
            if upload_date == 'today':
                gte = datetime.now().date()
            if upload_date == 'this_week':
                gte = datetime.now() - timedelta(days=7)
            if upload_date == 'this_month':
                year = datetime.now().date().year
                month = datetime.now().date().month
                gte = datetime(year, month, 1)
            if upload_date == 'this_year':
                year = datetime.now().date().year
                gte = datetime(year, 1, 1)
            if gte:
                media = media.filter(add_date__gte=gte)

        media = media.order_by(f"{ordering}{sort_by}")

        if self.request.query_params.get("show", "").strip() == "titles":
            media = media.values("title")[:40]
            return Response(media, status=status.HTTP_200_OK)
        else:
            media = media.prefetch_related("user")
            if category or tag:
                pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
            else:
                # pagination_class = FastPaginationWithoutCount
                pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
            paginator = pagination_class()
            page = paginator.paginate_queryset(media, request)
            serializer = MediaSearchSerializer(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)
        
class PlaylistSearch(APIView):
    """
    Retrieve results for searc
    Only GET is implemented here
    """

    parser_classes = (JSONParser,)

    @swagger_auto_schema(
        operation_description="Search for playlists by query term",
        manual_parameters=[
            openapi.Parameter(
                name='q', 
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description='Search query term',
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Successful search",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Total number of results'),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, description='URL to next page of results', nullable=True),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING, description='URL to previous page of results', nullable=True),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Playlist ID'),
                                    'add_date': openapi.Schema(type=openapi.TYPE_STRING, format='date-time', description='Date when playlist was created'),
                                    'title': openapi.Schema(type=openapi.TYPE_STRING, description='Playlist title'),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING, description='Playlist description'),
                                    'user': openapi.Schema(type=openapi.TYPE_STRING, description='Username of playlist creator'),
                                    'media_count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Number of media items in playlist'),
                                    'url': openapi.Schema(type=openapi.TYPE_STRING, description='Frontend URL for the playlist'),
                                    'api_url': openapi.Schema(type=openapi.TYPE_STRING, description='API URL for the playlist'),
                                    'thumbnail_url': openapi.Schema(type=openapi.TYPE_STRING, description='URL to playlist thumbnail', nullable=True),
                                    'category': openapi.Schema(type=openapi.TYPE_STRING, description='Playlist category', nullable=True),
                                    'cover_image': openapi.Schema(type=openapi.TYPE_STRING, description='URL to playlist cover image', nullable=True),
                                    'friendly_token': openapi.Schema(type=openapi.TYPE_STRING, description='Unique token identifier for the playlist')
                                }
                            )
                        )
                    }
                )
            ),
            400: "Bad request"
        }
    )
    def get(self, request, format=None):
        params = self.request.query_params
        query = params.get("q", "").strip().lower()

        if not (query):
            ret = {}
            return Response(ret, status=status.HTTP_200_OK)

        # media = Media.objects.filter(state="public", is_reviewed=True)
        playlist = Playlist.objects.filter()

        if query:
            # move this processing to a prepare_query function
            query = clean_query(query)
            q_parts = [q_part.rstrip("y") for q_part in query.split() if q_part not in STOP_WORDS]
            if q_parts:
                query = SearchQuery(q_parts[0] + ":*", search_type="raw")
                for part in q_parts[1:]:
                    query &= SearchQuery(part + ":*", search_type="raw")
            else:
                query = None
        if query:
            playlist = playlist.filter(search=query)

        if self.request.query_params.get("show", "").strip() == "titles":
            playlist = playlist.values("title")[:40]
            return Response(playlist, status=status.HTTP_200_OK)
        else:
            pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
            paginator = pagination_class()
            page = paginator.paginate_queryset(playlist, request)
            serializer = PlaylistSerializer(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)


class PlaylistList(APIView):
    """Playlists listings and creation views"""

    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorizedToAdd)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
        responses={
            200: openapi.Response('response description', PlaylistSerializer(many=True)),
        },
    )
    def get(self, request, format=None):
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        playlists = Playlist.objects.filter().prefetch_related("user")

        # Add category filtering
        if "category" in self.request.query_params:
            category = self.request.query_params["category"].strip()
            playlists = playlists.filter(category__title=category)

        if "author" in self.request.query_params:
            author = self.request.query_params["author"].strip()
            playlists = playlists.filter(user__username=author)

        page = paginator.paginate_queryset(playlists, request)

        serializer = PlaylistSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def post(self, request, format=None):
        serializer = PlaylistSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PlaylistRandomList(APIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorizedToAdd)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
        responses={
            200: openapi.Response('response description', PlaylistSerializer(many=True)),
        },
    )
    def get(self, request, format=None):
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        playlists = Playlist.objects.filter().prefetch_related("user")

        # Add category filtering
        if "category" in self.request.query_params:
            category = self.request.query_params["category"].strip()
            playlists = playlists.filter(category__title=category)

        if "author" in self.request.query_params:
            author = self.request.query_params["author"].strip()
            playlists = playlists.filter(user__username=author)

        page = paginator.paginate_queryset(playlists, request)

        # Randomize the current page
        secure_random = SystemRandom()
        randomized_page = secure_random.sample(list(page), len(page))

        serializer = PlaylistSerializer(randomized_page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
    
class PlaylistRandomList(APIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorizedToAdd)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
        responses={
            200: openapi.Response('response description', PlaylistSerializer(many=True)),
        },
    )

    def get(self, request, format=None):
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        playlists = Playlist.objects.filter().prefetch_related("user")

        # Add category filtering
        if "category" in self.request.query_params:
            category = self.request.query_params["category"].strip()
            playlists = playlists.filter(category__title=category)

        if "author" in self.request.query_params:
            author = self.request.query_params["author"].strip()
            playlists = playlists.filter(user__username=author)

        user = request.user
        if user.is_authenticated:
            from django.utils import timezone
            one_week_ago = timezone.now() - timezone.timedelta(days=7)
            
            user_events = UserEvents.objects.filter(
                user_id=user.id,
                visit_time__gte=one_week_ago
            )
            
            # If user has activity, use it for recommendations
            if user_events.exists():

                # Count category occurrences
                category_counter = Counter()
                for event in user_events:
                    category_counter[event.category] += 1
                
                # Get all playlists for ordering
                all_playlists = list(playlists)
                
                # Separate playlists into two groups
                playlists_in_counter = []
                playlists_not_in_counter = []
                
                for playlist in all_playlists:
                    category = playlist.category.title if hasattr(playlist.category, 'title') else playlist.category
                    if category in category_counter:
                        playlists_in_counter.append(playlist)
                    else:
                        playlists_not_in_counter.append(playlist)
                
                # Sort playlists that have categories in counter by preference score
                # def get_preference_score(playlist):
                #     category = playlist.category.title if hasattr(playlist.category, 'title') else playlist.category
                #     return category_counter.get(category, 0)
                
                # sorted_playlists_in_counter = sorted(playlists_in_counter, key=get_preference_score, reverse=True)

                # Randomize playlists that don't have categories in counter
                secure_random = SystemRandom()
                secure_random.shuffle(playlists_in_counter)

                randomized_playlists_not_in_counter = secure_random.sample(
                    playlists_not_in_counter, len(playlists_not_in_counter)
                ) if playlists_not_in_counter else []
                
                # Combine the sorted playlists with the randomized ones
                sorted_playlists = playlists_in_counter + randomized_playlists_not_in_counter
                
                # Paginate the sorted playlists
                page_size = paginator.get_page_size(request)



                
                page_query_param = paginator.page_query_param
                page_number = request.query_params.get(page_query_param, 1)
                try:
                    page_number = int(page_number)
                except (TypeError, ValueError):
                    page_number = 1
                
                start = (page_number - 1) * page_size
                end = min(page_number * page_size, len(sorted_playlists))
                
                page = sorted_playlists[start:end]
                
                base_url = request.build_absolute_uri().split('?')[0]
                next_url = f"{base_url}?{page_query_param}={page_number+1}" if end < len(sorted_playlists) else None
                previous_url = f"{base_url}?{page_query_param}={page_number-1}" if page_number > 1 else None
                
                data = {
                    'count': len(sorted_playlists),
                    'next': next_url,
                    'previous': previous_url,
                    'results': PlaylistSerializer(page, many=True, context={"request": request}).data
                }
                
                return Response(data)
        
        # Default case: paginate and randomize as before
        page = paginator.paginate_queryset(playlists, request)
        secure_random = SystemRandom()
        randomized_page = secure_random.sample(list(page), len(page))
        serializer = PlaylistSerializer(randomized_page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
    

class PlaylistDetail(APIView):
    """Playlist related views"""

    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsUserOrEditor)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    def get_playlist(self, friendly_token):
        try:
            playlist = Playlist.objects.get(friendly_token=friendly_token)
            self.check_object_permissions(self.request, playlist)
            return playlist
        except PermissionDenied:
            return Response({"detail": "not enough permissions"}, status=status.HTTP_400_BAD_REQUEST)
        except BaseException:
            return Response(
                {"detail": "Playlist does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def get(self, request, friendly_token, format=None):
        playlist = self.get_playlist(friendly_token)
        if isinstance(playlist, Response):
            return playlist

        serializer = PlaylistDetailSerializer(playlist, context={"request": request})
        playlist_media = PlaylistMedia.objects.filter(playlist=playlist).prefetch_related("media__user")

        playlist_media = [c.media for c in playlist_media]
        playlist_media_serializer = MediaSerializer(playlist_media, many=True, context={"request": request})
        ret = serializer.data
        ret["playlist_media"] = playlist_media_serializer.data
        return Response(ret)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def post(self, request, friendly_token, format=None):
        playlist = self.get_playlist(friendly_token)
        if isinstance(playlist, Response):
            return playlist
        serializer = PlaylistDetailSerializer(playlist, data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def put(self, request, friendly_token, format=None):
        playlist = self.get_playlist(friendly_token)
        if isinstance(playlist, Response):
            return playlist
        action = request.data.get("type")
        media_friendly_token = request.data.get("media_friendly_token")
        category_name = request.data.get("category")

        if action == "set_category" and category_name:
            try:
                category = Category.objects.get(title=category_name)
                playlist.category = category
                playlist.save()
                return Response(
                    {"detail": "category updated"},
                    status=status.HTTP_200_OK
                )
            except Category.DoesNotExist:
                return Response(
                    {"detail": f"category '{category_name}' does not exist"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except ValueError:
                return Response(
                    {"detail": "invalid category value"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        ordering = 0
        if request.data.get("ordering"):
            try:
                ordering = int(request.data.get("ordering"))
            except ValueError:
                pass

        if action in ["add", "remove", "ordering"]:
            media = Media.objects.filter(friendly_token=media_friendly_token).first()
            if media:
                if action == "add":
                    media_in_playlist = PlaylistMedia.objects.filter(playlist=playlist).count()
                    if media_in_playlist >= settings.MAX_MEDIA_PER_PLAYLIST:
                        return Response(
                            {"detail": "max number of media for a Playlist reached"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    else:
                        obj, created = PlaylistMedia.objects.get_or_create(
                            playlist=playlist,
                            media=media,
                            ordering=media_in_playlist + 1,
                        )
                        obj.save()
                        return Response(
                            {"detail": "media added to Playlist"},
                            status=status.HTTP_201_CREATED,
                        )
                elif action == "remove":
                    PlaylistMedia.objects.filter(playlist=playlist, media=media).delete()
                    return Response(
                        {"detail": "media removed from Playlist"},
                        status=status.HTTP_201_CREATED,
                    )
                elif action == "ordering":
                    if ordering:
                        playlist.set_ordering(media, ordering)
                        return Response(
                            {"detail": "new ordering set"},
                            status=status.HTTP_201_CREATED,
                        )
            else:
                return Response({"detail": "media is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"detail": "invalid or not specified action"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Playlists'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def delete(self, request, friendly_token, format=None):
        playlist = self.get_playlist(friendly_token)
        if isinstance(playlist, Response):
            return playlist

        playlist.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EncodingDetail(APIView):
    """Experimental. This View is used by remote workers
    Needs heavy testing and documentation.
    """

    permission_classes = (permissions.IsAdminUser,)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(auto_schema=None)
    def post(self, request, encoding_id):
        ret = {}
        force = request.data.get("force", False)
        task_id = request.data.get("task_id", False)
        action = request.data.get("action", "")
        chunk = request.data.get("chunk", False)
        chunk_file_path = request.data.get("chunk_file_path", "")

        encoding_status = request.data.get("status", "")
        progress = request.data.get("progress", "")
        commands = request.data.get("commands", "")
        logs = request.data.get("logs", "")
        retries = request.data.get("retries", "")
        worker = request.data.get("worker", "")
        temp_file = request.data.get("temp_file", "")
        total_run_time = request.data.get("total_run_time", "")
        if action == "start":
            try:
                encoding = Encoding.objects.get(id=encoding_id)
                media = encoding.media
                profile = encoding.profile
            except BaseException:
                Encoding.objects.filter(id=encoding_id).delete()
                return Response({"status": "fail"}, status=status.HTTP_400_BAD_REQUEST)
            # TODO: break chunk True/False logic here
            if (
                Encoding.objects.filter(
                    media=media,
                    profile=profile,
                    chunk=chunk,
                    chunk_file_path=chunk_file_path,
                ).count()
                > 1  # noqa
                and force is False  # noqa
            ):
                Encoding.objects.filter(id=encoding_id).delete()
                return Response({"status": "fail"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                Encoding.objects.filter(
                    media=media,
                    profile=profile,
                    chunk=chunk,
                    chunk_file_path=chunk_file_path,
                ).exclude(id=encoding.id).delete()

            encoding.status = "running"
            if task_id:
                encoding.task_id = task_id

            encoding.save()
            if chunk:
                original_media_path = chunk_file_path
                original_media_md5sum = encoding.md5sum
                original_media_url = settings.SSL_FRONTEND_HOST + encoding.media_chunk_url
            else:
                original_media_path = media.media_file.path
                original_media_md5sum = media.md5sum
                original_media_url = settings.SSL_FRONTEND_HOST + media.original_media_url

            ret["original_media_url"] = original_media_url
            ret["original_media_path"] = original_media_path
            ret["original_media_md5sum"] = original_media_md5sum

            # generating the commands here, and will replace these with temporary
            # files created on the remote server
            tf = "TEMP_FILE_REPLACE"
            tfpass = "TEMP_FPASS_FILE_REPLACE"
            ffmpeg_commands = produce_ffmpeg_commands(
                original_media_path,
                media.media_info,
                resolution=profile.resolution,
                codec=profile.codec,
                output_filename=tf,
                pass_file=tfpass,
                chunk=chunk,
            )
            if not ffmpeg_commands:
                encoding.delete()
                return Response({"status": "fail"}, status=status.HTTP_400_BAD_REQUEST)

            ret["duration"] = media.duration
            ret["ffmpeg_commands"] = ffmpeg_commands
            ret["profile_extension"] = profile.extension
            return Response(ret, status=status.HTTP_201_CREATED)
        elif action == "update_fields":
            try:
                encoding = Encoding.objects.get(id=encoding_id)
            except BaseException:
                return Response({"status": "fail"}, status=status.HTTP_400_BAD_REQUEST)
            to_update = ["size", "update_date"]
            if encoding_status:
                encoding.status = encoding_status
                to_update.append("status")
            if progress:
                encoding.progress = progress
                to_update.append("progress")
            if logs:
                encoding.logs = logs
                to_update.append("logs")
            if commands:
                encoding.commands = commands
                to_update.append("commands")
            if task_id:
                encoding.task_id = task_id
                to_update.append("task_id")
            if total_run_time:
                encoding.total_run_time = total_run_time
                to_update.append("total_run_time")
            if worker:
                encoding.worker = worker
                to_update.append("worker")
            if temp_file:
                encoding.temp_file = temp_file
                to_update.append("temp_file")

            if retries:
                encoding.retries = retries
                to_update.append("retries")

            try:
                encoding.save(update_fields=to_update)
            except BaseException:
                return Response({"status": "fail"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"status": "success"}, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(auto_schema=None)
    def put(self, request, encoding_id, format=None):
        encoding_file = request.data["file"]
        encoding = Encoding.objects.filter(id=encoding_id).first()
        if not encoding:
            return Response(
                {"detail": "encoding does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        encoding.media_file = encoding_file
        encoding.save()
        return Response({"detail": "ok"}, status=status.HTTP_201_CREATED)


class CommentList(APIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAuthorizedToAdd)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='page', type=openapi.TYPE_INTEGER, in_=openapi.IN_QUERY, description='Page number'),
            openapi.Parameter(name='author', type=openapi.TYPE_STRING, in_=openapi.IN_QUERY, description='username'),
        ],
        tags=['Comments'],
        operation_summary='Lists Comments',
        operation_description='Paginated listing of all comments',
        responses={
            200: openapi.Response('response description', CommentSerializer(many=True)),
        },
    )
    def get(self, request, format=None):
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        comments = Comment.objects.filter()
        comments = comments.prefetch_related("user")
        comments = comments.prefetch_related("media")
        params = self.request.query_params
        if "author" in params:
            author_param = params["author"].strip()
            user_queryset = User.objects.all()
            user = get_object_or_404(user_queryset, username=author_param)
            comments = comments.filter(user=user)

        page = paginator.paginate_queryset(comments, request)

        serializer = CommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class CommentDetail(APIView):
    """Comments related views
    Listings of comments for a media (GET)
    Create comment (POST)
    Delete comment (DELETE)
    """

    permission_classes = (IsAuthorizedToAddComment,)
    parser_classes = (JSONParser, MultiPartParser, FormParser, FileUploadParser)

    def get_object(self, friendly_token):
        try:
            media = Media.objects.select_related("user").get(friendly_token=friendly_token)
            self.check_object_permissions(self.request, media)
            if media.state == "private" and self.request.user != media.user:
                return Response({"detail": "media is private"}, status=status.HTTP_400_BAD_REQUEST)
            return media
        except PermissionDenied:
            return Response({"detail": "bad permissions"}, status=status.HTTP_400_BAD_REQUEST)
        except BaseException:
            return Response(
                {"detail": "media file does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def get(self, request, friendly_token):
        # list comments for a media
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media
        comments = media.comments.filter().prefetch_related("user")
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        page = paginator.paginate_queryset(comments, request)
        serializer = CommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def delete(self, request, friendly_token, uid=None):
        """Delete a comment
        Administrators, MediaCMS editors and managers,
        media owner, and comment owners, can delete a comment
        """
        if uid:
            try:
                comment = Comment.objects.get(uid=uid)
            except BaseException:
                return Response(
                    {"detail": "comment does not exist"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (comment.user == self.request.user) or comment.media.user == self.request.user or is_mediacms_editor(self.request.user):
                comment.delete()
            else:
                return Response({"detail": "bad permissions"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Media'],
        operation_summary='to_be_written',
        operation_description='to_be_written',
    )
    def post(self, request, friendly_token):
        """Create a comment"""
        media = self.get_object(friendly_token)
        if isinstance(media, Response):
            return media

        if not media.enable_comments:
            return Response(
                {"detail": "comments not allowed here"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CommentSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user, media=media)
            if request.user != media.user:
                notify_user_on_comment(friendly_token=media.friendly_token)
            # here forward the comment to check if a user was mentioned
            if settings.ALLOW_MENTION_IN_COMMENTS:
                check_comment_for_mention(friendly_token=media.friendly_token, comment_text=serializer.data['text'])
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserActions(APIView):
    parser_classes = (JSONParser,)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='action', type=openapi.TYPE_STRING, in_=openapi.IN_PATH, description='action', required=True, enum=VALID_USER_ACTIONS),
        ],
        tags=['Users'],
        operation_summary='List user actions',
        operation_description='Lists user actions',
    )
    def get(self, request, action):
        media = []
        if action in VALID_USER_ACTIONS:
            if request.user.is_authenticated:
                media = Media.objects.select_related("user").filter(mediaactions__user=request.user, mediaactions__action=action).order_by("-mediaactions__action_date")
            elif request.session.session_key:
                media = (
                    Media.objects.select_related("user")
                    .filter(
                        mediaactions__session_key=request.session.session_key,
                        mediaactions__action=action,
                    )
                    .order_by("-mediaactions__action_date")
                )

        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        page = paginator.paginate_queryset(media, request)
        serializer = MediaSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class CategoryList(APIView):
    """List categories"""

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Categories'],
        operation_summary='Lists Categories',
        operation_description='Lists all categories',
        responses={
            200: openapi.Response('response description', CategorySerializer),
        },
    )
    def get(self, request, format=None):
        categories = Category.objects.filter().order_by("title")
        serializer = CategorySerializer(categories, many=True, context={"request": request})
        ret = serializer.data
        return Response(ret)


class TagList(APIView):
    """List tags"""

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(name='page', type=openapi.TYPE_INTEGER, in_=openapi.IN_QUERY, description='Page number'),
        ],
        tags=['Tags'],
        operation_summary='Lists Tags',
        operation_description='Paginated listing of all tags',
        responses={
            200: openapi.Response('response description', TagSerializer),
        },
    )
    def get(self, request, format=None):
        tags = Tag.objects.filter().order_by("-media_count")
        pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
        paginator = pagination_class()
        page = paginator.paginate_queryset(tags, request)
        serializer = TagSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class EncodeProfileList(APIView):
    """List encode profiles"""

    @swagger_auto_schema(
        manual_parameters=[],
        tags=['Encoding Profiles'],
        operation_summary='List Encoding Profiles',
        operation_description='Lists all encoding profiles for videos',
        responses={200: EncodeProfileSerializer(many=True)},
    )
    def get(self, request, format=None):
        profiles = EncodeProfile.objects.all()
        serializer = EncodeProfileSerializer(profiles, many=True, context={"request": request})
        return Response(serializer.data)


class TasksList(APIView):
    """List tasks"""

    swagger_schema = None

    permission_classes = (permissions.IsAdminUser,)

    def get(self, request, format=None):
        ret = list_tasks()
        return Response(ret)


class TaskDetail(APIView):
    """Cancel a task"""

    swagger_schema = None

    permission_classes = (permissions.IsAdminUser,)

    def delete(self, request, uid, format=None):
        # This is not imported!
        # revoke(uid, terminate=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

class FavoriteShowView(APIView):
    permission_classes = [permissions.IsAuthenticated]
        
    # @swagger_auto_schema(
    #     manual_parameters=[
    #         openapi.Parameter(
    #             'id',
    #             openapi.IN_QUERY,
    #             description="id to check for is_favorite or not",
    #             type=openapi.TYPE_INTEGER,
    #             required=True
    #         ),
    #         openapi.Parameter(
    #             'type',
    #             openapi.IN_QUERY,
    #             description="Type of favorite (playlist or media)",
    #             type=openapi.TYPE_STRING,
    #             enum=['playlist', 'media'],
    #             default='playlist',
    #         )
    #     ]
        
    # )
    def get(self, request,id=None):
        if id is None:
            pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
            paginator = pagination_class()
            favorite_type = get_favorite_type_param(self.request.query_params,"playlist")
            if favorite_type == "playlist":
                favorite_playlists = request.user.favorite_shows.all()
                page = paginator.paginate_queryset(favorite_playlists, request)
                serializer = FavoritePlaylistSerializer(page, many=True, context={'request': request})
                return paginator.get_paginated_response(serializer.data)
            else:
                favorite_medias = request.user.favorite_medias.all()
                page = paginator.paginate_queryset(favorite_medias, request)
                serializer = MediaSerializer(page, many=True, context={'request': request})
                return paginator.get_paginated_response(serializer.data)
        else:
            favorite_type = request.query_params.get('type')
            if not is_valid_favorite_type_param(favorite_type):
                return Response({
                    'success': False,
                    'error': 'invalid type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if favorite_type == "playlist":
                playlist = get_object_or_404(Playlist, id=id)
                is_favorite = playlist.favorites.filter(id=request.user.id).exists()
                return Response({
                    'success': True,
                    'is_favorite':is_favorite
                }, status=status.HTTP_200_OK)
            else:
                media = get_object_or_404(Media, id=id)
                is_favorite = media.favorites.filter(id=request.user.id).exists()
                return Response({
                    'success': True,
                    'is_favorite':is_favorite
                }, status=status.HTTP_200_OK)
    
    # @swagger_auto_schema(
    #     manual_parameters=[
    #         openapi.Parameter(
    #             'type',
    #             openapi.IN_QUERY,
    #             description="Type of favorite to remove (playlist or media)",
    #             type=openapi.TYPE_STRING,
    #             enum=['playlist', 'media'],
    #             required=True
    #         )
    #     ],
    # )
    def delete(self, request):
        item_id = request.query_params.get('id')
        favorite_type = request.query_params.get('type')
        
        if not item_id or not favorite_type:
            return Response({
                'success': False,
                'error': 'invalid type or missing id'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if favorite_type == 'playlist':
            item = get_object_or_404(Playlist, id=item_id)
            if item.favorites.filter(id=request.user.id).exists():
                item.favorites.remove(request.user)
        elif favorite_type == 'media':
            item = get_object_or_404(Media, id=item_id)
            if item.favorites.filter(id=request.user.id).exists():
                item.favorites.remove(request.user)
        else:
            return Response({
                'success': False,
                'error': 'invalid type'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({
            'success': True,
        }, status=status.HTTP_200_OK)

    # @swagger_auto_schema(
    #     request_body=openapi.Schema(
    #         type=openapi.TYPE_OBJECT,
    #         required=['type'],
    #         properties={
    #             'type': openapi.Schema(
    #                 type=openapi.TYPE_STRING,
    #                 enum=['media', 'playlist'],
    #                 description='Type of favorite'
    #             )
    #         }
    #     ),
    # )
    def post(self, request, id):
        favorite_type = request.data.get("type")
        if favorite_type == None or (favorite_type != "media" and favorite_type != "playlist") :
               return JsonResponse({
                'success': False,
                'error': 'invalid type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if favorite_type == "playlist":
            playlist = get_object_or_404(Playlist, id=id)        
            if playlist.favorites.filter(id=request.user.id).exists():
                return Response({
                    'success': True,
                }, status=status.HTTP_200_OK)
            else:
                playlist.favorites.add(request.user)
                
            return Response({
                'success': True,
            }, status=status.HTTP_200_OK)
        
        else:
            media = get_object_or_404(Media, id=id)        
            if media.favorites.filter(id=request.user.id).exists():
                return Response({
                    'success': True,
                }, status=status.HTTP_200_OK)
            else:
                media.favorites.add(request.user)
                
            return Response({
                'success': True,
            }, status=status.HTTP_200_OK)
            
    
def get_favorite_type_param(params:QueryDict, default:str):
    favorite_type = params.get("type", default)
    if not is_valid_favorite_type_param(favorite_type):
        favorite_type = default
    return favorite_type

def is_valid_favorite_type_param(favorite_type:str):
    if favorite_type != "media" and favorite_type != "playlist":
        return False
    return True