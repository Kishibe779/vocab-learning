import json
import os
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from core import models

BLOCKS=[]
def h(text,level=1):BLOCKS.append({'type':'heading','text':text,'level':level})
def p(text):BLOCKS.append({'type':'paragraph','text':text})
def t(headers,rows,widths=None):
    x={'type':'table','headers':headers,'rows':rows}
    if widths:x['widths']=widths
    BLOCKS.append(x)
def img(name,w,hh,caption=None):BLOCKS.append({'type':'image','path':'图件/'+name+'.png','width':w,'height':hh,'caption':caption or name.replace('_',' ' )})

h('摘要')
p('针对考研英语复习中试卷词汇分散、人工统计耗时、历年新增词不易定位和复习记录缺少连续性的问题，本项目设计并实现“词序”英语词汇学习与复习管理系统。系统采用 Python 与 Django 服务端模板架构，利用数据库保存试卷、词条、词频、关联资料及个人复习进度，形成“录入试卷—分析词汇—比较历史—查询用法—加入词表—复习反馈”的业务闭环。管理员负责公共资料和规则维护，学生负责个人学习。当前运行数据库为 SQLite；MySQL 作为可配置后端尚未完成连接验收。默认英文处理采用明确标注的基础规则词形归一，不将其包装为完整自然语言模型。演示正文与例句均明确标注为原创教学资料，不能代替真实考研语料。')
p('关键词：英语词汇；词频统计；历史对比；Django；复习管理；角色权限')
h('1 项目背景与需求分析')
h('1.1 背景与建设目标',2)
p('在传统词汇复习中，学生往往逐篇阅读试卷、手工摘录陌生单词，并独立查找同源词、近义词、反义词和短语。此方式难以回答“某词在本篇出现几次”“是否在已收录的早年资料中出现”“本人的复习进度如何”等问题。本系统将年度语料、词汇资料和个人学习过程关联起来，帮助学生以可追溯的上下文学习词汇。统计结论严格限定于系统已收录且已分析的资料，不声称覆盖全部历年真题。')
p('建设目标包括：建立可查询的年度试卷资料；对无复习意义的功能词进行排除并统计有效词频；以同类别的较早年份资料为基线定位新增词；保存词汇关系与典型用法；以个人词表和复习日志实现持续学习；通过后端角色与对象归属检查保证多人使用时的数据隔离。')
h('1.2 用户与职责',2)
t(['角色','职责','限制'],[['游客','登录、注册学生账号','不能访问业务页面'],['学生','查询试卷、词频、历史对比、词条资料；维护本人词表与复习记录','不能执行公共资料管理写操作；不能读写他人的个人记录'],['管理员','录入和分析试卷；维护词条、关联、短语、例句、停用规则；后台用户管理','不能把演示资料冒称真题；派生词频、学习状态和复习日志后台只读']])
h('1.3 功能结构与用例模型',2)
img('图1_系统功能结构图',1800,1000)
p('图1按业务职责划分八个模块；注册与登录仅为基础服务，不计入课程要求的六个业务模块。所有业务由单一 core 应用承载，功能划分不等于微服务或多个 Django 应用。')
img('图2_UML用例图',1800,1400)
p('图2以系统边界、参与者、椭圆用例和关联表示权限。管理员继承学生的个人学习访问能力，并额外承担管理用例；普通学生没有管理写权限。图中泛化表达角色权限关系，不表示源码中存在角色类继承。')
h('1.4 核心用例',2)
usecases=[('UC01 录入并分析试卷','管理员','已登录管理员；数据库可写；选择的分析引擎可用','填写标题、年份、英语类别、来源、演示标记；粘贴正文或上传UTF-8 TXT；表单通过后保存待分析试卷；在详情页提交分析；服务读取停用词，计算归一词形与频次；事务保存词条、词频并更新分析状态；页面显示原词形和上下文。','错误年份、非UTF-8、文件超限、同时粘贴与上传、无英文正文返回错误；学生请求拒绝；引擎资源缺失明确提示；正文在分析中变更时拒绝旧结果；数据库写入失败回滚。','试卷状态为已分析，词频真实持久化；重新分析替换旧频次而不累计。'),('UC02 历年新增词查询与加入词表','学生或管理员','已登录；目标试卷已分析','进入目标试卷历史对比；可选历史起止年份；筛选同英语类别、同演示标记、严格较早年份的已分析试卷；汇总历史词频；标记历史频次为零的当前范围新词；查询词条资料；提交加入本人词表；系统按用户和词条去重。','目标未分析或年份倒序提示错误；无历史基线明确标注；未来年份、英语另一类别、演示与真实集合不混用；重复加入保留原进度；来源试卷不包含该词则拒绝。','个人词表新增一条立即到期的学习项；对比结果保留历史资料范围。'),('UC03 到期复习与记录','学生或管理员','本人存在到期学习项','打开到期复习页，先回忆再展开释义与例句；选择忘记、困难、记住或轻松；提交评分与UUID；服务验证归属、到期时间和幂等标识；事务更新等级、学习状态、下一次日期并写日志；返回复习列表并在历史页查看记录。','无到期词显示空状态；他人编号拒绝；未到期不能提交；评分或UUID无效提示错误；同UUID同对象同评分重试返回原记录；冲突请求拒绝，不重复推进。','一条复习日志与一次状态更新一致保存，刚复习词离开当前到期队列。')]
for title,role,pre,flow,error,result in usecases:
    h(title,3);t(['要素','描述'],[['参与角色',role],['前置条件',pre],['主要流程',flow],['异常/特殊情况',error],['结果',result]],[1500,6806])
