# 词序 · 英语词汇学习与复习系统

课程设计第1题，Python/Django 服务端模板项目。当前先构建并启动应用，完整测试记录及课程设计报告在系统运行后补充，不能把尚未执行的测试写成通过。

## 给同组成员：先看这里

这是浏览器访问的 Web 项目，不是双击 `manage.py` 就能打开的软件。默认采用 SQLite，**先运行这一版不需要配置 MySQL**。

- 项目入口：`manage.py`。
- 网站地址：**http://127.0.0.1:8000/**。
- 管理后台：**http://127.0.0.1:8000/admin/**。
- 请保持启动窗口运行；关闭窗口或按 `Ctrl+C` / `Ctrl+Break` 后，网站停止。
- 这里的 `127.0.0.1` 指运行项目的那台电脑，不是所有成员共同访问的远程网站。

### 演示账号和密码（仅限组内本地测试）

| 角色 | 用户名 | 初始测试密码 |
|---|---|---|
| 管理员 | `admin` | `z-1LNx-jPeWZFHDHWW65ZsmQwB1PFahj` |
| 学生 | `student` | `aYIA__HIrmRSBrppUikm2LdfsrSwwFPa` |

**以上仅是本项目演示账号，不是 MySQL 登录信息。** 密码区分大小写，复制时不要包含空格。此文档按组内测试需求记录明文演示密码；不要公开发布带有这些密码的项目，正式使用前请更换密码并移除本节凭据。

两种交接情况：

1. **拿到当前 `db.sqlite3` 的副本**：账号已保存在数据库里，上述密码适用于本次初始化的账号（前提是没有改过密码）。复制数据库前，先停止运行中的项目。文件副本包含演示用户与学习记录，不要混入真实个人资料后随意分享。
2. **只拿到源码，没有 `db.sqlite3`**：按下面“另一台电脑首次运行”执行，并明确指定上面的初始演示密码。否则 `seed_demo` 会生成新的随机密码，和此表不同。

### A. 在本机继续运行

这台电脑已完成依赖安装、数据库迁移和演示初始化：

1. 打开 `E:\CompanyCourse\vocab_learning`。
2. 双击 **`启动项目.bat`**，等待出现 `Starting development server`。
3. 浏览器打开上述地址，用管理员或学生账号登录。

如果提示端口已被占用，可能网站已经在运行，先直接访问地址，不要重复启动。完整业务测试尚未完成，能打开页面不代表所有功能已验收。

### B. 另一台电脑首次运行（Windows）

**不要直接使用从其他电脑复制来的 `.venv`**：虚拟环境包含本机路径，应在自己的电脑重新创建。建议安装 Python 3.13；首次安装依赖需要网络。

1. 解压项目到任意自己的目录，例如 `D:\Course\vocab_learning`。
2. 在包含 `manage.py` 的目录打开 PowerShell：可在文件夹地址栏输入 `powershell` 后回车。
3. 执行以下命令（每行执行完再执行下一行）：

