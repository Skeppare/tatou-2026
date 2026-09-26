import cv2
import numpy as np
import base64
import hashlib
import hmac
import io

import pymupdf
import qrcode

from watermarking_method import (
    WatermarkingMethod,
    PdfSource,
    load_pdf_bytes,
    SecretNotFoundError,
    InvalidKeyError,
    WatermarkingError,
)


class RedundantQRWatermark(WatermarkingMethod):
    name = "redundant-qr"

    @staticmethod
    def get_usage() -> str:
        return (
            "Embeds a redundant QR-code watermark in the PDF. "
            "Position may be 'all', 'corners', or 'center'. "
            "If no position is given, 'all' is used."
        )

    def is_watermark_applicable(
        self,
        pdf: PdfSource,
        position: str | None = None,
    ) -> bool:
        import pymupdf

        # First normalize the input into PDF bytes
        data = load_pdf_bytes(pdf)

        # Check that position is one we support
        valid_positions = {None, "all", "corners", "center"}

        if position not in valid_positions:
            return False

        # Check that the PDF can actually be opened
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
            applicable = doc.page_count > 0
            doc.close()
            return applicable

        except Exception:
            return False

    def add_watermark(
        self,
        pdf: PdfSource,
        secret: str,
        key: str,
        position: str | None = None,
    ) -> bytes:

        # Secret and key must contain something
        if not secret:
            raise ValueError("Secret must not be empty")

        if not key:
            raise ValueError("Key must not be empty")

        # Convert PDF input to bytes
        data = load_pdf_bytes(pdf)

        # Check that our method can be used
        if not self.is_watermark_applicable(data, position):
            raise WatermarkingError(
                "Watermark cannot be applied to this PDF"
            )

        # ---------------------------------------
        # 1. Create the data stored in the QR
        # ---------------------------------------

        secret_bytes = secret.encode("utf-8")
        key_bytes = key.encode("utf-8")

        # Create an authentication code using the secret + key
        mac = hmac.new(
            key_bytes,
            secret_bytes,
            hashlib.sha256,
        ).hexdigest()

        # Encode secret safely as text
        encoded_secret = base64.urlsafe_b64encode(
            secret_bytes
        ).decode("ascii")

        # Our QR payload
        payload = f"TATOUQR1:{encoded_secret}:{mac}"

        # ---------------------------------------
        # 2. Generate QR code
        # ---------------------------------------

        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=2,
        )

        qr.add_data(payload)
        qr.make(fit=True)

        qr_image = qr.make_image(
            fill_color="black",
            back_color="white",
        )

        # Convert QR image into PNG bytes
        image_buffer = io.BytesIO()
        qr_image.save(image_buffer, format="PNG")
        qr_bytes = image_buffer.getvalue()

        # ---------------------------------------
        # 3. Open PDF
        # ---------------------------------------

        doc = pymupdf.open(
            stream=data,
            filetype="pdf"
        )

        try:
            for page in doc:
                width = page.rect.width
                height = page.rect.height

                # QR size = 12% of shortest page dimension
                qr_size = min(width, height) * 0.12
                margin = qr_size * 0.25

                # Four corners
                corners = [
                    # Top left
                    pymupdf.Rect(
                        margin,
                        margin,
                        margin + qr_size,
                        margin + qr_size,
                    ),

                    # Top right
                    pymupdf.Rect(
                        width - margin - qr_size,
                        margin,
                        width - margin,
                        margin + qr_size,
                    ),

                    # Bottom left
                    pymupdf.Rect(
                        margin,
                        height - margin - qr_size,
                        margin + qr_size,
                        height - margin,
                    ),

                    # Bottom right
                    pymupdf.Rect(
                        width - margin - qr_size,
                        height - margin - qr_size,
                        width - margin,
                        height - margin,
                    ),
                ]

                # Center
                center = pymupdf.Rect(
                    width / 2 - qr_size / 2,
                    height / 2 - qr_size / 2,
                    width / 2 + qr_size / 2,
                    height / 2 + qr_size / 2,
                )

                # Decide where to put QR codes
                if position in (None, "all"):
                    positions = corners + [center]

                elif position == "corners":
                    positions = corners

                elif position == "center":
                    positions = [center]

                else:
                    raise WatermarkingError(
                        f"Unsupported position: {position}"
                    )

                # Add the QR to all chosen positions
                for rect in positions:
                    page.insert_image(
                        rect,
                        stream=qr_bytes,
                        overlay=True,
                    )

            # Return complete modified PDF as bytes
            return doc.tobytes(
                garbage=4,
                deflate=True,
                no_new_id=True,
            )

        finally:
            doc.close()

    def read_secret(
        self,
        pdf: PdfSource,
        key: str,
    ) -> str:

        if not key:
            raise ValueError("Key must not be empty")

        data = load_pdf_bytes(pdf)
        detector = cv2.QRCodeDetector()

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(3, 3),
                    alpha=False,
                )

                png_bytes = pix.tobytes("png")

                image_array = np.frombuffer(
                    png_bytes,
                    dtype=np.uint8,
                )

                image = cv2.imdecode(
                    image_array,
                    cv2.IMREAD_COLOR,
                )

                found, decoded_info, points, _ = detector.detectAndDecodeMulti(
                    image
                )

                if not found:
                    continue

                for payload in decoded_info:
                    if not payload:
                        continue

                    if not payload.startswith("TATOUQR1:"):
                        continue

                    parts = payload.split(":")

                    if len(parts) != 3:
                        continue

                    _, encoded_secret, stored_mac = parts

                    try:
                        secret_bytes = base64.urlsafe_b64decode(
                            encoded_secret.encode("ascii")
                        )
                        secret = secret_bytes.decode("utf-8")

                    except Exception:
                        continue

                    expected_mac = hmac.new(
                        key.encode("utf-8"),
                        secret_bytes,
                        hashlib.sha256,
                    ).hexdigest()

                    if not hmac.compare_digest(
                        stored_mac,
                        expected_mac,
                    ):
                        raise InvalidKeyError(
                            "Watermark found, but key is incorrect"
                        )

                    return secret

        raise SecretNotFoundError(
            "No valid redundant QR watermark found"
        )

    