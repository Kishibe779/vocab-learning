import uuid
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .decorators import admin_required
from .forms import RegistrationForm, PaperForm, WordForm, RelationForm, PhraseForm, ExampleForm, StopWordForm, LexiconImportForm
from .models import Paper, Word, PaperWord, WordRelation, Phrase, UsageExample, StudyItem, ReviewLog, StopWord
from .services import analyze_paper, compare_paper, add_to_study, submit_review


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "auth/register.html", {"form": form})


@login_required
def dashboard(request):
    items = StudyItem.objects.filter(user=request.user)
    return render(request, "dashboard.html", {
        "paper_count": Paper.objects.count(), "word_count": Word.objects.count(),
        "study_count": items.count(), "due_count": items.filter(next_review_at__lte=timezone.now()).count(),
        "recent_papers": Paper.objects.order_by("-year", "-created_at")[:5],
        "recent_reviews": ReviewLog.objects.filter(study_item__user=request.user).select_related("study_item__word").order_by("-reviewed_at")[:5],
    })


@login_required
def paper_list(request):
    q = request.GET.get("q", "").strip()[:100]
    category = request.GET.get("category", "")
    papers = Paper.objects.all().order_by("-year", "-created_at")
    if q:
        papers = papers.filter(Q(title__icontains=q) | Q(source__icontains=q))
    if category in ("english1", "english2"):
        papers = papers.filter(category=category)
    return render(request, "papers/list.html", {"papers": papers, "q": q, "category": category})


def form_page(request, form, title, back_url, subtitle=""):
    return render(request, "generic_form.html", {"form": form, "title": title, "subtitle": subtitle, "back_url": back_url})


@admin_required
def paper_create(request):
    form = PaperForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        paper = form.save(commit=False)
        paper.created_by = request.user
        paper.status = "draft"
        paper.save()
        messages.success(request, "试卷已保存，可进入详情页分析。")
        return redirect("paper_detail", pk=paper.pk)
    return form_page(request, form, "录入试卷", reverse("paper_list"), "支持正文粘贴或 UTF-8 TXT；请填写真实来源，演示资料需勾选标记。")


