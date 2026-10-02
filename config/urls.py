from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("papers/", views.paper_list, name="paper_list"),
    path("papers/create/", views.paper_create, name="paper_create"),
    path("papers/<int:pk>/", views.paper_detail, name="paper_detail"),
    path("papers/<int:pk>/edit/", views.paper_edit, name="paper_edit"),
    path("papers/<int:pk>/analyze/", views.paper_analyze, name="paper_analyze"),
    path("papers/<int:pk>/compare/", views.paper_compare, name="paper_compare"),
    path("words/", views.word_list, name="word_list"),
    path("words/create/", views.word_create, name="word_create"),
    path("words/import/", views.lexicon_import, name="lexicon_import"),
    path("words/<int:pk>/", views.word_detail, name="word_detail"),
    path("words/<int:pk>/edit/", views.word_edit, name="word_edit"),
    path("words/<int:pk>/relations/add/", views.relation_create, name="relation_create"),
    path("words/<int:pk>/phrases/add/", views.phrase_create, name="phrase_create"),
    path("words/<int:pk>/examples/add/", views.example_create, name="example_create"),
    path("words/<int:pk>/study/", views.study_add, name="study_add"),
    path("study/", views.study_list, name="study_list"),
    path("study/<int:pk>/remove/", views.study_remove, name="study_remove"),
    path("review/", views.review_list, name="review_list"),
    path("review/<int:pk>/submit/", views.review_submit, name="review_submit"),
    path("review/history/", views.review_history, name="review_history"),
    path("management/stopwords/", views.stopword_list, name="stopword_list"),
    path("management/stopwords/create/", views.stopword_create, name="stopword_create"),
    path("management/stopwords/<int:pk>/toggle/", views.stopword_toggle, name="stopword_toggle"),
]
