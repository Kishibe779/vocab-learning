from pathlib import Path
import json
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "图件"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "C:/Windows/Fonts/msyh.ttc"
DARK, LINE, PALE = "#173b32", "#50665e", "#edf3ee"


def canvas(w, h):
    return Image.new("RGB", (w, h), "white")


def text(im, xy, value, size=28, fill=DARK, anchor="mm"):
    d = ImageDraw.Draw(im)
    d.multiline_text(xy, value, font=ImageFont.truetype(FONT, size), fill=fill, anchor=anchor, align="center", spacing=7)


def box(im, bounds, label, kind="box", size=27):
    d = ImageDraw.Draw(im)
    if kind == "ellipse":
        d.ellipse(bounds, fill=PALE, outline=LINE, width=3)
    elif kind == "diamond":
        x1, y1, x2, y2 = bounds
        d.polygon([(x1+(x2-x1)/2,y1),(x2,y1+(y2-y1)/2),(x1+(x2-x1)/2,y2),(x1,y1+(y2-y1)/2)], fill=PALE, outline=LINE, width=3)
    else:
        d.rounded_rectangle(bounds, radius=14, fill=PALE, outline=LINE, width=3)
    text(im, ((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2), label, size)


def arrow(im, pts, label="", dashed=False, head=True):
    d = ImageDraw.Draw(im)
    for a, b in zip(pts, pts[1:]):
        if dashed:
            length = math.dist(a,b)
            for t in range(0,int(length),18):
                u,v=t/max(length,1),min(t+10,length)/max(length,1)
                d.line([(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u),(a[0]+(b[0]-a[0])*v,a[1]+(b[1]-a[1])*v)], fill=LINE,width=3)
        else:
            d.line([a,b],fill=LINE,width=3)
    if head:
        a,b=pts[-2],pts[-1]
        ang=math.atan2(b[1]-a[1],b[0]-a[0])
        d.polygon([b,(b[0]-15*math.cos(ang-.4),b[1]-15*math.sin(ang-.4)),(b[0]-15*math.cos(ang+.4),b[1]-15*math.sin(ang+.4))],fill=LINE)
    if label:
        a,b=pts[0],pts[-1]
        text(im,((a[0]+b[0])/2+25,(a[1]+b[1])/2-18),label,23)


def save(im, name, spec):
    im.save(OUT / (name+".png"),dpi=(220,220))
    (OUT / (name+".json")).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding="utf-8")


def functional():
    im=canvas(1800,1000)
    box(im,(570,45,1230,140),"词序：英语词汇学习与复习系统",size=34)
    labels=[("试卷管理","年份/英语类别\n正文/TXT录入\n来源与演示标记"),("词频分析","停用词筛选\n规则词形归一\n频次/原词形/上下文"),("历年对比","严格较早年份\n同类别同资料类型\n新增词与历史频次"),("词汇关系","释义与词根\n同源/近义/反义\n来源维护"),("短语与用法","典型短语\n词汇/短语例句\nJSON资料导入"),("个人学习","添加/去重/移除\n本人词表\n学习状态"),("复习管理","到期任务\n四档掌握反馈\n下次时间与日志"),("规则与后台","停用词维护\n用户与角色\n后台公共资料管理")]
    for i,(name,detail) in enumerate(labels):
        row,col=divmod(i,4); x=65+col*435; y=300+row*360
        box(im,(x,y,x+370,y+90),name,size=31)
        box(im,(x,y+115,x+370,y+260),detail,size=26)
        arrow(im,[(x+185,y+90),(x+185,y+115)])
        if row==0:
            arrow(im,[(900,140),(900,210),(x+185,210),(x+185,y)])
        else:
            rail=30+col*435
            arrow(im,[(900,140),(900,170),(rail,170),(rail,y+45),(x,y+45)])
    text(im,(900,960),"注册/登录为公共基础功能，不计入以上业务模块。",24)
    save(im,"图1_系统功能结构图",{"modules":labels})


def actor(im,x,y,name):
    d=ImageDraw.Draw(im);d.ellipse((x-20,y-80,x+20,y-40),outline=LINE,width=3)
    d.line([(x,y-40),(x,y+35)],fill=LINE,width=3);d.line([(x-40,y-10),(x+40,y-10)],fill=LINE,width=3)
    d.line([(x,y+35),(x-35,y+90)],fill=LINE,width=3);d.line([(x,y+35),(x+35,y+90)],fill=LINE,width=3)
    text(im,(x,y+125),name,30)


