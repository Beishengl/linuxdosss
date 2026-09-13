# -*- coding: utf-8 -*-
"""
Linux.do 论坛刷帖助手 v8.5
功能：
1. 自动获取用户等级和升级进度
2. 多板块浏览
3. 随机点赞帖子和回复
4. 随机回帖
5. 统计报告
6. 防风控机制（随机间隔）
7. 升级进度实时追踪
8. 系统托盘支持
9. 快速浏览模式（增加浏览话题数）
10. 真实进度变化统计
11. 支持手动/自动配置浏览器可执行文件路径 (Chrome/Edge/Chromium)
"""

import sys, os, random, time, json, threading
import urllib.request
import urllib.error
from datetime import datetime, date

# Linux 输入法兼容性修复（必须在导入 tkinter 之前设置）
import platform

if platform.system() == "Linux":
    if "GTK_IM_MODULE" not in os.environ:
        if os.path.exists("/usr/bin/fcitx") or os.path.exists("/usr/bin/fcitx5"):
            os.environ["GTK_IM_MODULE"] = "fcitx"
            os.environ["QT_IM_MODULE"] = "fcitx"
            os.environ["XMODIFIERS"] = "@im=fcitx"
        elif os.path.exists("/usr/bin/ibus"):
            os.environ["GTK_IM_MODULE"] = "ibus"
            os.environ["QT_IM_MODULE"] = "ibus"
            os.environ["XMODIFIERS"] = "@im=ibus"

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

# 版本信息
VERSION = "8.5.0"
GITHUB_REPO = "icysaintdx/linuxdosss"
CONFIG_FILE = "browser_config.json"

# 跨平台字体配置
if platform.system() == "Darwin":  # macOS
    FONT_FAMILY = "PingFang SC"
    FONT_MONO = "Menlo"
elif platform.system() == "Linux":
    FONT_FAMILY = "Noto Sans CJK SC"
    FONT_MONO = "Monospace"
else:  # Windows
    FONT_FAMILY = "Microsoft YaHei UI"
    FONT_MONO = "Consolas"

# 托盘支持（macOS 上禁用，因为可能导致 UI 问题）
TRAY_SUPPORT = False
if platform.system() != "Darwin":
    try:
        import pystray
        from PIL import Image, ImageDraw

        TRAY_SUPPORT = True
    except ImportError:
        TRAY_SUPPORT = False
else:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        pass

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
except:
    print("pip install DrissionPage")
    sys.exit(1)


def get_icon_path():
    """获取图标路径"""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "icon.ico")


