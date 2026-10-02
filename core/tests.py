"""Acceptance tests: synthetic fixtures only; Django's isolated test database.

Case metadata is consumed by the acceptance evidence collector. No production
fixtures, account credentials, external services, browser, or downloads are used.
"""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import PaperForm
from .models import (Paper, PaperWord, Phrase, ReviewLog, StopWord, StudyItem,
                     UsageExample, User, Word, WordRelation)
from .services import (add_to_study, analyze_paper, compare_paper,
                       lexical_analysis, submit_review)


ACCEPTANCE_CASES = []


def acceptance_case(number, feature, steps, expected, group):
    """Metadata only: ordinary Django/unittest methods retain real assertions."""
    def decorate(method):
        ACCEPTANCE_CASES.append({
            "id": number, "feature": feature, "steps_input": steps,
            "expected": expected, "tester_group": group,
            "method": method.__name__,
        })
        return method
    return decorate


@override_settings(ANALYSIS_ENGINE="rule", ALLOWED_HOSTS=["testserver", "localhost"])
class AcceptanceBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Unusable-password users are synthetic test identities, not real accounts.
        cls.admin_user = User.objects.create_user(username="fixture_admin", role="admin")
        cls.student = User.objects.create_user(username="fixture_student", role="student")
        cls.other = User.objects.create_user(username="fixture_other", role="student")

    def paper(self, content="Learn learning. Research works.", year=2025,
              category="english1", is_demo=False, analyzed=False, **extra):
        paper = Paper.objects.create(title="Synthetic acceptance text", year=year,
                                     category=category, content=content, is_demo=is_demo,
                                     created_by=self.admin_user, **extra)
        if analyzed:
            analyze_paper(paper, self.admin_user)
        return paper

    def admin_login(self):
        self.client.force_login(self.admin_user)

    def student_login(self):
        self.client.force_login(self.student)

    def upload_json(self, rows, name="fixture.json"):
        return SimpleUploadedFile(name, json.dumps(rows, ensure_ascii=False).encode("utf-8"),
                                  content_type="application/json")

    def due_item(self, user=None, lemma="learn", level=0):
        word, _ = Word.objects.get_or_create(lemma=lemma)
        return StudyItem.objects.create(user=user or self.student, word=word, level=level,
                                        next_review_at=timezone.now() - timedelta(minutes=1))


class LexicalAcceptanceTests(AcceptanceBase):
    @acceptance_case("TC01", "规则词形归一", "分析 studies studied studying running stopped cities watches；规则引擎", "study=3，run/stop/city/watch各1；规则引擎声明非完整NLP", "A")
    def test_tc01_rule_inflections(self):
        result = lexical_analysis("studies studied studying running stopped cities watches")
        counts = {r["lemma"]: r["count"] for r in result["records"]}
        self.assertEqual(counts, {"study": 3, "run": 1, "stop": 1, "city": 1, "watch": 1})
        self.assertIn("非完整NLP", result["engine"])

    @acceptance_case("TC02", "不规则词形", "分析 went gone children women wrote written better best", "go/child/woman/write/good归并且次数正确", "A")
    def test_tc02_irregular_forms(self):
        result = lexical_analysis("went gone children women wrote written better best")
        self.assertEqual({r["lemma"]: r["count"] for r in result["records"]},
                         {"go": 2, "child": 1, "woman": 1, "write": 2, "good": 2})

    @acceptance_case("TC03", "高风险词尾保护", "分析 analysis business news unknowns high-quality student's", "不误截断analysis/business/news/unknowns；连字符保留；所有格student", "A")
    def test_tc03_conservative_suffixes(self):
        result = lexical_analysis("analysis business news unknowns high-quality student's")
        self.assertEqual({r["lemma"] for r in result["records"]},
                         {"analysis", "business", "news", "unknowns", "high-quality", "student"})

    @acceptance_case("TC04", "默认停用与缩写", "分析 The and is was I'M we're don't can't learn Z", "tokens=10，valid=1，仅learn；单字符与缩写排除", "A")
    def test_tc04_default_stops_and_contractions(self):
        result = lexical_analysis("The and is was I'M we're don't can't learn Z")
        self.assertEqual(result["tokens"], 10)
        self.assertEqual(result["valid"], 1)
        self.assertEqual([r["lemma"] for r in result["records"]], ["learn"])

    @acceptance_case("TC05", "大小写/原词形/词频", "分析 Learn LEARN learning. Research research.", "tokens=valid=5；learn=3 research=2；保留原大小写forms", "A")
    def test_tc05_case_forms_frequency(self):
        result = lexical_analysis("Learn LEARN learning. Research research.")
        records = {r["lemma"]: r for r in result["records"]}
        self.assertEqual((result["tokens"], result["valid"], result["words"]), (5, 5, 2))
        self.assertEqual(records["learn"]["count"], 3)
        self.assertEqual(records["learn"]["forms"], {"Learn": 1, "LEARN": 1, "learning": 1})
        self.assertEqual(records["research"]["count"], 2)

    @acceptance_case("TC06", "自定义停用归一", "stop_words=[' Studies ','RESEARCH']；分析study studies studying research learn", "停用词及其基本词形均排除，仅learn", "A")
    def test_tc06_custom_stop_normalization(self):
        result = lexical_analysis("study studies studying research learn", [" Studies ", "RESEARCH"])
        self.assertEqual([r["lemma"] for r in result["records"]], ["learn"])

    @acceptance_case("TC07", "上下文去重上限", "同一词learn跨四个不同句子，并重复第一句；分析600字符长句", "上下文不重复最多3条；每条<=500字符", "A")
    def test_tc07_context_limits(self):
        result = lexical_analysis("Learn first. Learn second. Learn third. Learn fourth. Learn first.")
        context = next(r for r in result["records"] if r["lemma"] == "learn")["contexts"]
        self.assertEqual(len(context), 3)
        self.assertEqual(len(set(context)), 3)
        result = lexical_analysis("learn " * 120)
        self.assertTrue(all(len(c) <= 500 for r in result["records"] for c in r["contexts"]))

    @acceptance_case("TC08", "分析输入异常", "传入bytes、纯中文、200001字符、101字符词形、无效Unicode", "各项ValidationError，不发生写库", "A")
    def test_tc08_lexical_invalid_inputs(self):
        for text in (b"learn", "只有中文123", "x" * 200001, "x" * 101, "learn \ud800"):
            with self.subTest(kind=type(text).__name__, length=len(text)):
                with self.assertRaises(ValidationError):
                    lexical_analysis(text)
        self.assertEqual(Word.objects.count(), 0)

    @acceptance_case("TC09", "分析持久化", "管理员分析含learn/learning和the的已保存试卷", "Paper状态analyzed、时间/计数正确；PaperWord计数forms/context/total_tokens持久化", "A")
    def test_tc09_analysis_persistence(self):
        paper = self.paper("Learn learning the.")
        result = analyze_paper(paper, self.admin_user)
        paper.refresh_from_db()
        entry = PaperWord.objects.get(paper=paper)
        self.assertEqual(result["words"], 1)
        self.assertEqual((paper.token_count, paper.valid_count, paper.status), (3, 2, "analyzed"))
        self.assertIsNotNone(paper.analyzed_at)
        self.assertEqual((entry.word.lemma, entry.count, entry.total_tokens), ("learn", 2, 3))
        self.assertEqual(entry.forms, {"Learn": 1, "learning": 1})
        self.assertEqual(entry.contexts, ["Learn learning the."])

    @acceptance_case("TC10", "重复分析去重", "同一试卷连续分析两次；词库已有人工释义", "词库和PaperWord不重复；计数不累加；已有释义保留", "A")
    def test_tc10_repeat_analysis_deduplicates(self):
        word = Word.objects.create(lemma="learn", meaning="人工释义", source="人工来源")
        paper = self.paper("Learn learning.")
        analyze_paper(paper, self.admin_user)
        analyze_paper(paper, self.admin_user)
        word.refresh_from_db()
        self.assertEqual((Word.objects.count(), PaperWord.objects.count()), (1, 1))
        self.assertEqual(PaperWord.objects.get(paper=paper).count, 2)
        self.assertEqual((word.meaning, word.source), ("人工释义", "人工来源"))

    @acceptance_case("TC11", "分析权限", "学生、匿名、停用管理员调用analyze_paper；学生POST分析接口", "服务PermissionDenied/HTTP403，无词频写入", "A")
    def test_tc11_analysis_permission(self):
        paper = self.paper()
        inactive = User.objects.create_user(username="fixture_inactive", role="admin", is_active=False)
        for user in (self.student, AnonymousUser(), inactive):
            with self.subTest(role=type(user).__name__):
                with self.assertRaises(PermissionDenied):
                    analyze_paper(paper, user)
        self.student_login()
        self.assertEqual(self.client.post(reverse("paper_analyze", args=[paper.pk])).status_code, 403)
        self.assertFalse(PaperWord.objects.exists())

    @acceptance_case("TC12", "停用启停生效", "启用study停用规则分析study/learn；关闭规则再分析", "启用只learn；关闭后study恢复；重新分析替换结果", "A")
    def test_tc12_stopword_enabled_disabled(self):
        rule = StopWord.objects.create(text="study", enabled=True, created_by=self.admin_user)
        paper = self.paper("study studies learn")
        analyze_paper(paper, self.admin_user)
        self.assertEqual(list(paper.paper_words.values_list("word__lemma", flat=True)), ["learn"])
        rule.enabled = False
        rule.save()
        analyze_paper(paper, self.admin_user)
        self.assertEqual(set(paper.paper_words.values_list("word__lemma", flat=True)), {"study", "learn"})

    @acceptance_case("TC13", "分析失败不破坏原结果", "已分析试卷输入失效正文；另用过期对象与数据库已修改正文比较", "两种情况均ValidationError，原状态和PaperWord完整保留", "A")
    def test_tc13_analysis_failure_preserves_previous(self):
        paper = self.paper("Learn learning.", analyzed=True)
        before = list(paper.paper_words.values("word_id", "count", "forms"))
        paper.content = "纯中文"
        with self.assertRaises(ValidationError):
            analyze_paper(paper, self.admin_user)
        paper.refresh_from_db()
        Paper.objects.filter(pk=paper.pk).update(content="Research changed.")
        with self.assertRaises(ValidationError):
            analyze_paper(paper, self.admin_user)
        self.assertEqual(list(paper.paper_words.values("word_id", "count", "forms")), before)
        self.assertEqual(Paper.objects.get(pk=paper.pk).status, "analyzed")


