"""
Extractor for YouTube channel data from raw HTML or embedded ytInitialData JSON.
"""

from __future__ import annotations
import json
import re
from typing import Any, Optional
from youtube_parser.models import (
    YouTubeChannelExportResult,
    YouTubeChannelInfo,
    YouTubeVideo,
)


def parse_duration_to_seconds(duration_str: Optional[str]) -> Optional[int]:
    """Converts a duration string like '14:25' or '1:02:15' to total seconds."""
    if not duration_str:
        return None
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, TypeError):
        return None
    return None


def parse_count_text_to_int(count_text: Optional[str]) -> Optional[int]:
    """Converts strings like '18.5M subscribers', '450K views', '1,234 views' to integer."""
    if not count_text:
        return None
    cleaned = count_text.strip().replace(",", "")
    match = re.search(r"([\d\.]+)\s*([KkMmBb])?", cleaned)
    if not match:
        return None

    number_str, suffix = match.groups()
    try:
        num = float(number_str)
        if suffix:
            suffix = suffix.upper()
            if suffix == "K":
                num *= 1_000
            elif suffix == "M":
                num *= 1_000_000
            elif suffix == "B":
                num *= 1_000_000_000
        return int(num)
    except (ValueError, TypeError):
        return None


def extract_yt_initial_data(html_content: str) -> dict[str, Any]:
    """
    Extracts the ytInitialData JSON object from YouTube channel HTML.
    Supports raw JSON input, standard var assignment, and window assignment.
    """
    trimmed = html_content.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            return json.loads(trimmed)
        except json.JSONDecodeError:
            pass

    # Pattern 1: var ytInitialData = {...};
    patterns = [
        r"var\s+ytInitialData\s*=\s*(\{.*?\});\s*(?:</script>|\n|var )",
        r'window\["ytInitialData"\]\s*=\s*(\{.*?\});\s*(?:</script>|\n)',
        r"ytInitialData\s*=\s*(\{.*?\});",
    ]

    for pat in patterns:
        match = re.search(pat, html_content, re.DOTALL)
        if match:
            raw_json = match.group(1)
            try:
                return json.loads(raw_json)
            except json.JSONDecodeError:
                # Try finding balanced braces if regex cut too early
                start_idx = match.start(1)
                depth = 0
                for i in range(start_idx, len(html_content)):
                    if html_content[i] == "{":
                        depth += 1
                    elif html_content[i] == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = html_content[start_idx : i + 1]
                            try:
                                return json.loads(candidate)
                            except json.JSONDecodeError:
                                break
                            break

    # Look for script tag containing ytInitialData
    start_marker = "ytInitialData"
    pos = html_content.find(start_marker)
    if pos != -1:
        brace_pos = html_content.find("{", pos)
        if brace_pos != -1:
            depth = 0
            for i in range(brace_pos, len(html_content)):
                if html_content[i] == "{":
                    depth += 1
                elif html_content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = html_content[brace_pos : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

    raise ValueError("Could not extract ytInitialData from provided YouTube HTML content.")


class YouTubeHTMLParser:
    """
    Parses ytInitialData into structured YouTubeChannelExportResult.
    """

    def parse(self, html_or_json: str) -> YouTubeChannelExportResult:
        data = extract_yt_initial_data(html_or_json)
        channel_info = self._extract_channel_info(data)
        videos = self._extract_videos(data)

        # Update total video count if not set or smaller
        if channel_info.total_videos_count is None or channel_info.total_videos_count < len(videos):
            channel_info.total_videos_count = len(videos)
        if not channel_info.total_videos_text:
            channel_info.total_videos_text = f"{len(videos)} videos"

        return YouTubeChannelExportResult(
            status="success",
            channel_info=channel_info,
            total_videos=len(videos),
            videos=videos,
        )

    def _extract_channel_info(self, data: dict[str, Any]) -> YouTubeChannelInfo:
        channel_name = "Unknown Channel"
        handle: Optional[str] = None
        description: Optional[str] = None
        subscriber_count_text: Optional[str] = None
        total_videos_text: Optional[str] = None
        avatar_url: Optional[str] = None
        banner_url: Optional[str] = None
        is_verified = False
        channel_id: Optional[str] = None
        custom_url: Optional[str] = None

        # Check metadata.channelMetadataRenderer
        metadata = data.get("metadata", {}).get("channelMetadataRenderer", {})
        if metadata:
            channel_name = metadata.get("title", channel_name)
            description = metadata.get("description")
            channel_id = metadata.get("externalId")
            custom_url = metadata.get("vanityChannelUrl") or metadata.get("channelUrl")
            avatars = metadata.get("avatar", {}).get("thumbnails", [])
            if avatars:
                avatar_url = avatars[-1].get("url")

        # Check modern header: header.pageHeaderRenderer
        header = data.get("header", {})
        page_header = header.get("pageHeaderRenderer", {})
        if page_header:
            vm = page_header.get("content", {}).get("pageHeaderViewModel", {})
            if vm:
                # Title
                title_vm = vm.get("title", {})
                title_node = title_vm.get("dynamicTextViewModel", {}).get("text", {})
                if title_node.get("content"):
                    channel_name = title_node["content"]

                # Verified / Official Artist Channel badge check
                dt_vm = title_vm.get("dynamicTextViewModel", {})
                acc_label = (
                    title_vm.get("rendererContext", {}).get("accessibilityContext", {}).get("label", "")
                    or dt_vm.get("rendererContext", {}).get("accessibilityContext", {}).get("label", "")
                )
                if "official artist" in acc_label.lower() or "verified" in acc_label.lower():
                    is_verified = True

                for att in title_node.get("attachmentRuns", []):
                    img_name = (
                        att.get("element", {})
                        .get("type", {})
                        .get("imageType", {})
                        .get("image", {})
                        .get("sources", [{}])[0]
                        .get("clientResource", {})
                        .get("imageName", "")
                    )
                    if any(k in img_name.upper() for k in ("BADGE", "CHECK", "VERIFIED")):
                        is_verified = True

                # Description
                desc_vm = vm.get("description", {}).get("descriptionPreviewViewModel", {}).get("description", {})
                if desc_vm.get("content"):
                    description = desc_vm["content"]

                # Metadata rows: handle, subscribers, video count
                metadata_rows = vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                for row in metadata_rows:
                    parts = row.get("metadataParts", [])
                    for part in parts:
                        text = part.get("text", {}).get("content", "")
                        if text.startswith("@"):
                            handle = text
                        elif "subscriber" in text.lower():
                            subscriber_count_text = text
                        elif "video" in text.lower():
                            total_videos_text = text

                # Avatar
                avatar_sources = (
                    vm.get("image", {})
                    .get("decoratedAvatarViewModel", {})
                    .get("avatar", {})
                    .get("avatarViewModel", {})
                    .get("image", {})
                    .get("sources", [])
                )
                if avatar_sources:
                    avatar_url = avatar_sources[-1].get("url")

                # Banner
                banner_sources = (
                    vm.get("banner", {})
                    .get("imageBannerViewModel", {})
                    .get("image", {})
                    .get("sources", [])
                )
                if banner_sources:
                    banner_url = banner_sources[-1].get("url")

        # Check classic header: header.c4TabbedHeaderRenderer
        c4_header = header.get("c4TabbedHeaderRenderer", {})
        if c4_header:
            channel_name = c4_header.get("title", channel_name)
            channel_id = c4_header.get("channelId", channel_id)
            if c4_header.get("subscriberCountText", {}).get("simpleText"):
                subscriber_count_text = c4_header["subscriberCountText"]["simpleText"]
            if c4_header.get("videosCountText", {}).get("runs"):
                total_videos_text = "".join(r.get("text", "") for r in c4_header["videosCountText"]["runs"])
            if not avatar_url and c4_header.get("avatar", {}).get("thumbnails"):
                avatar_url = c4_header["avatar"]["thumbnails"][-1].get("url")
            if not banner_url and c4_header.get("banner", {}).get("thumbnails"):
                banner_url = c4_header["banner"]["thumbnails"][-1].get("url")
            for badge in c4_header.get("badges", []):
                style = badge.get("metadataBadgeRenderer", {}).get("style", "")
                if "VERIFIED" in style:
                    is_verified = True

        # Check direct channel_info dictionary (e.g. from JSON export)
        if "channel_info" in data and isinstance(data["channel_info"], dict):
            ci = data["channel_info"]
            return YouTubeChannelInfo(
                channel_id=ci.get("channel_id"),
                channel_name=ci.get("channel_name", "Unknown Channel"),
                handle=ci.get("handle"),
                description=ci.get("description"),
                subscriber_count_text=ci.get("subscriber_count_text"),
                subscriber_count=ci.get("subscriber_count") or parse_count_text_to_int(ci.get("subscriber_count_text")),
                total_videos_text=ci.get("total_videos_text"),
                total_videos_count=ci.get("total_videos_count") or parse_count_text_to_int(ci.get("total_videos_text")),
                avatar_url=ci.get("avatar_url"),
                banner_url=ci.get("banner_url"),
                is_verified=ci.get("is_verified", False),
                custom_url=ci.get("custom_url"),
                joined_date_text=ci.get("joined_date_text"),
            )

        # Check direct top-level fields for convenience
        if "channel_name" in data:
            channel_name = data.get("channel_name", channel_name)
        if "handle" in data:
            handle = data.get("handle", handle)
        if "description" in data:
            description = data.get("description", description)
        if "subscriber_count_text" in data:
            subscriber_count_text = data.get("subscriber_count_text", subscriber_count_text)
        if "total_videos_text" in data:
            total_videos_text = data.get("total_videos_text", total_videos_text)
        if "avatar_url" in data:
            avatar_url = data.get("avatar_url", avatar_url)
        if "banner_url" in data:
            banner_url = data.get("banner_url", banner_url)

        # Fallback handle if not found
        if not handle and custom_url and "/@" in custom_url:
            handle = "@" + custom_url.split("/@")[-1].split("/")[0]
        elif not handle and channel_name:
            clean_name = re.sub(r"[^\w]", "", channel_name).lower()
            handle = f"@{clean_name}"

        return YouTubeChannelInfo(
            channel_id=channel_id,
            channel_name=channel_name,
            handle=handle,
            description=description,
            subscriber_count_text=subscriber_count_text,
            subscriber_count=parse_count_text_to_int(subscriber_count_text),
            total_videos_text=total_videos_text,
            total_videos_count=parse_count_text_to_int(total_videos_text),
            avatar_url=avatar_url,
            banner_url=banner_url,
            is_verified=is_verified,
            custom_url=custom_url,
        )

    def _extract_videos(self, data: dict[str, Any]) -> list[YouTubeVideo]:
        videos: list[YouTubeVideo] = []
        seen_ids: set[str] = set()

        # If data already contains a direct "videos" list (e.g. from JSON export)
        if "videos" in data and isinstance(data["videos"], list):
            for v in data["videos"]:
                if isinstance(v, dict) and "video_id" in v:
                    vid_id = v["video_id"]
                    if vid_id not in seen_ids:
                        seen_ids.add(vid_id)
                        videos.append(
                            YouTubeVideo(
                                video_id=vid_id,
                                title=v.get("title", "Untitled"),
                                url=v.get("url", f"https://www.youtube.com/watch?v=f{vid_id}"),
                                thumbnail_url=v.get("thumbnail_url"),
                                duration_text=v.get("duration_text"),
                                duration_seconds=v.get("duration_seconds")
                                or parse_duration_to_seconds(v.get("duration_text")),
                                view_count_text=v.get("view_count_text"),
                                view_count=v.get("view_count")
                                or parse_count_text_to_int(v.get("view_count_text")),
                                published_time_text=v.get("published_time_text"),
                                is_short=v.get("is_short", False),
                                description_snippet=v.get("description_snippet"),
                            )
                        )
            if videos:
                return videos

        # Traverse tabs in contents.twoColumnBrowseResultsRenderer.tabs
        tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
        for tab in tabs:
            tab_renderer = tab.get("tabRenderer", {})
            tab_content = tab_renderer.get("content", {})
            items = []

            # richGridRenderer
            if "richGridRenderer" in tab_content:
                items = tab_content["richGridRenderer"].get("contents", [])
            elif "sectionListRenderer" in tab_content:
                sections = tab_content["sectionListRenderer"].get("contents", [])
                for sec in sections:
                    shelf = sec.get("itemSectionRenderer", {}).get("contents", [])
                    for sub in shelf:
                        if "gridRenderer" in sub:
                            items.extend(sub["gridRenderer"].get("items", []))

            for item in items:
                # 1. Check richItemRenderer -> lockupViewModel (YouTube modern 2025/2026 UI)
                if "richItemRenderer" in item:
                    rir_content = item["richItemRenderer"].get("content", {})
                    if "lockupViewModel" in rir_content:
                        video_obj = self._parse_lockup_view_model(rir_content["lockupViewModel"])
                        if video_obj and video_obj.video_id not in seen_ids:
                            seen_ids.add(video_obj.video_id)
                            videos.append(video_obj)
                        continue

                video_data = None
                is_short = False

                if "richItemRenderer" in item:
                    content = item["richItemRenderer"].get("content", {})
                    if "videoRenderer" in content:
                        video_data = content["videoRenderer"]
                    elif "reelItemRenderer" in content:
                        video_data = content["reelItemRenderer"]
                        is_short = True
                elif "videoRenderer" in item:
                    video_data = item["videoRenderer"]
                elif "gridVideoRenderer" in item:
                    video_data = item["gridVideoRenderer"]

                if not video_data:
                    continue

                vid_id = video_data.get("videoId")
                if not vid_id or vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)

                # Title
                title = "Untitled"
                if "title" in video_data:
                    t_obj = video_data["title"]
                    if "runs" in t_obj and t_obj["runs"]:
                        title = "".join(r.get("text", "") for r in t_obj["runs"])
                    elif "simpleText" in t_obj:
                        title = t_obj["simpleText"]
                elif "headline" in video_data:
                    title = video_data["headline"].get("simpleText", "Untitled")

                # Thumbnail
                thumb_url = None
                thumbs = video_data.get("thumbnail", {}).get("thumbnails", [])
                if thumbs:
                    thumb_url = thumbs[-1].get("url")

                # Duration
                duration_text = None
                if "lengthText" in video_data:
                    duration_text = video_data["lengthText"].get("simpleText")

                # View count
                view_text = None
                if "viewCountText" in video_data:
                    v_obj = video_data["viewCountText"]
                    if "simpleText" in v_obj:
                        view_text = v_obj["simpleText"]
                    elif "runs" in v_obj:
                        view_text = "".join(r.get("text", "") for r in v_obj["runs"])

                # Published time
                published_time = None
                if "publishedTimeText" in video_data:
                    published_time = video_data["publishedTimeText"].get("simpleText")

                # Description snippet
                snippet = None
                if "descriptionSnippet" in video_data:
                    s_runs = video_data["descriptionSnippet"].get("runs", [])
                    snippet = "".join(r.get("text", "") for r in s_runs)

                videos.append(
                    YouTubeVideo(
                        video_id=vid_id,
                        title=title,
                        url=f"https://www.youtube.com/watch?v={vid_id}",
                        thumbnail_url=thumb_url,
                        duration_text=duration_text,
                        duration_seconds=parse_duration_to_seconds(duration_text),
                        view_count_text=view_text,
                        view_count=parse_count_text_to_int(view_text),
                        published_time_text=published_time,
                        is_short=is_short,
                        description_snippet=snippet,
                    )
                )

        return videos

    def _parse_lockup_view_model(self, lockup: dict[str, Any]) -> Optional[YouTubeVideo]:
        """
        Parses YouTube's modern lockupViewModel component into a YouTubeVideo model.
        """
        # 1. Video ID
        vid_id = None
        cmd = (
            lockup.get("rendererContext", {})
            .get("commandContext", {})
            .get("onTap", {})
            .get("innertubeCommand", {})
        )
        if "watchEndpoint" in cmd:
            vid_id = cmd["watchEndpoint"].get("videoId")

        if not vid_id:
            meta_title = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {})
            for cr in meta_title.get("commandRuns", []):
                wp = cr.get("onTap", {}).get("innertubeCommand", {}).get("watchEndpoint", {})
                if wp.get("videoId"):
                    vid_id = wp["videoId"]
                    break

        if not vid_id:
            overlays = lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
            for ov in overlays:
                for b in ov.get("thumbnailBottomOverlayViewModel", {}).get("badges", []):
                    t_id = b.get("thumbnailBadgeViewModel", {}).get("animationActivationTargetId")
                    if t_id and len(t_id) >= 10:
                        vid_id = t_id
                        break
                if vid_id:
                    break

        if not vid_id and lockup.get("contentId"):
            vid_id = lockup.get("contentId")

        if not vid_id:
            return None

        # 2. Title
        title = (
            lockup.get("metadata", {})
            .get("lockupMetadataViewModel", {})
            .get("title", {})
            .get("content", "Untitled")
        )

        # 3. Thumbnail
        thumb_url = None
        sources = (
            lockup.get("contentImage", {})
            .get("thumbnailViewModel", {})
            .get("image", {})
            .get("sources", [])
        )
        if sources:
            thumb_url = sources[-1].get("url")

        # 4. Duration & Short Detection
        duration_text = None
        is_short = False
        overlays = lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
        for ov in overlays:
            b_list = ov.get("thumbnailBottomOverlayViewModel", {}).get("badges", [])
            for b in b_list:
                badge_vm = b.get("thumbnailBadgeViewModel", {})
                t = badge_vm.get("text")
                style = badge_vm.get("badgeStyle", "")
                if "SHORTS" in style or (t and t.upper() == "SHORTS"):
                    is_short = True
                elif t and (":" in t or t.isdigit()):
                    duration_text = t

        # 5. Metadata rows (views, date)
        view_text = None
        pub_text = None
        rows = (
            lockup.get("metadata", {})
            .get("lockupMetadataViewModel", {})
            .get("metadata", {})
            .get("contentMetadataViewModel", {})
            .get("metadataRows", [])
        )
        for r in rows:
            for p in r.get("metadataParts", []):
                c = p.get("text", {}).get("content", "")
                if not c:
                    continue
                if "ago" in c.lower() or "stream" in c.lower() or "yesterday" in c.lower():
                    pub_text = c
                elif "view" in c.lower() or re.match(r"^\d+[\d\.,]*\s*[KMBkmb]?$", c):
                    view_text = c if "view" in c.lower() else f"{c} views"

        duration_secs = parse_duration_to_seconds(duration_text)
        if duration_secs and duration_secs <= 60 and ("#short" in title.lower() or is_short):
            is_short = True

        return YouTubeVideo(
            video_id=vid_id,
            title=title,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            thumbnail_url=thumb_url,
            duration_text=duration_text,
            duration_seconds=duration_secs,
            view_count_text=view_text,
            view_count=parse_count_text_to_int(view_text),
            published_time_text=pub_text,
            is_short=is_short,
            description_snippet=None,
        )
