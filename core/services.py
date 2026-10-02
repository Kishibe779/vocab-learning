"""词频、历史对照与个人复习业务；默认算法为规则归一，不声称完整 NLP。"""

import re
import uuid
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Paper, PaperWord, ReviewLog, StopWord, StudyItem, User, Word


RULE_ENGINE_LABEL = "规则词形归一（非完整NLP）"
WORDNET_ENGINE_LABEL = "NLTK WordNet 词形归一（非上下文语义分析）"
MAX_TEXT_LENGTH = 200_000
MAX_DISTINCT_WORDS = 10_000
TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]+(?:[-'’][A-Za-z]+)*(?![A-Za-z])")
SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")

# 高风险词尾只对已知基础词做变换，避免将 analysis、business 等误截断。
RULE_VOCABULARY = frozenset("""
ability accept achieve act action add adapt advance affect age agree allow answer
appear apply argue ask assess avoid be become begin believe benefit book break
bring build business buy call carry cause change child choose city class close
collect come communicate community compare complete consider continue contribute
control cooperate create culture cut day decide decision decrease define demand
describe design develop development discover discuss do draw drive early earn
educate education effective effort encourage end energy enjoy environment examine
example experience explain explore face fact fail family feel find finish focus
follow form friend gain give go good grow growth guide happen have help high
history hope human idea identify improve improvement include increase influence
information interest introduce issue join keep know knowledge large learn leave
life listen live local look lose low make manage management many measure meet
method mind move need notice offer old open opportunity organize paper part
participate pay person plan play policy practice prepare prevent process produce
product protect provide public read reason receive record reduce reflect relate
remember report require research resource respond result review rise role run
say school science scientific see seek sell send service share show simple skill
sleep small society solve speak spend start stay stop strategy student study
succeed success support take talk teach technology tell test think time train
travel try understand use value wait walk want watch water way well win woman
word work world write year young useful harmful positive negative major minor
increase decrease rapid slow important significant opportunity challenge solution
""".split())
IRREGULAR_FORMS = {
    "am": "be", "is": "be", "are": "be", "was": "be", "were": "be", "been": "be", "being": "be",
    "has": "have", "had": "have", "having": "have", "does": "do", "did": "do", "done": "do", "doing": "do",
    "went": "go", "gone": "go", "going": "go", "came": "come", "coming": "come",
    "became": "become", "becoming": "become", "began": "begin", "begun": "begin",
    "brought": "bring", "bought": "buy", "built": "build", "chose": "choose", "chosen": "choose",
    "drew": "draw", "drawn": "draw", "drove": "drive", "driven": "drive", "ate": "eat", "eaten": "eat",
    "felt": "feel", "found": "find", "gave": "give", "given": "give", "giving": "give",
    "grew": "grow", "grown": "grow", "kept": "keep", "knew": "know", "known": "know",
    "left": "leave", "leaving": "leave", "lost": "lose", "losing": "lose", "made": "make", "making": "make",
    "met": "meet", "paid": "pay", "ran": "run", "said": "say", "saw": "see", "seen": "see",
    "sold": "sell", "sent": "send", "slept": "sleep", "spoke": "speak", "spoken": "speak",
    "spent": "spend", "took": "take", "taken": "take", "taking": "take", "taught": "teach",
    "told": "tell", "thought": "think", "understood": "understand", "won": "win",
    "wrote": "write", "written": "write", "writing": "write", "children": "child",
    "people": "person", "men": "man", "women": "woman", "feet": "foot", "teeth": "tooth",
    "mice": "mouse", "better": "good", "best": "good", "worse": "bad", "worst": "bad",
    "lives": "life", "leaves": "leaf", "knives": "knife", "wives": "wife",
}
DEFAULT_STOP_WORDS = frozenset("""
a an the and or but if as at by for from in into of on onto to with without
about above after before between during under over through than then that
this these those it its itself they them their theirs themselves we us our
ours ourselves you your yours yourself yourselves i me my mine myself he
him his himself she her hers herself who whom whose which what when where
why how not no nor only also very more most some any each either neither
both all such there here can could may might must shall should will would
be am is are was were been being have has had do does did
""".split())
DEFAULT_STOP_CONTRACTIONS = frozenset("""
i'm i've i'd i'll you're you've you'd you'll he's he'd he'll she's she'd she'll
it's it'd it'll we're we've we'd we'll they're they've they'd they'll that's
there's here's isn't aren't wasn't weren't don't doesn't didn't haven't hasn't
hadn't can't cannot couldn't won't wouldn't shouldn't mustn't let's
""".split())


def is_admin(user):
    return bool(
        user and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and (getattr(user, "is_superuser", False) or getattr(user, "role", None) == User.Role.ADMIN)
    )


def _require_user(user):
    if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False) or not user.pk:
        raise PermissionDenied("请先使用有效账号登录。")


def _rule_lemma(token):
    if token in IRREGULAR_FORMS:
        return IRREGULAR_FORMS[token]
    if token in RULE_VOCABULARY:
        return token
    if token.endswith("'s"):
        token = token[:-2]
        if token in IRREGULAR_FORMS:
            return IRREGULAR_FORMS[token]
        if token in RULE_VOCABULARY:
            return token
    if "-" in token:
        return token
    candidates = []
    if token.endswith("ies") and len(token) > 4:
        candidates.append(token[:-3] + "y")
    if token.endswith("ied") and len(token) > 4:
        candidates.append(token[:-3] + "y")
    if token.endswith("ing") and len(token) > 5:
        stem = token[:-3]
        candidates.extend([stem + "e", stem])
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            candidates.append(stem[:-1])
    if token.endswith("ed") and len(token) > 4:
        stem = token[:-2]
        candidates.extend([token[:-1], stem])
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            candidates.append(stem[:-1])
    if token.endswith("es") and len(token) > 3:
        candidates.append(token[:-2])
    if token.endswith("s") and not token.endswith(("ss", "us", "is")) and len(token) > 3:
        candidates.append(token[:-1])
    return next((candidate for candidate in candidates if candidate in RULE_VOCABULARY), token)


def _select_engine():
    engine = getattr(settings, "ANALYSIS_ENGINE", "rule")
    if engine == "rule":
        return _rule_lemma, RULE_ENGINE_LABEL
    if engine != "wordnet":
        raise ImproperlyConfigured("ANALYSIS_ENGINE 只能为 'rule' 或 'wordnet'。")
    try:
        from nltk.corpus import wordnet
        wordnet.ensure_loaded()
    except (ImportError, LookupError) as exc:
        raise ImproperlyConfigured(
            "已选择 WordNet，但 NLTK 或本地 WordNet 语料不可用。请改用 ANALYSIS_ENGINE='rule'；本程序不会下载资源。"
        ) from exc

    def wordnet_lemma(token):
        base = _rule_lemma(token)
        if base != token or "-" in base:
            return base
        noun = wordnet.morphy(base, wordnet.NOUN)
        if noun and noun != base:
            return noun
        verb = wordnet.morphy(base, wordnet.VERB)
        if verb and verb != base:
            return verb
        return noun or verb or base

    return wordnet_lemma, WORDNET_ENGINE_LABEL


def lexical_analysis(text, stop_words=None):
    """无数据库写操作：返回 tokens/valid/words/engine 与按 lemma 排序的 records。"""
    if not isinstance(text, str):
        raise ValidationError("正文必须为 Unicode 文本，请以 UTF-8 解码上传文件。")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"正文最多允许 {MAX_TEXT_LENGTH:,} 个字符。")
    try:
        text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValidationError("正文包含无效 Unicode 字符，请使用 UTF-8 文本。") from exc
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        raise ValidationError("正文中没有可分析的英文单词。")
    lemmatize, engine_label = _select_engine()
    stops = set(DEFAULT_STOP_WORDS) | set(DEFAULT_STOP_CONTRACTIONS)
    if stop_words is not None:
        if isinstance(stop_words, str):
            stop_words = [stop_words]
        stops.update(str(word).strip().lower().replace("’", "'") for word in stop_words)
    stops.update(lemmatize(word) for word in tuple(stops))
    sentences = list(SENTENCE_RE.finditer(text))
    sentence_index = 0
    records = {}
    valid = 0
    for match in matches:
        original = match.group()
        token = original.lower().replace("’", "'")
        if len(token) > 100:
            raise ValidationError("正文中存在超过 100 个字符的英文词形，请检查输入。")
        lemma = lemmatize(token)
        if token in stops or lemma in stops or len(lemma) <= 1:
            continue
        if not re.fullmatch(r"[a-z]+(?:[-'][a-z]+)*", lemma):
            continue
        valid += 1
        if lemma not in records:
            if len(records) >= MAX_DISTINCT_WORDS:
                raise ValidationError(f"不同词汇数量不能超过 {MAX_DISTINCT_WORDS:,}。")
            records[lemma] = {"lemma": lemma, "count": 0, "forms": Counter(), "contexts": []}
        record = records[lemma]
        record["count"] += 1
        record["forms"][original] += 1
        while sentence_index < len(sentences) and sentences[sentence_index].end() <= match.start():
            sentence_index += 1
        if sentence_index < len(sentences) and sentences[sentence_index].start() <= match.start():
            sentence = sentences[sentence_index]
            start, end = sentence.start(), sentence.end()
        else:
            start, end = max(0, match.start() - 180), min(len(text), match.end() + 180)
        if end - start > 500:
            start = max(start, match.start() - 180)
            end = min(end, start + 500)
        context = " ".join(text[start:end].split())
        if context and context not in record["contexts"] and len(record["contexts"]) < 3:
            record["contexts"].append(context)
    normalized = []
    for lemma in sorted(records):
        record = records[lemma]
        record["forms"] = dict(sorted(record["forms"].items()))
        normalized.append(record)
    return {"tokens": len(matches), "valid": valid, "words": len(normalized), "engine": engine_label, "records": normalized}


