import os
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from core.models import Paper, Phrase, StopWord, StudyItem, UsageExample, User, Word, WordRelation
from core.services import add_to_study, analyze_paper, is_admin


SOURCE = "人工整理演示资料，需核验后用于正式学习"
PAPER_SOURCE = "原创英文教学示例，非考研真题，不代表真实考试频率"

# 释义及例句均为原创教学整理，不冒充权威词典或真题。
VOCABULARY = (
    ("learn", "学习；学会", "v.", ""),
    ("study", "学习；研究", "n.; v.", ""),
    ("education", "教育", "n.", "educate"),
    ("educate", "教育；培养", "v.", "educate"),
    ("develop", "发展；开发", "v.", "develop"),
    ("development", "发展；开发；成长", "n.", "develop"),
    ("science", "科学", "n.", "science"),
    ("scientific", "科学的", "adj.", "science"),
    ("research", "研究；调查", "n.; v.", ""),
    ("knowledge", "知识；了解", "n.", ""),
    ("skill", "技能；技巧", "n.", ""),
    ("improve", "改进；改善", "v.", ""),
    ("improvement", "改进；改善", "n.", ""),
    ("community", "社区；共同体", "n.", ""),
    ("environment", "环境", "n.", ""),
    ("energy", "能源；精力", "n.", ""),
    ("technology", "技术；科技", "n.", ""),
    ("information", "信息；资料", "n.", ""),
    ("experience", "经验；经历；体验", "n.; v.", ""),
    ("opportunity", "机会；机遇", "n.", ""),
    ("challenge", "挑战；向……提出挑战", "n.; v.", ""),
    ("solution", "解决办法；溶液", "n.", ""),
    ("change", "改变；变化", "n.; v.", ""),
    ("growth", "增长；成长", "n.", ""),
    ("create", "创造；创作", "v.", ""),
    ("support", "支持；支撑", "n.; v.", ""),
    ("protect", "保护；防护", "v.", ""),
    ("reduce", "减少；降低", "v.", ""),
    ("resource", "资源", "n.", ""),
    ("value", "价值；重视", "n.; v.", ""),
    ("increase", "增加；增长", "n.; v.", ""),
    ("decrease", "减少；下降", "n.; v.", ""),
    ("important", "重要的", "adj.", ""),
    ("significant", "重要的；显著的", "adj.", ""),
    ("rapid", "迅速的", "adj.", ""),
    ("slow", "缓慢的；减速", "adj.; v.", ""),
    ("useful", "有用的；有益的", "adj.", ""),
    ("harmful", "有害的", "adj.", ""),
    ("positive", "积极的；正面的", "adj.", ""),
    ("negative", "消极的；负面的", "adj.", ""),
    ("cooperate", "合作；协作", "v.", ""),
    ("communicate", "交流；传达", "v.", ""),
    ("practice", "练习；实践", "n.; v.", ""),
    ("evidence", "证据；依据", "n.", ""),
    ("benefit", "益处；使受益", "n.; v.", ""),
)

