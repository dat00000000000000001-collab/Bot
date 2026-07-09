"""
bot.py
Bot Telegram tìm/tra cứu tài liệu & đề thi từ toanmath.com,
nganhangdethi.org và dethi.violet.vn

Lệnh hỗ trợ:
  /start        - hướng dẫn
  /moinhat [n]  - n tài liệu mới nhất, gộp cả 3 nguồn (mặc định 5)
  /timkiem <từ khóa>          - tìm theo từ khóa trên cả 3 nguồn
  /lop <10|11|12|thpt>        - xem danh sách loại tài liệu (chỉ toanmath.com)
  /theolop <lop> <loại> [n]   - vd: /theolop 12 "Đề HSG" 5 (chỉ toanmath.com)
  /subscribe    - đăng ký nhận thông báo khi có bài mới (tự động check định kỳ)
  /unsubscribe  - hủy đăng ký
"""

import json
import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from scraper import get_latest, get_by_category, search_keyword, CATEGORIES_BY_CLASS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "1800"))  # 30 phút

DATA_FILE = Path(__file__).parent / "subscribers.json"


def _load_subscribers() -> set:
    if DATA_FILE.exists():
        try:
            return set(json.loads(DATA_FILE.read_text()))
        except Exception:
            return set()
    return set()


def _save_subscribers(subs: set):
    DATA_FILE.write_text(json.dumps(list(subs)))


def _load_seen_urls() -> set:
    seen_file = Path(__file__).parent / "seen_urls.json"
    if seen_file.exists():
        try:
            return set(json.loads(seen_file.read_text()))
        except Exception:
            return set()
    return set()


def _save_seen_urls(urls: set):
    seen_file = Path(__file__).parent / "seen_urls.json"
    # chỉ giữ 200 url gần nhất để file không phình to
    urls_list = list(urls)[-200:]
    seen_file.write_text(json.dumps(urls_list))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Xin chào! Mình là bot tra cứu tài liệu/đề thi từ toanmath.com, "
        "nganhangdethi.org và dethi.violet.vn.\n\n"
        "Các lệnh:\n"
        "/moinhat [số lượng] - tài liệu mới nhất (gộp cả 3 nguồn)\n"
        "/timkiem <từ khóa> - tìm theo từ khóa trên cả 3 nguồn, vd: /timkiem oxyz\n"
        "/lop <10|11|12|thpt> - xem các loại tài liệu của lớp đó (toanmath.com)\n"
        '/theolop <lớp> "<loại>" [số lượng] - vd: /theolop 12 "Đề HSG" 5 (toanmath.com)\n'
        "/subscribe - nhận thông báo tự động khi có bài mới\n"
        "/unsubscribe - hủy nhận thông báo"
    )
    await update.message.reply_text(text)


async def moinhat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = 5
    if context.args:
        try:
            limit = max(1, min(20, int(context.args[0])))
        except ValueError:
            pass
    await update.message.reply_text("Đang lấy danh sách mới nhất...")
    try:
        items = get_latest(limit=limit)
    except Exception as e:
        logger.exception("Lỗi get_latest")
        await update.message.reply_text(f"Có lỗi khi lấy dữ liệu: {e}")
        return
    if not items:
        await update.message.reply_text("Không lấy được dữ liệu, thử lại sau.")
        return
    lines = [
        f"{i+1}. [{it.get('source', '?')}] {it['title']}\n{it['url']}"
        for i, it in enumerate(items)
    ]
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)


async def timkiem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Cú pháp: /timkiem <từ khóa>\nVí dụ: /timkiem oxyz")
        return
    keyword = " ".join(context.args)
    await update.message.reply_text(f"Đang tìm '{keyword}'...")
    try:
        items = search_keyword(keyword, limit=10)
    except Exception as e:
        logger.exception("Lỗi search_keyword")
        await update.message.reply_text(f"Có lỗi khi tìm kiếm: {e}")
        return
    if not items:
        await update.message.reply_text(
            "Không tìm thấy kết quả phù hợp. Thử từ khóa khác hoặc ngắn hơn."
        )
        return
    lines = [
        f"{i+1}. [{it.get('source', '?')}] {it['title']}\n{it['url']}"
        for i, it in enumerate(items)
    ]
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)