def usecase_old():
    im=canvas(1700,1450);d=ImageDraw.Draw(im)
    d.rectangle((380,60,1340,1390),outline=LINE,width=3)
    text(im,(860,105),"词序系统边界",33)
    actor(im,160,410,"管理员");actor(im,1530,970,"学生")
    cases=[(680,245,"录入/编辑试卷","admin"),(680,405,"执行有效词分析","admin"),(680,565,"维护词汇关系","admin"),(680,725,"维护短语与用法","admin"),(680,885,"词库导入/停用规则","admin"),(1050,325,"查询试卷与词频","both"),(1050,545,"比较历年新增词","both"),(1050,765,"查看关联与用法","both"),(1050,985,"维护本人学习清单","both"),(1050,1205,"复习与查看记录","both")]
    for x,y,name,role in cases:
        box(im,(x-190,y-55,x+190,y+55),name,"ellipse",26)
        if role in ("admin","both"):arrow(im,[(200,410),(x-190,y)],head=False)
        if role=="both":arrow(im,[(1490,970),(x+190,y)],head=False)
    text(im,(850,1430),"管理员可使用个人学习功能；学生不可执行管理写操作。",24)
    save(im,"图2_UML用例图",{"actors":["管理员","学生"],"usecases":cases})


def analysis_flow():
    im=canvas(1450,1650)
    nodes=[(400,50,1000,130,"管理员录入年份、类别、来源及正文"),(400,200,1000,285,"表单校验并保存待分析试卷"),(470,355,930,470,"英文正文有效？"),(400,550,1000,635,"读取停用配置；分词与基础词形归一"),(400,710,1000,800,"统计频次、原词形与上下文"),(470,875,930,990,"原文仍未变化？"),(400,1070,1000,1160,"事务替换词频；更新分析状态"),(400,1235,1000,1325,"提交完整结果并展示详情")]
    for i,n in enumerate(nodes):box(im,n[:4],n[4],"diamond" if i in (2,5) else "box",27)
    for a,b in zip(nodes,nodes[1:]):arrow(im,[((a[0]+a[2])/2,a[3]),((b[0]+b[2])/2,b[1])],"是" if a is nodes[2] or a is nodes[5] else "")
    box(im,(1080,360,1410,480),"拒绝无效输入\n不保存分析结果",size=25);arrow(im,[(930,412),(1080,412)],"否")
    box(im,(1080,870,1410,1000),"拒绝过期结果\n提示重新分析",size=25);arrow(im,[(930,930),(1080,930)],"否")
    box(im,(65,1090,350,1245),"写入异常\n事务回滚\n保留旧结果",size=25);arrow(im,[(400,1120),(350,1120)],"异常",dashed=True)
    text(im,(720,1500),"相同试卷重复分析替换原频次，不累计重复行。\n关联词义及学习记录不会因重新分析被删除。",27)
    save(im,"图3_试卷分析业务流程图",{"steps":[n[4] for n in nodes]})


def review_flow():
    im=canvas(1350,1600)
    labels=["从试卷/对比/词条加入本人词表","按 user + word 去重创建学习项","查询本人到期项目并展示单词","显示释义/例句后选择四档自评","校验归属、评分、UUID和到期时间","事务内计算等级与下次日期","更新学习项并写入一条复习日志","展示反馈，查看下次时间与历史"]
    for i,s in enumerate(labels):
        y=50+i*160;box(im,(290,y,1010,y+90),s,size=28)
        if i:arrow(im,[(650,y-70),(650,y)])
    box(im,(1040,675,1320,865),"同UUID重复提交\n返回已有记录\n不重复推进",size=24);arrow(im,[(1010,735),(1040,735)],dashed=True)
    box(im,(20,900,250,1100),"越权/未到期\n或状态冲突\n拒绝并提示",size=23);arrow(im,[(290,1010),(250,1010)],dashed=True)
    text(im,(660,1450),"忘记：10分钟；困难：1天；记住/轻松：按等级1/3/7/14/30天。\n四档反馈属于用户自评，不是自动考试评分。",26)
    save(im,"图4_学习复习业务流程图",{"steps":labels})