PAPERS = (
    (2022, "社区学习", """A community library can become a place where people learn together. In one small town, students and older readers meet every week to share useful books. The students bring questions from school, while other readers bring experience from work. They do not always agree, but they listen carefully and support each other. This simple practice helps them develop communication skills and gain knowledge beyond a single subject.

The library also offers a study room for people who need a quiet environment. Volunteers organize the books and explain how to find reliable information. A teacher asks each group to describe an important idea in clear English. When a student makes a mistake, the group treats it as an opportunity to improve rather than a reason to stop.

Education is not limited to formal lessons. Community learning can create a positive change in daily life. It requires time, patience, and shared effort. The library cannot solve every problem, yet its work shows that a small resource can have lasting value when people use it with care. Every reader can contribute a question, a useful example, or a new way of thinking."""),
    (2023, "能源与环境", """A community school decided to study how it used energy. Students first collected information about lights, water, and heating. They learned that a useful solution must begin with careful observation. A science teacher helped them compare records from different weeks. The research did not require expensive technology, but it required clear questions and reliable evidence.

The students found an opportunity to reduce waste by closing empty rooms and checking old equipment. Some people expected a rapid decrease in costs. The teacher explained that improvement could be slow because habits take time to change. The group agreed to protect the environment without making the school uncomfortable. They created a simple plan and asked everyone to cooperate.

This experience connected scientific knowledge with daily practice. Younger students developed new skills, while older students learned how to communicate results. The school shared its report with the local library so that other readers could learn from it. The project showed that responsible development depends on both information and support. A positive result is not only a smaller bill; it is also a community that understands the value of its resources and continues to ask important questions."""),
    (2024, "技术与协作", """New technology can create an opportunity for education, but it also brings a challenge. A community learning center introduced a digital collection of original study materials. Students could review useful information at home and discuss questions in class. Teachers hoped that the change would support learning rather than replace personal communication. They asked students to describe both the benefit and the difficulty of the new system.

At first, some learners expected rapid growth in their skills. Others worried that too much screen time might be harmful. The center used evidence from short interviews instead of assuming that every person had the same experience. Research showed that a clear study plan was more important than the number of available pages. Teachers helped students reduce distraction and practice difficult words in meaningful contexts.

The center also encouraged groups to cooperate on scientific projects about energy and the environment. Students compared possible solutions, explained their choices, and protected shared resources. This work helped them communicate with confidence. Technology has significant value when people use it responsibly. Its development should increase access to knowledge while keeping human support at the heart of education. A useful tool cannot make every decision for a learner."""),
)

RELATIONS = (
    ("develop", "development", "root", "development 是 develop 的明显派生名词；这里只标注同源关系，不猜测拉丁词根。"),
    ("educate", "education", "root", "educate 与 education 为明显同源词，分别常用作动词与名词。"),
    ("science", "scientific", "root", "science 与 scientific 为明显同源词，后者表示科学的。"),
    ("important", "significant", "synonym", "在表示重要、值得关注时意思接近；significant 还可表示显著的，不能一概替换。"),
    ("learn", "study", "synonym", "在学习语境中有关联；learn 偏向获得知识，study 偏向学习活动，并非所有语境可互换。"),
    ("increase", "decrease", "antonym", "表示数量变化时，增加与减少构成反义。"),
    ("rapid", "slow", "antonym", "描述速度时，迅速与缓慢构成反义。"),
    ("positive", "negative", "antonym", "描述态度或影响时，积极或正面与消极或负面构成反义。"),
)

PHRASES = (
    ("learn", "learn from experience", "从经验中学习", "We learn from experience when we reflect on our mistakes.", "当我们反思错误时，就能从经验中学习。"),
    ("study", "study plan", "学习计划", "A clear study plan helps the group use its time well.", "清晰的学习计划帮助小组合理利用时间。"),
    ("education", "access to education", "接受教育的机会", "The new library improves access to education in the town.", "新图书馆改善了镇上居民接受教育的机会。"),
    ("develop", "develop skills", "培养技能", "Students develop skills by solving practical problems.", "学生通过解决实际问题培养技能。"),
    ("research", "conduct research", "开展研究", "The class will conduct research on local energy use.", "这个班将开展关于当地能源使用情况的研究。"),
    ("knowledge", "gain knowledge", "获得知识", "Readers gain knowledge by comparing different sources.", "读者通过比较不同来源获得知识。"),
    ("improve", "improve communication", "改善交流", "Listening carefully can improve communication within a team.", "认真倾听能够改善团队内部的交流。"),
    ("environment", "protect the environment", "保护环境", "We protect the environment by reducing unnecessary waste.", "我们通过减少不必要的浪费来保护环境。"),
    ("energy", "save energy", "节约能源", "Closing an unused room can help the school save energy.", "关闭闲置房间能够帮助学校节约能源。"),
    ("opportunity", "an opportunity to learn", "学习的机会", "A difficult question can be an opportunity to learn.", "一个难题也可以是学习的机会。"),
    ("challenge", "face a challenge", "面临挑战", "Teams face a challenge when reliable information is missing.", "当可靠信息不足时，团队就面临挑战。"),
    ("solution", "find a solution", "找到解决办法", "The students worked together to find a solution.", "学生们共同努力寻找解决办法。"),
    ("change", "make a change", "作出改变", "We can make a change by checking our daily habits.", "我们可以通过审视日常习惯作出改变。"),
    ("support", "provide support", "提供支持", "Teachers provide support without making every decision for students.", "教师提供支持，但不替学生作每一个决定。"),
    ("value", "lasting value", "持久的价值", "A useful learning habit has lasting value.", "一个有用的学习习惯具有持久的价值。"),
)