def create_tray_image(color="#0f3460"):
    """创建托盘图标图像"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    padding = 4
    draw.ellipse([padding, padding, size - padding, size - padding], fill=color)

    inner_padding = 12
    draw.ellipse(
        [inner_padding, inner_padding, size - inner_padding, size - inner_padding],
        fill="#1a1a2e",
    )

    center = size // 2
    dot_size = 8
    draw.ellipse(
        [center - dot_size, center - dot_size, center + dot_size, center + dot_size],
        fill="#00d9ff",
    )

    return img


def find_default_browser_path():
    """尝试自动发现系统安装的 Chrome 或 Edge 路径"""
    candidates = []
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif platform.system() == "Linux":
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge-stable",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


# 板块配置
CATS = [
    {"n": "开发调优", "u": "/c/develop/4", "e": True},
    {"n": "国产替代", "u": "/c/domestic/98", "e": True},
    {"n": "资源荟萃", "u": "/c/resource/14", "e": True},
    {"n": "网盘资源", "u": "/c/resource/cloud-asset/94", "e": True},
    {"n": "文档共建", "u": "/c/wiki/42", "e": True},
    {"n": "积分乐园", "u": "/c/credit/106", "e": False},
    {"n": "非我莫属", "u": "/c/job/27", "e": True},
    {"n": "读书成诗", "u": "/c/reading/32", "e": True},
    {"n": "扬帆起航", "u": "/c/startup/46", "e": False},
    {"n": "前沿快讯", "u": "/c/news/34", "e": True},
    {"n": "网络记忆", "u": "/c/feeds/92", "e": True},
    {"n": "福利羊毛", "u": "/c/welfare/36", "e": True},
    {"n": "搞七捻三", "u": "/c/gossip/11", "e": True},
    {"n": "社区孵化", "u": "/c/incubator/102", "e": False},
    {"n": "虫洞广场", "u": "/c/square/110", "e": True},
    {"n": "运营反馈", "u": "/c/feedback/2", "e": False},
]

CFG = {
    "proxy": "127.0.0.1:7897",
    "base": "https://linux.do",
    "connect": "https://connect.linux.do",
    "browser_path": "",
    "like_rate": 0.3,
    "reply_rate": 0.05,
    "like_reply_rate": 0.15,
    "scroll_time": 3,
    "wait_min": 1,
    "wait_max": 3,
    "tpl": [
        "感谢分享！学习了",
        "感谢楼主的分享",
        "感谢分享，很有帮助",
        "感谢大佬的分享",
        "感谢楼主无私分享",
        "感谢分享，收藏学习",
        "感谢楼主，学到了",
        "感谢分享，受益匪浅",
        "学习了，谢谢楼主！",
        "学到了新知识，感谢",
        "涨知识了，谢谢分享",
        "学习学习，感谢大佬",
        "又学到了，感谢楼主",
        "学习一下，感谢分享",
        "认真学习中，感谢",
        "好好学习天天向上",
        "支持一下，感谢分享",
        "支持楼主，继续加油",
        "必须支持，感谢分享",
        "大力支持，感谢楼主",
        "支持支持，学习了",
        "强烈支持，感谢分享",
        "好文章，收藏了",
        "收藏了，感谢分享",
        "先收藏，慢慢学习",
        "收藏学习，感谢楼主",
        "马克一下，感谢分享",
        "mark一下，以后学习",
        "先马后看，感谢分享",
        "不错不错，学习了",
        "写得很好，感谢分享",
        "内容很棒，感谢楼主",
        "干货满满，感谢分享",
        "质量很高，感谢楼主",
        "很有价值，感谢分享",
        "非常实用，感谢楼主",
        "很有帮助，感谢分享",
        "前排围观，感谢分享",
        "前排学习，感谢楼主",
        "前排支持，感谢分享",
        "前排关注，学习了",
        "前排占座，感谢分享",
        "谢谢佬，学习了",
        "感谢佬的分享",
        "佬太强了，学习了",
        "跟着佬学习一下",
        "佬就是佬，感谢分享",
        "大佬牛逼，学习了",
        "膜拜大佬，感谢分享",
        "路过学习，感谢分享",
        "围观学习，感谢楼主",
        "来学习一下，感谢",
        "看看学习，感谢分享",
        "顶一下，感谢分享",
        "顶顶顶，感谢楼主",
        "帮顶一下，感谢分享",
        "好帖必顶，感谢楼主",
        "精华帖子，感谢分享",
        "优质内容，感谢楼主",
        "实用干货，感谢分享",
        "很有意思，感谢楼主",
        "长见识了，感谢分享",
        "开眼界了，感谢楼主",
        "受教了，感谢分享",
        "茅塞顿开，感谢楼主",
    ],
}


class Bot:
    def __init__(
        s,
        cfg,
        cats,
        lg,
        update_info=None,
        update_progress=None,
        update_countdown=None,
        mode="endless",
        target_value=0,
        enable_like=True,
        enable_reply=True,
        enable_wait=True,
        browse_mode="deep",
    ):
        s.cfg = cfg
        s.cats = cats
        s.lg = lg
        s.update_info = update_info
        s.update_progress = update_progress
        s.update_countdown = update_countdown
        s.mode = mode
        s.target_value = target_value
        s.enable_like = enable_like
        s.enable_reply = enable_reply
        s.enable_wait = enable_wait
        s.browse_mode = browse_mode
        s.pg = None
        s.run = False
        s.stats = {"topic": 0, "like": 0, "reply": 0, "like_reply": 0, "floors": 0}
        s.user_info = None
        s.level_requirements = []
        s.initial_level_info = None
        s.start_time = None

    def _random_delay(s, min_sec=0.5, max_sec=2.0, reason=""):
        """防风控：随机延迟"""
        delay = random.uniform(min_sec, max_sec)
        if reason:
            s.lg(f"[防风控] {reason}，等待 {delay:.1f}s")
        time.sleep(delay)

    def start(s):
        if s.pg:
            s.lg("关闭旧的浏览器实例...")
            try:
                s.pg.quit()
                time.sleep(1)
            except:
                pass
            s.pg = None

        s.lg("启动浏览器...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                co = ChromiumOptions()

                # 指定浏览器可执行文件路径
                browser_path = s.cfg.get("browser_path", "").strip()
                if browser_path:
                    if os.path.exists(browser_path):
                        s.lg(f"使用指定浏览器: {browser_path}")
                        co.set_browser_path(browser_path)
                    else:
                        s.lg(f"⚠ 指定的浏览器路径不存在: {browser_path}，尝试默认配置")

                user_data_dir = os.path.join(os.getcwd(), "browser_data")
                co.set_user_data_path(user_data_dir)

                if s.cfg.get("proxy"):
                    co.set_proxy(s.cfg["proxy"])
                co.set_argument("--disable-blink-features=AutomationControlled")

                # 设置浏览器窗口大小为屏幕高度
                root = tk.Tk()
                screen_height = root.winfo_screenheight()
                root.destroy()

                co.set_argument(f"--window-size=1200,{screen_height}")
                s.lg(f"设置浏览器窗口大小: 1200x{screen_height}")

                s.pg = ChromiumPage(co)
                s.lg("浏览器就绪")
                return True

            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg and attempt < max_retries - 1:
                    s.lg(f"启动失败（尝试 {attempt + 1}/{max_retries}），重试中...")
                    time.sleep(2)
                    continue
                else:
                    s.lg(f"启动失败: {error_msg}")
                    return False

        return False

    def stop(s):
        s.run = False

    def close(s):
        if s.pg:
            try:
                s.pg.quit()
                time.sleep(0.5)
            except Exception as e:
                s.lg(f"关闭浏览器时出错: {e}")
            s.pg = None

    def check_login(s, wait_for_login=True, max_wait=600, check_interval=15):
        s.lg("检查登录...")
        s.pg.get(s.cfg["base"])
        time.sleep(3)

        start_time = time.time()
        check_count = 0
        first_check = True

        while s.run:
            check_count += 1
            try:
                user_ele = s.pg.ele("#current-user", timeout=3)
                if user_ele:
                    try:
                        img = s.pg.ele("#current-user img", timeout=2)
                        s.user_info = {"username": img.attr("title") if img else "用户"}
                    except:
                        s.user_info = {"username": "用户"}
                    s.lg("已登录: " + s.user_info["username"])
                    return True
            except Exception:
                pass

            if not wait_for_login:
                s.lg("未登录，请先登录")
                return False

            elapsed = time.time() - start_time
            remaining = max_wait - elapsed

            if remaining <= 0:
                s.lg("等待登录超时，请重新启动")
                return False

            if first_check:
                s.lg("未检测到登录，请在浏览器中完成登录")
                s.lg("提示：登录成功后会自动检测，无需其他操作")
                s.lg(f"检查间隔：{check_interval}秒，最长等待：{int(remaining)}秒")
                first_check = False
            else:
                s.lg(f"第{check_count}次检查，未检测到登录，剩余等待{int(remaining)}秒")

            time.sleep(check_interval)

        return False

    def get_level_info(s, is_final=False):
        s.lg("获取等级信息...")
        try:
            if is_final:
                s.lg("强制刷新页面获取最新数据...")
                s.pg.get(s.cfg["connect"])
                time.sleep(2)
                s.pg.run_js("location.reload(true)")
                time.sleep(4)
            else:
                s.pg.get(s.cfg["connect"])
                time.sleep(4)

            info = s.pg.run_js("""
            function getLevelInfo() {
                const result = {
                    username: '',
                    level: '',
                    nextLevel: '',
                    requirements: []
                };

                const subtitle = document.querySelector('.card-subtitle');
                if (subtitle) {
                    const text = subtitle.textContent;
                    const match = text.match(/@([^\\s·]+)/);
                    if (match) {
                        result.username = match[1];
                    }
                }

                const cardTitle = document.querySelector('.card-title');
                if (cardTitle) {
                    const text = cardTitle.textContent;
                    const match = text.match(/信任级别\\s*(\\d+)/);
                    if (match) {
                        result.nextLevel = match[1];
                        result.level = String(parseInt(match[1]) - 1);
                    }
                }

                const rings = document.querySelectorAll('.tl3-ring');
                rings.forEach(ring => {
                    const label = ring.querySelector('.tl3-ring-label');
                    const current = ring.querySelector('.tl3-ring-current');
                    const target = ring.querySelector('.tl3-ring-target');

                    if (label && current && target) {
                        result.requirements.push({
                            name: label.textContent.trim(),
                            current: current.textContent.trim(),
                            required: target.textContent.replace('/', '').trim()
                        });
                    }
                });

                const bars = document.querySelectorAll('.tl3-bar-item');
                bars.forEach(bar => {
                    const label = bar.querySelector('.tl3-bar-label');
                    const nums = bar.querySelector('.tl3-bar-nums');

                    if (label && nums) {
                        const match = nums.textContent.trim().match(/(\\d+)\\/(\\d+)/);
                        if (match) {
                            result.requirements.push({
                                name: label.textContent.trim(),
                                current: match[1],
                                required: match[2]
                            });
                        }
                    }
                });

                const quotas = document.querySelectorAll('.tl3-quota-card');
                quotas.forEach(quota => {
                    const label = quota.querySelector('.tl3-quota-label');
                    const nums = quota.querySelector('.tl3-quota-nums');

                    if (label && nums) {
                        const match = nums.textContent.trim().match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                        if (match) {
                            result.requirements.push({
                                name: label.textContent.trim(),
                                current: match[1],
                                required: match[2]
                            });
                        }
                    }
                });

                const vetos = document.querySelectorAll('.tl3-veto-item');
                vetos.forEach(veto => {
                    const label = veto.querySelector('.tl3-veto-label');
                    const value = veto.querySelector('.tl3-veto-value');

                    if (label && value) {
                        result.requirements.push({
                            name: label.textContent.trim(),
                            current: value.textContent.trim(),
                            required: '0'
                        });
                    }
                });

                return result;
            }
            return getLevelInfo();
            """)

            if info:
                s.user_info = info
                s.lg("用户: " + info.get("username", "未知"))
                s.lg("当前等级: " + info.get("level", "未知") + "级")
                if info.get("nextLevel"):
                    s.lg("下一级: " + info.get("nextLevel") + "级")
                if info.get("requirements"):
                    s.lg("升级要求:")
                    for req in info["requirements"][:8]:
                        s.lg(f"  {req['name']}: {req['current']}/{req['required']}")

                if s.update_info:
                    s.update_info(info, is_final)

                s.level_requirements = info.get("requirements", [])
                if not is_final and s.initial_level_info is None:
                    s.initial_level_info = info.copy()

                return info
        except Exception as e:
            s.lg("获取等级失败: " + str(e))
        return None

    def get_topics(s, cat):
        url = s.cfg["base"] + cat["u"]
        s.lg("进入板块: " + cat["n"])
        s.pg.get(url)
        s._random_delay(2, 4, "页面加载")

        s.lg("点击'回复'按钮进行排序...")
        clicked = s.pg.run_js("""
        function clickRepliesSort() {
            const replyButton = document.querySelector('th[data-sort-order="posts"] button');
            if (replyButton) {
                replyButton.click();
                return true;
            }
            return false;
        }
        return clickRepliesSort();
        """)

        if clicked:
            s.lg("已点击回复排序按钮")
            time.sleep(2)
        else:
            s.lg("未找到回复排序按钮，使用默认排序")

        topics = s.pg.run_js("""
        function getTopics() {
            const rows = document.querySelectorAll('tr.topic-list-item');
            const unreadTopics = [];
            const readTopics = [];

            rows.forEach(row => {
                const link = row.querySelector('a.title.raw-link.raw-topic-link');
                if (link) {
                    const href = link.getAttribute('href');
                    const title = link.textContent.trim();
                    const topicId = row.getAttribute('data-topic-id');

                    if (href && title && !row.classList.contains('pinned')) {
                        const newTopicBadge = row.querySelector('.badge.badge-notification.new-topic');
                        const topicData = {
                            url: href,
                            title: title.substring(0, 50),
                            id: topicId,
                            isUnread: !!newTopicBadge
                        };

                        if (newTopicBadge) {
                            unreadTopics.push(topicData);
                        } else {
                            readTopics.push(topicData);
                        }
                    }
                }
            });

            return {
                unread: unreadTopics,
                read: readTopics,
                all: [...unreadTopics, ...readTopics]
            };
        }
        return getTopics();
        """)

        if topics:
            unread = topics.get("unread", [])
            read = topics.get("read", [])
            s.lg(f"找到 {len(unread)} 个未读话题，{len(read)} 个已读话题")

            if unread:
                s.lg(f"优先浏览 {len(unread)} 个未读话题")
                if len(unread) < 3 and read:
                    s.lg(f"未读话题较少，补充 {min(3, len(read))} 个已读话题")
                    return unread + read[:3]
                return unread
            else:
                s.lg("没有未读话题，浏览已读话题")
                return read

        return []

    def get_floor_info(s):
        floor_info = s.pg.run_js("""
        function getFloorInfo() {
            const timelineElement = document.querySelector('.timeline-replies');
            if (timelineElement) {
                const match = timelineElement.textContent.trim().match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                if (match) {
                    return {
                        current: parseInt(match[1]),
                        total: parseInt(match[2]),
                        source: 'timeline-replies'
                    };
                }
            }
            const progressElement = document.querySelector('#topic-progress .nums');
            if (progressElement) {
                const spans = progressElement.querySelectorAll('span');
                if (spans.length >= 3) {
                    const current = parseInt(spans[0].textContent);
                    const total = parseInt(spans[2].textContent);
                    if (!isNaN(current) && !isNaN(total)) {
                        return {
                            current: current,
                            total: total,
                            source: 'topic-progress'
                        };
                    }
                }
            }
            return null;
        }
        return getFloorInfo();
        """)
        return floor_info

    def scroll_page(s, duration=None, quick_mode=False):
        if quick_mode or s.browse_mode == "quick":
            return s._scroll_page_quick()

        floor_info = s.get_floor_info()
        if not floor_info:
            s.lg("⚠ 无法获取楼层信息，使用传统滚动模式")
            s._scroll_page_legacy(duration)
            return 0

        total_floors = floor_info["total"]
        start_floor = floor_info["current"]
        s.lg(f"帖子总楼层数: {total_floors}，开始楼层: {start_floor} (来源: {floor_info.get('source', 'unknown')})")

        if total_floors < 10:
            s.lg(f"楼层数太少（{total_floors}），使用快速浏览")
            s._scroll_page_legacy(duration)
            return max(0, total_floors - start_floor)

        scroll_count = 0
        current_floor = start_floor
        last_floor = start_floor
        stuck_count = 0

        while current_floor < total_floors and s.run:
            if s._check_target_reached():
                s.lg("已达到目标，停止爬楼")
                s.run = False
                break

            time.sleep(random.uniform(2, 4))
            s.pg.run_js(f"window.scrollBy(0, {random.randint(600, 1200)})")
            scroll_count += 1
            time.sleep(0.5)

            floor_info = s.get_floor_info()
            if floor_info:
                current_floor = floor_info["current"]
                if current_floor > last_floor:
                    floors_climbed = current_floor - last_floor
                    s.stats["floors"] += floors_climbed
                    s.lg(f"爬楼 #{scroll_count} → 当前: {current_floor}/{total_floors} 楼 (本帖已爬 {current_floor - start_floor} 层)")
                    last_floor = current_floor
                    stuck_count = 0

                    if s.update_progress:
                        s.update_progress(s.stats)
                    s._update_countdown_display()
                else:
                    stuck_count += 1
                    if stuck_count >= 3:
                        s.lg("楼层卡住，加大滚动距离")
                        s.pg.run_js("window.scrollBy(0, 1500)")
                        time.sleep(1)
                        stuck_count = 0

            if scroll_count >= 200:
                s.lg("达到最大滚动次数，停止爬楼")
                break

        floors_climbed_total = current_floor - start_floor
        s.lg(f"爬楼完成: 滚动 {scroll_count} 次，从 {start_floor} 爬到 {current_floor}，共爬 {floors_climbed_total} 层")
        return floors_climbed_total

    def _scroll_page_quick(s):
        floor_info = s.get_floor_info()
        if not floor_info:
            s.lg("⚠ 无法获取楼层信息，快速滚动3次")
            for _ in range(3):
                if not s.run:
                    break
                time.sleep(random.uniform(1, 2))
                s.pg.run_js(f"window.scrollBy(0, {random.randint(400, 800)})")
            s.stats["floors"] += 3
            if s.update_progress:
                s.update_progress(s.stats)
            s._update_countdown_display()
            return 3

        total_floors = floor_info["total"]
        start_floor = floor_info["current"]
        target_climb = random.randint(3, 5)

        s.lg(f"[快速浏览] 开始楼层: {start_floor}，目标爬: {target_climb} 层 (总楼层: {total_floors})")

        scroll_count = 0
        current_floor = start_floor
        last_floor = start_floor

        while (current_floor - start_floor) < target_climb and current_floor < total_floors and s.run:
            time.sleep(random.uniform(1, 2))
            s.pg.run_js(f"window.scrollBy(0, {random.randint(400, 800)})")
            scroll_count += 1
            time.sleep(0.3)

            floor_info = s.get_floor_info()
            if floor_info:
                current_floor = floor_info["current"]
                if current_floor > last_floor:
                    floors_climbed = current_floor - last_floor
                    s.stats["floors"] += floors_climbed
                    last_floor = current_floor
                    if s.update_progress:
                        s.update_progress(s.stats)
                    s._update_countdown_display()

            if scroll_count >= 10:
                break

        floors_climbed_total = current_floor - start_floor
        s.lg(f"[快速浏览] 完成: 从 {start_floor} 爬到 {current_floor}，共爬 {floors_climbed_total} 层")
        return floors_climbed_total

    def _scroll_page_legacy(s, duration=None):
        if duration is None:
            duration = random.uniform(8, 15)

        s.lg(f"传统滚动模式 {duration:.1f}s...")
        start = time.time()
        while time.time() - start < duration and s.run:
            dist = random.randint(150, 400)
            s.pg.run_js(f"window.scrollBy(0, {dist})")
            time.sleep(random.uniform(1.0, 3.0))

            at_bottom = s.pg.run_js("""
            return (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 100;
            """)
            if at_bottom:
                s._random_delay(1, 3, "阅读完毕")
                break
        return 0

    def do_like(s, index=0):
        try:
            result = s.pg.run_js(f"""
            function clickLike(idx) {{
                const buttons = document.querySelectorAll('button.btn-toggle-reaction-like');
                if (buttons.length > idx) {{
                    const btn = buttons[idx];
                    if (!btn.classList.contains('has-like') && !btn.classList.contains('my-likes')) {{
                        btn.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                        setTimeout(() => btn.click(), 300);
                        return true;
                    }}
                }}
                return false;
            }}
            return clickLike({index});
            """)

            if result:
                s._random_delay(0.8, 1.5, "点赞后")
                if index == 0:
                    s.stats["like"] += 1
                    s.lg("点赞主帖成功")
                else:
                    s.stats["like_reply"] += 1
                    s.lg(f"点赞回复 #{index} 成功")
                if s.update_progress:
                    s.update_progress(s.stats)
                return True
        except Exception as e:
            s.lg("点赞失败: " + str(e))
        return False

    def do_reply(s, content=None):
        try:
            if content is None:
                content = random.choice(s.cfg["tpl"])

            s.lg("准备回复: " + content)
            clicked = s.pg.run_js("""
            function clickReply() {
                const btn = document.querySelector('.topic-footer-main-buttons button.create');
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }
            return clickReply();
            """)

            if not clicked:
                s.lg("未找到回复按钮")
                return False

            s._random_delay(1.5, 3, "等待编辑器")
            s.pg.run_js(f"""
            (function() {{
                const textarea = document.querySelector('#reply-control textarea, .d-editor-input');
                if (textarea) {{
                    textarea.focus();
                    textarea.value = '{content}';
                    textarea.dispatchEvent(new Event('input', {{bubbles: true}}));
                }}
            }})();
            """)

            s._random_delay(0.8, 1.5, "输入内容后")
            submitted = s.pg.run_js("""
            function submit() {
                const btn = document.querySelector('#reply-control button.create');
                if (btn && !btn.disabled) {
                    btn.click();
                    return true;
                }
                return false;
            }
            return submit();
            """)

            if submitted:
                s._random_delay(2, 4, "回复提交后")
                s.stats["reply"] += 1
                s.lg("回复成功")
                if s.update_progress:
                    s.update_progress(s.stats)
                return True
            else:
                s.lg("提交失败")

        except Exception as e:
            s.lg("回复失败: " + str(e))
        return False

    def browse_topic(s, topic):
        title = topic["title"]
        topic_id = topic.get("id", "")
        is_unread = topic.get("isUnread", False)

        if is_unread:
            s.lg("浏览未读话题: " + title)
        else:
            s.lg("浏览已读话题: " + title)

        try:
            clicked = s.pg.run_js(f"""
            function clickTopic() {{
                const topicRow = document.querySelector('tr.topic-list-item[data-topic-id="{topic_id}"]');
                if (!topicRow) return false;
                const link = topicRow.querySelector('a.title.raw-link.raw-topic-link');
                if (!link) return false;
                link.click();
                return true;
            }}
            return clickTopic();
            """)

            if not clicked:
                s.lg("点击话题失败，跳过")
                return False

            s._random_delay(3, 5, "话题页面加载")
            s.lg("话题页面已加载")
            s.stats["topic"] += 1

            if s.update_progress:
                s.update_progress(s.stats)
            s._update_countdown_display()

            s.scroll_page()
            s._random_delay(1, 2, "阅读后")

            btn_count = s.pg.run_js("""
            return document.querySelectorAll('button.btn-toggle-reaction-like').length;
            """) or 0

            s.lg(f"找到 {btn_count} 个点赞按钮")

            if s.enable_like and btn_count > 0 and random.random() < s.cfg["like_rate"]:
                s.do_like(0)
                if s.enable_wait:
                    s._random_delay(s.cfg["wait_min"], s.cfg["wait_max"], "点赞后休息")

            if s.enable_like and btn_count > 1:
                for i in range(1, min(btn_count, 5)):
                    if random.random() < s.cfg["like_reply_rate"]:
                        s.do_like(i)
                        if s.enable_wait:
                            s._random_delay(s.cfg["wait_min"], s.cfg["wait_max"], "点赞回复后")

            if s.enable_reply and random.random() < s.cfg["reply_rate"]:
                if s.enable_wait:
                    s._random_delay(s.cfg["wait_min"], s.cfg["wait_max"], "准备回帖")
                s.do_reply()

            s.lg("返回板块列表...")
            s.pg.back()
            s._random_delay(2, 3, "返回后等待")

            if is_unread:
                badge_gone = s.pg.run_js(f"""
                function checkBadgeGone() {{
                    const topicRow = document.querySelector('tr.topic-list-item[data-topic-id="{topic_id}"]');
                    if (!topicRow) return true;
                    const badge = topicRow.querySelector('.badge.badge-notification.new-topic');
                    return !badge;
                }}
                return checkBadgeGone();
                """)
                if badge_gone:
                    s.lg("✓ 小蓝点已消失，话题已标记为已读")
                else:
                    s.lg("⚠ 小蓝点仍存在，可能需要更长浏览时间")

            return True
        except Exception as e:
            s.lg("浏览失败: " + str(e))
            try:
                s.pg.back()
                time.sleep(1)
            except:
                pass
            return False

    def _update_countdown_display(s):
        if not s.update_countdown or not s.start_time:
            return

        elapsed_time = time.time() - s.start_time
        elapsed_minutes = int(elapsed_time / 60)
        elapsed_seconds = int(elapsed_time % 60)

        if s.browse_mode == "quick":
            total_read = s.stats.get("topic", 0)
            read_desc = f"主题{total_read}"
        else:
            topics = s.stats.get("topic", 0)
            floors = s.stats.get("floors", 0)
            total_read = topics + floors
            read_desc = f"帖{topics}+楼{floors}"

        if s.mode == "topics":
            remaining = s.target_value - total_read
            text = f"剩余: {remaining} | 已读: {total_read} ({read_desc}) | 用时: {elapsed_minutes}:{elapsed_seconds:02d}"
        elif s.mode == "time":
            remaining_secs = s.target_value * 60 - elapsed_time
            if remaining_secs > 0:
                text = f"剩余: {int(remaining_secs / 60)}:{int(remaining_secs % 60):02d} | 已读: {total_read} ({read_desc})"
            else:
                text = f"已超时 | 已读: {total_read} ({read_desc})"
        else:
            text = f"用时: {elapsed_minutes}:{elapsed_seconds:02d} | 已读: {total_read} ({read_desc})"

        s.update_countdown(text)

    def _check_target_reached(s):
        if s.mode == "topics":
            if s.browse_mode == "quick":
                return s.stats.get("topic", 0) >= s.target_value
            else:
                total_read = s.stats.get("topic", 0) + s.stats.get("floors", 0)
                return total_read >= s.target_value
        elif s.mode == "time":
            if s.start_time:
                elapsed_minutes = (time.time() - s.start_time) / 60
                return elapsed_minutes >= s.target_value
        return False

    def browse_cat(s, cat):
        if s._check_target_reached():
            return 0

        topics = s.get_topics(cat)
        s.lg(f"找到 {len(topics)} 个帖子")
        if not topics:
            return 0

        count = min(random.randint(3, 8), len(topics))
        selected = random.sample(topics, count)

        browsed = 0
        for topic in selected:
            if not s.run or s._check_target_reached():
                s.run = False
                break

            if s.browse_topic(topic):
                browsed += 1

            if s._check_target_reached():
                s.run = False
                break

            if s.run and s.enable_wait:
                s._random_delay(0.5, 1.5, "准备下一个话题")

        return browsed

    def run_session(s):
        s.run = True
        s.stats = {"topic": 0, "like": 0, "reply": 0, "like_reply": 0, "floors": 0}
        s.start_time = time.time()

        if not s.start():
            return

        login_success = False
        try:
            if not s.check_login(wait_for_login=True, max_wait=300, check_interval=5):
                s.lg("登录检查失败或超时，任务终止")
                return

            login_success = True
            s.get_level_info()

            enabled = [c for c in s.cats if c.get("e", True)]
            random.shuffle(enabled)

            s.lg("=" * 30)
            if s.mode == "topics":
                s.lg(f"运行模式: 帖子数量限制 (目标: {s.target_value} 个帖子)")
            elif s.mode == "time":
                s.lg(f"运行模式: 时间限制 (目标: {s.target_value} 分钟)")
            else:
                s.lg("运行模式: 无尽模式 (手动停止)")
            s.lg("=" * 30)

            while s.run:
                for cat in enabled:
                    if not s.run or s._check_target_reached():
                        s.run = False
                        break

                    s.browse_cat(cat)

                    if s._check_target_reached():
                        s.run = False
                        break

                    if s.enable_wait and s.run:
                        s._random_delay(s.cfg["wait_min"] + 1, s.cfg["wait_max"] + 2, "切换板块")

                if s.mode != "endless" or not s.run:
                    break

                if s.run:
                    random.shuffle(enabled)
                    s.lg("=" * 30)
                    s.lg("继续下一轮浏览...")
                    s.lg("=" * 30)

            elapsed_time = time.time() - s.start_time
            total_read = s.stats.get("topic", 0) + s.stats.get("floors", 0)

            s.lg("=" * 30)
            s.lg("完成!")
            s.lg(f"浏览帖子: {s.stats['topic']}")
            s.lg(f"爬楼总数: {s.stats.get('floors', 0)} 楼")
            s.lg(f"已读总计: {total_read} (帖子+爬楼)")
            s.lg(f"点赞主帖: {s.stats['like']}")
            s.lg(f"点赞回复: {s.stats['like_reply']}")
            s.lg(f"回帖数量: {s.stats['reply']}")
            s.lg(f"耗时: {int(elapsed_time / 60)} 分 {int(elapsed_time % 60)} 秒")
            s.lg("=" * 30)

            if s.pg:
                s.lg("重新获取等级信息验证效果...")
                s.get_level_info(is_final=True)

        finally:
            s.run = False
            if login_success:
                s.close()


class GUI:
    def __init__(s):
        s.rt = tk.Tk()
        s.rt.title(f"Linux.do 刷帖助手 v{VERSION}")
        s.rt.geometry("720x960")
        s.rt.minsize(680, 850)
        s.rt.configure(bg="#1a1a2e")

        try:
            icon_path = get_icon_path()
            if os.path.exists(icon_path):
                s.rt.iconbitmap(icon_path)
        except:
            pass

        s.cats = [c.copy() for c in CATS]
        s.cfg = CFG.copy()
        
        # 尝试读取上次保存的浏览器配置
        s._load_local_config()

        s.bot = None
        s.th = None
        s.req_labels = {}
        s.initial_requirements = []

        s.tray_icon = None
        s.tray_thread = None
        s._running_status = "就绪"

        s._ui()
        s._center_window()

        if TRAY_SUPPORT:
            s._init_tray()

        s.rt.protocol("WM_DELETE_WINDOW", s._on_close_window)
        s.rt.after(1000, s._check_update)

    def _load_local_config(s):
        """加载已保存的本地配置，如未保存则尝试智能探测"""
        saved_path = ""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    saved_path = data.get("browser_path", "")
            except:
                pass

        if saved_path and os.path.exists(saved_path):
            s.cfg["browser_path"] = saved_path
        else:
            s.cfg["browser_path"] = find_default_browser_path()

    def _save_local_config(s):
        """保存配置到本地 json 文件"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"browser_path": s.browser_path_var.get().strip()}, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _select_browser_path(s):
        """弹出文件选择对话框选取浏览器 exe"""
        file_path = filedialog.askopenfilename(
            title="选择浏览器可执行文件 (Chrome / Edge / Chromium)",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")] if platform.system() == "Windows" else [("All Files", "*")],
        )
        if file_path:
            s.browser_path_var.set(file_path)
            s._save_local_config()

    def _check_update(s):
        def check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "LinuxDoHelper"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    latest_version = data.get("tag_name", "").lstrip("v")
                    release_url = data.get("html_url", "")
                    if latest_version and s._compare_versions(latest_version, VERSION) > 0:
                        s.rt.after(0, lambda: s._show_update_dialog(latest_version, release_url))
            except:
                pass

        threading.Thread(target=check, daemon=True).start()

    def _compare_versions(s, v1, v2):
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            while len(parts1) < len(parts2):
                parts1.append(0)
            while len(parts2) < len(parts1):
                parts2.append(0)
            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except:
            return 0

    def _show_update_dialog(s, latest_version, release_url):
        result = messagebox.askyesno(
            "发现新版本",
            f"🎉 发现新版本 v{latest_version}\n\n当前版本: v{VERSION}\n最新版本: v{latest_version}\n\n是否打开下载页面？",
            icon="info",
        )
        if result and release_url:
            import webbrowser
            webbrowser.open(release_url)

    def _init_tray(s):
        if not TRAY_SUPPORT:
            return

        def create_menu():
            return pystray.Menu(
                pystray.MenuItem("显示窗口", s._show_window, default=True),
                pystray.MenuItem("开始运行", s._tray_start),
                pystray.MenuItem("停止运行", s._tray_stop),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", s._tray_quit),
            )

        s.tray_icon = pystray.Icon(
            "LinuxDoHelper",
            create_tray_image("#0f3460"),
            "Linux.do 刷帖助手 - 就绪",
            create_menu(),
        )
        s.tray_thread = threading.Thread(target=s.tray_icon.run, daemon=True)
        s.tray_thread.start()

    def _update_tray_status(s, status, stats=None):
        if not TRAY_SUPPORT or not s.tray_icon:
            return

        s._running_status = status
        color = "#00ff88" if status == "运行中" else ("#ffaa00" if "停止" in status or "完成" in status else "#0f3460")
        s.tray_icon.icon = create_tray_image(color)

        tooltip = f"Linux.do 刷帖助手 v{VERSION} - {status}\n"
        if s.bot and s.bot.start_time:
            elapsed_time = time.time() - s.bot.start_time
            total_read = s.bot.stats.get("topic", 0) + s.bot.stats.get("floors", 0)
            tooltip += f"用时: {int(elapsed_time / 60)}:{int(elapsed_time % 60):02d}\n"

        if stats:
            total_read = stats.get("topic", 0) + stats.get("floors", 0)
            tooltip += f"已读: {total_read} | 点赞: {stats.get('like', 0) + stats.get('like_reply', 0)} | 回复: {stats.get('reply', 0)}"

        s.tray_icon.title = tooltip

    def _show_window(s, icon=None, item=None):
        s.rt.after(0, s._do_show_window)

    def _do_show_window(s):
        s.rt.deiconify()
        s.rt.lift()
        s.rt.focus_force()

    def _tray_start(s, icon=None, item=None):
        s.rt.after(0, s._start)

    def _tray_stop(s, icon=None, item=None):
        s.rt.after(0, s._stop)

    def _tray_quit(s, icon=None, item=None):
        if s.tray_icon:
            s.tray_icon.stop()
        s.rt.after(0, s._close)

    def _on_close_window(s):
        s._save_local_config()
        if TRAY_SUPPORT and s.tray_icon:
            s.rt.withdraw()
        else:
            s._close()

    def _center_window(s):
        s.rt.update_idletasks()
        w = s.rt.winfo_width()
        h = s.rt.winfo_height()
        sw = s.rt.winfo_screenwidth()
        sh = s.rt.winfo_screenheight()
        s.rt.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _close(s):
        s._save_local_config()
        if s.bot:
            s.bot.stop()
        if s.tray_icon:
            try:
                s.tray_icon.stop()
            except:
                pass
        s.rt.destroy()

    def _ui(s):
        s.status = tk.StringVar(value="就绪")
        content = tk.Frame(s.rt, bg="#1a1a2e")
        content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 用户信息栏
        info_frame = tk.LabelFrame(
            content,
            text=" 用户信息 ",
            bg="#1a1a2e",
            fg="#00d9ff",
            font=(FONT_FAMILY, 10, "bold"),
        )
        info_frame.pack(fill=tk.X, padx=15, pady=5)

        info_inner = tk.Frame(info_frame, bg="#1a1a2e")
        info_inner.pack(fill=tk.X, padx=10, pady=5)

        s.user_label = tk.StringVar(value="用户: 未登录")
        s.level_label = tk.StringVar(value="等级: -")
        s.next_level_label = tk.StringVar(value="下一级: -")

        tk.Label(info_inner, textvariable=s.user_label, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=10)
        tk.Label(info_inner, textvariable=s.level_label, bg="#1a1a2e", fg="#00ff88", font=(FONT_FAMILY, 10, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(info_inner, textvariable=s.next_level_label, bg="#1a1a2e", fg="#ffaa00", font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=10)

        # 升级进度面板
        progress_frame = tk.LabelFrame(
            content,
            text=" 升级进度追踪 ",
            bg="#1a1a2e",
            fg="#00d9ff",
            font=(FONT_FAMILY, 10, "bold"),
        )
        progress_frame.pack(fill=tk.X, padx=15, pady=5)

        s.progress_canvas = tk.Canvas(progress_frame, bg="#1a1a2e", height=180, highlightthickness=0)
        s.progress_scrollbar = ttk.Scrollbar(progress_frame, orient="vertical", command=s.progress_canvas.yview)
        s.progress_inner = tk.Frame(s.progress_canvas, bg="#1a1a2e")

        s.progress_inner.bind("<Configure>", lambda e: s.progress_canvas.configure(scrollregion=s.progress_canvas.bbox("all")))
        s.progress_canvas.create_window((0, 0), window=s.progress_inner, anchor="nw")
        s.progress_canvas.configure(yscrollcommand=s.progress_scrollbar.set)

        s.progress_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        s.progress_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # 运行模式选择
        mode_frame = tk.LabelFrame(
            content,
            text=" 运行模式 ",
            bg="#1a1a2e",
            fg="#00d9ff",
            font=(FONT_FAMILY, 10, "bold"),
        )
        mode_frame.pack(fill=tk.X, padx=15, pady=5)

        mode_inner = tk.Frame(mode_frame, bg="#1a1a2e")
        mode_inner.pack(fill=tk.X, padx=10, pady=6)

        s.mode_var = tk.StringVar(value="endless")

        tk.Radiobutton(mode_inner, text="无尽模式", variable=s.mode_var, value="endless", bg="#1a1a2e", fg="#eaeaea", selectcolor="#16213e", activebackground="#1a1a2e", activeforeground="#00d9ff", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=10)

        tk.Radiobutton(mode_inner, text="帖子数量:", variable=s.mode_var, value="topics", bg="#1a1a2e", fg="#eaeaea", selectcolor="#16213e", activebackground="#1a1a2e", activeforeground="#00d9ff", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=10)
        s.topics_var = tk.StringVar(value="50")
        tk.Entry(mode_inner, textvariable=s.topics_var, width=6, bg="#16213e", fg="#eaeaea", insertbackground="#eaeaea").pack(side=tk.LEFT, padx=2)
        tk.Label(mode_inner, text="个", bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)

        tk.Radiobutton(mode_inner, text="时间限制:", variable=s.mode_var, value="time", bg="#1a1a2e", fg="#eaeaea", selectcolor="#16213e", activebackground="#1a1a2e", activeforeground="#00d9ff", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=10)
        s.time_var = tk.StringVar(value="30")
        tk.Entry(mode_inner, textvariable=s.time_var, width=6, bg="#16213e", fg="#eaeaea", insertbackground="#eaeaea").pack(side=tk.LEFT, padx=2)
        tk.Label(mode_inner, text="分钟", bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)

        browse_mode_inner = tk.Frame(mode_frame, bg="#1a1a2e")
        browse_mode_inner.pack(fill=tk.X, padx=10, pady=(0, 6))

        tk.Label(browse_mode_inner, text="浏览模式:", bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=(0, 10))
        s.browse_mode_var = tk.StringVar(value="deep")

        tk.Radiobutton(browse_mode_inner, text="深度爬楼（完整阅读）", variable=s.browse_mode_var, value="deep", bg="#1a1a2e", fg="#eaeaea", selectcolor="#16213e", activebackground="#1a1a2e", activeforeground="#00d9ff", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(browse_mode_inner, text="快速浏览（3-5层换帖）", variable=s.browse_mode_var, value="quick", bg="#1a1a2e", fg="#eaeaea", selectcolor="#16213e", activebackground="#1a1a2e", activeforeground="#00d9ff", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=5)

        # 控制栏及路径配置
        ctrl_frame = tk.LabelFrame(
            content,
            text=" 基础环境与网络配置 ",
            bg="#1a1a2e",
            fg="#00d9ff",
            font=(FONT_FAMILY, 10, "bold"),
        )
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        # 浏览器路径配置行
        browser_row = tk.Frame(ctrl_frame, bg="#1a1a2e")
        browser_row.pack(fill=tk.X, padx=10, pady=4)

        tk.Label(browser_row, text="浏览器路径:", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)
        s.browser_path_var = tk.StringVar(value=s.cfg.get("browser_path", ""))
        tk.Entry(
            browser_row,
            textvariable=s.browser_path_var,
            bg="#16213e",
            fg="#eaeaea",
            insertbackground="#eaeaea",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Button(
            browser_row,
            text="选择路径...",
            command=s._select_browser_path,
            bg="#0f3460",
            fg="white",
            font=(FONT_FAMILY, 8),
        ).pack(side=tk.RIGHT)

        # 控制按钮与代理行
        ctrl = tk.Frame(ctrl_frame, bg="#1a1a2e", pady=3)
        ctrl.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(ctrl, text="代理地址:", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)
        s.proxy_var = tk.StringVar(value=s.cfg["proxy"])
        tk.Entry(ctrl, textvariable=s.proxy_var, width=15, bg="#16213e", fg="#eaeaea", insertbackground="#eaeaea").pack(side=tk.LEFT, padx=5)

        s.start_btn = tk.Button(ctrl, text="开始", command=s._start, width=9, bg="#0f3460", fg="white", font=(FONT_FAMILY, 10, "bold"))
        s.start_btn.pack(side=tk.LEFT, padx=10)

        s.stop_btn = tk.Button(ctrl, text="停止", command=s._stop, width=7, bg="#e94560", fg="white", state=tk.DISABLED)
        s.stop_btn.pack(side=tk.LEFT)

        s.countdown_var = tk.StringVar(value="")
        s.countdown_label = tk.Label(ctrl, textvariable=s.countdown_var, bg="#1a1a2e", fg="#00d9ff", font=(FONT_FAMILY, 9, "bold"))
        s.countdown_label.pack(side=tk.LEFT, padx=10)

        # 主区域
        main = tk.Frame(content, bg="#1a1a2e")
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=6)

        # 左侧 - 板块选择
        left = tk.LabelFrame(
            main,
            text=" 板块选择 ",
            bg="#1a1a2e",
            fg="#00d9ff",
            font=(FONT_FAMILY, 10, "bold"),
        )
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        s.cat_vars = {}
        for cat in s.cats:
            var = tk.BooleanVar(value=cat.get("e", True))
            s.cat_vars[cat["n"]] = var
            cb = tk.Checkbutton(
                left,
                text=cat["n"],
                variable=var,
                bg="#1a1a2e",
                fg="#eaeaea",
                selectcolor="#0f3460",
                activebackground="#1a1a2e",
                command=lambda n=cat["n"], v=var: s._toggle_cat(n, v),
            )
            cb.pack(anchor=tk.W, pady=1)

        # 右侧 - 日志与参数
        right = tk.Frame(main, bg="#1a1a2e")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right, text="运行日志", bg="#1a1a2e", fg="#00d9ff", font=(FONT_FAMILY, 10, "bold")).pack(anchor=tk.W)
        s.log = scrolledtext.ScrolledText(right, height=11, bg="#16213e", fg="#eaeaea", font=(FONT_MONO, 9), insertbackground="#eaeaea")
        s.log.pack(fill=tk.BOTH, expand=True, pady=4)
        s.log.config(state=tk.DISABLED)

        param = tk.Frame(right, bg="#1a1a2e")
        param.pack(fill=tk.X, pady=3)

        param_row1 = tk.Frame(param, bg="#1a1a2e")
        param_row1.pack(fill=tk.X, pady=2)

        s.enable_like_var = tk.BooleanVar(value=False)
        tk.Checkbutton(param_row1, text="自动点赞", variable=s.enable_like_var, bg="#1a1a2e", fg="#eaeaea", selectcolor="#0f3460", activebackground="#1a1a2e").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(param_row1, text="点赞率:", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)
        s.like_var = tk.StringVar(value="30")
        tk.Entry(param_row1, textvariable=s.like_var, width=4, bg="#16213e", fg="#eaeaea").pack(side=tk.LEFT)
        tk.Label(param_row1, text="%", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT, padx=(0, 15))

        s.enable_reply_var = tk.BooleanVar(value=False)
        s.reply_checkbox = tk.Checkbutton(param_row1, text="自动回复", variable=s.enable_reply_var, bg="#1a1a2e", fg="#eaeaea", selectcolor="#0f3460", activebackground="#1a1a2e", command=s._on_reply_toggle)
        s.reply_checkbox.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(param_row1, text="回复率:", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)
        s.reply_var = tk.StringVar(value="5")
        tk.Entry(param_row1, textvariable=s.reply_var, width=4, bg="#16213e", fg="#eaeaea").pack(side=tk.LEFT)
        tk.Label(param_row1, text="%", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)

        param_row2 = tk.Frame(param, bg="#1a1a2e")
        param_row2.pack(fill=tk.X, pady=2)

        s.enable_wait_var = tk.BooleanVar(value=True)
        tk.Checkbutton(param_row2, text="启用等待", variable=s.enable_wait_var, bg="#1a1a2e", fg="#eaeaea", selectcolor="#0f3460", activebackground="#1a1a2e").pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(param_row2, text="等待:", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT)
        s.wait_var = tk.StringVar(value="1-3")
        tk.Entry(param_row2, textvariable=s.wait_var, width=6, bg="#16213e", fg="#eaeaea").pack(side=tk.LEFT)
        tk.Label(param_row2, text="秒", bg="#1a1a2e", fg="#eaeaea").pack(side=tk.LEFT, padx=(0, 5))

        stats_frame = tk.LabelFrame(right, text=" 本次统计 ", bg="#1a1a2e", fg="#00d9ff", font=(FONT_FAMILY, 10, "bold"))
        stats_frame.pack(fill=tk.X, pady=3)

        stats_inner = tk.Frame(stats_frame, bg="#1a1a2e")
        stats_inner.pack(fill=tk.X, padx=10, pady=3)

        s.stats_topic = tk.StringVar(value="帖子: 0")
        s.stats_floors = tk.StringVar(value="爬楼: 0")
        s.stats_total = tk.StringVar(value="已读: 0")
        s.stats_like = tk.StringVar(value="点赞: 0")
        s.stats_reply = tk.StringVar(value="回复: 0")

        tk.Label(stats_inner, textvariable=s.stats_topic, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=6)
        tk.Label(stats_inner, textvariable=s.stats_floors, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=6)
        tk.Label(stats_inner, textvariable=s.stats_total, bg="#1a1a2e", fg="#00ff88", font=(FONT_FAMILY, 9, "bold")).pack(side=tk.LEFT, padx=6)
        tk.Label(stats_inner, textvariable=s.stats_like, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=6)
        tk.Label(stats_inner, textvariable=s.stats_reply, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9)).pack(side=tk.LEFT, padx=6)

    def _toggle_cat(s, name, var):
        for cat in s.cats:
            if cat["n"] == name:
                cat["e"] = var.get()
                break

    def _on_reply_toggle(s):
        if s.enable_reply_var.get():
            result = messagebox.askokcancel(
                "风险提醒",
                "⚠️ 自动回复功能风险提示\n\n据社区反馈，L站可能存在检测自动回复的机制：\n• 曾有用户因自动回复被举报\n• 可能影响账号信任等级\n• 建议仅在必要时谨慎使用\n\n是否确定要启用自动回复功能？",
                icon="warning",
            )
            if not result:
                s.enable_reply_var.set(False)

    def _update_info(s, info, is_final=False):
        def update():
            if info.get("username"):
                s.user_label.set("用户: " + info["username"])
            if info.get("level"):
                s.level_label.set("等级: " + info["level"] + "级")
            if info.get("nextLevel"):
                s.next_level_label.set("下一级: " + info["nextLevel"] + "级")

            requirements = info.get("requirements", [])
            if requirements:
                if not s.initial_requirements:
                    s.initial_requirements = requirements.copy()
                    s._build_progress_panel(requirements)
                elif is_final:
                    s._update_final_progress(requirements)

        s.rt.after(0, update)

    def _update_final_progress(s, new_requirements):
        for new_req in new_requirements:
            name = new_req.get("name", "")
            new_current = new_req.get("current", "0")
            if name in s.req_labels:
                labels = s.req_labels[name]
                try:
                    initial = int(labels["initial"].replace(",", ""))
                    new_val = int(new_current.replace(",", ""))
                    actual_added = new_val - initial
                    labels["current_var"].set(new_current)
                    labels["added_var"].set(f"+{actual_added}" if actual_added >= 0 else str(actual_added))
                except:
                    labels["current_var"].set(new_current)

    def _build_progress_panel(s, requirements):
        for widget in s.progress_inner.winfo_children():
            widget.destroy()
        s.req_labels = {}

        headers = ["指标", "初始值", "当前值", "目标值", "本次+"]
        col_padx = [(10, 20), (10, 20), (10, 15), (10, 15), (10, 10)]

        for col, header in enumerate(headers):
            tk.Label(s.progress_inner, text=header, bg="#1a1a2e", fg="#00d9ff", font=(FONT_FAMILY, 9, "bold"), anchor="w").grid(row=0, column=col, padx=col_padx[col], pady=4, sticky="w")

        for row, req in enumerate(requirements[:8], start=1):
            name = req.get("name", "")
            current = req.get("current", "0")
            required = req.get("required", "0")

            tk.Label(s.progress_inner, text=name, bg="#1a1a2e", fg="#eaeaea", font=(FONT_FAMILY, 9), anchor="w").grid(row=row, column=0, padx=col_padx[0], pady=2, sticky="w")
            tk.Label(s.progress_inner, text=current, bg="#1a1a2e", fg="#888888", font=(FONT_FAMILY, 9), anchor="w").grid(row=row, column=1, padx=col_padx[1], pady=2, sticky="w")

            current_var = tk.StringVar(value=current)
            tk.Label(s.progress_inner, textvariable=current_var, bg="#1a1a2e", fg="#00ff88", font=(FONT_FAMILY, 9, "bold"), anchor="w").grid(row=row, column=2, padx=col_padx[2], pady=2, sticky="w")

            tk.Label(s.progress_inner, text=required, bg="#1a1a2e", fg="#ffaa00", font=(FONT_FAMILY, 9), anchor="w").grid(row=row, column=3, padx=col_padx[3], pady=2, sticky="w")

            added_var = tk.StringVar(value="+0")
            tk.Label(s.progress_inner, textvariable=added_var, bg="#1a1a2e", fg="#00d9ff", font=(FONT_FAMILY, 9, "bold"), anchor="w").grid(row=row, column=4, padx=col_padx[4], pady=2, sticky="w")

            s.req_labels[name] = {"initial": current, "current_var": current_var, "added_var": added_var}

    def _update_progress(s, stats):
        def update():
            if not s.req_labels:
                return
            for name, labels in s.req_labels.items():
                try:
                    initial = int(labels["initial"].replace(",", ""))
                    added = 0
                    if any(k in name for k in ["浏览", "阅读", "话题"]):
                        added = stats.get("topic", 0)
                    elif any(k in name for k in ["点赞", "赞"]):
                        added = stats.get("like", 0) + stats.get("like_reply", 0)
                    elif any(k in name for k in ["回复", "发帖"]):
                        added = stats.get("reply", 0)

                    if added > 0:
                        labels["current_var"].set(str(initial + added))
                        labels["added_var"].set(f"+{added}")
                except:
                    pass
            s._update_tray_status("运行中", stats)

        s.rt.after(0, update)

    def _update_countdown(s, text):
        s.rt.after(0, lambda: s.countdown_var.set(text))

    def _lg(s, msg):
        def log():
            ts = datetime.now().strftime("%H:%M:%S")
            s.log.config(state=tk.NORMAL)
            s.log.insert(tk.END, f"[{ts}] {msg}\n")
            s.log.see(tk.END)
            s.log.config(state=tk.DISABLED)

            if s.bot:
                topics = s.bot.stats.get("topic", 0)
                floors = s.bot.stats.get("floors", 0)
                s.stats_topic.set(f"帖子: {topics}")
                s.stats_floors.set(f"爬楼: {floors}")
                s.stats_total.set(f"已读: {topics + floors}")
                s.stats_like.set(f"点赞: {s.bot.stats['like'] + s.bot.stats['like_reply']}")
                s.stats_reply.set(f"回复: {s.bot.stats['reply']}")

        s.rt.after(0, log)

    def _start(s):
        if s.th and s.th.is_alive():
            return

        # 保存并读取浏览器可执行路径
        s._save_local_config()
        s.cfg["browser_path"] = s.browser_path_var.get().strip()

        s.cfg["proxy"] = s.proxy_var.get()
        try:
            s.cfg["like_rate"] = int(s.like_var.get()) / 100
        except:
            s.cfg["like_rate"] = 0.3
        try:
            s.cfg["reply_rate"] = int(s.reply_var.get()) / 100
        except:
            s.cfg["reply_rate"] = 0.05
        try:
            parts = s.wait_var.get().split("-")
            s.cfg["wait_min"] = float(parts[0])
            s.cfg["wait_max"] = float(parts[1]) if len(parts) > 1 else float(parts[0])
        except:
            s.cfg["wait_min"], s.cfg["wait_max"] = 1, 3

        s.start_btn.config(state=tk.DISABLED)
        s.stop_btn.config(state=tk.NORMAL)
        s.status.set("运行中...")
        s._update_tray_status("运行中")
        s.initial_requirements = []

        mode = s.mode_var.get()
        target_value = 0
        if mode == "topics":
            try:
                target_value = int(s.topics_var.get())
            except:
                target_value = 50
        elif mode == "time":
            try:
                target_value = int(s.time_var.get())
            except:
                target_value = 30

        s.bot = Bot(
            s.cfg,
            s.cats,
            s._lg,
            s._update_info,
            s._update_progress,
            s._update_countdown,
            mode=mode,
            target_value=target_value,
            enable_like=s.enable_like_var.get(),
            enable_reply=s.enable_reply_var.get(),
            enable_wait=s.enable_wait_var.get(),
            browse_mode=s.browse_mode_var.get(),
        )
        s.th = threading.Thread(target=s._run, daemon=True)
        s.th.start()

    def _run(s):
        try:
            s.bot.run_session()
        finally:
            s.rt.after(0, s._done)

    def _done(s):
        s.start_btn.config(state=tk.NORMAL)
        s.stop_btn.config(state=tk.DISABLED)
        s.status.set("已完成")
        if s.bot:
            s._update_tray_status("已完成", s.bot.stats)
        else:
            s._update_tray_status("已完成")

    def _stop(s):
        if s.bot:
            s.bot.stop()
        s.status.set("正在停止...")
        s._update_tray_status("已停止")

    def run(s):
        s.rt.mainloop()


if __name__ == "__main__":
    GUI().run()
