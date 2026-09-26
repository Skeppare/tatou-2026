"""Combine QR, invisible-text, and coordinate-distance watermark layers.

This module does not register a method or change any HTTP endpoints.
"""
from invisible_text import InvisibleText
from redundant_qr import RedundantQRWatermark
from distance_watermarking import DistanceWatermarking
from watermarking_method import (
    PdfSource,
    SecretNotFoundError,
    WatermarkingError,
    WatermarkingMethod,
    load_pdf_bytes,
)


class CombinedWatermark(WatermarkingMethod):
    name = "combined-watermark"

    def __init__(self):
        self.qr = RedundantQRWatermark()
        self.invisible = InvisibleText()
        self.distance = DistanceWatermarking()

    @staticmethod
    def get_usage() -> str:
        return (
            "Redundant QR codes, invisible text, and coordinate-distance marks. "
            "Secret: 1–100 UTF-8 bytes. A non-empty key is required. "
            "Position controls QR placement: all, corners, or center. "
            "Reading verifies all three layers and the QR key."
        )

    def is_watermark_applicable(self, pdf: PdfSource, position: str | None = None) -> bool:
        data = load_pdf_bytes(pdf)
        return (
            self.invisible.is_watermark_applicable(data)
            and self.qr.is_watermark_applicable(data, position)
            and self.distance.is_watermark_applicable(data, position)
        )

    def add_watermark(
        self, pdf: PdfSource, secret: str, key: str, position: str | None = None,
    ) -> bytes:
        if not isinstance(secret, str) or not 1 <= len(secret.encode("utf-8")) <= 100:
            raise ValueError("Secret must contain 1–100 UTF-8 bytes")
        if not isinstance(key, str) or not key:
            raise ValueError("Key must be a non-empty string")
        data = load_pdf_bytes(pdf)
        if not self.is_watermark_applicable(data, position):
            raise WatermarkingError("Both watermarking methods must be applicable")

        # Apply each existing implementation in sequence without changing it.
        data = self.qr.add_watermark(data, secret, key, position)
        data = self.invisible.add_watermark(data, secret, key)
        return self.distance.add_watermark(data, secret, key, position)

    def read_secret(self, pdf: PdfSource, key: str) -> str:
        data = load_pdf_bytes(pdf)
        # InvisibleText ignores the key: never use it to bypass QR verification.
        secret = self.qr.read_secret(data, key)
        text_secret = self.invisible.read_secret(data, key)
        distance_secret = self.distance.read_secret(data, key)
        if text_secret != secret or distance_secret != secret:
            raise WatermarkingError("Watermark layers disagree")
        return secret
