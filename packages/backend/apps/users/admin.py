from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.token_blacklist import admin as token_admin, models as token_models
from social_django.models import UserSocialAuth
from apps.multitenancy.models import TenantMembership
from . import tasks
from . import models
from .services.account_reclaim import reclaim_unconfirmed_account
from .services.password_policy import validate_password
from .services.deletion import delete_account, deletion_blockers
from .services.otp import validate_otp
from .exceptions import OTPVerificationFailure, OTPAttemptLimitExceeded
from apps.sso.services import passkey_management

admin.site.unregister(token_models.OutstandingToken)


@admin.register(token_models.OutstandingToken)
class OutstandingTokenAdmin(token_admin.OutstandingTokenAdmin):
    def has_delete_permission(self, *args, **kwargs):
        return True


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = models.User
        fields = ("email",)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        if password2:
            validate_password(password2, models.User(email=self.cleaned_data.get('email', '')))
        return password2

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = models.User
        fields = ("email", "password", "is_active", "is_superuser")

    def clean_password(self):
        return self.initial["password"]


class UserProfileInline(admin.StackedInline):
    model = models.UserProfile


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ("__str__", "created", "last_login", "is_confirmed", "otp_enabled", "linked_providers")
    list_filter = ("is_superuser", "is_confirmed", "otp_enabled")
    fieldsets = (
        (None, {"fields": ("email", "password", "is_active")}),
        (
            "Account status",
            {"fields": ("is_confirmed", "otp_enabled", "linked_providers")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "groups",
                    "is_superuser",
                )
            },
        ),
    )
    readonly_fields = ("is_confirmed", "otp_enabled", "linked_providers")
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    search_fields = ("email",)
    ordering = ("created",)
    filter_horizontal = ()
    inlines = [
        UserProfileInline,
    ]
    actions = ["export_user_data", "reclaim_unconfirmed_account"]
    delete_confirmation_template = 'admin/users/user/delete_confirmation.html'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def delete_view(self, request, object_id, extra_context=None):
        context = dict(extra_context or {})
        if request.method == 'POST':
            obj = self.get_object(request, object_id)
            try:
                if obj is None or not self.has_delete_permission(request, obj):
                    raise PermissionDenied('permission_denied')
                if deletion_blockers(obj):
                    raise ValidationError('Transfer ownership or delete the organizations first.')
                token = passkey_management.password_grant(
                    request.user, {'action': 'account_delete', 'password': request.POST.get('password', '')}
                )
                request.META['HTTP_X_PASSKEY_AUTHORIZATION'] = token
                if request.user.otp_enabled and request.user.otp_verified:
                    validate_otp(request.user, request.POST.get('otp_token', ''), request)
                    request._account_deletion_otp = (str(request.user.pk), request.user.otp_last_used_code_hash)
                return super().delete_view(request, object_id, extra_context=context)
            except (PermissionDenied, ValidationError, OTPVerificationFailure, OTPAttemptLimitExceeded) as exc:
                if isinstance(exc, ValidationError) and isinstance(exc.detail, dict):
                    context['deletion_error'] = ' '.join(
                        str(message) for messages in exc.detail.values() for message in messages
                    )
                else:
                    context['deletion_error'] = str(exc)
                method, post = request.method, request.POST
                request.method, request.POST = 'GET', request.POST.copy()
                request.POST.clear()
                try:
                    return super().delete_view(request, object_id, extra_context=context)
                finally:
                    request.method, request.POST = method, post
        return super().delete_view(request, object_id, extra_context=context)

    def delete_model(self, request, obj):
        delete_account(obj.pk, request, via_admin=True)

    def delete_queryset(self, request, queryset):
        raise PermissionDenied('Delete accounts individually with fresh authentication.')

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Django's default bulk action bypasses per-account fresh confirmation.
        actions.pop('delete_selected', None)
        if not request.user.is_superuser:
            actions.pop("reclaim_unconfirmed_account", None)
        return actions

    def linked_providers(self, obj):
        if not obj.pk:
            return "-"
        providers = UserSocialAuth.objects.filter(user=obj).values_list("provider", flat=True)
        return ", ".join(sorted(providers)) or "-"

    linked_providers.short_description = _("Linked social providers")

    def export_user_data(self, request, queryset):
        data = {
            "user_ids": [str(user_id) for user_id in queryset.values_list("id", flat=True)],
            "admin_email": request.user.email,
        }
        tasks.export_user_data.apply_async((data["user_ids"], data["admin_email"]))

        self.message_user(request, "Exported user data will be sent to you via e-mail", messages.SUCCESS)

    export_user_data.short_description = _("Export selected %(verbose_name_plural)s")

    def reclaim_unconfirmed_account(self, request, queryset):
        """Strip credentials from unconfirmed accounts so a verified owner can reclaim them.

        See apps.users.services.account_reclaim for what this does and why it
        requires an out-of-band ownership check before use - this action does
        not perform that check itself, it only enforces is_confirmed=False and
        superuser-only access.
        """
        ineligible = list(queryset.filter(is_confirmed=True))

        if request.POST.get("post") and not ineligible:
            reclaimed = 0
            for user in queryset:
                try:
                    reclaim_unconfirmed_account(user, request.user)
                except (PermissionDenied, ValidationError) as exc:
                    self.message_user(request, f"{user.email}: {exc}", messages.ERROR)
                    continue
                reclaimed += 1
            if reclaimed:
                self.message_user(
                    request,
                    f"Reclaimed {reclaimed} account(s). A password-reset email was sent to each.",
                    messages.SUCCESS,
                )
            return None

        # Reclaim only strips credentials; it deliberately leaves org memberships for
        # manual review (they may have been created by whoever preregistered the
        # account) - so support needs to see them here, before confirming, not after.
        eligible = list(queryset)
        memberships = TenantMembership.objects.filter(user__in=eligible, is_accepted=True).select_related("tenant")
        memberships_by_user = {}
        for membership in memberships:
            memberships_by_user.setdefault(membership.user_id, []).append(membership)
        for user in eligible:
            user.reclaim_memberships = memberships_by_user.get(user.pk, [])

        context = {
            **self.admin_site.each_context(request),
            "title": _("Reclaim unconfirmed account"),
            "queryset": eligible,
            "ineligible": ineligible,
            "opts": self.model._meta,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, "admin/users/user/reclaim_confirmation.html", context)

    reclaim_unconfirmed_account.short_description = _("Reclaim unconfirmed account (support use only)")


@admin.register(models.SecurityEmailOutbox)
class SecurityEmailOutboxAdmin(admin.ModelAdmin):
    list_display = ('kind', 'created_at', 'attempts', 'sent_at', 'failed_at', 'cancelled_at', 'last_error')
    list_filter = ('kind', 'failed_at', 'sent_at', 'cancelled_at')
    readonly_fields = [field.name for field in models.SecurityEmailOutbox._meta.fields]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.AccountDeletion)
class AccountDeletionAdmin(SecurityEmailOutboxAdmin):
    list_display = ('account_id', 'actor_id', 'deleted_at')
    list_filter = ()
    readonly_fields = [field.name for field in models.AccountDeletion._meta.fields]