def _chunks(values, size=500):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def analyze_paper(paper, user):
    if not is_admin(user):
        raise PermissionDenied("只有管理员可以分析试卷。")
    if not paper.pk:
        raise ValidationError("请先保存试卷。")
    original_content = paper.content
    stops = list(StopWord.objects.filter(enabled=True).values_list("text", flat=True))
    try:
        result = lexical_analysis(original_content, stop_words=stops)
    except ImproperlyConfigured as exc:
        raise ValidationError(str(exc)) from exc
    with transaction.atomic():
        try:
            locked = Paper.objects.select_for_update().get(pk=paper.pk)
        except Paper.DoesNotExist as exc:
            raise ValidationError("试卷已被删除。") from exc
        if locked.content != original_content:
            raise ValidationError("分析过程中试卷正文已被修改，请重新分析。")
        lemmas = [record["lemma"] for record in result["records"]]
        word_map = {}
        for batch in _chunks(lemmas):
            word_map.update({word.lemma: word for word in Word.objects.filter(lemma__in=batch)})
        missing = [Word(lemma=lemma, source="正文词频分析生成，释义待人工补充") for lemma in lemmas if lemma not in word_map]
        Word.objects.bulk_create(missing, batch_size=500, ignore_conflicts=True)
        for batch in _chunks(lemmas):
            word_map.update({word.lemma: word for word in Word.objects.filter(lemma__in=batch)})
        if any(lemma not in word_map for lemma in lemmas):
            raise ValidationError("词库并发更新未完成，请重试分析。")
        locked.paper_words.all().delete()
        PaperWord.objects.bulk_create([
            PaperWord(
                paper=locked, word=word_map[record["lemma"]], count=record["count"],
                forms=record["forms"], contexts=record["contexts"], total_tokens=result["tokens"],
            ) for record in result["records"]
        ], batch_size=500)
        locked.token_count = result["tokens"]
        locked.valid_count = result["valid"]
        locked.status = Paper.Status.ANALYZED
        locked.analyzed_at = timezone.now()
        locked.save(update_fields=["token_count", "valid_count", "status", "analyzed_at", "updated_at"])
    for field in ("token_count", "valid_count", "status", "analyzed_at", "updated_at"):
        setattr(paper, field, getattr(locked, field))
    return {key: result[key] for key in ("tokens", "valid", "words", "engine")}


