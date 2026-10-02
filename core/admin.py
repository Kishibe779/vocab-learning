from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Paper, PaperWord, Phrase, ReviewLog, StopWord, StudyItem, UsageExample,
    User, Word, WordRelation,
)
from .services import is_admin


class AdministratorOnlyMixin:
    def has_module_permission(self, request):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin(request.user)

    def has_add_permission(self, request):
        return is_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_admin(request.user)


@admin.register(User)
class UserAdmin(AdministratorOnlyMixin, DjangoUserAdmin):
    list_display = ("username", "display_name", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("username", "display_name", "email")
    readonly_fields = ("is_staff", "last_login", "date_joined", "created_at", "updated_at")
    fieldsets = (
        ("账号", {"fields": ("username", "password")}),
        ("个人资料", {"fields": ("display_name", "first_name", "last_name", "email")}),
        ("角色及权限", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("时间信息", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        ("创建账号", {"classes": ("wide",), "fields": ("username", "display_name", "role", "password1", "password2", "usable_password")}),
    )
    ordering = ("username", "pk")

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        protected = {"is_superuser", "groups", "user_permissions"}
        return tuple(
            (title, {**options, "fields": tuple(field for field in options["fields"] if field not in protected)})
            for title, options in fieldsets
        )

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and (obj.pk == request.user.pk or (obj.is_superuser and not request.user.is_superuser)):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(Paper)
class PaperAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("title", "year", "category", "is_demo", "status", "token_count", "valid_count", "analyzed_at")
    list_filter = ("category", "status", "is_demo", "year")
    search_fields = ("title", "content", "source")
    readonly_fields = ("status", "token_count", "valid_count", "analyzed_at", "created_at", "updated_at")
    autocomplete_fields = ("created_by",)
    list_select_related = ("created_by",)
    ordering = ("-year", "category", "pk")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change and "content" in form.changed_data:
            obj.status = Paper.Status.DRAFT
            obj.token_count = obj.valid_count = 0
            obj.analyzed_at = None
        super().save_model(request, obj, form, change)
        if change and "content" in form.changed_data:
            obj.paper_words.all().delete()


@admin.register(Word)
class WordAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("lemma", "meaning", "pos", "root", "source", "updated_at")
    search_fields = ("lemma", "meaning", "root", "notes")
    list_filter = ("pos", "source")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PaperWord)
class PaperWordAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("paper", "word", "count", "total_tokens", "updated_at")
    list_filter = ("paper__category", "paper__year")
    search_fields = ("word__lemma", "paper__title")
    list_select_related = ("paper", "word")
    readonly_fields = ("paper", "word", "count", "forms", "contexts", "total_tokens", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WordRelation)
class WordRelationAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("word", "related_word", "relation_type", "source", "updated_at")
    list_filter = ("relation_type",)
    search_fields = ("word__lemma", "related_word__lemma", "explanation")
    autocomplete_fields = ("word", "related_word")
    list_select_related = ("word", "related_word")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Phrase)
class PhraseAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("text", "word", "meaning", "source", "updated_at")
    search_fields = ("text", "meaning", "word__lemma")
    autocomplete_fields = ("word",)
    list_select_related = ("word",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UsageExample)
class UsageExampleAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("word", "kind", "short_text", "phrase", "paper", "source")
    list_filter = ("kind",)
    search_fields = ("word__lemma", "text", "translation", "source")
    autocomplete_fields = ("word", "phrase", "paper")
    list_select_related = ("word", "phrase", "paper")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="英文例句")
    def short_text(self, obj):
        return obj.text[:90]


@admin.register(StopWord)
class StopWordAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("text", "reason", "enabled", "created_by", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("text", "reason")
    autocomplete_fields = ("created_by",)
    list_select_related = ("created_by",)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        obj.text = obj.text.strip().lower()
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StudyItem)
class StudyItemAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("user", "word", "status", "level", "next_review_at", "source_paper")
    list_filter = ("status", "level")
    search_fields = ("user__username", "user__display_name", "word__lemma")
    list_select_related = ("user", "word", "source_paper")
    readonly_fields = ("user", "word", "source_paper", "status", "level", "next_review_at", "added_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReviewLog)
class ReviewLogAdmin(AdministratorOnlyMixin, admin.ModelAdmin):
    list_display = ("study_item", "rating", "previous_level", "new_level", "reviewed_at", "next_review_at")
    list_filter = ("rating", "reviewed_at")
    search_fields = ("study_item__user__username", "study_item__word__lemma", "note")
    list_select_related = ("study_item__user", "study_item__word")
    readonly_fields = (
        "study_item", "rating", "previous_level", "new_level", "next_review_at", "reviewed_at", "note", "idempotency_key",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
