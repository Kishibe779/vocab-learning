import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


english_word_validator = RegexValidator(
    regex=r"^[a-z]+(?:[-'][a-z]+)*$",
    message="请输入小写英文单词，可包含英文撇号或连字符。",
)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        STUDENT = "student", "学生"

    role = models.CharField("角色", max_length=10, choices=Role.choices, default=Role.STUDENT)
    display_name = models.CharField("显示名称", max_length=80, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        ordering = ["username", "pk"]

    def save(self, *args, **kwargs):
        self.is_staff = bool(self.is_superuser or self.role == self.Role.ADMIN)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_staff"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.username


class Paper(models.Model):
    class Category(models.TextChoices):
        ENGLISH1 = "english1", "英语一"
        ENGLISH2 = "english2", "英语二"

    class Status(models.TextChoices):
        DRAFT = "draft", "待分析"
        ANALYZED = "analyzed", "已分析"

    title = models.CharField("试卷标题", max_length=200)
    year = models.PositiveSmallIntegerField(
        "年份", validators=[MinValueValidator(1900), MaxValueValidator(2200)]
    )
    category = models.CharField("试卷类别", max_length=10, choices=Category.choices)
    content = models.TextField("英文正文")
    source = models.CharField("来源说明", max_length=255, blank=True)
    is_demo = models.BooleanField("原创演示资料", default=False)
    status = models.CharField("分析状态", max_length=12, choices=Status.choices, default=Status.DRAFT)
    token_count = models.PositiveIntegerField("英文词次总数", default=0)
    valid_count = models.PositiveIntegerField("有效词次总数", default=0)
    analyzed_at = models.DateTimeField("分析时间", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建人", on_delete=models.SET_NULL,
        related_name="created_papers", null=True, blank=True,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "试卷"
        verbose_name_plural = "试卷"
        ordering = ["-year", "category", "pk"]
        indexes = [models.Index(fields=["category", "status", "year"], name="paper_history_idx")]
        constraints = [
            models.CheckConstraint(condition=models.Q(valid_count__lte=models.F("token_count")), name="paper_valid_lte_tokens"),
        ]

    def __str__(self):
        return f"{self.year} · {self.get_category_display()} · {self.title}"


class Word(models.Model):
    lemma = models.CharField("基本词形", max_length=100, unique=True, validators=[english_word_validator])
    meaning = models.TextField("中文释义", blank=True)
    pos = models.CharField("词性", max_length=80, blank=True)
    root = models.CharField("词根或同源基础词", max_length=100, blank=True)
    notes = models.TextField("学习说明", blank=True)
    source = models.CharField("词典来源", max_length=255, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "单词"
        verbose_name_plural = "单词"
        ordering = ["lemma", "pk"]

    def __str__(self):
        return self.lemma


class PaperWord(models.Model):
    paper = models.ForeignKey(Paper, verbose_name="试卷", on_delete=models.CASCADE, related_name="paper_words")
    word = models.ForeignKey(Word, verbose_name="单词", on_delete=models.CASCADE, related_name="paper_words")
    count = models.PositiveIntegerField("出现次数", validators=[MinValueValidator(1)])
    forms = models.JSONField("原词形及出现次数", default=dict)
    contexts = models.JSONField("原文上下文（最多三条）", default=list)
    total_tokens = models.PositiveIntegerField("所属正文英文词次", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "试卷词频"
        verbose_name_plural = "试卷词频"
        ordering = ["-count", "word__lemma", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["paper", "word"], name="unique_paper_word"),
            models.CheckConstraint(condition=models.Q(count__gte=1), name="paperword_positive_count"),
        ]

    def __str__(self):
        return f"{self.paper.year} · {self.word.lemma} × {self.count}"


class WordRelation(models.Model):
    class RelationType(models.TextChoices):
        ROOT = "root", "同源词"
        SYNONYM = "synonym", "近义词"
        ANTONYM = "antonym", "反义词"

    word = models.ForeignKey(Word, verbose_name="单词", on_delete=models.PROTECT, related_name="relations")
    related_word = models.ForeignKey(Word, verbose_name="关联单词", on_delete=models.PROTECT, related_name="incoming_relations")
    relation_type = models.CharField("关联类型", max_length=12, choices=RelationType.choices)
    explanation = models.TextField("关联说明", blank=True)
    source = models.CharField("资料来源", max_length=255, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "词汇关联"
        verbose_name_plural = "词汇关联"
        ordering = ["word__lemma", "relation_type", "related_word__lemma", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["word", "related_word", "relation_type"], name="unique_word_relation"),
            models.CheckConstraint(condition=~models.Q(word=models.F("related_word")), name="relation_different_words"),
        ]

    def __str__(self):
        return f"{self.word} — {self.get_relation_type_display()} — {self.related_word}"


class Phrase(models.Model):
    word = models.ForeignKey(Word, verbose_name="核心单词", on_delete=models.CASCADE, related_name="phrases")
    text = models.CharField("短语", max_length=200)
    meaning = models.CharField("中文释义", max_length=255)
    example = models.TextField("原创英文例句", blank=True)
    translation = models.TextField("例句译文", blank=True)
    source = models.CharField("资料来源", max_length=255, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "常用短语"
        verbose_name_plural = "常用短语"
        ordering = ["word__lemma", "text", "pk"]
        constraints = [models.UniqueConstraint(fields=["word", "text"], name="unique_word_phrase")]

    def __str__(self):
        return self.text


class UsageExample(models.Model):
    class Kind(models.TextChoices):
        WORD = "word", "单词例句"
        PHRASE = "phrase", "短语例句"

    word = models.ForeignKey(Word, verbose_name="单词", on_delete=models.CASCADE, related_name="examples")
    phrase = models.ForeignKey(Phrase, verbose_name="短语", on_delete=models.SET_NULL, related_name="examples", null=True, blank=True)
    paper = models.ForeignKey(Paper, verbose_name="原文试卷", on_delete=models.SET_NULL, related_name="examples", null=True, blank=True)
    text = models.TextField("英文例句")
    translation = models.TextField("中文译文", blank=True)
    source = models.CharField("资料来源", max_length=255, blank=True)
    kind = models.CharField("例句类型", max_length=10, choices=Kind.choices, default=Kind.WORD)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "用法例句"
        verbose_name_plural = "用法例句"
        ordering = ["word__lemma", "kind", "pk"]

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.phrase_id and self.phrase.word_id != self.word_id:
            raise ValidationError({"phrase": "短语与例句必须属于同一个单词。"})
        if self.phrase_id and self.kind != self.Kind.PHRASE:
            raise ValidationError({"kind": "指定短语的例句应选择短语例句类型。"})

    def __str__(self):
        return f"{self.word} · {self.text[:60]}"


class StopWord(models.Model):
    text = models.CharField("停用词", max_length=100, unique=True, validators=[english_word_validator])
    reason = models.CharField("排除原因", max_length=255, blank=True)
    enabled = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建人", on_delete=models.SET_NULL,
        related_name="created_stop_words", null=True, blank=True,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "停用词"
        verbose_name_plural = "停用词"
        ordering = ["text", "pk"]

    def __str__(self):
        return self.text


class StudyItem(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "未学习"
        LEARNING = "learning", "学习中"
        MASTERED = "mastered", "已掌握"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="学习者", on_delete=models.CASCADE, related_name="study_items")
    word = models.ForeignKey(Word, verbose_name="单词", on_delete=models.PROTECT, related_name="study_items")
    source_paper = models.ForeignKey(Paper, verbose_name="来源试卷", on_delete=models.SET_NULL, related_name="study_items", null=True, blank=True)
    status = models.CharField("学习状态", max_length=12, choices=Status.choices, default=Status.NEW)
    level = models.PositiveSmallIntegerField("记忆等级", default=0, validators=[MaxValueValidator(5)])
    next_review_at = models.DateTimeField("下次复习时间", default=timezone.now)
    added_at = models.DateTimeField("加入时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "个人生词"
        verbose_name_plural = "个人生词"
        ordering = ["next_review_at", "word__lemma", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["user", "word"], name="unique_user_study_word"),
            models.CheckConstraint(condition=models.Q(level__gte=0, level__lte=5), name="study_level_between_0_5"),
        ]
        indexes = [models.Index(fields=["user", "next_review_at"], name="study_due_idx")]

    def __str__(self):
        return f"{self.user} · {self.word} · {self.get_status_display()}"


class ReviewLog(models.Model):
    class Rating(models.TextChoices):
        AGAIN = "again", "忘记"
        HARD = "hard", "困难"
        GOOD = "good", "记住"
        EASY = "easy", "轻松"

    study_item = models.ForeignKey(StudyItem, verbose_name="学习项目", on_delete=models.CASCADE, related_name="review_logs")
    rating = models.CharField("复习评分", max_length=8, choices=Rating.choices)
    previous_level = models.PositiveSmallIntegerField("原记忆等级", validators=[MaxValueValidator(5)])
    new_level = models.PositiveSmallIntegerField("新记忆等级", validators=[MaxValueValidator(5)])
    next_review_at = models.DateTimeField("本次安排的下次复习时间")
    reviewed_at = models.DateTimeField("复习时间", default=timezone.now)
    note = models.TextField("复习备注", blank=True)
    idempotency_key = models.UUIDField("重复提交识别码", unique=True, default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = "复习记录"
        verbose_name_plural = "复习记录"
        ordering = ["-reviewed_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(previous_level__lte=5, new_level__lte=5), name="review_levels_lte_5"),
        ]

    def __str__(self):
        return f"{self.study_item.word} · {self.get_rating_display()} · {self.reviewed_at:%Y-%m-%d %H:%M}"