def compare_paper(paper, start_year=None, end_year=None):
    if not paper.pk or paper.status != Paper.Status.ANALYZED:
        raise ValidationError("请先分析并保存当前试卷。")
    bounds = []
    for value in (start_year, end_year):
        if value in (None, ""):
            bounds.append(None)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValidationError("年份应为整数。")
        try:
            bounds.append(int(value))
        except (ValueError, TypeError) as exc:
            raise ValidationError("年份应为整数。") from exc
    start_year, end_year = bounds
    if start_year is not None and end_year is not None and start_year > end_year:
        raise ValidationError("起始年份不能晚于结束年份。")
    history = Paper.objects.filter(
        category=paper.category, is_demo=paper.is_demo,
        status=Paper.Status.ANALYZED, year__lt=paper.year,
    ).exclude(pk=paper.pk)
    if start_year is not None:
        history = history.filter(year__gte=start_year)
    if end_year is not None:
        history = history.filter(year__lte=end_year)
    history = history.order_by("year", "pk")
    history_ids = list(history.values_list("pk", flat=True))
    counts = {
        entry["word_id"]: entry["historical_count"]
        for entry in PaperWord.objects.filter(paper_id__in=history_ids).values("word_id").annotate(historical_count=Sum("count"))
    }
    entries = list(paper.paper_words.select_related("word").order_by("-count", "word__lemma", "pk"))
    new_words, known_words, rows = [], [], []
    for entry in entries:
        historical_count = counts.get(entry.word_id, 0)
        is_new = historical_count == 0
        (new_words if is_new else known_words).append(entry)
        rows.append({"entry": entry, "historical_count": historical_count, "is_new": is_new})
    return {
        "history_papers": history, "new_words": new_words, "known_words": known_words, "rows": rows,
        "new_count": len(new_words), "history_count": len(history_ids),
    }


