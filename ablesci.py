#!/usr/bin/env python
# cron:40 7,21 * * *
# new Env("科研通签到")
# coding=utf-8

"""
AbleSci 科研通 Cookie 自动签到脚本

说明：
1. 不再使用邮箱/密码 + CSRF 登录。
2. 使用浏览器登录后的 Cookie 直接访问科研通。
3. 支持 GitHub Actions / 青龙面板 / 本地运行。
4. 支持多账号：
   ABLESCI_COOKIES 中每个账号一行 Cookie，
   或者使用 ||| 分隔。
"""

import os
import sys
import time
import json
import datetime
from pathlib import Path
from datetime import timezone, timedelta

import requests
from bs4 import BeautifulSoup


try:
    from zoneinfo import ZoneInfo

    ZONEINFO_AVAILABLE = True
except ImportError:
    ZONEINFO_AVAILABLE = False


# ==============================
# 环境变量
# ==============================

ENV_COOKIES = "ABLESCI_COOKIES"


# ==============================
# .env 文件读取
# ==============================

def load_env_file():
    """
    加载脚本目录下的 .env 文件。

    系统环境变量优先于 .env。
    """

    env_file = Path(__file__).parent / ".env"

    if not env_file.exists():
        return

    with open(env_file, "r", encoding="utf-8") as f:

        for raw_line in f:

            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            key = key.strip()
            value = value.strip()

            # 去掉引号
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in ("'", '"')
            ):
                value = value[1:-1]

            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()


# ==============================
# 北京时间
# ==============================

def get_beijing_time():
    """返回北京时间"""

    if ZONEINFO_AVAILABLE:

        try:
            return datetime.datetime.now(
                ZoneInfo("Asia/Shanghai")
            )

        except Exception:
            pass

    try:

        import pytz

        return datetime.datetime.now(
            pytz.timezone("Asia/Shanghai")
        )

    except ImportError:
        pass

    return datetime.datetime.now(
        timezone.utc
    ).astimezone(
        timezone(
            timedelta(hours=8)
        )
    )


# ==============================
# 隐私处理
# ==============================

def protect_privacy(text):
    """隐藏用户名的一部分"""

    if not text:
        return "未知用户"

    text = str(text).strip()

    if len(text) <= 2:
        return "***"

    return text[:2] + "***"


# ==============================
# 通知
# ==============================

class Notifier:

    def __init__(self, title="科研通签到"):

        self.log_content = []

        self.title = title

        self.notify_enabled = False

        try:

            sys.path.append(
                os.path.dirname(
                    os.path.abspath(__file__)
                )
            )

            from sendNotify import send

            self.send = send

            self.notify_enabled = True

        except ImportError:

            try:

                parent_dir = os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__)
                    )
                )

                sys.path.append(parent_dir)

                from sendNotify import send

                self.send = send

                self.notify_enabled = True

            except Exception:

                self.notify_enabled = False


    def log(self, message, level="info"):

        beijing_time = get_beijing_time()

        timestamp = beijing_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        level_map = {

            "info": "ℹ️",

            "success": "✅",

            "error": "❌",

            "warning": "⚠️"

        }

        symbol = level_map.get(
            level,
            "ℹ️"
        )

        log_message = (
            f"[{timestamp}] "
            f"{symbol} "
            f"{message}"
        )

        print(log_message)

        self.log_content.append(
            log_message
        )


    def send_notification(self):

        if not self.notify_enabled:

            self.log(
                "通知功能未启用",
                "warning"
            )

            return False

        content = "\n".join(
            self.log_content
        )

        try:

            self.send(
                self.title,
                content
            )

            self.log(
                "通知发送成功",
                "success"
            )

            return True

        except Exception as e:

            self.log(
                f"发送通知失败: {e}",
                "error"
            )

            return False


    def get_content(self):

        return "\n".join(
            self.log_content
        )


# ==============================
# 科研通签到
# ==============================