h('1.5 非功能需求与实现边界',2)
t(['编号','需求与验证方法','当前证据/限制'],[['NFR01 数据准确性','词频等于可复现归一后计数；重复分析不翻倍；学习加入去重；复习日志和状态一致','自动化案例验证指定样本；规则归一不保证所有英语词正确还原'],['NFR02 安全与隔离','注册固定学生；管理写操作服务端检查；个人记录按当前用户过滤；CSRF与输出转义','按权限和错误输入测试验收；并不等于公网安全审计'],['NFR03 稳定性','分析与复习使用数据库事务，失败不产生半份结果；幂等处理重复提交','SQLite自动化验证；MySQL行锁与高并发尚未验证'],['NFR04 易用性','中文页面、空状态、反馈、字段校验；资料→词条→学习→复习可连续操作','页面实现存在；尚需教师现场及人工设备体验'],['NFR05 可复现性','已有迁移、依赖锁定、初始化与启动文档；不依赖外部AI接口或CDN','本机已启动；其他成员干净环境需按README复现']])
p('已实现范围为文本/TXT录入、词频与历史集合比较、人工或JSON维护词汇关系及用法、个人学习清单与复习。暂不实现PDF/扫描件OCR、自动联网词典补全、音频、考试预测、即时通讯、生产公网部署或复杂记忆模型；这些不是第1题明确必需项。真实词典和试卷来源由资料提供者确认，系统不生成虚假引文。')
h('2 总体设计与模块设计')
h('2.1 技术方案与架构',2)
img('图6_系统总体架构图',1550,1200)
p('浏览器请求先经过会话、认证和CSRF中间件，路由进入 core/views.py；表单负责输入校验，服务函数处理词汇算法与事务，models.py通过Django ORM访问数据库。Django模板返回真实数据库内容，static提供本地样式和交互。当前默认SQLite数据库是项目文件db.sqlite3，具有真实持久化能力；MySQL连接分支提供utf8mb4及严格模式配置但尚未验收。')
h('2.2 各模块职责',2)
t(['模块','主要页面/入口','核心对象'],[['试卷管理','paper_list/create/edit/detail；papers模板','Paper'],['有效词分析','paper_analyze；lexical_analysis/analyze_paper','Word、PaperWord、StopWord'],['历史对比','paper_compare；compare_paper','Paper、PaperWord'],['词汇关系','word_list/detail；relation_create','Word、WordRelation'],['短语与用法','phrase_create/example_create；lexicon_import','Phrase、UsageExample'],['个人学习','study_add/list/remove；add_to_study','StudyItem'],['复习管理','review_list/submit/history；submit_review','StudyItem、ReviewLog'],['规则与后台','stopword_list/create/toggle；Django Admin','StopWord、User及公共资料']])
img('图8_模块结构图',1650,1000)
p('models、forms、views、services、admin相互配合，而不是另建Controller或Repository类。初始化命令seed_demo只建立明确标记的演示资料，并保留已有账号密码与进度；不将初始化状态伪造为真实复习日志。')
h('2.3 业务状态与规则',2)
p('试卷状态为draft/analyzed。正文变化清除旧词频并回到待分析，单独修改标题等元数据不清统计。每个词以小写lemma为基本词形；原始大小写词形及其次数保存在JSON中。停用词由固定内置集合加数据库启用规则组成；停用词配置变化不自动更新已分析试卷，需要重新分析。比较前应人工统一规则，避免混用不同口径。')
p('学习状态为new/learning/mastered。新加入立即到期；忘记回到等级0、10分钟后重试；困难降低一级且1天后；记住加一级、轻松加两级，最高5级。记住/轻松根据新等级安排1、3、7、14、30天；等级4及以上为mastered，仍保留未来复习。反馈是用户掌握自评，不是自动判卷。')
h('3 数据库设计')
h('3.1 实体关系与表数量',2)
img('图5_数据库ER图',2100,2000)
p('自定义User之外有9张独立业务表，均不少于6字段，未把会话、权限及迁移等框架表用于凑数量。Paper与Word通过PaperWord保存带频次的多对多关系；User与Word通过StudyItem保存个人进度；ReviewLog从学习项确定归属。WordRelation当前为有向资料关系，详情显示word端记录，不能声称自动推导双向或传递关系。')
entities=[models.User,models.Paper,models.Word,models.PaperWord,models.WordRelation,models.Phrase,models.UsageExample,models.StopWord,models.StudyItem,models.ReviewLog]
t(['实体','实际表名','实体列数'],[[m.__name__,m._meta.db_table,str(len(m._meta.fields))] for m in entities])
h('3.2 完整数据字典',2)
p('以下为Django逻辑字段类型，不将其冒称SQLite物理VARCHAR定义。NULL与表单blank不同：允许留空的文本一般存空字符串，只有null=True的字段可存NULL。id为BigAutoField主键；外键物理列带_id后缀。用户password为哈希字段，不在报告中保存账号明文口令。')
for model in entities:
    h(model.__name__+'（'+model._meta.db_table+'）',3)
    rows=[]
    for f in model._meta.fields:
        kind=f.get_internal_type()
        if getattr(f,'max_length',None):kind+='('+str(f.max_length)+')'
        flags=[]
        if f.primary_key:flags.append('主键')
        elif f.unique:flags.append('唯一')
        flags.append('可NULL' if f.null else '非NULL')
        if getattr(f,'auto_now_add',False):flags.append('创建时自动')
        if getattr(f,'auto_now',False):flags.append('更新时自动')
        if f.is_relation:
            flags.append('外键→'+f.related_model.__name__)
            flags.append(f.remote_field.on_delete.__name__)
        if f.choices:flags.append(' / '.join(str(a)+':'+str(b) for a,b in f.choices))
        rows.append([f.column,str(f.verbose_name),kind,'；'.join(flags)])
    t(['字段','含义','逻辑类型','约束/说明'],rows,[1800,1450,1750,3306])
    cons=[c.name for c in model._meta.constraints]
    if cons:p('数据库约束：'+ '、'.join(cons)+'。')
    if model.__name__=='UsageExample':p('模型clean额外验证：指定短语须属于同一单词，且kind应为phrase；这是模型/表单层校验，不是跨表数据库CHECK。')
