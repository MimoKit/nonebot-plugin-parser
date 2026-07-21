import re
from typing import Any, ClassVar

from httpx import AsyncClient
from nonebot import logger

from ..base import (
    COMMON_TIMEOUT,
    Platform,
    BaseParser,
    PlatformEnum,
    ParseException,
    handle,
)


class DouyinParser(BaseParser):
    platform: ClassVar[Platform] = Platform(name=PlatformEnum.DOUYIN, display_name="抖音")

    # https://v.douyin.com/_2ljF4AmKL8
    @handle("v.douyin", r"v\.douyin\.com/[a-zA-Z0-9_\-]+")
    @handle("jx.douyin", r"jx\.douyin\.com/[a-zA-Z0-9_\-]+")
    async def _parse_short_link(self, searched: re.Match[str]):
        url = f"https://{searched.group(0)}"
        return await self.parse_with_redirect(url)

    # https://www.douyin.com/video/7521023890996514083
    # https://www.douyin.com/note/7469411074119322899
    @handle("douyin", r"douyin\.com/(?P<ty>video|note)/(?P<vid>\d+)")
    @handle("iesdouyin", r"iesdouyin\.com/share/(?P<ty>slides|video|note)/(?P<vid>\d+)")
    @handle("m.douyin", r"m\.douyin\.com/share/(?P<ty>slides|video|note)/(?P<vid>\d+)")
    # https://jingxuan.douyin.com/m/video/7574300896016862490?app=yumme&utm_source=copy_link
    @handle("jingxuan.douyin", r"jingxuan\.douyin.com/m/(?P<ty>slides|video|note)/(?P<vid>\d+)")
    async def _parse_douyin(self, searched: re.Match[str]):
        ty, vid = searched.group("ty"), searched.group("vid")

        # slides 动态图同样需要详情接口中的 images[].video；旧 slides 接口可能只返回静态图片。
        try:
            from .detail import fetch_aweme_detail

            return self._parse_detail(await fetch_aweme_detail(vid))
        except Exception as e:
            logger.warning(f"failed to parse detail API for {vid}, falling back to legacy parser: {e}")

        if ty == "slides":
            return await self.parse_slides(vid)

        for url in (self._build_m_douyin_url(ty, vid), self._build_iesdouyin_url(ty, vid)):
            try:
                return await self.parse_video(url)
            except ParseException as e:
                logger.warning(f"failed to parse {url}, error: {e}")
                continue
        raise ParseException("分享已删除或资源直链提取失败, 请稍后再试")

    @staticmethod
    def _build_iesdouyin_url(ty: str, vid: str) -> str:
        return f"https://www.iesdouyin.com/share/{ty}/{vid}"

    @staticmethod
    def _build_m_douyin_url(ty: str, vid: str) -> str:
        return f"https://m.douyin.com/share/{ty}/{vid}"

    @staticmethod
    def _first_url(value: Any) -> str | None:
        """从抖音返回的 url_list/urlList 结构中取第一条有效地址。"""
        if isinstance(value, str):
            return value or None
        if isinstance(value, dict):
            for key in ("url_list", "urlList", "url"):
                if result := DouyinParser._first_url(value.get(key)):
                    return result
        if isinstance(value, (list, tuple)):
            for item in value:
                if result := DouyinParser._first_url(item):
                    return result
        return None

    @staticmethod
    def _is_video_url(url: str | None) -> bool:
        if not url:
            return False
        lowered = url.lower()
        return not any(
            marker in lowered
            for marker in (".mp3", ".m4a", ".aac", "ies-music", "audio/", "mime_type=audio")
        )

    @staticmethod
    def _duration_seconds(video: dict[str, Any] | None) -> float | None:
        if not video:
            return None
        duration = video.get("duration")
        if not isinstance(duration, (int, float)) or duration <= 0:
            return None
        return duration / 1000 if duration > 1000 else float(duration)

    def _parse_detail(self, detail: dict[str, Any]):
        author_data = detail.get("author") or {}
        avatar_url = self._first_url(
            author_data.get("avatar_thumb") or author_data.get("avatar_medium") or author_data.get("avatar_larger")
        )
        author = self.create_author(str(author_data.get("nickname") or "未知用户"), avatar_url)
        result = self.result(
            title=detail.get("desc") or detail.get("title"),
            author=author,
            timestamp=detail.get("create_time"),
        )

        image_urls: list[str] = []
        dynamic_urls: list[tuple[str, dict[str, Any]]] = []
        for image in detail.get("images") or []:
            if not isinstance(image, dict):
                continue
            if image_url := self._first_url(image.get("url_list") or image.get("urlList")):
                image_urls.append(image_url)
            image_video = image.get("video")
            if isinstance(image_video, dict):
                video_url = self._first_url((image_video.get("play_addr") or {}).get("url_list"))
                if self._is_video_url(video_url):
                    dynamic_urls.append((video_url, image_video))

        top_video = detail.get("video")
        if isinstance(top_video, dict):
            top_video_url = self._first_url((top_video.get("play_addr") or {}).get("url_list"))
            if self._is_video_url(top_video_url) and not any(url == top_video_url for url, _ in dynamic_urls):
                dynamic_urls.append((top_video_url, top_video))

        if dynamic_urls:
            # 动态图先发一张静态封面，再发送原始动态视频；不再转 GIF，也不额外合并音乐。
            if image_urls:
                result.contents.extend(self.create_images([image_urls[0]]))
            for video_url, video_data in dynamic_urls:
                cover_url = self._first_url((video_data.get("cover") or {}).get("url_list"))
                result.contents.append(
                    self.create_video(
                        video_url.replace("playwm", "play"), cover_url, self._duration_seconds(video_data)
                    )
                )
        elif image_urls:
            result.contents.extend(self.create_images(image_urls))

        return result

    async def parse_video(self, url: str, video_id: str | None = None):
        from . import video

        if video_id:
            try:
                from .detail import fetch_aweme_detail

                return self._parse_detail(await fetch_aweme_detail(video_id))
            except Exception as e:
                logger.warning(f"failed to parse detail API for {video_id}, falling back to page: {e}")

        async with AsyncClient(
            headers=self.ios_headers,
            timeout=COMMON_TIMEOUT,
            follow_redirects=False,
            verify=False,
        ) as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise ParseException(f"status: {response.status_code}")
            text = response.text

        pattern = re.compile(
            pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
            flags=re.DOTALL,
        )
        matched = pattern.search(text)

        if not matched or not matched.group(1):
            raise ParseException("can't find _ROUTER_DATA in html")

        video_data = video.decoder.decode(matched.group(1).strip()).video_data

        # 作者
        author = self.create_author(
            video_data.author.nickname,
            video_data.avatar_url,
        )

        # 先以部分数据构建结果，后续再填充内容，避免使用临时变量
        result = self.result(
            title=video_data.desc,
            author=author,
            timestamp=video_data.create_time,
        )

        # 添加图片内容
        if image_urls := video_data.image_urls:
            result.contents.extend(self.create_images(image_urls))
        # 添加视频内容
        elif video_url := video_data.video_url:
            result.video = self.create_video(
                video_url,
                video_data.cover_url,
                video_data.duration,
            )

        return result

    async def parse_slides(self, video_id: str):
        from . import slides

        url = "https://www.iesdouyin.com/web/api/v2/aweme/slidesinfo/"
        params = {
            "aweme_ids": f"[{video_id}]",
            "request_source": "200",
        }
        async with AsyncClient(headers=self.android_headers, verify=False) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        slides_data = slides.decoder.decode(response.content).aweme_details[0]

        # 作者
        author = self.create_author(slides_data.name, slides_data.avatar_url)

        # 先以部分数据构建结果，后续再填充内容，避免使用临时变量
        result = self.result(
            title=slides_data.desc,
            author=author,
            timestamp=slides_data.create_time,
        )

        # 优先取动图
        if dynamic_urls := slides_data.dynamic_urls:
            if image_urls := slides_data.image_urls:
                result.contents.extend(self.create_images([image_urls[0]]))
            for dynamic_url in dynamic_urls:
                result.contents.append(self.create_video(dynamic_url))
        elif image_urls := slides_data.image_urls:
            result.contents.extend(self.create_images(image_urls))

        return result
