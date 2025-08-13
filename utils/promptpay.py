\
"""
PromptPay QR generator (EMVCo-compliant) — Compatible with Thai banking apps.
"""

from enum import Enum
import qrcode
import io, base64, re

class PromptPayIDType(Enum):
    PHONE = 1
    NATIONAL_ID = 2

def _format_id(pp_id: str, kind: PromptPayIDType) -> str:
    pp_id = re.sub(r"\D", "", pp_id)
    if kind == PromptPayIDType.PHONE:
        if pp_id.startswith("0"):
            pp_id = "66" + pp_id[1:]
        elif not pp_id.startswith("66"):
            pp_id = "66" + pp_id
        return pp_id
    else:
        return pp_id

def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"

def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for c in payload.encode("utf-8"):
        crc ^= (c << 8)
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def _sanitize_name(text: str, fallback: str = "PROMPTPAY"):
    text = (text or "").strip()
    return text if text else fallback

def build_promptpay_payload(
    pp_id: str,
    kind: PromptPayIDType,
    amount: float | None = None,
    merchant_name: str | None = None,
    merchant_city: str | None = None,
    reference: str | None = None,
    dynamic: bool | None = None,
) -> str:
    pfi = _tlv("00", "01")
    if dynamic is None:
        dynamic = amount is not None
    poi = _tlv("01", "12" if dynamic else "11")

    guid = _tlv("00", "A000000677010111")
    if kind == PromptPayIDType.PHONE:
        acc = _tlv("01", _format_id(pp_id, kind))
    else:
        acc = _tlv("02", _format_id(pp_id, kind))
    mai = _tlv("29", guid + acc)

    currency = _tlv("53", "764")
    txn_amt = _tlv("54", f"{amount:.2f}") if amount is not None else ""
    country = _tlv("58", "TH")

    m_name = _tlv("59", _sanitize_name(merchant_name, "PROMPTPAY"))
    m_city = _tlv("60", _sanitize_name(merchant_city, "BANGKOK"))

    addl = ""
    if reference:
        addl = _tlv("62", _tlv("05", reference[:25]))

    payload_wo_crc = pfi + poi + mai + currency + txn_amt + country + m_name + m_city + addl + "6304"
    crc = _crc16(payload_wo_crc)
    return payload_wo_crc + crc

def build_promptpay_qr_png(
    pp_id: str,
    kind: PromptPayIDType,
    amount: float | None = None,
    merchant_name: str | None = None,
    merchant_city: str | None = None,
    reference: str | None = None,
    dynamic: bool | None = None,
    box_size: int = 8,
) -> str:
    data = build_promptpay_payload(
        pp_id=pp_id,
        kind=kind,
        amount=amount,
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        reference=reference,
        dynamic=dynamic,
    )
    qr = qrcode.QRCode(box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return base64.b64encode(bio.getvalue()).decode("utf-8")
