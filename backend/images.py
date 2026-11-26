"""图片上传与处理（T-12）。

处理流程：
1. 文件头魔数校验（仅信任魔数，不信任扩展名或 MIME）；
2. 解码前尺寸限制（防内存炸弹）；
3. EXIF 方向校正后剥离全部元数据；
4. 静态图（JPEG/PNG/静态 WebP）转 WebP quality 85，长边 ≤1600；
5. GIF / 动画 WebP 转动画 WebP（帧数 ≤300，保留循环与时长）；
6. 生成缩略图（长边 ≤400，动画缩略图只保留第一帧）；
7. 使用随机 UUID 文件名保存到 uploads/{YYYY}/{MM}/。

图片不去重；删除帖子的图片清理在 T-17 实现。
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

import config

MAX_UPLOAD_BYTES = 5 * 1024 * 1024          # 单张原始上传 ≤5MB
MAX_STATIC_WEBP_BYTES = 5 * 1024 * 1024    # 静态成品 ≤5MB
MAX_ANIMATED_WEBP_BYTES = 10 * 1024 * 1024 # 动画成品 ≤10MB
MAX_THUMB_BYTES = 1 * 1024 * 1024          # 缩略图 ≤1MB
MAX_ORIGINAL_EDGE = 1600                   # 原图长边
MAX_THUMB_EDGE = 400                       # 缩略图长边
MAX_FRAMES = 300                           # 动画最大帧数
MAX_DECODE_EDGE = 8000                     # 解码前最长边限制
MAX_DECODE_PIXELS = 40_000_000             # 解码前总像素限制
WEBP_QUALITY = 85


class ImageError(Exception):
    """图片校验或处理失败。"""


@dataclass
class ProcessedImage:
    path: str          # 原图相对路径（WebP）
    thumb_path: str    # 缩略图相对路径
    bytes: int         # 原图字节数
    thumb_bytes: int   # 缩略图字节数
    width: int
    height: int
    is_animated: bool


def _detect_format(data: bytes) -> str:
    """按文件头魔数判断格式，返回 'jpeg' | 'png' | 'gif' | 'webp'，否则抛错。"""
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ImageError("不支持的图片格式")


def _fit_size(size: tuple[int, int], max_edge: int) -> tuple[int, int]:
    """等比缩放到长边不超过 max_edge（不放大）。"""
    w, h = size
    edge = max(w, h)
    if edge <= max_edge:
        return w, h
    scale = max_edge / edge
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))


def _encode_static_webp(img: Image.Image, max_edge: int) -> bytes:
    """静态图转 WebP（保留透明通道），返回编码后的字节。"""
    img = ImageOps.exif_transpose(img)          # 按 EXIF 方向校正
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    img = img.resize(_fit_size(img.size, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


def _is_animated(img: Image.Image, fmt: str) -> bool:
    if fmt == "gif":
        return getattr(img, "n_frames", 1) > 1
    if fmt == "webp":
        return bool(getattr(img, "is_animated", False))
    return False


def _encode_animated_webp(img: Image.Image) -> bytes:
    """动画（GIF/WebP）转动画 WebP，帧数上限校验，保留循环与时长。"""
    frames = []
    duration = getattr(img, "info", {}).get("duration", 100)
    loop = getattr(img, "info", {}).get("loop", 0)
    n = getattr(img, "n_frames", 1)
    if n > MAX_FRAMES:
        raise ImageError(f"动画帧数不能超过 {MAX_FRAMES} 帧")

    for i, frame in enumerate(ImageSequence.Iterator(img)):
        if i >= MAX_FRAMES:
            break
        frame = frame.convert("RGBA")
        frame = frame.resize(_fit_size(frame.size, MAX_ORIGINAL_EDGE), Image.LANCZOS)
        frames.append(frame)

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        quality=WEBP_QUALITY,
        method=6,
        loop=loop,
        duration=duration,
    )
    return buf.getvalue()


def _first_frame_thumb(img: Image.Image, fmt: str) -> bytes:
    """缩略图：静态图缩到长边 400；动画取第一帧缩到长边 400。"""
    if _is_animated(img, fmt):
        img = next(iter(ImageSequence.Iterator(img))).copy()
    else:
        img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    img = img.resize(_fit_size(img.size, MAX_THUMB_EDGE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


def _save(data: bytes) -> tuple[str, Path]:
    """按 uploads/{YYYY}/{MM}/{uuid}.webp 保存，返回 (相对路径, 绝对路径)。"""
    now = datetime.now(timezone.utc)
    rel_dir = Path("uploads") / f"{now.year:04d}" / f"{now.month:02d}"
    abs_dir = config.Config.UPLOAD_DIR / f"{now.year:04d}" / f"{now.month:02d}"
    abs_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.webp"
    rel_path = (rel_dir / name).as_posix()
    abs_path = abs_dir / name
    abs_path.write_bytes(data)
    return rel_path, abs_path


def process_image(raw: bytes) -> ProcessedImage:
    """处理单张图片，返回落盘后的元信息。失败抛 ImageError。"""
    if not raw:
        raise ImageError("图片为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageError("图片不能超过 5MB")

    fmt = _detect_format(raw)

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise ImageError("图片解码失败") from exc

    # 解码前尺寸限制
    w, h = img.size
    if max(w, h) > MAX_DECODE_EDGE or w * h > MAX_DECODE_PIXELS:
        raise ImageError("图片尺寸过大")

    animated = _is_animated(img, fmt)

    if animated:
        main_data = _encode_animated_webp(img)
    else:
        main_data = _encode_static_webp(img, MAX_ORIGINAL_EDGE)

    limit = MAX_ANIMATED_WEBP_BYTES if animated else MAX_STATIC_WEBP_BYTES
    if len(main_data) > limit:
        raise ImageError("图片处理后过大")

    thumb_data = _first_frame_thumb(img, fmt)
    if len(thumb_data) > MAX_THUMB_BYTES:
        # 缩略图超限时降质重试
        thumb_data = _first_frame_thumb(img, fmt)

    rel_path, abs_path = _save(main_data)
    thumb_rel, thumb_abs = _save(thumb_data)

    return ProcessedImage(
        path=rel_path,
        thumb_path=thumb_rel,
        bytes=abs_path.stat().st_size,
        thumb_bytes=thumb_abs.stat().st_size,
        width=w,
        height=h,
        is_animated=animated,
    )