def add_to_study(user, word, source_paper=None):
    _require_user(user)
    if not word.pk:
        raise ValidationError("请选择已保存的单词。")
    if source_paper is not None and not source_paper.pk:
        raise ValidationError("来源试卷尚未保存。")
    return StudyItem.objects.get_or_create(
        user=user, word=word,
        defaults={"source_paper": source_paper, "next_review_at": timezone.now()},
    )


def _existing_review(user, item_id, key, rating):
    log = ReviewLog.objects.select_related("study_item").filter(idempotency_key=key).first()
    if log is None:
        return None
    if log.study_item.user_id != user.pk or log.study_item_id != item_id or log.rating != rating:
        raise ValidationError("重复提交识别码已用于其他用户、项目或评分，请勿重复使用。")
    return log


def submit_review(user, item_id, rating, idempotency_key=None, note=""):
    """只接受本人已到期项目；同一幂等键重试不受新的到期时间限制。"""
    _require_user(user)
    if rating not in ReviewLog.Rating.values:
        raise ValidationError("请选择有效复习评分。")
    try:
        if isinstance(item_id, bool) or not isinstance(item_id, (int, str)):
            raise ValueError
        item_id = int(item_id)
        if item_id <= 0:
            raise ValueError
        key = uuid.uuid4() if idempotency_key is None else uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("学习项目编号或重复提交识别码无效。") from exc
    if not isinstance(note, str) or len(note) > 2000:
        raise ValidationError("复习备注必须为文本且最多 2000 个字符。")
    existing = _existing_review(user, item_id, key, rating)
    if existing:
        return existing
    try:
        with transaction.atomic():
            try:
                item = StudyItem.objects.select_for_update().get(pk=item_id, user=user)
            except StudyItem.DoesNotExist as exc:
                raise PermissionDenied("学习项目不存在或不属于当前用户。") from exc
            existing = _existing_review(user, item_id, key, rating)
            if existing:
                return existing
            now = timezone.now()
            if item.next_review_at > now:
                raise ValidationError("该单词尚未到复习时间，请在到期后复习。")
            previous_level = item.level
            if rating == ReviewLog.Rating.AGAIN:
                new_level, interval = 0, timedelta(minutes=10)
            elif rating == ReviewLog.Rating.HARD:
                new_level = max(0, previous_level - 1)
                interval = timedelta(days=1)
            else:
                increment = 2 if rating == ReviewLog.Rating.EASY else 1
                new_level = min(5, previous_level + increment)
                interval = timedelta(days={0: 1, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}[new_level])
            next_review_at = now + interval
            # 条件更新补足 SQLite 不提供行锁的限制，不允许两个请求同时推进同一状态。
            changed = StudyItem.objects.filter(
                pk=item.pk, user=user, level=previous_level, next_review_at=item.next_review_at,
            ).update(
                level=new_level,
                status=StudyItem.Status.MASTERED if new_level >= 4 else StudyItem.Status.LEARNING,
                next_review_at=next_review_at, updated_at=now,
            )
            if changed != 1:
                raise ValidationError("该学习项目已被其他请求更新，请刷新后重试。")
            log = ReviewLog.objects.create(
                study_item=item, rating=rating, previous_level=previous_level, new_level=new_level,
                next_review_at=next_review_at, reviewed_at=now, note=note, idempotency_key=key,
            )
            return log
    except IntegrityError:
        # 唯一键竞争后必须离开已回滚的事务，再检查所有者和请求内容。
        existing = _existing_review(user, item_id, key, rating)
        if existing:
            return existing
        raise
    except OperationalError as exc:
        if "locked" in str(exc).lower() or (exc.args and exc.args[0] in (1205, 1213)):
            existing = _existing_review(user, item_id, key, rating)
            if existing:
                return existing
            raise ValidationError("另一个请求正在更新学习项目，请稍后刷新重试。") from exc
        raise