def architecture():
    im=canvas(1550,1200)
    nodes=[((380,50,1170,170),"浏览器\n中文模板页面 + 本地CSS/JS"),((170,280,720,445),"请求与安全层\nURL / views / forms\n登录、角色、归属、CSRF校验"),((840,280,1390,445),"公共维护\nDjango Admin\n词条、关系、例句、账号"),((380,570,1170,745),"核心业务服务 core/services.py\n分析 / 历史比较 / 个人词表 / 复习事务"),((190,890,730,1070),"Django ORM + 事务\nSQLite：当前实际运行\nMySQL：可配置，尚未验证"),((840,890,1380,1070),"本地文本处理\nrule：当前基础归一\nWordNet：可选，资源未配置")]
    for b,l in nodes:box(im,b,l,size=28)
    arrow(im,[(775,170),(445,280)]);arrow(im,[(775,170),(1115,280)])
    arrow(im,[(445,445),(630,570)]);arrow(im,[(1115,445),(930,570)])
    arrow(im,[(630,745),(460,890)]);arrow(im,[(930,745),(1110,890)])
    text(im,(775,1150),"单体Django项目；无外部AI接口、微服务或CDN依赖。",26)
    save(im,"图6_系统总体架构图",{"nodes":nodes})


def sequence():
    im=canvas(1750,1450);d=ImageDraw.Draw(im)
    xs=[160,560,1000,1500];names=["学生浏览器","review_submit视图","submit_review服务","数据库"]
    for x,n in zip(xs,names):box(im,(x-135,45,x+135,130),n,size=24);arrow(im,[(x,130),(x,1370)],dashed=True,head=False)
    events=[(0,1,220,"POST item/rating/UUID + CSRF"),(1,1,310,"登录和本人记录校验"),(1,2,400,"调用复习服务"),(2,3,490,"查询幂等日志"),(3,2,580,"不存在则继续；存在则返回"),(2,3,690,"事务锁定本人学习项"),(3,2,780,"返回等级及到期时间"),(2,2,880,"校验到期；计算新状态"),(2,3,990,"条件更新学习项 + 写日志"),(3,2,1080,"提交成功/异常回滚"),(2,1,1170,"返回复习记录或校验错误"),(1,0,1260,"重定向复习页并显示反馈")]
    for a,b,y,label in events:
        if a==b:
            arrow(im,[(xs[a],y),(xs[a]+120,y),(xs[a]+120,y+35),(xs[a],y+35)])
            text(im,(xs[a]+160,y+10),label,23,anchor="lm")
        else:
            arrow(im,[(xs[a],y),(xs[b],y)]);text(im,((xs[a]+xs[b])/2,y-23),label,24)
    save(im,"图7_核心复习功能时序图",{"participants":names,"events":events})


def modules():
    im=canvas(1650,1000)
    nodes=[((50,50,440,210),"config\nsettings / urls\n项目配置与路由"),((640,50,1030,210),"core/views.py\n请求、权限和页面"),((1180,50,1590,210),"templates + static\n页面、样式与交互"),((50,410,440,590),"core/forms.py\n录入 / 上传\n词库导入校验"),((640,410,1030,590),"core/services.py\n业务规则、分析与事务"),((1180,410,1590,590),"core/admin.py\n后台资料维护"),((370,780,850,920),"core/models.py + migrations\n自定义用户与9张业务表"),((1010,780,1510,920),"seed_demo\n原创演示数据初始化")]
    for b,l in nodes:box(im,b,l,size=28)
    arrow(im,[(440,130),(640,130)]);arrow(im,[(1030,130),(1180,130)])
    arrow(im,[(750,210),(750,410)]);arrow(im,[(660,210),(245,410)])
    arrow(im,[(840,590),(710,780)]);arrow(im,[(245,590),(470,780)])
    arrow(im,[(1380,590),(800,780)]);arrow(im,[(1010,850),(850,850)])
    save(im,"图8_模块结构图",{"modules":nodes})