WORD_EXAMPLES = (
    ("science", "Science begins with questions that can be examined carefully.", "科学始于能够被认真检验的问题。"),
    ("scientific", "The group compared its scientific results with earlier records.", "小组将其科学研究结果与早期记录作了比较。"),
    ("development", "Responsible development should respect local resources.", "负责任的发展应当尊重当地资源。"),
    ("evidence", "The report offers evidence rather than unsupported guesses.", "报告提供的是证据，而不是没有依据的猜测。"),
    ("technology", "Technology is helpful when it serves a clear learning goal.", "当技术服务于明确的学习目标时，它就能发挥作用。"),
    ("positive", "A positive attitude can help a team discuss mistakes openly.", "积极的态度能够帮助团队坦诚地讨论错误。"),
)


class Command(BaseCommand):
    help = "幂等创建原创演示资料、词汇和账号；不重置已有数据或密码。默认用规则引擎分析新演示试卷。"

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default=os.environ.get("DEMO_ADMIN_USERNAME", "admin"), help="管理员登录名")
        parser.add_argument("--student-username", default=os.environ.get("DEMO_STUDENT_USERNAME", "student"), help="学生登录名")
        parser.add_argument("--no-analyze", action="store_true", help="仅创建演示数据，不执行词频分析")

    def _user(self, username, role, password_env, generated):
        existing = User.objects.filter(username=username).first()
        if existing:
            if role == User.Role.ADMIN and not is_admin(existing):
                raise CommandError("指定管理员登录名已存在，但不是有效管理员；请选择其他登录名，不会自动提权。")
            if role == User.Role.STUDENT and (existing.role != User.Role.STUDENT or existing.is_superuser or not existing.is_active):
                raise CommandError("指定学生登录名已存在，但不是有效学生；请选择其他登录名，不会修改现有账号。")
            return existing, False
        supplied = os.environ.get(password_env)
        if supplied is not None and not supplied:
            raise CommandError(f"环境变量 {password_env} 为空；请提供密码或取消设置以随机生成。")
        password = supplied if supplied is not None else secrets.token_urlsafe(24)
        candidate = User(username=username, role=role)
        try:
            candidate.full_clean(exclude=["password"])
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError(f"演示账号或密码不符合验证要求：{'；'.join(exc.messages)}") from exc
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "password": make_password(password), "role": role,
                "display_name": "演示管理员" if role == User.Role.ADMIN else "演示学生",
                "is_active": True, "is_staff": role == User.Role.ADMIN,
            },
        )
        if not created:
            if role == User.Role.ADMIN and not is_admin(user):
                raise CommandError("管理员登录名被其他请求占用，请换用其他名称。")
            if role == User.Role.STUDENT and (user.role != User.Role.STUDENT or user.is_superuser or not user.is_active):
                raise CommandError("学生登录名被其他请求占用，请换用其他名称。")
        if created and supplied is None:
            generated.append((username, password))
        return user, created

    def handle(self, *args, **options):
        admin_username = options["admin_username"].strip()
        student_username = options["student_username"].strip()
        if not admin_username or not student_username or admin_username == student_username:
            raise CommandError("管理员和学生登录名必须非空且不同。")
        generated = []
        analyzed = 0
        new_users = 0
        with transaction.atomic():
            administrator, admin_created = self._user(admin_username, User.Role.ADMIN, "DEMO_ADMIN_PASSWORD", generated)
            student, student_created = self._user(student_username, User.Role.STUDENT, "DEMO_STUDENT_PASSWORD", generated)
            new_users = int(admin_created) + int(student_created)
            words = {}
            for lemma, meaning, pos, root in VOCABULARY:
                words[lemma], _ = Word.objects.get_or_create(
                    lemma=lemma,
                    defaults={"meaning": meaning, "pos": pos, "root": root, "notes": "原创演示释义，正式学习前请核验。", "source": SOURCE},
                )
            for left, right, kind, explanation in RELATIONS:
                WordRelation.objects.get_or_create(
                    word=words[left], related_word=words[right], relation_type=kind,
                    defaults={"explanation": explanation, "source": SOURCE},
                )
            for lemma, text, meaning, example, translation in PHRASES:
                phrase, _ = Phrase.objects.get_or_create(
                    word=words[lemma], text=text,
                    defaults={"meaning": meaning, "example": example, "translation": translation, "source": SOURCE},
                )
                UsageExample.objects.get_or_create(
                    word=words[lemma], phrase=phrase, kind=UsageExample.Kind.PHRASE,
                    text=example, source=SOURCE, defaults={"translation": translation},
                )
            for lemma, text, translation in WORD_EXAMPLES:
                UsageExample.objects.get_or_create(
                    word=words[lemma], phrase=None, kind=UsageExample.Kind.WORD,
                    text=text, source=SOURCE, defaults={"translation": translation},
                )
            for text in ("the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "am", "is", "are"):
                StopWord.objects.get_or_create(
                    text=text,
                    defaults={"reason": "保守排除常见功能词，作为内置停用规则的管理示例。", "created_by": administrator},
                )
            papers = []
            with override_settings(ANALYSIS_ENGINE="rule"):
                for year, topic, text in PAPERS:
                    paper, _ = Paper.objects.get_or_create(
                        title=f"演示试卷（原创，非考研真题）·{year}·{topic}",
                        year=year, category=Paper.Category.ENGLISH1, is_demo=True,
                        defaults={"content": text.strip(), "source": PAPER_SOURCE, "created_by": administrator},
                    )
                    papers.append(paper)
                    if not options["no_analyze"] and paper.status == Paper.Status.DRAFT:
                        analyze_paper(paper, administrator)
                        analyzed += 1
            for lemma in ("learn", "study", "education", "develop", "research", "knowledge", "skill", "environment", "technology", "opportunity", "challenge", "solution"):
                add_to_study(student, words[lemma], source_paper=papers[-1])
            # 初始掌握状态不伪造实际复习记录；后续复习仍经正常服务产生日志。
            now = timezone.now()
            for lemma in ("important", "useful"):
                StudyItem.objects.get_or_create(
                    user=student, word=words[lemma],
                    defaults={"source_paper": papers[0], "status": StudyItem.Status.MASTERED, "level": 4, "next_review_at": now + timedelta(days=14)},
                )
        self.stdout.write(self.style.SUCCESS(
            f"演示数据就绪：新增账号 {new_users} 个，词汇整理 {len(VOCABULARY)} 条，演示试卷 {len(PAPERS)} 份，本次规则分析 {analyzed} 份。"
        ))
        self.stdout.write("已有账号密码及学习进度均保留。演示正文非考研真题，频率不可作为真实考试统计。")
        for username, password in generated:
            self.stdout.write(self.style.WARNING(f"新账号 {username} 的随机密码（仅本次显示，请妥善保存）：{password}"))
        if new_users > len(generated):
            self.stdout.write("部分新账号已使用环境变量提供的密码，密码不会显示。")
