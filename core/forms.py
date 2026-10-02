import json
import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Paper, Word, WordRelation, Phrase, UsageExample, StopWord


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "display_name", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = "student"
        user.is_staff = False
        if commit:
            user.save()
        return user


class PaperForm(forms.ModelForm):
    text_file = forms.FileField(label="或上传 TXT 文件", required=False, help_text="仅支持 UTF-8 文本，最大 1 MB；粘贴正文与上传文件二选一。")

    class Meta:
        model = Paper
        fields = ("title", "year", "category", "source", "is_demo", "content")
        widgets = {"content": forms.Textarea(attrs={"rows": 14}), "year": forms.NumberInput(attrs={"min": 1900, "max": 2100})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].required = False

    def clean_year(self):
        year = self.cleaned_data["year"]
        if not 1900 <= year <= 2100:
            raise forms.ValidationError("年份必须在 1900—2100 之间。")
        return year

    def clean(self):
        data = super().clean()
        uploaded = data.get("text_file")
        text = (data.get("content") or "").strip()
        if uploaded:
            if text:
                raise forms.ValidationError("请只选择粘贴正文或上传 TXT 文件中的一种。")
            if not uploaded.name.lower().endswith(".txt"):
                raise forms.ValidationError("只支持 .txt 文本文件。")
            if uploaded.size > 1024 * 1024:
                raise forms.ValidationError("文件不能超过 1 MB。")
            try:
                text = uploaded.read().decode("utf-8-sig").strip()
            except UnicodeDecodeError:
                raise forms.ValidationError("文件不是 UTF-8 编码，请转换后再上传。")
        if not text or not re.search(r"[A-Za-z]{2}", text):
            raise forms.ValidationError("正文必须包含可分析的英文文本。")
        if len(text) > 200_000 or "\x00" in text:
            raise forms.ValidationError("正文最多 20 万字符，且不能包含空字符。")
        data["content"] = text
        return data


class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = ("lemma", "meaning", "pos", "root", "notes", "source")
        widgets = {"meaning": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    def clean_lemma(self):
        text = self.cleaned_data["lemma"].strip().lower()
        if not re.fullmatch(r"[a-z]+(?:[-'][a-z]+)*", text):
            raise forms.ValidationError("请输入单个英文词，可包含词内连字符或撇号。")
        if Word.objects.filter(lemma=text).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("该词汇已存在，请编辑已有词条。")
        return text


class RelationForm(forms.ModelForm):
    class Meta:
        model = WordRelation
        fields = ("related_word", "relation_type", "explanation", "source")
        widgets = {"explanation": forms.Textarea(attrs={"rows": 3})}


class PhraseForm(forms.ModelForm):
    class Meta:
        model = Phrase
        fields = ("text", "meaning", "example", "translation", "source")
        widgets = {"example": forms.Textarea(attrs={"rows": 3})}


class ExampleForm(forms.ModelForm):
    class Meta:
        model = UsageExample
        fields = ("phrase", "paper", "text", "translation", "source", "kind")
        widgets = {"text": forms.Textarea(attrs={"rows": 4}), "translation": forms.Textarea(attrs={"rows": 3})}


class StopWordForm(forms.ModelForm):
    class Meta:
        model = StopWord
        fields = ("text", "reason", "enabled")

    def clean_text(self):
        text = self.cleaned_data["text"].strip().lower()
        if not re.fullmatch(r"[a-z]+(?:'[a-z]+)?", text):
            raise forms.ValidationError("请输入单个英文停用词。")
        if StopWord.objects.filter(text=text).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("该规则已存在。")
        return text


class LexiconImportForm(forms.Form):
    file = forms.FileField(label="词汇资料 JSON 文件", help_text="UTF-8 编码，最大 1 MB。字段格式见下方说明。")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".json") or uploaded.size > 1024 * 1024:
            raise forms.ValidationError("请上传不超过 1 MB 的 .json 文件。")
        try:
            rows = json.loads(uploaded.read().decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError):
            raise forms.ValidationError("文件必须是有效 UTF-8 JSON。")
        if not isinstance(rows, list) or not rows or len(rows) > 1000:
            raise forms.ValidationError("顶层必须是包含 1—1000 个词条的数组。")
        allowed = {"lemma", "meaning", "pos", "root", "notes", "source", "relations", "phrases", "examples"}
        for row in rows:
            if not isinstance(row, dict) or set(row) - allowed:
                raise forms.ValidationError("词条包含未知字段或不是对象。")
            lemma = row.get("lemma", "")
            if not isinstance(lemma, str) or len(lemma) > 100 or not re.fullmatch(r"[a-z]+(?:[-'][a-z]+)*", lemma):
                raise forms.ValidationError("lemma 必须是小写英文词，最长 100 字符。")
            if not isinstance(row.get("source"), str) or not row["source"].strip():
                raise forms.ValidationError("每个词条必须填写 source，说明资料来源。")
            for key in ("meaning", "pos", "root", "notes", "source"):
                if key in row and (not isinstance(row[key], str) or len(row[key]) > 5000):
                    raise forms.ValidationError(f"{key} 必须是合理长度的字符串。")
            for key in ("relations", "phrases", "examples"):
                if key in row and (not isinstance(row[key], list) or len(row[key]) > 100):
                    raise forms.ValidationError(f"{key} 必须是最多 100 条的数组。")
        return rows
