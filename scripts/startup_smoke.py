"""仅进行本地网站的启动交互确认，不替代正式测试。密码通过标准输入输入。"""
import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request


def main():
    username = sys.stdin.readline().strip()
    password = sys.stdin.readline().strip()
    if not username or not password:
        raise SystemExit("需要通过标准输入提供演示账号和密码。")
    base = "http://127.0.0.1:8000"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    with opener.open(base + "/login/", timeout=10) as response:
        body = response.read().decode("utf-8")
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)
    if not match:
        raise SystemExit("登录页缺少CSRF表单。")
    payload = urllib.parse.urlencode({"username": username, "password": password, "csrfmiddlewaretoken": match.group(1)}).encode()
    request = urllib.request.Request(base + "/login/", data=payload, headers={"Referer": base + "/login/"})
    with opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        if response.geturl().split("?")[0].endswith("/login/"):
            raise SystemExit("账号登录失败。")
        print("LOGIN: HTTP", response.status, "dashboard loaded:", "学习概览" in body)
    paths = ["/papers/", "/papers/1/", "/papers/3/compare/", "/words/", "/words/1/", "/study/", "/review/", "/review/history/"]
    if username == "admin":
        paths.extend(["/papers/create/", "/words/create/", "/words/import/", "/management/stopwords/", "/admin/"])
    for path in paths:
        with opener.open(base + path, timeout=10) as response:
            body = response.read().decode("utf-8")
            print(path, "HTTP", response.status, "HTML bytes", len(body.encode("utf-8")))
    password = ""


if __name__ == "__main__":
    main()
