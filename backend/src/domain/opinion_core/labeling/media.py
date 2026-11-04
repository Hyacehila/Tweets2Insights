"""Model capabilities, bounded image selection and native image preparation."""

import base64
import binascii
import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGES_PER_POST = 9


class ImageInputError(ValueError):
    """A selected image could not be loaded; the post must not become text-only silently."""


class EmptyModelInput(ValueError):
    """No content remains in the model's effective input mode."""


def supports_images(provider, model):
    if provider == "openai_decisions":
        return model == "gpt-6-luna"
    if provider == "jev":
        return model in {"jev-latest", "jev-preview", "jev-1.13.0", "jev-1.14.0"}
    # Alibaba's documented System One endpoint is text-only. Unknown model IDs
    # and connectors require an explicit capability implementation before vision.
    return False


@dataclass(frozen=True)
class MediaPolicy:
    provider: str
    model: str
    requested_mode: str = "text_image"
    max_images_per_post: int = 3
    connector_images: bool = False

    def __post_init__(self):
        if self.requested_mode not in {"text_only", "text_image", "image_only"}:
            raise ValueError("invalid media mode")
        if (
            type(self.max_images_per_post) is not int
            or not 1 <= self.max_images_per_post <= MAX_IMAGES_PER_POST
        ):
            raise ValueError("max_images_per_post must be an integer from 1 to 9")

    @property
    def supports_images(self):
        if self.provider == "connector":
            return self.connector_images
        return supports_images(self.provider, self.model)

    @property
    def effective_mode(self):
        return self.requested_mode if self.supports_images else "text_only"

    @property
    def version(self):
        return f"media-v1:{self.effective_mode}:{self.max_images_per_post}"

    def references(self, post):
        return (
            post.media_refs[: self.max_images_per_post]
            if self.effective_mode != "text_only"
            else []
        )

    def text(self, post):
        # References, asset paths and Base64 are not text evidence.
        state = post.model_dump(mode="json", exclude={"media_refs", "raw_asset_ref"})
        if self.effective_mode == "image_only":
            state["content"] = ""
        return state

    def summary(self, posts):
        counts = [len(p.get("media_refs", [])) for p in posts]
        selected = (
            sum(min(n, self.max_images_per_post) for n in counts)
            if self.effective_mode != "text_only"
            else 0
        )
        notices = []
        if not self.supports_images:
            notices.append("model_text_only")
        elif self.effective_mode == "text_only":
            notices.append("text_only_selected")
        if selected and sum(counts) > selected:
            notices.append("image_limit_applied")
        return {
            "provider": self.provider,
            "model": self.model,
            "supports_images": self.supports_images,
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "max_images_per_post": self.max_images_per_post,
            "posts_with_images": sum(n > 0 for n in counts),
            "available_images": sum(counts),
            "selected_images": selected,
            "ignored_images": sum(counts) - selected,
            "notices": notices,
        }

    def prepare(self, post, image_loader=None):
        state = self.text(post)
        references = self.references(post)
        if not state["content"].strip() and not references:
            raise EmptyModelInput("no text or selected images available")
        images = []
        for ref in references:
            try:
                images.append((image_loader or load_image)(ref))
            except (ValueError, OSError, http.client.HTTPException) as exc:
                # Do not include a URL with credentials or a local path in errors.
                raise ImageInputError("selected image could not be read") from exc
        return state, images


def normalize_image(data):
    """Upright baseline JPEG, <=1568 px, padded to >=280 px for Jev."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageInputError("image must be at most 16 MiB")
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {"PNG", "JPEG", "WEBP"} or getattr(
                original, "is_animated", False
            ):
                raise ImageInputError("use a still PNG, JPEG or WebP image")
            if original.width * original.height > MAX_IMAGE_PIXELS:
                raise ImageInputError("image resolution exceeds 40 megapixels")
            img = ImageOps.exif_transpose(original)
            img.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
            # Flatten transparency onto white rather than turning transparent text black.
            rgba = img.convert("RGBA")
            canvas = Image.new(
                "RGB", (max(280, img.width), max(280, img.height)), "white"
            )
            canvas.paste(
                rgba,
                ((canvas.width - img.width) // 2, (canvas.height - img.height) // 2),
                rgba,
            )
            output = io.BytesIO()
            canvas.save(output, "JPEG", quality=85, optimize=True, progressive=False)
            result = output.getvalue()
            if len(result) > 2 * 1024 * 1024:
                raise ImageInputError("prepared image exceeds 2 MiB")
            return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageInputError("invalid image file") from exc


class DecisionInput:
    """Prepare one post at a time and fingerprint the exact image bytes sent."""

    def __init__(self, policy, loader=None):
        self.policy, self.loader = policy, loader
        self.prepared = None

    def prepare(self, post):
        state, images = self.policy.prepare(post, self.loader)
        self.prepared = (post.model_dump_json(), state, images)
        encoded = json.dumps(
            [state, [hashlib.sha256(data).hexdigest() for data in images]],
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(encoded.encode()).hexdigest()

    def consume(self, post):
        if self.prepared is None or self.prepared[0] != post.model_dump_json():
            self.prepare(post)
        _, state, images = self.prepared
        self.prepared = None
        return state, images


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, port):
        super().__init__(
            host, port=port, timeout=10, context=ssl.create_default_context()
        )
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _download(url):
    """Public HTTP(S) only; pin validated DNS addresses, validate each redirect."""
    deadline = time.monotonic() + 30
    for _ in range(4):
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ImageInputError(
                "images require a public HTTP(S) URL or an uploaded asset"
            )
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ImageInputError("image URLs must use port 80 or 443")
        addresses = {
            row[4][0]
            for row in socket.getaddrinfo(
                parsed.hostname, port, type=socket.SOCK_STREAM
            )
        }
        if not addresses or any(
            not ipaddress.ip_address(a).is_global for a in addresses
        ):
            raise ImageInputError("image URL must resolve to a public address")
        address = min(addresses)
        connection = (
            _PinnedHTTPSConnection(parsed.hostname, address, port)
            if parsed.scheme == "https"
            else http.client.HTTPConnection(address, port, timeout=10)
        )
        try:
            if time.monotonic() > deadline:
                raise ImageInputError("image download timed out")
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request(
                "GET",
                path,
                headers={
                    "Host": parsed.netloc,
                    "Accept": "image/*",
                    "User-Agent": "Tweets2Insights/0.2",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ImageInputError("image redirect has no destination")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ImageInputError("image download failed")
            length = response.getheader("Content-Length")
            if length and int(length) > MAX_IMAGE_BYTES:
                raise ImageInputError("image exceeds 16 MiB")
            result = bytearray()
            while chunk := response.read(65536):
                result.extend(chunk)
                if len(result) > MAX_IMAGE_BYTES or time.monotonic() > deadline:
                    raise ImageInputError("image download exceeds limits")
            return bytes(result)
        finally:
            connection.close()
    raise ImageInputError("too many image redirects")


def load_image(ref):
    if ref.startswith("data:"):
        header, separator, encoded = ref.partition(",")
        if not separator or not re.fullmatch(
            r"data:image/(png|jpeg|jpg|webp);base64", header
        ):
            raise ImageInputError("invalid image data URL")
        if len(encoded) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
            raise ImageInputError("image exceeds 16 MiB")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ImageInputError("invalid image Base64") from exc
    else:
        data = _download(ref)
    return normalize_image(data)