class HistoryAcceptanceTests(AcceptanceBase):
    @acceptance_case("TC14", "严格历史年份/类别/演示标记", "当前2025英语一非演示；加入2024同类、2025同年、2026未来、英语二、演示、未分析等资料", "仅2024同类同标记已分析入基线；learn历史频2；research新词", "A")
    def test_tc14_strict_history_scope(self):
        eligible = self.paper("Learn learning.", year=2024, analyzed=True)
        current = self.paper("Learn research.", analyzed=True)
        for year, category, demo, analyzed in ((2025, "english1", False, True),
                                             (2026, "english1", False, True),
                                             (2023, "english2", False, True),
                                             (2022, "english1", True, True),
                                             (2021, "english1", False, False)):
            self.paper("Research research.", year=year, category=category, is_demo=demo, analyzed=analyzed)
        result = compare_paper(current)
        self.assertEqual(list(result["history_papers"].values_list("pk", flat=True)), [eligible.pk])
        self.assertEqual({r["entry"].word.lemma: (r["historical_count"], r["is_new"]) for r in result["rows"]},
                         {"learn": (2, False), "research": (0, True)})

    @acceptance_case("TC15", "演示历史分离", "当前演示资料；历史同年类别内分别演示/非演示", "只比较历史演示资料，非演示不混入", "A")
    def test_tc15_demo_scope(self):
        eligible = self.paper("learn", year=2024, is_demo=True, analyzed=True)
        self.paper("research", year=2023, analyzed=True)
        current = self.paper("learn research", is_demo=True, analyzed=True)
        result = compare_paper(current)
        self.assertEqual(list(result["history_papers"].values_list("pk", flat=True)), [eligible.pk])
        self.assertEqual({e.word.lemma for e in result["new_words"]}, {"research"})

    @acceptance_case("TC16", "历史范围/汇总频率", "2021/2022/2023历史learn次数1/2/3，当前2025；范围2022至2023", "包含两个边界年；history_count=2，learn历史合计5", "A")
    def test_tc16_history_range_aggregation(self):
        for year, content in ((2021, "learn"), (2022, "learn learn"), (2023, "learn learn learn")):
            self.paper(content, year=year, analyzed=True)
        current = self.paper("learn", analyzed=True)
        result = compare_paper(current, "2022", "2023")
        self.assertEqual(result["history_count"], 2)
        self.assertEqual(result["rows"][0]["historical_count"], 5)
        self.assertEqual(list(result["history_papers"].values_list("year", flat=True)), [2022, 2023])

    @acceptance_case("TC17", "无效历史年份", "起始大于结束、非整数、布尔、浮点输入；Client非法年份GET", "服务ValidationError；页面重定向至详情，不报500", "A")
    def test_tc17_invalid_history_years(self):
        paper = self.paper(analyzed=True)
        for start, end in ((2024, 2020), ("abc", None), (True, None), (2020.5, None)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValidationError):
                    compare_paper(paper, start, end)
        self.student_login()
        response = self.client.get(reverse("paper_compare", args=[paper.pk]), {"start_year": "abc"})
        self.assertRedirects(response, reverse("paper_detail", args=[paper.pk]))

    @acceptance_case("TC18", "未分析拒绝对比", "保存draft资料后服务对比及Client GET对比", "服务ValidationError；页面重定向；无伪造统计", "A")
    def test_tc18_draft_comparison_rejected(self):
        paper = self.paper()
        with self.assertRaises(ValidationError):
            compare_paper(paper)
        self.student_login()
        self.assertRedirects(self.client.get(reverse("paper_compare", args=[paper.pk])),
                             reverse("paper_detail", args=[paper.pk]))
        self.assertFalse(PaperWord.objects.exists())

    @acceptance_case("TC19", "无历史基线", "仅当前已分析资料且有learn/research；Client查看对比", "history_count=0，历史频0，新词2；明确无基线不证明普遍新词", "A")
    def test_tc19_no_history_baseline(self):
        paper = self.paper("learn research", analyzed=True)
        result = compare_paper(paper)
        self.assertEqual((result["history_count"], result["new_count"]), (0, 2))
        self.assertTrue(all(r["historical_count"] == 0 for r in result["rows"]))
        self.student_login()
        response = self.client.get(reverse("paper_compare", args=[paper.pk]))
        self.assertContains(response, "历史词频为零不能证明它是普遍意义上的新词")