```powershell
# 检查 Python。若找不到 py，请安装 Python，或用自己的 python.exe 完整路径替代 py -3.13。
py -3.13 --version
py -3.13 -m venv .venv

# 使用项目虚拟环境，不必执行 Activate.ps1。
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements-lock.txt

# 项目已包含迁移文件，只需 migrate，不必重新 makemigrations。
.\.venv\Scripts\python.exe manage.py migrate

# 仅指定新建演示账号的初始密码；这不会重置数据库中已有账号。
$env:DEMO_ADMIN_PASSWORD = 'z-1LNx-jPeWZFHDHWW65ZsmQwB1PFahj'
$env:DEMO_STUDENT_PASSWORD = 'aYIA__HIrmRSBrppUikm2LdfsrSwwFPa'
.\.venv\Scripts\python.exe manage.py seed_demo
Remove-Item Env:DEMO_ADMIN_PASSWORD
Remove-Item Env:DEMO_STUDENT_PASSWORD

# 启动网站，然后在浏览器访问 http://127.0.0.1:8000/。
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

依赖从 PyPI 安装 Django、NLTK、python-dotenv、mysqlclient 等，以 `requirements-lock.txt` 锁定版本。不必安装 Java、Node.js 或 MySQL 来启动默认 SQLite 版本。

若复制的是包含已有数据库的项目，`seed_demo` 会保留已有密码和学习进度；上述环境变量**只影响新建账号**。如果已经用随机密码初始化过，不要删除数据库解决登录问题：使用当时输出的密码，或在本机交互执行 `manage.py changepassword admin` / `manage.py changepassword student`，并更新组内测试说明。

### 建议第一次操作顺序

**管理员：**

1. 进入“阅读资料”，查看 2022、2023、2024 的原创演示试卷。
2. 打开详情，查看有效词频、原词形和上下文。
3. 打开 2024 资料的历史对比，查看与较早年份的新增词。
4. 在“词汇索引”搜索 `develop`，查看同源词、短语及例句；搜索 `increase` 查看反义关系。
5. 尝试录入自己的英文正文，保存后执行分析。
6. 在词条详情补充释义、关系、短语和例句；在停用词管理中维护规则。

**学生：**

1. 查询试卷、历年对比和词汇详情。
2. 点击“加入词表”，在“我的词表”查看本人记录。
3. 进入“到期复习”，点击显示释义，再提交“忘记/困难/记住/轻松”反馈。
4. 查看“复习记录”和更新后的下次复习时间。刚复习过的词会离开到期队列，这不是数据丢失。
5. 学生没有管理写权限；多人测试个人数据隔离时，各自在注册页创建不同学生账号，不要都共用 `student`。

### 常见问题

| 现象 | 如何处理 |
|---|---|
| 浏览器无法访问 | 确认启动窗口仍在运行，并检查地址和端口。 |
| 8000 端口已被占用 | 先检查现有网站；或用 `runserver 127.0.0.1:8001` 启动，再访问 8001。不要关闭不属于本项目的进程。 |
| `No module named django` | 用 `.venv\Scripts\python.exe` 运行，不要用系统或 Anaconda 的其他解释器；检查依赖是否安装成功。 |
| 提示表不存在 | 在项目目录执行 `.\.venv\Scripts\python.exe manage.py migrate`。 |
| 登录失败 | 检查密码空格/大小写，以及是否曾初始化其他随机密码或修改密码；`seed_demo` 不重置已有密码。 |
| 找不到 `py` | 用本机 Python 的完整路径替代；原电脑 `E:\python\python.exe` 路径不一定适用于你。 |
| 默认提示开发服务器警告 | 本地课程开发属于正常用途，该提示不是启动错误。 |
| 词条没有释义或关系 | 自动分析只提取词汇；资料尚未维护时会显示缺失，由管理员补充。 |

### 可选：切换 MySQL

默认 SQLite 数据真实保存到 `db.sqlite3`。MySQL 切换需要确认可用账号及独立项目库，不擅自重置密码或修改旧库。复制 `.env.example` 为 `.env`，设置 `DB_ENGINE=mysql` 及相应连接信息，创建专用 utf8mb4 数据库后再执行迁移和初始化。不要共享包含数据库口令的 `.env`；SQLite 与 MySQL 数据不自动互通。**目前 MySQL 连接未验证。**

## 功能

- 管理员：试卷文本/TXT录入、分析、编辑；词汇资料、词根/同义/反义关系、短语和用法维护；JSON词库导入；停用规则；用户管理后台。
- 学生：试卷查询、有效词频、历年新增词比较、词汇关系及例句短语查询、个人学习清单、到期复习、复习历史。
- 登录/注册和菜单之外，所有写接口均有后端权限校验；个人学习资料按用户隔离。
- 原创示例明确标注“演示”，不是实际考研试卷；真实试卷与词典资料需自行确认出处并录入。

## 文本处理限制

首版默认 `ANALYSIS_ENGINE=rule`，页面明确标注基础规则词形归一（非完整NLP）。英文正则分词、常见词形规则及小规模不规则词映射用于可解释的起步方案，不承诺所有英文词正确还原。

可设置 `ANALYSIS_ENGINE=wordnet` 使用 NLTK WordNet 词形归一；必须先准备本机 WordNet 资源，缺失时明确报错，不联网下载或静默回退。正式验收前需要针对选定引擎执行词形、停用词和对比测试。

新增词比较基于同英语类别、同演示/非演示集合、严格早于目标年份且已分析的试卷。没有历史试卷时只能说明缺少基线，不能宣称词汇从未在其他真题出现。更改分析规则后，应对参与比较的试卷重新分析。

## 词库导入

UTF-8 JSON 数组，每个词条必须有 lemma 和 source。示例结构：

```json
[
  {
    "lemma": "develop",
    "meaning": "发展；开发",
    "pos": "v.",
    "root": "develop",
    "source": "原创教学演示，非词典引文",
    "relations": [{"lemma": "development", "type": "root", "explanation": "develop 的名词派生词", "source": "人工整理演示"}],
    "phrases": [{"text": "develop a habit", "meaning": "养成习惯", "example": "Students develop a habit of reviewing words.", "translation": "学生养成复习单词的习惯。"}],
    "examples": [{"text": "Students develop practical skills through projects.", "translation": "学生通过项目培养实践技能。"}]
  },
  {"lemma": "development", "meaning": "发展", "source": "原创教学演示，非词典引文"}
]
```

关联词必须已存在或在同批资料中定义；单个错误会回滚整批。释义、词汇关系和例句是资料维护，不是自动伪造的词典结果。

## 安全与提交

仅本地运行 Django 开发服务器，不用于公网部署。不得提交 `.env`、虚拟环境、数据库口令、个人真实密码或未经许可的试卷资料。本 README 中的演示密码是按组内交接要求保留的测试凭据，仅限封闭小组测试；公开源码、正式提交或对外部署前，应更换演示密码并删除本文中的明文凭据及对应初始化示例值。学校模板与三名成员实际贡献未确认时，报告不得虚构。
