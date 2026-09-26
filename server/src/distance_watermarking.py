import hashlib
import random
import zlib

import pymupdf

from watermarking_method import (
    WatermarkingMethod,
    SecretNotFoundError,
    load_pdf_bytes,
)

class DistanceWatermarking(WatermarkingMethod):
    name = "watermark_marcus"

    MAGIC = b"GROUP34MARCUS"

    # Secret size in UTF-8 bytes
    MAX_SECRET_BYTES = 100

    # Coordinate encoding
    X_ZERO = 10.0
    X_ONE = 10.8

    # How close an extracted coordinate must be to ours.
    X_TOLERANCE = 0.20
    Y_TOLERANCE = 0.25

    # Keep watermark positions away from top/bottom edges.
    Y_MARGIN = 30.0

    # Distance between possible Y positions.
    # Small enough to give reasonable capacity, but large enough that
    # adjacent positions can still be distinguished.
    Y_SLOT_SPACING = 0.75

    @staticmethod
    def get_usage() -> str:
        return (
            "watermarking added"
        )

    @staticmethod
    def _rng_from_key(key: str) -> random.Random:
        if not isinstance(key, str) or not key:
            raise ValueError("A non-empty key is required")

        digest = hashlib.sha256(key.encode("utf-8")).digest()
        seed = int.from_bytes(digest, byteorder="big")

        return random.Random(seed)

    @classmethod
    def _make_y_positions(cls, page_height: float, key: str) -> list[float]:
        start = cls.Y_MARGIN
        end = page_height - cls.Y_MARGIN

        if end <= start:
            return []

        positions = []

        y = start
        while y <= end:
            positions.append(y)
            y += cls.Y_SLOT_SPACING

        rng = cls._rng_from_key(key)
        rng.shuffle(positions)

        return positions

    @staticmethod
    def _bytes_to_bits(data: bytes) -> str:
        return "".join(f"{byte:08b}" for byte in data)

    @staticmethod
    def _bits_to_bytes(bits: str) -> bytes:
        if len(bits) % 8 != 0:
            raise ValueError("Bit string length must be divisible by 8")

        return bytes(
            int(bits[i:i + 8], 2)
            for i in range(0, len(bits), 8)
        )

    @classmethod
    def _build_payload(cls, secret: str) -> bytes:
        if not isinstance(secret, str):
            raise ValueError("Secret must be a string")

        secret_bytes = secret.encode("utf-8")

        if not 1 <= len(secret_bytes) <= cls.MAX_SECRET_BYTES:
            raise ValueError(
                f"Secret must contain 1-{cls.MAX_SECRET_BYTES} UTF-8 bytes"
            )

        # Two-byte unsigned length field.
        length = len(secret_bytes).to_bytes(2, byteorder="big")

        # Checksum lets read_secret distinguish a valid watermark from
        # coincidentally matching PDF content.
        checksum = zlib.crc32(secret_bytes).to_bytes(4, byteorder="big")

        return cls.MAGIC + length + secret_bytes + checksum

    def is_watermark_applicable(self, pdf, position=None) -> bool:
        try:
            data = load_pdf_bytes(pdf)

            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.page_count < 1:
                    return False

                if doc.needs_pass:
                    return False

                page = doc[0]

                # Make sure there is at least some usable coordinate space.
                available_height = (
                    page.rect.height - (2 * self.Y_MARGIN)
                )

                return available_height > 0

        except Exception:
            return False

    def add_watermark(
        self,
        pdf,
        secret: str,
        key: str,
        position=None,
    ) -> bytes:

        data = load_pdf_bytes(pdf)

        payload = self._build_payload(secret)
        bits = self._bytes_to_bits(payload)

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count < 1:
                raise ValueError("PDF has no pages")
            
            if doc.needs_pass:
                raise ValueError("PDFs protectedd by password are not supported")

            page = doc[0]

            y_positions = self._make_y_positions(
                page.rect.height,
                key,
            )

            if len(bits) > len(y_positions):
                raise ValueError(
                    "Secret is too large for the first page. "
                    f"Need {len(bits)} coordinate slots but only "
                    f"{len(y_positions)} are available."
                )

            for index, bit in enumerate(bits):
                y_pos = y_positions[index]
                if bit == "0":
                    x_pos = self.X_ZERO
                else:
                    x_pos = self.X_ONE
                page.insert_text(
                    (x_pos, y_pos),
                    ".",
                    fontsize=2,
                    render_mode=3,
                )
            return doc.tobytes(
                deflate=True,
                no_new_id=True,
            )

    def read_secret(
        self,
        pdf,
        key: str,
        position=None,
    ) -> str:

        data = load_pdf_bytes(pdf)

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count < 1:
                raise SecretNotFoundError("PDF has no pages")

            page = doc[0]

            y_positions = self._make_y_positions(
                page.rect.height,
                key,
            )

            text_dict = page.get_text("dict")

            candidates = []

            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")

                        if text != ".":
                            continue

                        origin = span.get("origin")

                        if not origin or len(origin) < 2:
                            continue

                        x_coord = float(origin[0])
                        y_coord = float(origin[1])

                        near_zero = (
                            abs(x_coord - self.X_ZERO)
                            <= self.X_TOLERANCE
                        )

                        near_one = (
                            abs(x_coord - self.X_ONE)
                            <= self.X_TOLERANCE
                        )

                        if not (near_zero or near_one):
                            continue

                        candidates.append(
                            (x_coord, y_coord)
                        )

            if not candidates:
                raise SecretNotFoundError(
                    "Could not find coordinate watermark"
                )

            binary_result = ""

            # First recover enough bytes to obtain MAGIC + length.
            header_size = len(self.MAGIC) + 2
            header_bits = header_size * 8

            expected_total_bits = None

            for expected_y in y_positions:
                found_bit = None
                best_distance = None

                for x_coord, y_coord in candidates:
                    y_distance = abs(y_coord - expected_y)

                    if y_distance > self.Y_TOLERANCE:
                        continue

                    # Choose the closest matching candidate if more than
                    # one happens to fall in the tolerance window.
                    if (
                        best_distance is not None
                        and y_distance >= best_distance
                    ):
                        continue

                    if (
                        abs(x_coord - self.X_ZERO)
                        <= self.X_TOLERANCE
                    ):
                        bit = "0"

                    elif (
                        abs(x_coord - self.X_ONE)
                        <= self.X_TOLERANCE
                    ):
                        bit = "1"

                    else:
                        continue

                    found_bit = bit
                    best_distance = y_distance

                if found_bit is None:
                    raise SecretNotFoundError(
                        "Coordinate watermark is incomplete"
                    )

                binary_result += found_bit

                # Once the header has been recovered, determine exactly
                # how many bits the complete payload should contain.
                if (
                    expected_total_bits is None
                    and len(binary_result) >= header_bits
                ):
                    try:
                        header = self._bits_to_bytes(
                            binary_result[:header_bits]
                        )
                    except ValueError as exc:
                        raise SecretNotFoundError(
                            "Invalid watermark header"
                        ) from exc

                    magic = header[:len(self.MAGIC)]

                    if magic != self.MAGIC:
                        raise SecretNotFoundError(
                            "Coordinate watermark signature not found"
                        )

                    length_start = len(self.MAGIC)

                    secret_length = int.from_bytes(
                        header[
                            length_start:
                            length_start + 2
                        ],
                        byteorder="big",
                    )

                    if not 1 <= secret_length <= self.MAX_SECRET_BYTES:
                        raise SecretNotFoundError(
                            "Invalid watermark secret length"
                        )

                    total_payload_bytes = (
                        len(self.MAGIC)
                        + 2
                        + secret_length
                        + 4
                    )

                    expected_total_bits = total_payload_bytes * 8

                    if expected_total_bits > len(y_positions):
                        raise SecretNotFoundError(
                            "Watermark payload exceeds page capacity"
                        )

                if (
                    expected_total_bits is not None
                    and len(binary_result) >= expected_total_bits
                ):
                    break

            if (
                expected_total_bits is None
                or len(binary_result) < expected_total_bits
            ):
                raise SecretNotFoundError(
                    "Incomplete coordinate watermark"
                )

            try:
                payload = self._bits_to_bytes(
                    binary_result[:expected_total_bits]
                )
            except ValueError as exc:
                raise SecretNotFoundError(
                    "Invalid watermark bitstream"
                ) from exc

            offset = len(self.MAGIC)

            magic = payload[:offset]

            if magic != self.MAGIC:
                raise SecretNotFoundError(
                    "Coordinate watermark signature not found"
                )

            secret_length = int.from_bytes(
                payload[offset:offset + 2],
                byteorder="big",
            )

            offset += 2

            secret_bytes = payload[
                offset:
                offset + secret_length
            ]

            offset += secret_length

            stored_checksum = int.from_bytes(
                payload[offset:offset + 4],
                byteorder="big",
            )

            calculated_checksum = zlib.crc32(secret_bytes)

            if stored_checksum != calculated_checksum:
                raise SecretNotFoundError(
                    "Watermark checksum verification failed"
                )

            try:
                return secret_bytes.decode("utf-8")

            except UnicodeDecodeError as exc:
                raise SecretNotFoundError(
                    "Watermark contains invalid UTF-8"
                ) from exc