h('3.3 数据一致性与删除行为',2)
p('同试卷同词仅一条词频，同用户同词仅一条学习项，幂等UUID唯一。词汇关系禁止自身关联；记忆等级限定0—5。来源试卷和资料创建者可置空以避免无关资料删除破坏学习。删除StudyItem会级联删除该项ReviewLog，这是当前数据保留限制，操作前必须确认，后续可改为归档。分析结果在同一事务替换，避免频次只有部分写入。')
h('4 页面与核心业务详细设计')
h('4.1 页面与业务对应',2)
t(['页面','功能/输入','数据输出'],[['登录/注册','会话认证；注册固定student','本人身份及角色菜单'],['学习概览','查询公共数量及个人到期','真实试卷/词条/学习数与最近记录'],['阅读资料列表与详情','查询、年份分类；正文录入/分析','Paper、PaperWord、原词形及上下文'],['历史对比','目标试卷及历史年份范围','本篇与历史频次、新词标记、基线范围'],['词汇索引/详情','词条检索与维护','释义、root、关联、短语、用法来源'],['词库导入','带source的UTF-8 JSON','整批校验后更新资料或整批回滚'],['我的词表','本人查询、添加/移除','学习状态、等级和下次日期'],['到期复习/历史','展开释义，四档反馈与UUID','调整后的等级、日期和复习日志'],['停用词/管理后台','管理员维护规则及公共数据','启用状态；用户和词汇资料']])
p('主要页面采用纸感浅色、墨绿强调色与本地字体，统一导航、反馈和空状态。管理员按钮隐藏仅改善体验，真正权限由后端装饰器和服务检查实现。页面目前没有列表分页；复习最多100项、历史最多300项，不能将这些界限写成无限查询能力。')
h('4.2 试卷分析详细流程',2)
img('图3_试卷分析业务流程图',1450,1650)
p('PaperForm对年份、文件扩展名、UTF-8编码、1MiB文件大小、20万字符正文、空字符和英文内容进行校验。lexical_analysis先取英文tokens，统一小写和弯撇号，再进行小规模不规则映射及已知基础词限定的词尾变换，排除内置和自定义停用词，累积lemma频次。forms保留原词形，contexts保存最多三条去重语境，长句截断。analyze_paper计算完成后锁定试卷再次比较正文，批量补足未知Word但不编造释义，再事务替换PaperWord。')
p('从需求到实现：UC01对应录入/详情页面，数据落在Paper、Word、PaperWord与StopWord；核心代码为core/forms.py:PaperForm和core/services.py:lexical_analysis/analyze_paper。当前没有自动查词典或自动生成词根关系；这些数据由管理员或JSON导入。')
h('4.3 历史对比算法',2)
p('设目标试卷有效词集合为C，筛选范围内严格早于目标年份的同类别且同is_demo历史词集合为H，则当前范围新增词为C−H。历史频次按Word ID汇总所有选中历史PaperWord.count，不是某词出现过的试卷数量。当前实现比较一份目标试卷，不自动合并目标年全部试卷。无历史时会标记当前范围词，但页面必须说明没有基线，不表示真题中首次出现。')
h('4.4 学习与复习详细流程',2)
img('图4_学习复习业务流程图',1350,1600)
img('图7_核心复习功能时序图',1750,1450)
p('review_submit先按本人学习编号取对象并验证UUID；submit_review查询已有幂等日志，进入事务锁定本人学习项，检查是否到期，计算新等级和日期，按原等级与原到期时间条件更新，再创建日志。条件更新为SQLite缺少SELECT FOR UPDATE行锁提供冲突防护，但不构成已完成高并发实测的证据。重复UUID若对象或评分不同会拒绝；同对象同评分返回已有日志。')
p('本流程覆盖需求UC03、两张流程/时序图、到期复习和历史页面、StudyItem/ReviewLog表以及submit_review代码。记录结果来自实际用户提交；初始化只创建示例学习状态，不生成虚假的历史评分。')
h('5 软件实现与部署说明')
h('5.1 关键实现与权限',2)
p('注册表单只接受用户名、显示名称、邮箱和密码，保存时强制student，忽略客户端伪造的角色权限。admin_required先要求登录再校验管理员；分析服务再次校验角色。学习查询、删除、复习和历史按request.user过滤，不能根据请求中的user_id改变归属。写操作采用POST和CSRF，模板对纯文本自动转义，ORM参数化访问数据库。')
p('JSON资料导入限定顶层1—1000词条、UTF-8及1MiB，每个lemma小写且source非空。先建立全批词条，再处理关系、短语和例句，因此关联词可以在同批定义。未知字段、非法关系或模型约束异常回滚整批。真实来源未到位时显示未补充，不自动生成权威词典引文。')
h('5.2 本地运行与安装使用',2)
p('项目主程序为manage.py，依赖见requirements-lock.txt。另一台电脑重新创建.venv并安装锁定依赖，执行manage.py migrate、manage.py seed_demo，再以runserver 127.0.0.1:8000启动。已有迁移不需首次再makemigrations。PyCharm须选择项目.venv/Scripts/python.exe，以manage.py为脚本、runserver 127.0.0.1:8000为参数、项目目录为工作目录。管理员/学生演示账号仅见组内README，不将明文密码放进正式报告。')
p('SQLite保存为db.sqlite3，关闭服务后可复制纯演示数据库交接；真实个人资料不可随意分享。切换MySQL必须有独立项目库和有效账号，配置字符集后迁移；两种数据库数据不自动迁移。本项目使用本地开发服务器，运行警告正常但不适用于公网正式部署。详细步骤见项目README与程序功能说明.txt。')
h('6 软件测试与验收记录')
h('6.1 对象、环境与方法',2)
p('测试对象包括模型约束、文本分析、历史范围、资料导入、角色权限、个人词表和复习服务。环境为Windows11、Python3.13、Django5.2系列与SQLite隔离测试数据库；测试运行时禁用本机.env并强制SQLite，避免读取真实密码及修改db.sqlite3。方法包括Django TestCase/Client、算法指定输入输出校验、正常/异常表单、越权请求、事务和幂等用例。执行者标注自动化工具，不冒充三名学生现场执行。')
results=ROOT/'测试证据'/'自动测试记录.json'
if results.exists():
    testdata=json.loads(results.read_text(encoding='utf-8'))
    p('实际执行证据见测试证据目录；以下结果从本次自动化记录提取，不将设计预期直接写作通过。')
    runs=testdata.get('runs',[]) if isinstance(testdata,dict) else []
    latest=runs[-1] if runs else testdata
    if runs:
        for run in runs:
            p(f"第{run['run_number']}轮：执行{run['total']}项，结果{run['summary']}，退出码{run['exit_code']}；时间{run['completed_at']}。")
        if len(runs)>1:
            p('首轮TC57失败：含短语的同一JSON重复导入被唯一约束误拒绝。第一次补丁仅赋已有主键，Django仍将候选视为新对象，第二轮仍失败。最终修正core/views.py：在已有实例上校验候选字段但不保存，合法重复资料去重，非法字段仍拒绝；第三轮全量回归结果见下表。前两轮失败日志均保留。')
    rows=latest if isinstance(latest,list) else latest.get('cases',latest.get('tests',[]))
    for i,row in enumerate(rows):
        if not isinstance(row,dict):continue
        get=lambda *ks:next((str(row[k]) for k in ks if k in row),'')
        state=get('actual_status','status','result')
        state_label={'PASS':'通过','FAIL':'未通过','ERROR':'运行错误','NOT_RUN':'未执行'}.get(state,state)
        t(['字段','内容'],[['编号',get('编号','id','tc_id') or f'TC{i+1:02d}'],['功能',get('功能','feature','function','module','name')],['操作或输入',get('操作或输入','steps_input','steps','input','operation','操作')],['预期结果',get('预期结果','expected','expected_result')],['实际结果',get('实际结果','actual','actual_result','status')],['是否通过',state_label],['自动化方法',get('test_method','method','test_id')]], [1500,6806])
    p('结果汇总以原始运行日志和自动测试记录为准。未通过项及修正说明随测试证据保留；即使自动化通过，也不能替代MySQL专项、浏览器设备操作和教师现场抽查。')