class AuthorizationAcceptanceTests(AcceptanceBase):
    @acceptance_case("TC20", "注册不能提权", "匿名注册，额外传role=admin/is_staff/is_superuser/groups等权限字段（随机合成密码，不记录）", "注册成功，但role=student、staff/superuser均False、无权限组", "B")
    def test_tc20_registration_no_privilege_escalation(self):
        synthetic_password = "Generated-test-" + uuid.uuid4().hex + "!"
        response = self.client.post(reverse("register"), {
            "username": "fixture_registered", "display_name": "合成注册测试", "email": "fixture@example.invalid",
            "password1": synthetic_password, "password2": synthetic_password,
            "role": "admin", "is_staff": "on", "is_superuser": "on", "groups": "1", "user_permissions": "1",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="fixture_registered")
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.groups.count(), 0)
        self.assertEqual(user.user_permissions.count(), 0)

    @acceptance_case("TC21", "匿名登录保护", "匿名GET资料/词库/生词/复习/历史/管理页面；POST加入生词", "均302转登录，未生成学习项目", "B")
    def test_tc21_anonymous_login_required(self):
        word = Word.objects.create(lemma="learn")
        for name in ("dashboard", "paper_list", "word_list", "study_list", "review_list", "review_history", "stopword_list"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))
        self.assertEqual(self.client.post(reverse("study_add", args=[word.pk])).status_code, 302)
        self.assertFalse(StudyItem.objects.exists())

    @acceptance_case("TC22", "学生管理接口拒绝", "学生访问/POST试卷新增编辑分析、词汇新增编辑关联短语例句、导入、停用新增启停及Django后台", "管理接口403；后台转登录；无新增词条或停用改动", "B")
    def test_tc22_student_management_denied(self):
        paper = self.paper()
        word = Word.objects.create(lemma="learn")
        rule = StopWord.objects.create(text="research")
        self.student_login()
        targets = [("paper_create", []), ("paper_edit", [paper.pk]), ("paper_analyze", [paper.pk]),
                   ("word_create", []), ("word_edit", [word.pk]), ("relation_create", [word.pk]),
                   ("phrase_create", [word.pk]), ("example_create", [word.pk]),
                   ("lexicon_import", []), ("stopword_list", []), ("stopword_create", []),
                   ("stopword_toggle", [rule.pk])]
        for name, args in targets:
            for method in (self.client.get, self.client.post):
                with self.subTest(route=name, method=method.__name__):
                    self.assertEqual(method(reverse(name, args=args)).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:core_word_changelist")).status_code, 302)
        self.assertEqual(Word.objects.count(), 1)
        rule.refresh_from_db()
        self.assertTrue(rule.enabled)

    @acceptance_case("TC23", "管理员词库CRUD", "管理员Client新增LEARN、读取详情、编辑释义；Django后台删除无引用词汇", "词元小写learn，数据读改成功，后台确认删除后词条不存在", "B")
    def test_tc23_admin_word_crud(self):
        self.admin_login()
        response = self.client.post(reverse("word_create"), {"lemma": "LEARN", "meaning": "学习", "source": "合成测试"})
        word = Word.objects.get(lemma="learn")
        self.assertRedirects(response, reverse("word_detail", args=[word.pk]))
        self.assertContains(self.client.get(reverse("word_detail", args=[word.pk])), "学习")
        response = self.client.post(reverse("word_edit", args=[word.pk]),
                                    {"lemma": "learn", "meaning": "修改释义", "source": "合成测试"})
        self.assertEqual(response.status_code, 302)
        word.refresh_from_db()
        self.assertEqual(word.meaning, "修改释义")
        self.assertEqual(self.client.get(reverse("admin:core_word_delete", args=[word.pk])).status_code, 200)
        response = self.client.post(reverse("admin:core_word_delete", args=[word.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Word.objects.filter(pk=word.pk).exists())

    @acceptance_case("TC24", "管理员试卷CRUD", "Client新增试卷/查看/编辑标题；Django后台确认删除", "创建人管理员，内容保存，标题更新，删除成功", "B")
    def test_tc24_admin_paper_crud(self):
        self.admin_login()
        data = {"title": "合成CRUD", "year": 2025, "category": "english1", "source": "原创测试", "content": "Learn research."}
        response = self.client.post(reverse("paper_create"), data)
        paper = Paper.objects.get(title="合成CRUD")
        self.assertRedirects(response, reverse("paper_detail", args=[paper.pk]))
        self.assertEqual(paper.created_by_id, self.admin_user.pk)
        data["title"] = "更新CRUD"
        self.assertEqual(self.client.post(reverse("paper_edit", args=[paper.pk]), data).status_code, 302)
        paper.refresh_from_db()
        self.assertEqual(paper.title, "更新CRUD")
        self.assertEqual(self.client.post(reverse("admin:core_paper_delete", args=[paper.pk]), {"post": "yes"}).status_code, 302)
        self.assertFalse(Paper.objects.filter(pk=paper.pk).exists())

    @acceptance_case("TC25", "编辑正文使分析失效", "先分析；仅改标题，再改正文", "标题修改保留统计；正文修改置draft、清零/清分析时间并删除旧PaperWord", "B")
    def test_tc25_content_edit_invalidates_analysis(self):
        paper = self.paper("learn learn", analyzed=True)
        self.admin_login()
        data = {"title": "新标题", "year": paper.year, "category": paper.category,
                "source": "合成测试", "content": paper.content}
        self.client.post(reverse("paper_edit", args=[paper.pk]), data)
        paper.refresh_from_db()
        self.assertEqual(paper.status, "analyzed")
        self.assertEqual(paper.paper_words.count(), 1)
        data["content"] = "Research changes."
        self.assertEqual(self.client.post(reverse("paper_edit", args=[paper.pk]), data).status_code, 302)
        paper.refresh_from_db()
        self.assertEqual((paper.status, paper.token_count, paper.valid_count), ("draft", 0, 0))
        self.assertIsNone(paper.analyzed_at)
        self.assertEqual(paper.paper_words.count(), 0)

    @acceptance_case("TC26", "管理员关联/短语/例句与停用管理", "新增词关联、短语、对应短语例句；创建大写STUDY停用词并关闭", "关联/短语/例句保存；停用小写study且创建人为管理员；关闭成功", "B")
    def test_tc26_admin_related_material_and_stopwords(self):
        learn = Word.objects.create(lemma="learn")
        study = Word.objects.create(lemma="study")
        self.admin_login()
        response = self.client.post(reverse("relation_create", args=[learn.pk]),
                                    {"related_word": study.pk, "relation_type": "synonym", "source": "合成来源"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(WordRelation.objects.filter(word=learn, related_word=study).exists())
        self.assertEqual(self.client.post(reverse("phrase_create", args=[learn.pk]),
                                         {"text": "learn from", "meaning": "向某人学习", "source": "合成来源"}).status_code, 302)
        phrase = Phrase.objects.get(word=learn)
        self.assertEqual(self.client.post(reverse("example_create", args=[learn.pk]),
                                         {"phrase": phrase.pk, "text": "Learn from others.", "kind": "phrase", "source": "合成来源"}).status_code, 302)
        self.assertEqual(UsageExample.objects.get(word=learn).phrase_id, phrase.pk)
        self.assertEqual(self.client.post(reverse("stopword_create"),
                                         {"text": "STUDY", "reason": "合成规则", "enabled": "on"}).status_code, 302)
        rule = StopWord.objects.get(text="study")
        self.assertEqual(rule.created_by_id, self.admin_user.pk)
        self.assertEqual(self.client.post(reverse("stopword_toggle", args=[rule.pk])).status_code, 302)
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)

    @acceptance_case("TC27", "只读HTTP方法保护", "管理员GET分析/停用切换；学生GET加入/移除/提交复习", "所有变更接口405，不写入和删除", "B")
    def test_tc27_mutations_require_post(self):
        paper = self.paper()
        rule = StopWord.objects.create(text="learn")
        item = self.due_item()
        self.admin_login()
        for name, pk in (("paper_analyze", paper.pk), ("stopword_toggle", rule.pk)):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 405)
        self.student_login()
        for name, pk in (("study_add", item.word_id), ("study_remove", item.pk), ("review_submit", item.pk)):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 405)
        self.assertTrue(StudyItem.objects.filter(pk=item.pk).exists())
        self.assertFalse(ReviewLog.objects.exists())

    @acceptance_case("TC28", "关联与例句一致性校验", "提交自身关联；将其他单词短语用于当前词例句", "表单HTTP200带错误；无WordRelation/UsageExample写入", "B")
    def test_tc28_related_material_validation(self):
        learn = Word.objects.create(lemma="learn")
        study = Word.objects.create(lemma="study")
        phrase = Phrase.objects.create(word=study, text="study hard", meaning="努力学习")
        self.admin_login()
        response = self.client.post(reverse("relation_create", args=[learn.pk]),
                                    {"related_word": learn.pk, "relation_type": "synonym"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        response = self.client.post(reverse("example_create", args=[learn.pk]),
                                    {"phrase": phrase.pk, "kind": "phrase", "text": "Synthetic example."})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(WordRelation.objects.exists())
        self.assertFalse(UsageExample.objects.exists())


class PersonalStudyAcceptanceTests(AcceptanceBase):
    @acceptance_case("TC29", "个人学习去重", "同用户同词add_to_study两次；另一个用户同词添加", "前者created=True/False且同一pk；第二用户独立项目，共2条", "C")
    def test_tc29_personal_deduplication(self):
        word = Word.objects.create(lemma="learn")
        first, created = add_to_study(self.student, word)
        again, created_again = add_to_study(self.student, word)
        other, other_created = add_to_study(self.other, word)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertTrue(other_created)
        self.assertEqual(first.pk, again.pk)
        self.assertNotEqual(first.pk, other.pk)
        self.assertEqual(StudyItem.objects.count(), 2)

    @acceptance_case("TC30", "加入来源验证及去重", "词learn属于paper1不属于paper2；先错来源再正确两次POST", "错来源不加入；正确来源保存paper1且重复不增行", "C")
    def test_tc30_study_source_validation(self):
        paper1 = self.paper("learn", analyzed=True)
        paper2 = self.paper("research", analyzed=True)
        word = Word.objects.get(lemma="learn")
        self.student_login()
        self.client.post(reverse("study_add", args=[word.pk]), {"paper_id": paper2.pk})
        self.assertFalse(StudyItem.objects.exists())
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("study_add", args=[word.pk]), {"paper_id": paper1.pk}).status_code, 302)
        self.assertEqual(StudyItem.objects.count(), 1)
        self.assertEqual(StudyItem.objects.get().source_paper_id, paper1.pk)

    @acceptance_case("TC31", "个人列表/详情/仪表盘隔离", "用户甲learn且有review，用户乙research且有review；登录甲读取列表/仪表盘/词详情", "只含甲项目和甲日志；乙词详情study_item为None", "C")
    def test_tc31_personal_read_isolation(self):
        mine = self.due_item(lemma="learn")
        other = self.due_item(user=self.other, lemma="research")
        submit_review(self.student, mine.pk, "good")
        submit_review(self.other, other.pk, "good")
        self.student_login()
        response = self.client.get(reverse("study_list"))
        self.assertEqual([i.pk for i in response.context["items"]], [mine.pk])
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["study_count"], 1)
        self.assertEqual([log.study_item_id for log in response.context["recent_reviews"]], [mine.pk])
        response = self.client.get(reverse("word_detail", args=[other.word_id]))
        self.assertIsNone(response.context["study_item"])

    @acceptance_case("TC32", "个人项目移除与越权拒绝", "甲POST移除乙项目再移除本人已有日志项目", "越权404乙项目保留；本人移除成功且其日志级联删除", "C")
    def test_tc32_remove_ownership_and_cascade(self):
        mine = self.due_item(lemma="learn")
        other = self.due_item(user=self.other, lemma="research")
        submit_review(self.student, mine.pk, "good")
        self.student_login()
        self.assertEqual(self.client.post(reverse("study_remove", args=[other.pk])).status_code, 404)
        self.assertTrue(StudyItem.objects.filter(pk=other.pk).exists())
        self.assertRedirects(self.client.post(reverse("study_remove", args=[mine.pk])), reverse("study_list"))
        self.assertFalse(StudyItem.objects.filter(pk=mine.pk).exists())
        self.assertFalse(ReviewLog.objects.exists())
        self.assertTrue(Word.objects.filter(pk=mine.word_id).exists())

    @acceptance_case("TC33", "到期列表隔离与UUID", "甲到期与未来项目、乙到期项目；登录甲GET复习", "只返回甲到期项目；review_token为合法UUID；due_count=1", "C")
    def test_tc33_due_list_isolation_and_uuid(self):
        due = self.due_item(lemma="learn")
        future = self.due_item(lemma="study")
        future.next_review_at = timezone.now() + timedelta(days=1)
        future.save()
        self.due_item(user=self.other, lemma="research")
        self.student_login()
        response = self.client.get(reverse("review_list"))
        self.assertEqual([i.pk for i in response.context["items"]], [due.pk])
        self.assertIsInstance(uuid.UUID(response.context["items"][0].review_token), uuid.UUID)
        self.assertEqual(self.client.get(reverse("dashboard")).context["due_count"], 1)

    @acceptance_case("TC34", "未到期拒绝复习", "未来1天学习项目submit_review及Client POST有效UUID/good", "服务ValidationError；接口返回提示；等级/到期不变且无日志", "C")
    def test_tc34_not_due_review_rejected(self):
        item = self.due_item()
        item.next_review_at = timezone.now() + timedelta(days=1)
        item.save()
        before = item.next_review_at
        with self.assertRaises(ValidationError):
            submit_review(self.student, item.pk, "good")
        self.student_login()
        response = self.client.post(reverse("review_submit", args=[item.pk]), {"rating": "good", "token": str(uuid.uuid4())}, follow=True)
        self.assertContains(response, "尚未到复习时间")
        item.refresh_from_db()
        self.assertEqual((item.level, item.next_review_at), (0, before))
        self.assertFalse(ReviewLog.objects.exists())

    @acceptance_case("TC35", "复习四种评分/上限与日志", "固定当前时间；again前4、hard前3、good前0/4、easy前3/5逐项复习", "等级0/2/1/5/5/5；间隔10分钟/1/1/30/30/30天；level>=4掌握；日志前后等级/时间一致", "C")
    def test_tc35_review_rating_schedule_and_logs(self):
        now = timezone.now()
        cases = [("again", 4, 0, timedelta(minutes=10)), ("hard", 3, 2, timedelta(days=1)),
                 ("good", 0, 1, timedelta(days=1)), ("good", 4, 5, timedelta(days=30)),
                 ("easy", 3, 5, timedelta(days=30)), ("easy", 5, 5, timedelta(days=30))]
        for index, (rating, old, new, interval) in enumerate(cases):
            with self.subTest(rating=rating, previous_level=old):
                item = self.due_item(lemma=["learn", "study", "research", "work", "run", "teach"][index], level=old)
                with patch("core.services.timezone.now", return_value=now):
                    log = submit_review(self.student, item.pk, rating, note="合成复习备注")
                item.refresh_from_db()
                self.assertEqual((log.previous_level, log.new_level, log.rating), (old, new, rating))
                self.assertEqual((item.level, item.next_review_at), (new, now + interval))
                self.assertEqual(log.next_review_at, item.next_review_at)
                self.assertEqual(log.reviewed_at, now)
                self.assertEqual(log.note, "合成复习备注")
                self.assertEqual(item.status, "mastered" if new >= 4 else "learning")
        self.assertEqual(ReviewLog.objects.count(), 6)

    @acceptance_case("TC36", "无效评分/UUID/编号/备注", "invalid评分、无效UUID、负数/布尔/浮点编号、过长/非文本note；接口缺少token", "全部拒绝，不改变项目且不生成日志；接口提示提交标识无效", "C")
    def test_tc36_invalid_review_inputs(self):
        item = self.due_item()
        cases = [(item.pk, "invalid", str(uuid.uuid4()), ""), (item.pk, "good", "invalid-uuid", ""),
                 (-1, "good", None, ""), (True, "good", None, ""), (1.2, "good", None, ""),
                 (item.pk, "good", None, "x" * 2001), (item.pk, "good", None, 7)]
        for item_id, rating, key, note in cases:
            with self.subTest(item_id=item_id, rating=rating, note_type=type(note).__name__):
                with self.assertRaises(ValidationError):
                    submit_review(self.student, item_id, rating, key, note)
        self.student_login()
        response = self.client.post(reverse("review_submit", args=[item.pk]), {"rating": "good"}, follow=True)
        self.assertContains(response, "提交标识无效")
        item.refresh_from_db()
        self.assertEqual(item.level, 0)
        self.assertFalse(ReviewLog.objects.exists())

    @acceptance_case("TC37", "复习UUID重试幂等", "到期项目以相同UUID/good连续提交两次；第二次虽未来到期", "返回同一ReviewLog；仅一次等级推进且日志1条", "C")
    def test_tc37_review_idempotency(self):
        item = self.due_item()
        key = uuid.uuid4()
        first = submit_review(self.student, item.pk, "good", key)
        again = submit_review(self.student, item.pk, "good", key)
        self.assertEqual(first.pk, again.pk)
        item.refresh_from_db()
        self.assertEqual(item.level, 1)
        self.assertEqual(ReviewLog.objects.count(), 1)

    @acceptance_case("TC38", "UUID绑定用户/项目/评分", "已使用UUID重新用于不同评分、另一个本人项目、另用户项目", "均ValidationError；不生成新日志、不推进其他项目", "C")
    def test_tc38_uuid_bound_to_request(self):
        item = self.due_item()
        another = self.due_item(lemma="study")
        other = self.due_item(user=self.other, lemma="research")
        key = uuid.uuid4()
        submit_review(self.student, item.pk, "good", key)
        for user, target, rating in ((self.student, item.pk, "easy"), (self.student, another.pk, "good"), (self.other, other.pk, "good")):
            with self.subTest(target=target, rating=rating):
                with self.assertRaises(ValidationError):
                    submit_review(user, target, rating, key)
        self.assertEqual(ReviewLog.objects.count(), 1)
        another.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((another.level, other.level), (0, 0))

    @acceptance_case("TC39", "复习越权", "甲通过服务及Client提交乙的学习项目", "服务PermissionDenied/接口404；乙项目等级不变，无日志", "C")
    def test_tc39_review_other_owner_denied(self):
        other = self.due_item(user=self.other)
        with self.assertRaises(PermissionDenied):
            submit_review(self.student, other.pk, "good")
        self.student_login()
        response = self.client.post(reverse("review_submit", args=[other.pk]), {"rating": "good", "token": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 404)
        other.refresh_from_db()
        self.assertEqual(other.level, 0)
        self.assertFalse(ReviewLog.objects.exists())

    @acceptance_case("TC40", "个人复习日志隔离", "甲learn、乙research各复习一条；登录甲读取历史", "history只包含甲日志和词条，乙备注不出现在HTML", "C")
    def test_tc40_history_isolation(self):
        mine = self.due_item()
        other = self.due_item(user=self.other, lemma="research")
        own = submit_review(self.student, mine.pk, "good", note="甲的合成备注")
        submit_review(self.other, other.pk, "good", note="乙的私有合成备注")
        self.student_login()
        response = self.client.get(reverse("review_history"))
        self.assertEqual([log.pk for log in response.context["logs"]], [own.pk])
        self.assertContains(response, "甲的合成备注")
        self.assertNotContains(response, "乙的私有合成备注")

    @acceptance_case("TC41", "加入学习回跳安全", "return_to外部URL、//外部、反斜杠路径及合法/study/", "危险回跳都回词详情；合法本站路径正常跳转", "C")
    def test_tc41_safe_return_redirect(self):
        word = Word.objects.create(lemma="learn")
        self.student_login()
        for target in ("https://example.invalid/", "//example.invalid/", "/\\example.invalid/"):
            response = self.client.post(reverse("study_add", args=[word.pk]), {"return_to": target})
            self.assertEqual(response.url, reverse("word_detail", args=[word.pk]))
        response = self.client.post(reverse("study_add", args=[word.pk]), {"return_to": reverse("study_list")})
        self.assertEqual(response.url, reverse("study_list"))
        self.assertEqual(StudyItem.objects.count(), 1)


class ImportAndSecurityAcceptanceTests(AcceptanceBase):
    @acceptance_case("TC42", "UTF-8 TXT成功上传", "管理员上传UTF-8 BOM的fixture.TXT，正文留空", "创建draft资料，去BOM/首尾空白，文本保存且无磁盘媒体文件", "B")
    def test_tc42_txt_utf8_bom_success(self):
        self.admin_login()
        upload = SimpleUploadedFile("fixture.TXT", b"\xef\xbb\xbf  Learn research.  ", content_type="text/plain")
        response = self.client.post(reverse("paper_create"), {"title": "TXT合成测试", "year": 2025,
            "category": "english1", "source": "合成文件", "content": "", "text_file": upload})
        self.assertEqual(response.status_code, 302)
        paper = Paper.objects.get(title="TXT合成测试")
        self.assertEqual((paper.content, paper.status), ("Learn research.", "draft"))

    @acceptance_case("TC43", "TXT异常与正文互斥", "上传pdf扩展、非UTF8、空文件、中文、含NUL、超1MB、超20万字符、同时粘贴正文", "各自表单错误HTTP200，不创建试卷", "B")
    def test_tc43_txt_invalid_uploads(self):
        self.admin_login()
        cases = [("bad.pdf", b"Learn", ""), ("bad.txt", b"\xff\xfe", ""),
                 ("empty.txt", b"", ""), ("chinese.txt", "只有中文".encode("utf-8"), ""),
                 ("nul.txt", b"Learn\x00", ""), ("large.txt", b"x" * (1024 * 1024 + 1), ""),
                 ("textlimit.txt", b"learn " * 33334, ""), ("both.txt", b"Research", "Learn")]
        for name, contents, pasted in cases:
            with self.subTest(upload=name):
                response = self.client.post(reverse("paper_create"), {"title": "异常上传", "year": 2025,
                    "category": "english1", "content": pasted,
                    "text_file": SimpleUploadedFile(name, contents, content_type="text/plain")})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(Paper.objects.count(), 0)

    @acceptance_case("TC44", "试卷年份/类别边界", "表单传1899/2101年份、非法category及合法1900/2100", "非法拒绝，两个年份边界合法", "B")
    def test_tc44_paper_form_year_category(self):
        data = {"title": "合成边界", "year": 2025, "category": "english1", "content": "Learn."}
        for year in (1899, 2101):
            self.assertFalse(PaperForm({**data, "year": year}).is_valid())
        self.assertFalse(PaperForm({**data, "category": "invalid"}).is_valid())
        for year in (1900, 2100):
            self.assertTrue(PaperForm({**data, "year": year}).is_valid())

    @acceptance_case("TC45", "JSON批量完整导入", "导入learn/study，含前向同义关联、短语、例句与来源", "词条2条、关联/短语/例句各1条，释义/来源/关联目标持久化", "B")
    def test_tc45_json_import_success(self):
        self.admin_login()
        rows = [{"lemma": "learn", "meaning": "学习", "pos": "v.", "source": "合成验收",
                 "relations": [{"lemma": "study", "type": "synonym", "explanation": "合成关联"}],
                 "phrases": [{"text": "learn from", "meaning": "向某人学习", "example": "Learn from others."}],
                 "examples": [{"text": "We learn together.", "translation": "一起学习"}]},
                {"lemma": "study", "meaning": "学习", "source": "合成验收"}]
        response = self.client.post(reverse("lexicon_import"), {"file": self.upload_json(rows)})
        self.assertRedirects(response, reverse("word_list"))
        self.assertEqual((Word.objects.count(), WordRelation.objects.count(), Phrase.objects.count(), UsageExample.objects.count()), (2, 1, 1, 1))
        word = Word.objects.get(lemma="learn")
        self.assertEqual((word.meaning, word.source, word.pos), ("学习", "合成验收", "v."))
        self.assertEqual(WordRelation.objects.get().related_word.lemma, "study")
        self.assertEqual(Phrase.objects.get().source, "合成验收")
        self.assertEqual(UsageExample.objects.get().source, "合成验收")

    @acceptance_case("TC46", "JSON错误整批回滚", "已有learn旧释义；导入修改learn并新增study；前段短语/例句成功后第二词关联不存在", "HTTP200表单错误；旧释义恢复；新增词/关联/短语/例句全部回滚", "B")
    def test_tc46_json_import_transaction_rollback(self):
        word = Word.objects.create(lemma="learn", meaning="旧释义", source="旧来源")
        self.admin_login()
        rows = [{"lemma": "learn", "meaning": "新释义", "source": "新来源",
                 "phrases": [{"text": "learn from", "meaning": "合成短语"}],
                 "examples": [{"text": "We learn together."}]},
                {"lemma": "study", "source": "新来源", "relations": [{"lemma": "missing", "type": "synonym"}]}]
        response = self.client.post(reverse("lexicon_import"), {"file": self.upload_json(rows)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        word.refresh_from_db()
        self.assertEqual((word.meaning, word.source), ("旧释义", "旧来源"))
        self.assertEqual(Word.objects.count(), 1)
        self.assertEqual((WordRelation.objects.count(), Phrase.objects.count(), UsageExample.objects.count()), (0, 0, 0))

    @acceptance_case("TC47", "JSON结构/编码/限制异常", "空数组/对象、未知字段、无source、大写lemma、非数组relations、错误扩展/JSON/UTF8及超1MB", "全部返回表单错误HTTP200，无词条写入", "B")
    def test_tc47_json_invalid_inputs(self):
        self.admin_login()
        invalid = [[], {}, [{"lemma": "learn", "source": "合成", "unknown": "x"}],
                   [{"lemma": "learn"}], [{"lemma": "LEARN", "source": "合成"}],
                   [{"lemma": "learn", "source": "合成", "relations": {}}]]
        uploads = [self.upload_json(rows) for rows in invalid]
        uploads.extend([self.upload_json([{"lemma": "learn", "source": "合成"}], "bad.txt"),
                        SimpleUploadedFile("bad.json", b"[not json]"),
                        SimpleUploadedFile("badencoding.json", b"\xff"),
                        SimpleUploadedFile("large.json", b"x" * (1024 * 1024 + 1))])
        for index, upload in enumerate(uploads):
            with self.subTest(index=index):
                response = self.client.post(reverse("lexicon_import"), {"file": upload})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(Word.objects.exists())

    @acceptance_case("TC48", "JSON嵌套约束失败回滚", "自关联、未知嵌套字段、缺短语释义、超长pos、非对象例句分别导入", "均表单错误HTTP200；每批没有残留Word/Relation/Phrase/Example", "B")
    def test_tc48_json_nested_constraint_rollback(self):
        self.admin_login()
        additions = [{"relations": [{"lemma": "learn", "type": "synonym"}]},
                     {"phrases": [{"text": "learn from", "meaning": "合成", "unknown": "x"}]},
                     {"phrases": [{"text": "learn from"}]}, {"pos": "x" * 81},
                     {"examples": ["not an object"]}]
        for addition in additions:
            with self.subTest(field=list(addition)[0]):
                rows = [{"lemma": "learn", "source": "合成测试", **addition}]
                response = self.client.post(reverse("lexicon_import"), {"file": self.upload_json(rows)})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual((Word.objects.count(), WordRelation.objects.count(), Phrase.objects.count(), UsageExample.objects.count()), (0, 0, 0, 0))

    @acceptance_case("TC49", "CSRF保护与合法提交", "enforce_csrf_checks=True学生Client；不带token POST加入；GET词详情取得token后携token重试", "无token403无写入；合法token302且新增本人学习项目", "B")
    def test_tc49_csrf_enforced(self):
        word = Word.objects.create(lemma="learn")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.student)
        target = reverse("study_add", args=[word.pk])
        self.assertEqual(client.post(target).status_code, 403)
        self.assertFalse(StudyItem.objects.exists())
        self.assertEqual(client.get(reverse("word_detail", args=[word.pk])).status_code, 200)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(target, {"csrfmiddlewaretoken": token}).status_code, 302)
        self.assertEqual(StudyItem.objects.get().user_id, self.student.pk)

    @acceptance_case("TC50", "HTML正文/词库转义", "paper标题正文和Word释义/notes、Phrase/Example写入script/img合成标记；Client读取", "HTML不出现原始可执行标记；显示&lt;转义文本", "B")
    def test_tc50_html_escaping(self):
        payload = '<script>alert("acceptance")</script><img src=x onerror=alert(1)>'
        paper = self.paper(content=payload + " Learn.")
        paper.title = payload
        paper.save()
        word = Word.objects.create(lemma="learn", meaning=payload, notes=payload)
        Phrase.objects.create(word=word, text=payload, meaning="合成", example=payload)
        UsageExample.objects.create(word=word, text=payload, translation=payload)
        self.student_login()
        for name, pk in (("paper_detail", paper.pk), ("word_detail", word.pk)):
            response = self.client.get(reverse(name, args=[pk]))
            self.assertNotContains(response, payload)
            self.assertNotContains(response, "<script>alert(")
            self.assertNotContains(response, "<img src=x")
            self.assertContains(response, "&lt;script&gt;")

    @acceptance_case("TC51", "复习备注HTML转义", "合成script备注随复习提交，Client读取本人复习历史", "日志存储原文，页面仅显示转义文本，无可执行script", "C")
    def test_tc51_review_note_escaped(self):
        payload = "<script>acceptance_note()</script>"
        item = self.due_item()
        log = submit_review(self.student, item.pk, "good", note=payload)
        self.assertEqual(log.note, payload)
        self.student_login()
        response = self.client.get(reverse("review_history"))
        self.assertNotContains(response, payload)
        self.assertContains(response, "&lt;script&gt;acceptance_note()&lt;/script&gt;")

    @acceptance_case("TC52", "模型各表至少6字段", "遍历core所有模型，用数据库introspection核实字段及关联真实表", "core模型10张表，逐表>=6个实际数据库列；记录每表字段清单", "A")
    def test_tc52_model_tables_field_counts(self):
        models = list(apps.get_app_config("core").get_models())
        self.assertEqual(len(models), 10)
        with connection.cursor() as cursor:
            for model in models:
                with self.subTest(model=model.__name__):
                    columns = [col.name for col in connection.introspection.get_table_description(cursor, model._meta.db_table)]
                    self.assertGreaterEqual(len(columns), 6)
                    self.assertTrue(set(f.column for f in model._meta.concrete_fields).issubset(columns))

    @acceptance_case("TC53", "SQLite测试库隔离", "检查测试运行时connection.settings_dict及SQLite database_list", "SQLite引擎，数据库file:memorydb测试库或:memory:，绝非真实db.sqlite3", "A")
    def test_tc53_sqlite_test_database_isolated(self):
        self.assertEqual(connection.vendor, "sqlite")
        name = str(connection.settings_dict["NAME"])
        self.assertTrue(name == ":memory:" or name.startswith("file:memorydb_"), name)
        self.assertNotIn("db.sqlite3", name)
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            self.assertTrue(all(not row[2] for row in cursor.fetchall()))

    @acceptance_case("TC54", "Client分析POST和词频读取", "管理员POST分析；学生读取详情并检索learn", "分析成功302，学生看见learn=2；过滤仅返回learn，不需管理员权限", "A")
    def test_tc54_analysis_http_and_search(self):
        paper = self.paper("Learn learning research.")
        self.admin_login()
        self.assertRedirects(self.client.post(reverse("paper_analyze", args=[paper.pk])),
                             reverse("paper_detail", args=[paper.pk]))
        self.student_login()
        response = self.client.get(reverse("paper_detail", args=[paper.pk]), {"q": "learn"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(e.word.lemma, e.count) for e in response.context["entries"]], [("learn", 2)])

    @acceptance_case("TC55", "Client复习提交与重试", "学生POST有效UUID/good/备注，再以idempotency_key兼容字段重试", "两次302；一条日志；等级只推进一次；备注保存", "C")
    def test_tc55_review_http_idempotency(self):
        item = self.due_item()
        key = str(uuid.uuid4())
        self.student_login()
        target = reverse("review_submit", args=[item.pk])
        self.assertRedirects(self.client.post(target, {"rating": "good", "token": key, "note": "接口合成备注"}), reverse("review_list"))
        self.assertRedirects(self.client.post(target, {"rating": "good", "idempotency_key": key}), reverse("review_list"))
        item.refresh_from_db()
        self.assertEqual(item.level, 1)
        self.assertEqual(ReviewLog.objects.count(), 1)
        self.assertEqual(ReviewLog.objects.get().note, "接口合成备注")

    @acceptance_case("TC56", "词汇查询与学习筛选", "词库按中文释义查询；本人new/learning项目按状态及关键词过滤", "词库仅匹配research；学习列表仅本人指定状态与关键词项目", "C")
    def test_tc56_search_and_study_filters(self):
        learn = self.due_item(lemma="learn")
        research = self.due_item(lemma="research")
        research.status = "learning"
        research.save()
        research.word.meaning = "研究"
        research.word.save()
        self.student_login()
        response = self.client.get(reverse("word_list"), {"q": "研究"})
        self.assertEqual([w.pk for w in response.context["words"]], [research.word_id])
        response = self.client.get(reverse("study_list"), {"status": "learning", "q": "研究"})
        self.assertEqual([i.pk for i in response.context["items"]], [research.pk])
        self.assertNotEqual(learn.pk, research.pk)

    @acceptance_case("TC57", "JSON再次导入资料去重", "同一包含短语及例句的JSON完整导入两次；再重复导入已有短语但传空释义", "两次合法导入均成功且Word/Phrase/Example各1条；非法重复资料仍验证且整批回滚、不覆盖原资料", "B")
    def test_tc57_json_reimport_deduplication(self):
        self.admin_login()
        rows = [{"lemma": "learn", "source": "合成测试",
                 "phrases": [{"text": "learn from", "meaning": "向某人学习"}],
                 "examples": [{"text": "We learn together."}]}]
        for attempt in range(2):
            with self.subTest(attempt=attempt + 1):
                response = self.client.post(reverse("lexicon_import"), {"file": self.upload_json(rows)})
                self.assertEqual(response.status_code, 302,
                                 "Repeated valid import must deduplicate existing material; form_errors="
                                 + str(response.context["form"].errors if response.context else "no form"))
        self.assertEqual((Word.objects.count(), Phrase.objects.count(), UsageExample.objects.count()), (1, 1, 1))
        # Existing material must still receive field validation, not be skipped.
        bad_rows = [{"lemma": "learn", "meaning": "回滚前修改", "source": "合成测试",
                     "phrases": [{"text": "learn from", "meaning": ""}]}]
        response = self.client.post(reverse("lexicon_import"), {"file": self.upload_json(bad_rows)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Phrase.objects.get().meaning, "向某人学习")
        self.assertEqual(Word.objects.get().meaning, "")

    @acceptance_case("TC58", "同年资料不能互为历史", "两份2025同类别均分析learn；对第二份比较", "同年第一份排除，history_count=0，历史频0", "A")
    def test_tc58_same_year_not_history(self):
        self.paper("learn learn", year=2025, analyzed=True)
        current = self.paper("learn", year=2025, analyzed=True)
        result = compare_paper(current)
        self.assertEqual(result["history_count"], 0)
        self.assertEqual(result["rows"][0]["historical_count"], 0)

    @acceptance_case("TC59", "全停用正文分析", "管理员分析the and was，并与无历史基线比较", "tokens=3/valid=words=0，仍标记已分析，无空白词条；比较结果0行", "A")
    def test_tc59_all_stop_words(self):
        paper = self.paper("the and was")
        result = analyze_paper(paper, self.admin_user)
        self.assertEqual((result["tokens"], result["valid"], result["words"]), (3, 0, 0))
        self.assertEqual(paper.status, "analyzed")
        self.assertFalse(paper.paper_words.exists())
        self.assertEqual(compare_paper(paper)["rows"], [])

    @acceptance_case("TC60", "个人学习服务拒绝无效用户", "匿名/停用用户添加已保存词；有效用户添加未保存词", "无效用户PermissionDenied；未保存词ValidationError；无学习记录", "C")
    def test_tc60_study_service_invalid_user_word(self):
        word = Word.objects.create(lemma="learn")
        inactive = User.objects.create_user(username="fixture_disabled", is_active=False)
        for user in (AnonymousUser(), inactive):
            with self.assertRaises(PermissionDenied):
                add_to_study(user, word)
        with self.assertRaises(ValidationError):
            add_to_study(self.student, Word(lemma="research"))
        self.assertFalse(StudyItem.objects.exists())
