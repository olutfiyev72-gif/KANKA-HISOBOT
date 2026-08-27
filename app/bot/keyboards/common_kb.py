"""Common keyboards used across the bot."""
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel button keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Bekor qilish")
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_confirm_inline(prefix: str, data: str = "") -> InlineKeyboardMarkup:
    """Yes/No confirmation inline keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha", callback_data=f"{prefix}:confirm:{data}")
    builder.button(text="❌ Bekor qilish", callback_data=f"{prefix}:cancel:{data}")
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard() -> ReplyKeyboardMarkup:
    """Back button keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Orqaga")
    builder.button(text="❌ Bekor qilish")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_skip_keyboard(cancel: bool = True) -> ReplyKeyboardMarkup:
    """Skip and cancel keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏩ O'tkazib yuborish")
    if cancel:
        builder.button(text="❌ Bekor qilish")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_today_keyboard() -> ReplyKeyboardMarkup:
    """Date selection with today default."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Bugun")
    builder.button(text="📅 Kecha")
    builder.button(text="❌ Bekor qilish")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    """Remove keyboard."""
    return ReplyKeyboardRemove()