else:
    p('本次自动化任务尚未返回，测试结果暂不填写通过。正式测试记录将由实际日志补充；仅此前本机启动、登录与页面HTTP可达性已核验。')
h('6.2 未执行项与验收限制',2)
t(['检查','状态','原因/后续'],[['MySQL实际连接、迁移及行锁','未执行','当前SQLite运行；需要有效独立数据库配置'],['WordNet语料及全量词形准确性','未执行','当前rule；尚未提供词典语料和完整金标准'],['浏览器多设备视觉/交互','待人工复核','本轮后端自动化不能替代真实设备截图'],['教师现场主要功能抽查','待执行','由教师现场验证'],['学校报告模板对齐','待提供模板','目前为规范A4学术草稿，不冒称学校指定格式'],['真实考研语料覆盖','待补资料','原创演示不能代替授权真题历史库']])
h('7 进度安排、分工与成果提交')
h('7.1 周进度建议',2)
t(['周次','任务','应留下的证据'],[['第1周','选题、角色、任务分工','教师审核与分工记录'],['第2—5周','需求、架构、数据库和界面设计','用例、图、数据字典与评审记录'],['第6—9周','试卷/词库/权限基础实现','可运行版本与模块说明'],['第10—12周','中期闭环演示与问题整理','中期检查意见、修正记录'],['第13—15周','复习闭环、联调和测试','真实测试日志、回归记录'],['第15—18周','报告、验收与答辩','每人报告、程序和说明文件']])
p('任务书总安排写第1—18周，而过程段写第15—19周文档与答辩，最终截止应以教师通知为准。上述为计划，不伪造成已发生的每周考勤或会议。已生成代码不能替代学生实际参与与理解。')
h('7.2 三人分工与个人报告区分',2)
t(['成员占位','建议模块','个人报告应突出'],[['成员A（姓名学号待填）','试卷与文本分析、历史对比','分词归一、频次与历史边界、事务；亲自执行的测试与修改'],['成员B（姓名学号待填）','词库、关系、短语、用法和导入','资料来源、约束、整批回滚与检索；实际核验和完善'],['成员C（姓名学号待填）','个人学习、复习、权限和集成','归属隔离、到期规则、UUID幂等；实际测试与演示']])
p('以上只是建议分工。三份个人报告提供不同技术重点，但真实贡献必须由成员本人根据实际阅读、复现、测试、修改和协作填写；不得把AI生成的初版描述为某成员独立手写代码。每人须能解释输入输出、相关数据表、一个异常分支和一条实际测试。')
h('7.3 提交清单与要求对应',2)
t(['任务书要求','本项目对应材料','状态'],[['源程序（小组一份）','项目源码、迁移、模板、静态资源、依赖锁','已生成'],['功能说明.txt（小组一份）','项目程序功能说明.txt、README','已有；版本变化应同步'],['个人报告（每人一份）','本目录三份个人侧重稿','真实姓名、学号、贡献待本人补充'],['需求分析','本报告第1章：背景、角色、结构、3用例、NFR、范围','已写'],['工程图8张','图1—图8，PNG及可编辑JSON/绘图源码','已绘制并嵌入'],['总体/模块/数据库/页面与核心流程','第2—5章','依据现有实现'],['8表以上且每表6字段','第3章9业务表+用户表、完整字典','结构符合'],['6模块、角色与闭环、真实数据库','第1、2、4、5章及实现','待结合动态测试及现场验收'],['不少于15测试用例及结果','第6章与测试证据','从真实自动化运行记录生成']])
h('8 总结与改进方向')
p('项目以成熟的Django认证、表单与ORM实现可理解的本地词汇学习系统。核心价值不在于展示大量静态词条，而在于试卷词汇与年度范围、来源资料、个人学习进度之间的连接。设计在角色边界、去重和事务方面保留明确规则，并如实披露词形算法与资料覆盖限制。后续应根据实际试卷样本评估词形准确性、补充有来源词库、统一分析配置，完善分页与学习项归档，在授权MySQL环境进行专项验证，最后按教师模板和个人真实贡献形成提交版本。')
h('参考资料')
for ref in ['[1] 《企业课程1-3》任务书，26—27—1学期，用户提供文本。','[2] Django Software Foundation. Django 5.2 Documentation. https://docs.djangoproject.com/en/5.2/（框架参考，不冒称本轮联网审阅）。','[3] Python Software Foundation. Python 3.13 Documentation. https://docs.python.org/3.13/。','[4] NLTK Project. NLTK Documentation. https://www.nltk.org/（WordNet为可选配置，当前未启用）。','[5] 本项目core/models.py、services.py、forms.py、views.py及迁移文件，报告生成时静态核对。']:p(ref)