@admin_required
def paper_edit(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    form = PaperForm(request.POST or None, request.FILES or None, instance=paper)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Paper.objects.select_for_update().get(pk=pk)
            changed = locked.content != form.cleaned_data["content"]
            saved = form.save(commit=False)
            if changed:
                saved.status = "draft"
                saved.token_count = saved.valid_count = 0
                saved.analyzed_at = None
                PaperWord.objects.filter(paper=locked).delete()
            saved.save()
        messages.success(request, "试卷已更新。正文变化后需重新分析。" if changed else "试卷已更新。")
        return redirect("paper_detail", pk=pk)
    return form_page(request, form, "编辑试卷", reverse("paper_detail", args=[pk]))


@login_required
def paper_detail(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    q = request.GET.get("q", "").strip()[:100]
    entries = PaperWord.objects.filter(paper=paper).select_related("word").order_by("-count", "word__lemma")
    if q:
        entries = entries.filter(word__lemma__icontains=q)
    return render(request, "papers/detail.html", {"paper": paper, "entries": entries, "q": q})


@admin_required
@require_POST
def paper_analyze(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    try:
        result = analyze_paper(paper, request.user)
        messages.success(request, f"分析完成：有效词出现 {result['valid']} 次，共 {result['words']} 个词条。")
    except ValidationError as exc:
        messages.error(request, "；".join(exc.messages))
    return redirect("paper_detail", pk=pk)


@login_required
def paper_compare(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    start_raw, end_raw = request.GET.get("start_year", ""), request.GET.get("end_year", "")
    try:
        start = int(start_raw) if start_raw else None
        end = int(end_raw) if end_raw else None
        if start is not None and end is not None and start > end:
            raise ValueError()
        result = compare_paper(paper, start_year=start, end_year=end)
    except (ValueError, ValidationError) as exc:
        messages.error(request, "；".join(exc.messages) if isinstance(exc, ValidationError) else "年份范围无效，请选择由早到晚的历史范围。")
        return redirect("paper_detail", pk=pk)
    return render(request, "papers/compare.html", {"paper": paper, "start_year": start_raw, "end_year": end_raw, **result})


@login_required
def word_list(request):
    q = request.GET.get("q", "").strip()[:100]
    words = Word.objects.order_by("lemma")
    if q:
        words = words.filter(Q(lemma__icontains=q) | Q(meaning__icontains=q) | Q(root__icontains=q))
    return render(request, "lexicon/list.html", {"words": words, "q": q})


@login_required
def word_detail(request, pk):
    word = get_object_or_404(Word, pk=pk)
    return render(request, "lexicon/detail.html", {
        "word": word, "relations": WordRelation.objects.filter(word=word).select_related("related_word"),
        "phrases": Phrase.objects.filter(word=word), "examples": UsageExample.objects.filter(word=word).select_related("paper", "phrase"),
        "occurrences": PaperWord.objects.filter(word=word).select_related("paper").order_by("-paper__year"),
        "study_item": StudyItem.objects.filter(user=request.user, word=word).first(),
    })


@admin_required
def word_create(request):
    form = WordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        word = form.save()
        return redirect("word_detail", pk=word.pk)
    return form_page(request, form, "新增词汇", reverse("word_list"))


@admin_required
def word_edit(request, pk):
    word = get_object_or_404(Word, pk=pk)
    form = WordForm(request.POST or None, instance=word)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "词汇资料已更新。")
        return redirect("word_detail", pk=pk)
    return form_page(request, form, "编辑词汇资料", reverse("word_detail", args=[pk]))


def related_form(request, pk, form_class, title):
    word = get_object_or_404(Word, pk=pk)
    form = form_class(request.POST or None)
    form.instance.word = word
    if isinstance(form, RelationForm):
        form.fields["related_word"].queryset = Word.objects.exclude(pk=pk)
    if isinstance(form, ExampleForm):
        form.fields["phrase"].queryset = Phrase.objects.filter(word=word)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.word = word
        try:
            obj.full_clean()
            obj.save()
            messages.success(request, "资料已保存。")
            return redirect("word_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
    return form_page(request, form, title, reverse("word_detail", args=[pk]), f"关联词汇：{word.lemma}；请注明来源。")


@admin_required
def relation_create(request, pk):
    return related_form(request, pk, RelationForm, "添加词汇关联")


@admin_required
def phrase_create(request, pk):
    return related_form(request, pk, PhraseForm, "添加典型短语")


@admin_required
def example_create(request, pk):
    return related_form(request, pk, ExampleForm, "添加用法摘抄")


@login_required
@require_POST
def study_add(request, pk):
    word = get_object_or_404(Word, pk=pk)
    source = None
    paper_id = request.POST.get("paper_id", "")
    if paper_id:
        try:
            source = get_object_or_404(Paper, pk=int(paper_id))
        except ValueError:
            messages.error(request, "试卷编号无效。")
            return redirect("word_detail", pk=pk)
        if not PaperWord.objects.filter(paper=source, word=word).exists():
            messages.error(request, "该词不属于指定试卷。")
            return redirect("word_detail", pk=pk)
    _, created = add_to_study(request.user, word, source_paper=source)
    messages.success(request, "已加入学习清单。" if created else "该词已经在你的学习清单中。")
    target = request.POST.get("return_to", "")
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return redirect(target)
    return redirect("word_detail", pk=pk)


@login_required
def study_list(request):
    q, status = request.GET.get("q", "").strip()[:100], request.GET.get("status", "")
    items = StudyItem.objects.filter(user=request.user).select_related("word", "source_paper").order_by("next_review_at", "word__lemma")
    if q:
        items = items.filter(Q(word__lemma__icontains=q) | Q(word__meaning__icontains=q))
    if status in ("new", "learning", "mastered"):
        items = items.filter(status=status)
    return render(request, "learning/list.html", {"items": items, "q": q, "status": status})


@login_required
@require_POST
def study_remove(request, pk):
    item = get_object_or_404(StudyItem, pk=pk, user=request.user)
    item.delete()
    messages.success(request, "已移出你的学习清单。")
    return redirect("study_list")


@login_required
def review_list(request):
    items = list(StudyItem.objects.filter(user=request.user, next_review_at__lte=timezone.now()).select_related("word").order_by("next_review_at")[:100])
    for item in items:
        item.review_token = str(uuid.uuid4())
    return render(request, "learning/review.html", {"items": items, "today": timezone.localdate()})


@login_required
@require_POST
def review_submit(request, pk):
    get_object_or_404(StudyItem, pk=pk, user=request.user)
    try:
        raw_token = request.POST.get("token") or request.POST.get("idempotency_key", "")
        token = uuid.UUID(raw_token)
        rating = request.POST.get("rating", "")
        submit_review(request.user, pk, rating, idempotency_key=token, note=request.POST.get("note", "")[:1000])
        messages.success(request, "复习已记录，下一次复习日期已更新。")
    except (ValueError, ValidationError) as exc:
        messages.error(request, "；".join(exc.messages) if isinstance(exc, ValidationError) else "提交标识无效，请刷新页面重试。")
    return redirect("review_list")


@login_required
def review_history(request):
    logs = ReviewLog.objects.filter(study_item__user=request.user).select_related("study_item__word").order_by("-reviewed_at")[:300]
    return render(request, "learning/history.html", {"logs": logs})


@admin_required
def stopword_list(request):
    return render(request, "management/stopwords.html", {"stopwords": StopWord.objects.order_by("text")})


@admin_required
def stopword_create(request):
    form = StopWordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        rule = form.save(commit=False)
        rule.created_by = request.user
        rule.save()
        messages.success(request, "停用规则已添加，已有试卷需重新分析才会应用。")
        return redirect("stopword_list")
    return form_page(request, form, "添加停用词", reverse("stopword_list"))


@admin_required
@require_POST
def stopword_toggle(request, pk):
    with transaction.atomic():
        rule = get_object_or_404(StopWord.objects.select_for_update(), pk=pk)
        rule.enabled = not rule.enabled
        rule.save(update_fields=["enabled", "updated_at"])
    messages.success(request, "规则已更新，已有试卷需重新分析才会应用。")
    return redirect("stopword_list")


def _save_imported(model, values):
    obj = model(**values)
    obj.full_clean()
    obj.save()
    return obj


@admin_required
def lexicon_import(request):
    form = LexiconImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        rows = form.cleaned_data["file"]
        try:
            with transaction.atomic():
                for row in rows:
                    word, _ = Word.objects.get_or_create(lemma=row["lemma"])
                    for field in ("meaning", "pos", "root", "notes", "source"):
                        if field in row:
                            setattr(word, field, row[field])
                    word.full_clean()
                    word.save()
                for row in rows:
                    word = Word.objects.get(lemma=row["lemma"])
                    for data in row.get("relations", []):
                        if not isinstance(data, dict) or set(data) - {"lemma", "type", "explanation", "source"}:
                            raise ValidationError("relations 字段格式无效。")
                        related = Word.objects.filter(lemma=data.get("lemma")).first()
                        if not related or related == word or data.get("type") not in ("root", "synonym", "antonym"):
                            raise ValidationError("关联词必须存在、不能为自身，类型须为 root/synonym/antonym。")
                        relation, _ = WordRelation.objects.get_or_create(word=word, related_word=related, relation_type=data["type"])
                        relation.explanation = data.get("explanation", "")
                        relation.source = data.get("source", row["source"])
                        relation.full_clean()
                        relation.save()
                    for data in row.get("phrases", []):
                        if not isinstance(data, dict) or set(data) - {"text", "meaning", "example", "translation", "source"}:
                            raise ValidationError("phrases 字段格式无效。")
                        values = {**data, "word": word, "source": data.get("source", row["source"])}
                        obj = Phrase(**values)
                        existing = Phrase.objects.filter(word=word, text=obj.text).first()
                        if existing:
                            # 在已有实例上校验候选字段，不保存，保持合法重复资料幂等。
                            obj = existing
                            for field, value in values.items():
                                setattr(obj, field, value)
                        obj.full_clean()
                        if existing is None:
                            obj.save()
                    for data in row.get("examples", []):
                        if not isinstance(data, dict) or set(data) - {"text", "translation", "source"}:
                            raise ValidationError("examples 字段格式无效。")
                        values = {**data, "word": word, "kind": "word", "source": data.get("source", row["source"])}
                        obj = UsageExample(**values)
                        obj.full_clean()
                        if not UsageExample.objects.filter(word=word, text=obj.text).exists():
                            obj.save()
            messages.success(request, f"成功导入 {len(rows)} 个词条及关联资料。")
            return redirect("word_list")
        except (ValidationError, IntegrityError, TypeError, ValueError) as exc:
            form.add_error(None, "；".join(exc.messages) if isinstance(exc, ValidationError) else "资料格式或约束有误，已回滚整批导入。")
    return render(request, "lexicon/import.html", {"form": form})