class AbleSciAuto:

    def __init__(
        self,
        cookie,
        account_index=1,
        notifier=None
    ):

        self.session = requests.Session()

        self.cookie = cookie.strip()

        self.account_index = account_index

        self.username = None

        self.points = None

        self.sign_days = None

        self.notifier = (
            notifier
            if notifier
            else Notifier()
        )

        self.start_time = time.time()

        self.headers = {

            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/138.0.0.0 "
                "Safari/537.36"
            ),

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "image/apng,"
                "*/*;q=0.8"
            ),

            "Accept-Language": (
                "zh-CN,zh;q=0.9,en;q=0.8"
            ),

            "Referer": (
                "https://www.ablesci.com/"
            ),

            "X-Requested-With": (
                "XMLHttpRequest"
            ),

            # 核心：直接使用浏览器 Cookie
            "Cookie": self.cookie,
        }

        self.session.headers.update(
            self.headers
        )

        self.log(
            f"开始处理第 {self.account_index} 个账号",
            "info"
        )


    def log(
        self,
        message,
        level="info"
    ):

        self.notifier.log(
            message,
            level
        )


    # ==========================
    # 网络检查
    # ==========================

    def check_connection(self):

        try:

            response = self.session.get(

                "https://www.ablesci.com/",

                timeout=30,

                allow_redirects=True,
            )

            if response.status_code != 200:

                self.log(

                    "访问科研通失败，"
                    f"状态码: {response.status_code}",

                    "error"
                )

                return False

            return True

        except Exception as e:

            self.log(

                f"访问科研通时出错: {e}",

                "error"
            )

            return False


    # ==========================
    # 获取用户信息
    # ==========================

    def get_user_info(self):

        try:

            response = self.session.get(

                "https://www.ablesci.com/",

                timeout=30,

                allow_redirects=True,
            )

            if response.status_code != 200:

                self.log(

                    "获取首页失败，"
                    f"状态码: {response.status_code}",

                    "warning"
                )

                return False


            soup = BeautifulSoup(

                response.text,

                "html.parser"
            )


            # ==================
            # 用户名
            # ==================

            username_selectors = [

                ".mobile-hide."
                "able-head-user-vip-username",

                ".able-head-user-vip-username",
            ]

            username_element = None

            for selector in username_selectors:

                username_element = (
                    soup.select_one(
                        selector
                    )
                )

                if username_element:
                    break


            if username_element:

                self.username = (
                    username_element
                    .get_text(
                        strip=True
                    )
                )

                self.log(

                    "用户名: "
                    f"{protect_privacy(self.username)}",

                    "info"
                )

            else:

                self.log(

                    "未从首页解析到用户名，"
                    "继续尝试签到",

                    "warning"
                )


            # ==================
            # 积分
            # ==================

            points_element = (
                soup.select_one(
                    "#user-point-now"
                )
            )

            if points_element:

                self.points = (
                    points_element
                    .get_text(
                        strip=True
                    )
                )

                self.log(

                    f"当前积分: {self.points}",

                    "info"
                )


            # ==================
            # 连续签到天数
            # ==================

            sign_days_element = (
                soup.select_one(
                    "#sign-count"
                )
            )

            if sign_days_element:

                self.sign_days = (
                    sign_days_element
                    .get_text(
                        strip=True
                    )
                )

                self.log(

                    "连续签到天数: "
                    f"{self.sign_days}",

                    "info"
                )


            return True


        except Exception as e:

            self.log(

                f"获取用户信息时出错: {e}",

                "warning"
            )

            return False


    # ==========================
    # 签到
    # ==========================

    def sign_in(self):

        sign_url = (
            "https://www.ablesci.com/user/sign"
        )

        headers = self.headers.copy()

        headers["Accept"] = (
            "application/json, "
            "text/javascript, "
            "*/*; q=0.01"
        )

        headers["Referer"] = (
            "https://www.ablesci.com/"
        )

        headers["X-Requested-With"] = (
            "XMLHttpRequest"
        )


        try:

            response = self.session.get(

                sign_url,

                headers=headers,

                timeout=30,

                allow_redirects=True,
            )


            # ==================
            # HTTP 错误
            # ==================

            if response.status_code != 200:

                self.log(

                    "签到请求失败，"
                    f"状态码: {response.status_code}",

                    "error"
                )

                return False


            # ==================
            # 被重定向到登录页
            # ==================

            final_url = (
                response.url.lower()
            )

            if "/site/login" in final_url:

                self.log(

                    "Cookie 已失效或未登录，"
                    "请重新获取 Cookie",

                    "error"
                )

                return False


            # ==================
            # 解析 JSON
            # ==================

            try:

                result = (
                    response.json()
                )

            except json.JSONDecodeError:

                text = (
                    response.text
                    or ""
                )

                if (

                    "site/login"
                    in text.lower()

                    or "登录账户"
                    in text

                    or "请先登录"
                    in text

                ):

                    self.log(

                        "Cookie 已失效或未登录，"
                        "请重新获取 Cookie",

                        "error"
                    )

                else:

                    self.log(

                        "签到接口未返回 JSON，"
                        "可能是科研通接口发生变化",

                        "error"
                    )

                    self.log(

                        "响应地址: "
                        f"{response.url}",

                        "warning"
                    )

                return False


            code = result.get(
                "code"
            )

            msg = str(
                result.get(
                    "msg",
                    ""
                )
            ).strip()

            data = (
                result.get("data")
                or {}
            )


            # ==================
            # 签到成功
            # ==================

            if str(code) == "0":

                self.log(

                    "签到成功: "
                    f"{msg or '签到成功'}",

                    "success"
                )


                if isinstance(
                    data,
                    dict
                ):

                    if "points" in data:

                        self.points = (
                            data["points"]
                        )

                        self.log(

                            "更新积分: "
                            f"{self.points}",

                            "info"
                        )


                    if "sign_days" in data:

                        self.sign_days = (
                            data["sign_days"]
                        )

                        self.log(

                            "更新连续签到天数: "
                            f"{self.sign_days}",

                            "info"
                        )


                return True


            # ==================
            # 今日已经签到
            # ==================

            already_signed_keywords = (

                "已签到",

                "已于",

                "已经签到",

                "今日已签到",
            )


            if any(

                keyword in msg

                for keyword
                in already_signed_keywords

            ):

                self.log(

                    f"今日已签到: {msg}",

                    "info"
                )

                return True


            # ==================
            # Cookie 失效
            # ==================

            login_keywords = (

                "未登录",

                "请登录",

                "请先登录",

                "登录失效",

                "登陆失效",
            )


            if any(

                keyword in msg

                for keyword
                in login_keywords

            ):

                self.log(

                    "Cookie 已失效或"
                    f"登录状态无效: {msg}",

                    "error"
                )

                return False


            # ==================
            # 其他错误
            # ==================

            self.log(

                "签到失败: "
                f"{msg or result}",

                "error"
            )

            return False


        except requests.RequestException as e:

            self.log(

                f"签到网络请求出错: {e}",

                "error"
            )

            return False


        except Exception as e:

            self.log(

                f"签到过程中出错: {e}",

                "error"
            )

            return False


    # ==========================
    # 显示摘要
    # ==========================

    def display_summary(
        self,
        is_before_sign=False
    ):

        elapsed = round(

            time.time()
            - self.start_time,

            2
        )

        title = (

            "签到前信息"

            if is_before_sign

            else "签到后信息"
        )


        self.log(
            "=" * 50
        )

        self.log(

            f"第 {self.account_index} "
            f"个账号 {title}:"
        )


        if self.username:

            self.log(

                "  • 用户名: "
                f"{protect_privacy(self.username)}"
            )


        if self.points is not None:

            self.log(

                "  • 当前积分: "
                f"{self.points}"
            )


        if self.sign_days is not None:

            self.log(

                "  • 连续签到: "
                f"{self.sign_days}天"
            )


        self.log(

            "  • 执行耗时: "
            f"{elapsed}秒"
        )


        self.log(
            "=" * 50
        )


    # ==========================
    # 完整流程
    # ==========================

    def run(self):

        if not self.cookie:

            self.log(
                "Cookie 为空",
                "error"
            )

            return False


        if not self.check_connection():

            return False


        # 签到前
        self.get_user_info()

        self.display_summary(
            is_before_sign=True
        )


        # 签到
        sign_result = (
            self.sign_in()
        )


        if sign_result:

            self.log(

                "签到处理完成，"
                "刷新用户信息...",

                "info"
            )

            time.sleep(2)


            # 签到后
            self.get_user_info()

            self.display_summary(
                is_before_sign=False
            )


        return sign_result


