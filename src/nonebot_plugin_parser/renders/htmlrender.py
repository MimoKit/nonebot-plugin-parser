import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from typing_extensions import override

from nonebot import require

require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import get_new_page, template_to_html

from . import resources
from .base import ImageRenderer, pconfig

_FILE_URI_RE = re.compile(r"file://[^\s\"')]+")


def _file_uri_to_data_uri(uri: str) -> str:
    """把 file:// 资源内联为 data URI，避免 about:blank 无法加载本地文件。"""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return uri

    path = Path(unquote(parsed.path))
    if not path.is_file():
        return uri

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _embed_local_file_uris(html: str) -> str:
    return _FILE_URI_RE.sub(lambda match: _file_uri_to_data_uri(match.group(0)), html)


class HtmlRenderer(ImageRenderer):
    """HTML 渲染器"""

    @override
    async def render_image(self) -> bytes:
        await self.result.ensure_downloads_complete(img_only=True)

        logo = resources.RESOURCES_DIR / f"{self.result.platform.name}.png"
        logo = logo.as_uri() if logo.exists() else None

        font = pconfig.custom_font or resources.DEFAULT_FONT_PATH
        font = font.as_uri() if font.exists() else None

        html = await template_to_html(
            template_path=str(self.templates_dir),
            template_name="card.html.jinja2",
            logo=logo,
            font=font,
            result=self.result,
            font_weight=pconfig.custom_font_weight,
            fallback_pic=resources.random_fallback_pic().as_uri(),
            play_button=resources.DEFAULT_VIDEO_BUTTON_PATH.as_uri(),
            default_avatar=resources.DEFAULT_AVATAR_PATH.as_uri(),
        )
        html = _embed_local_file_uris(html)

        # htmlrender 的 template_to_pic 不会透传 omit_background；
        # 外层画布需要透明 PNG，因此直接走 Playwright 截图。
        async with get_new_page(
            device_scale_factor=2,
            viewport={"width": 800, "height": 100},
        ) as page:
            await page.set_content(html, wait_until="load")
            await page.wait_for_timeout(80)
            return await page.screenshot(
                full_page=True,
                type="png",
                omit_background=True,
            )