cover=['课程：《企业课程1-3》','学期：26—27—1；班级：23220196051-2（具体班级待确认）','小组成员：姓名、学号待补充；指导教师：待补充','版本：本地SQLite运行版本；原创演示资料','报告状态：验收草稿，学校模板及个人信息待补充','生成日期：'+str(date.today())]
def markdown(data):
    lines=['# '+data['title'],'',data['subtitle'],'']+data['cover']+['']
    for b in data['blocks']:
        if b['type']=='heading':lines+=['#'*(b['level']+1)+' '+b['text'],'']
        elif b['type']=='paragraph':lines+=[b['text'],'']
        elif b['type']=='image':lines+=['!['+b['caption']+']('+b['path']+')',b['caption'],'']
        elif b['type']=='table':
            clean=lambda s:str(s).replace('|','/').replace('\n','<br>')
            lines+=['| '+' | '.join(map(clean,b['headers']))+' |','| '+' | '.join(['---']*len(b['headers']))+' |']
            lines+=['| '+' | '.join(map(clean,row))+' |' for row in b['rows']];lines+=['']
    return '\n'.join(lines)

def emit(stem,blocks,title,subtitle):
    data={'title':title,'subtitle':subtitle,'cover':cover,'blocks':blocks}
    (ROOT/(stem+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/(stem+'.md')).write_text(markdown(data),encoding='utf-8')

emit('00_项目综合验收报告',BLOCKS,'英语词汇学习与复习管理系统\n课程设计综合验收报告','词序 / LEXIS · 按任务书需求与实际实现编写')
base=list(BLOCKS)
focus=[('A','试卷分析与历年对比','core/forms.py:PaperForm；core/services.py:lexical_analysis、analyze_paper、compare_paper','Paper、Word、PaperWord、StopWord','解释有效词与停用词；指定正文手工核对count与forms；比较不同年份、类别和is_demo；复核重复分析不翻倍；理解正文变化后为何需要重新分析。'),('B','词库资料、词汇关系与用法管理','core/models.py:WordRelation、Phrase、UsageExample；core/views.py:lexicon_import、related_form','Word、WordRelation、Phrase、UsageExample','核验释义与资料来源；实际维护同源/近反义关系、短语和词/短语例句；理解有向关系限制；设计带来源JSON并检验失败整批回滚；不把原创例句冒称词典引文。'),('C','个人学习、复习调度与权限集成','core/services.py:add_to_study、submit_review；core/views.py:study_list、review_submit、review_history','User、StudyItem、ReviewLog','用两个独立学生账号验证隔离；解释四档自评和间隔；检查UUID重试不重复日志；验证未到期和他人编号拒绝；理解状态更新与日志事务及SQLite并发限制。')]
for member,topic,code,tables,work in focus:
    blocks=[{'type':'heading','level':1,'text':'个人侧重与真实贡献填写说明'},{'type':'paragraph','text':f'本稿为成员{member}的技术侧重草稿，重点为“{topic}”。公共章节保留完整系统背景与八张工程图。姓名、学号和实际贡献没有提供，保留待填，不伪称该成员独立编写或执行了自动化测试。'},{'type':'table','headers':['个人重点','内容'],'rows':[['建议负责模块',topic],['应理解代码',code],['相关数据表',tables],['建议本人实际操作',work],['实际完成工作','待本人填写具体修改、资料整理、测试、协作事项及证据'],['遇到问题与解决过程','待本人结合实际经历填写'],['个人总结','待本人写出对模块设计、异常处理和协作的理解']]},{'type':'paragraph','text':'答辩准备：说明一个正常流程、一个失败分支、一个数据库约束及一条本人实际验证结果。不要只背诵方法名或把大量源码作为报告主体。'}]+base
    emit('0'+str(ord(member)-ord('A')+1)+'_成员'+member+'_课程设计报告草稿',blocks,'英语词汇学习与复习管理系统\n成员'+member+'课程设计报告',topic+' · 个人重点稿（身份与实际贡献待补充）')
test_start=next(i for i,b in enumerate(BLOCKS) if b.get('text')=='6 软件测试与验收记录')
test_end=next(i for i,b in enumerate(BLOCKS) if b.get('text')=='7 进度安排、分工与成果提交')
emit('04_软件测试报告',BLOCKS[test_start:test_end],'英语词汇学习与复习管理系统\n软件测试报告','SQLite隔离自动化测试 · 真实三轮记录及修复回归')
print('Wrote comprehensive report, 3 member drafts, and standalone test report (JSON/Markdown).')
