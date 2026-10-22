import base64
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers


def normalize_signature(upload):
    if upload.size > 1024 * 1024:
        raise serializers.ValidationError("Signature image must be 1 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in {"PNG", "JPEG"}:
                    raise serializers.ValidationError("Upload a PNG or JPEG signature image.")
                if source.width > 2000 or source.height > 1000:
                    raise serializers.ValidationError("Signature must be at most 2000 by 1000 pixels.")
                if source.width < 20 or source.height < 10:
                    raise serializers.ValidationError("Signature image is too small.")
                if getattr(source, "n_frames", 1) != 1:
                    raise serializers.ValidationError("Animated images are not supported.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                # Re-render into a fresh image to strip metadata and trailing payloads.
                clean = Image.new("RGBA", image.size)
                clean.paste(image)
                clean.thumbnail((800, 400))
                output = BytesIO()
                clean.save(output, format="PNG", optimize=True)
        if output.tell() > 512 * 1024:
            raise serializers.ValidationError("Signature image is too complex; upload a simpler image.")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise serializers.ValidationError("Upload a valid PNG or JPEG signature image.")


class SignatureUploadSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, max_length=1024, trim_whitespace=False)
    file = serializers.FileField()

    def validate_file(self, value):
        return normalize_signature(value)

    def validate_current_password(self, value):
        if not self.context["user"].check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
