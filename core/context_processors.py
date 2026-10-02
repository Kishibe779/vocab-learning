from django.conf import settings
from .services import is_admin


def site_context(request):
    label = "WordNet 词形归一" if settings.ANALYSIS_ENGINE == "wordnet" else "基础规则词形归一（非完整 NLP）"
    return {"is_admin": is_admin(request.user), "analysis_engine_label": label}