async def lop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] not in CATEGORIES_BY_CLASS:
        await update.message.reply_text(
            "Cú pháp: /lop <10|11|12|thpt>\nVí dụ: /lop 12"
        )
        return
    class_key = context.args[0]
    labels = list(CATEGORIES_BY_CLASS[class_key].keys())
    text = f"Các loại tài liệu cho lớp {class_key}:\n" + "\n".join(
        f"- {l}" for l in labels
    )
    text += f'\n\nDùng: /theolop {class_key} "<loại>" [số lượng]'
    await update.message.reply_text(text)


async def theolop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            'Cú pháp: /theolop <lớp> "<loại>" [số lượng]\n'
            'Ví dụ: /theolop 12 "Đề HSG" 5'
        )
        return

    class_key = args[0]
    if class_key not in CATEGORIES_BY_CLASS:
        await update.message.reply_text("Lớp không hợp lệ. Dùng: 10, 11, 12 hoặc thpt")
        return

    limit = 5
    rest = args[1:]
    if rest and rest[-1].isdigit():
        limit = max(1, min(20, int(rest[-1])))
        rest = rest[:-1]
    category_label = " ".join(rest).strip('"')

    if category_label not in CATEGORIES_BY_CLASS[class_key]:
        available = ", ".join(CATEGORIES_BY_CLASS[class_key].keys())
        await update.message.reply_text(
            f"Loại '{category_label}' không hợp lệ cho lớp {class_key}.\n"
            f"Các loại có sẵn: {available}"
        )
        return

    await update.message.reply_text("Đang lấy dữ liệu...")
    try:
        items = get_by_category(class_key, category_label, limit=limit)
    except Exception as e:
        logger.exception("Lỗi get_by_category")
        await update.message.reply_text(f"Có lỗi khi lấy dữ liệu: {e}")
        return
    if not items:
        await update.message.reply_text("Không lấy được dữ liệu, thử lại sau.")
        return
    lines = [f"{i+1}. {it['title']}\n{it['url']}" for i, it in enumerate(items)]
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = _load_subscribers()
    chat_id = update.effective_chat.id
    subs.add(chat_id)
    _save_subscribers(subs)
    await update.message.reply_text(
        "Đã đăng ký! Bạn sẽ nhận thông báo tự động khi trang có bài mới "
        f"(kiểm tra mỗi {CHECK_INTERVAL_SECONDS // 60} phút)."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = _load_subscribers()
    chat_id = update.effective_chat.id
    subs.discard(chat_id)
    _save_subscribers(subs)
    await update.message.reply_text("Đã hủy đăng ký thông báo tự động.")


async def check_new_posts(context: ContextTypes.DEFAULT_TYPE):
    """Job chạy định kỳ: kiểm tra bài mới và gửi cho các subscriber."""
    subs = _load_subscribers()
    if not subs:
        return

    try:
        items = get_latest(limit=10, source="all")
    except Exception:
        logger.exception("Lỗi khi check bài mới")
        return

    seen = _load_seen_urls()
    new_items = [it for it in items if it["url"] not in seen]

    if not new_items:
        return

    # lần chạy đầu tiên (seen rỗng): chỉ lưu lại, không spam toàn bộ danh sách
    if not seen:
        _save_seen_urls({it["url"] for it in items})
        return

    for it in reversed(new_items):  # gửi theo thứ tự cũ -> mới
        text = f"📄 Tài liệu mới [{it.get('source', '?')}]:\n{it['title']}\n{it['url']}"
        for chat_id in subs:
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text=text, disable_web_page_preview=True
                )
            except Exception:
                logger.exception(f"Không gửi được cho {chat_id}")

    seen.update(it["url"] for it in new_items)
    _save_seen_urls(seen)


def main():
    if not BOT_TOKEN:
        raise SystemExit("Chưa đặt biến môi trường BOT_TOKEN")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("moinhat", moinhat))
    app.add_handler(CommandHandler("timkiem", timkiem))
    app.add_handler(CommandHandler("lop", lop))
    app.add_handler(CommandHandler("theolop", theolop))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    app.job_queue.run_repeating(check_new_posts, interval=CHECK_INTERVAL_SECONDS, first=30)

    logger.info("Bot đang chạy...")
    app.run_polling()


if __name__ == "__main__":
    main()