# ==============================
# 获取 Cookie
# ==============================

def get_cookies():
    """
    从 ABLESCI_COOKIES 获取 Cookie。

    支持：

    1. 单账号
       ABLESCI_COOKIES=完整Cookie

    2. 多账号
       一个 Cookie 一行

    3. 使用 ||| 分隔

    注意：
    不要使用分号分隔账号。
    Cookie 本身就包含大量分号。
    """

    raw = os.getenv(
        ENV_COOKIES,
        ""
    ).strip()


    if not raw:

        return []


    # ==========================
    # 兼容 \n 字符串
    # ==========================

    if (
        "\\n" in raw
        and "\n" not in raw
    ):

        raw = raw.replace(
            "\\n",
            "\n"
        )


    # ==========================
    # 多账号解析
    # ==========================

    if "\n" in raw:

        items = (
            raw.splitlines()
        )

    elif "|||" in raw:

        items = (
            raw.split("|||")
        )

    else:

        items = [raw]


    cookies = []


    for item in items:

        cookie = (
            item
            .strip()
            .strip('"')
            .strip("'")
        )


        if not cookie:

            continue


        if "=" not in cookie:

            print(
                "警告：发现格式异常的 "
                "Cookie，已跳过"
            )

            continue


        cookies.append(
            cookie
        )


    return cookies