def er_old():
    im=canvas(1900,1550);d=ImageDraw.Draw(im)
    specs=[("User 用户",80,80,["PK id","username / role","display_name / password","created_at / updated_at"]),("Paper 试卷",730,80,["PK id；FK created_by","title / year / category","content / source / is_demo","status / token_count / valid_count"]),("Word 单词",1380,80,["PK id；UQ lemma","meaning / pos / root","notes / source","created_at / updated_at"]),("StopWord 停用规则",80,550,["PK id；UQ text","reason / enabled","FK created_by","created_at / updated_at"]),("PaperWord 词频",730,550,["PK id；FK paper / word","count / forms / contexts","total_tokens / timestamps","UQ (paper, word)"]),("WordRelation 词汇关联",1380,550,["PK id；FK word / related_word","relation_type / explanation","source / timestamps","UQ (word, related_word, type)"]),("StudyItem 学习项",80,1030,["PK id；FK user / word","FK source_paper（可空）","status / level / next_review_at","UQ (user, word)"]),("UsageExample 用法例句",730,1030,["PK id；FK word","FK phrase / paper（可空）","text / translation / source / kind","created_at / updated_at"]),("Phrase 短语",1380,1030,["PK id；FK word","text / meaning / example","translation / source / timestamps","UQ (word, text)"]),("ReviewLog 复习日志",80,1320,["PK id；FK study_item","rating / previous_level / new_level","next_review_at / reviewed_at / note","UQ idempotency_key"])]
    for name,x,y,fields in specs:
        h=205 if y<1300 else 210
        d.rounded_rectangle((x,y,x+440,y+h),radius=12,fill=PALE,outline=LINE,width=3)
        text(im,(x+220,y+35),name,27);d.line([(x,y+70),(x+440,y+70)],fill=LINE,width=2)
        text(im,(x+220,y+140),"\n".join(fields),22)
    links=[([(520,165),(730,165)],"1 : N 创建"), ([(160,285),(160,550)],"1 : N 创建"), ([(300,285),(580,350),(580,960),(300,960),(300,1030)],"1 : N 学习"), ([(960,285),(960,550)],"1 : N 词频"), ([(1380,185),(1260,185),(1260,650),(1170,650)],"1 : N 词频"), ([(1600,285),(1600,550)],"1 : N 两端"), ([(1750,285),(1850,285),(1850,1100),(1820,1100)],"1 : N 短语"), ([(160,1235),(160,1320)],"1 : N 日志"), ([(1380,1130),(1170,1130)],"1 : N 例句"), ([(940,285),(1220,350),(1220,960),(940,960),(940,1030)],"0..1 : N 来源"), ([(1380,120),(1290,120),(1290,890),(740,890),(740,1030)],"1 : N 例句"), ([(1470,285),(1470,920),(600,920),(600,1130),(520,1130)],"1 : N 生词")]
    for pts,label in links:arrow(im,pts,label,head=False)
    text(im,(1000,1450),"主图列出关键字段；完整字段、类型与约束见正文数据字典。\nStudyItem.source_paper 可空外键关联 Paper（为减少交叉线在此标注）。",25)
    save(im,"图5_数据库ER图",{"entities":specs,"relations":links})


def usecase():
    im=canvas(1800,1400);d=ImageDraw.Draw(im)
    d.rectangle((400,80,1320,1330),outline=LINE,width=3)
    text(im,(860,125),"词序系统边界",32)
    actor(im,160,480,"管理员");actor(im,1580,880,"学生")
    cases=[("录入/编辑试卷",290,"admin"),("执行有效词分析",485,"admin"),("维护词汇关系",680,"admin"),("维护短语与用法",875,"admin"),("词库导入/停用规则",1070,"admin"),("查询试卷与词频",290,"student"),("比较历年新增词",485,"student"),("查看关联与用法",680,"student"),("维护本人学习清单",875,"student"),("复习与查看记录",1070,"student")]
    for name,y,role in cases:
        x=650 if role=="admin" else 1070
        box(im,(x-185,y-55,x+185,y+55),name,"ellipse",25)
        arrow(im,[(200,480),(x-185,y)] if role=="admin" else [(1540,880),(x+185,y)],head=False)
    # Actor generalization expresses inherited learning access without crossing use cases.
    arrow(im,[(160,260),(160,30),(1580,30),(1580,710)],head=False)
    d.polygon([(1580,735),(1568,710),(1592,710)],fill="white",outline=LINE,width=3)
    text(im,(850,30),"参与者泛化：管理员继承学生的学习权限",23)
    text(im,(880,1380),"管理用例在左，学习用例在右；关联线不穿过其他用例。",23)
    save(im,"图2_UML用例图",{"actors":["管理员","学生"],"generalization":"管理员→学生（权限继承）","usecases":cases})


def er():
    im=canvas(2100,2000);d=ImageDraw.Draw(im)
    text(im,(1050,40),"数据库逻辑 E-R 图：公共资料与个人学习",38)
    records={
        "User":["PK id；UQ username","role / display_name","password（哈希） / timestamps"],
        "Paper":["PK id；FK created_by→User（可空）","title / year / category / content","source / is_demo / status / counts"],
        "Word":["PK id；UQ lemma","meaning / pos / root","notes / source / timestamps"],
        "PaperWord":["PK id；FK paper→Paper，word→Word","count / forms / contexts / total_tokens","UQ (paper, word)"],
        "WordRelation":["PK id；FK word与related_word→Word","relation_type / explanation / source","UQ (word, related_word, type)"],
        "Phrase":["PK id；FK word→Word","text / meaning / example / translation","source / timestamps；UQ (word, text)"],
        "UsageExample":["PK id；FK word→Word","FK phrase→Phrase，paper→Paper（可空）","text / translation / source / kind"],
        "StopWord":["PK id；UQ text；FK created_by→User","reason / enabled","created_at / updated_at"],
        "StudyItem":["PK id；FK user→User，word→Word","FK source_paper→Paper（可空）","status / level / due；UQ (user, word)"],
        "ReviewLog":["PK id；FK study_item→StudyItem","rating / levels / next_review_at / note","reviewed_at；UQ idempotency_key"]
    }
    labels={"User":"用户","Paper":"试卷","Word":"单词","PaperWord":"试卷词频","WordRelation":"词汇关联","Phrase":"短语","UsageExample":"用法例句","StopWord":"停用规则","StudyItem":"学习项","ReviewLog":"复习日志"}
    positions={"Paper":(800,120),"PaperWord":(800,450),"Word":(800,780),"WordRelation":(60,780),"Phrase":(1540,780),"UsageExample":(1540,120),"User":(60,120),"StopWord":(60,450),"StudyItem":(800,1200),"ReviewLog":(800,1610)}
    for key,(x,y) in positions.items():
        d.rounded_rectangle((x,y,x+500,y+205),radius=12,fill=PALE,outline=LINE,width=3)
        text(im,(x+250,y+35),key+" "+labels[key],27);d.line([(x,y+70),(x+500,y+70)],fill=LINE,width=2)
        text(im,(x+250,y+137),"\n".join(records[key]),22)
    links=[([(1050,325),(1050,450)],"1 : N"), ([(1050,780),(1050,655)],"1 : N"), ([(800,875),(560,875)],"1 : N（两端）"), ([(1300,875),(1540,875)],"1 : N"), ([(1790,780),(1790,325)],"0..1 : N"), ([(1300,820),(1440,820),(1440,220),(1540,220)],"1 : N"), ([(1300,200),(1540,200)],"0..1 : N 来源"), ([(310,325),(310,450)],"0..1 : N 创建"), ([(560,200),(800,200)],"0..1 : N 创建"), ([(1050,985),(1050,1200)],"1 : N"), ([(310,325),(680,325),(680,1260),(800,1260)],"1 : N 所属"), ([(1250,325),(1380,325),(1380,1300),(1300,1300)],"0..1 : N 来源"), ([(1050,1405),(1050,1610)],"1 : N")]
    # Label on each route's longest segment; never cover an entity.
    for pts,label in links:
        arrow(im,pts,head=False)
        a,b=max(zip(pts,pts[1:]),key=lambda ab:math.dist(*ab))
        xx,yy=(a[0]+b[0])/2,(a[1]+b[1])/2
        if a[0]==b[0]:xx+=70
        else:yy-=25
        text(im,(xx,yy),label,21)
    text(im,(1050,1920),"矩形表示实体，线表示一对多关系；可空外键的父端为0..1。\nFK列明确标注目标实体；完整字段、删除行为与约束见报告数据字典。",25)
    save(im,"图5_数据库ER图",{"entities":records,"positions":positions,"relations":links})


if __name__=="__main__":
    functional();usecase();analysis_flow();review_flow();er();architecture();sequence();modules()
    print("Generated 8 numbered project-specific PNG diagrams with editable JSON specifications.")