# ==============================
# 主函数
# ==============================

def main():

    global_notifier = Notifier(
        "科研通多账号签到"
    )


    global_notifier.log(

        "科研通 Cookie "
        "自动签到任务开始",

        "info"
    )


    cookies = (
        get_cookies()
    )


    account_count = len(
        cookies
    )


    # ==========================
    # 未配置 Cookie
    # ==========================

    if account_count == 0:

        global_notifier.log(

            "未找到有效 Cookie，"
            f"请设置环境变量/Secret: "
            f"{ENV_COOKIES}",

            "error"
        )


        global_notifier.log(

            "单账号填写完整 Cookie；"
            "多账号每个 Cookie 一行，"
            "或使用 ||| 分隔",

            "warning"
        )


        if (
            global_notifier
            .notify_enabled
        ):

            global_notifier.send_notification()


        return


    global_notifier.log(

        "找到 "
        f"{account_count} "
        "个 Cookie 账号",

        "info"
    )


    success_count = 0


    # ==========================
    # 逐个签到
    # ==========================

    for i, cookie in enumerate(
        cookies,
        1
    ):

        global_notifier.log(

            "\n"
            "===== "
            f"开始处理第 {i}/"
            f"{account_count} 个账号 "
            "=====",

            "info"
        )


        automator = AbleSciAuto(

            cookie=cookie,

            account_index=i,

            notifier=global_notifier,
        )


        if automator.run():

            success_count += 1


        global_notifier.log(

            "===== "
            f"完成第 {i}/"
            f"{account_count} 个账号处理 "
            "=====",

            "info"
        )


    # ==========================
    # 总结
    # ==========================

    global_notifier.log(

        "\n===== "
        "所有账号处理完成："
        f"成功 {success_count}/"
        f"{account_count} "
        "=====",

        "info"
    )


    # ==========================
    # 推送通知
    # ==========================

    if (
        global_notifier
        .notify_enabled
    ):

        global_notifier.send_notification()


if __name__ == "__main__":

    main()
