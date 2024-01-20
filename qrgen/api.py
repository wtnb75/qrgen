import io
import functools
from logging import getLogger
from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, HTMLResponse, PlainTextResponse, RedirectResponse
from enum import Enum
from qrcode.main import QRCode
import urllib.parse
import qrcode.constants
from qrcode.image.svg import SvgImage, SvgFragmentImage, SvgPathImage
from qrcode.image.pure import PyPNGImage
try:
    from opentelemetry import trace
    _tracer = trace.get_tracer("qrgen")
except ImportError:
    class trace:
        @staticmethod
        def get_current_span():
            return trace

        @staticmethod
        def set_attribute(k, v):
            pass

    class _tracer:
        @staticmethod
        def start_as_current_span(s):
            def _(fn):
                def _wrapper(*args, **kwargs):
                    return fn(*args, **kwargs)
                return _wrapper
            return _

_log = getLogger(__name__)
api = FastAPI()


def _wifi_escape(txt: str) -> str:
    esc_chars = r'\;,":'
    for c in esc_chars:
        txt = txt.replace(c, "\\"+c)
    return txt


html_prep = """
<!DOCTYPE html>
<html>
<style>
table.qr{
    border:none;
    border-collapse: collapse;
    margin: 20px;
}
.qr td{
    width: 10px;
    height: 10px;
}
.black{
    background-color: black;
}
.white{
    background-color: white;
}
</style>
<body>
<table class="qr">
"""

html_post = """
</table></body></html>
"""


class ErrorCorrect(str, Enum):
    M = "M"
    Q = "Q"
    H = "H"
    L = "L"


class Format(str, Enum):
    png = "png"
    svg = "svg"
    svg_fragment = "svg-fragment"
    svg_path = "svg-path"
    ascii_text = "ascii"
    html = "html"


def base_args(func):
    @functools.wraps(func)
    def _(*args, fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M, **kwargs):
        _log.info("fmt=%s, err=%s", fmt, err)
        txt = func(*args, fmt=fmt, err=err, **kwargs)
        return txt_response(txt, fmt, err)
    return _


@_tracer.start_as_current_span("do_work")
def txt_response(txt: str, format: Format, err: ErrorCorrect = ErrorCorrect.M) -> Response:
    span = trace.get_current_span()
    span.set_attribute("qrcode.txt", txt)
    span.set_attribute("qrcode.format", format.name)
    span.set_attribute("qrcode.error_collection", err.name)
    _log.info("generate %s, text=%s", format, txt)
    type_map = {
        Format.png: "image/png",
        Format.svg: "image/svg+xml",
        Format.svg_fragment: "image/svg+xml",
        Format.svg_path: "image/svg+xml",
        Format.ascii_text: "text/plain",
        Format.html: "text/html",
    }
    errcr_map = {}
    for v in dir(qrcode.constants):
        if not v.startswith("ERROR_CORRECT_"):
            continue
        k = v.split("_", 3)[-1]
        errcr_map[k] = getattr(qrcode.constants, v)
    def_type = "application/octet-stream"
    factory = None
    if format == Format.png:
        factory = PyPNGImage
    elif format == Format.svg:
        factory = SvgImage
    elif format == Format.svg_fragment:
        factory = SvgFragmentImage
    elif format == Format.svg_path:
        factory = SvgPathImage
    errcr = errcr_map.get(err, qrcode.constants.ERROR_CORRECT_M)
    qr = QRCode(error_correction=errcr, image_factory=factory)
    qr.add_data(txt)
    if format == Format.ascii_text:
        buf = io.StringIO()
        qr.print_ascii(out=buf)
        return PlainTextResponse(content=buf.getvalue())
    elif format == Format.html:
        buf = io.StringIO()
        buf.write(html_prep)
        qr.make()
        for y in range(qr.modules_count):
            buf.write("<tr>")
            mods = []
            cur = None
            for i in qr.modules[y]:
                if cur is None:
                    cur = [i, 1]
                elif cur[0] == i:
                    cur[1] += 1
                else:
                    mods.append(cur)
                    cur = [i, 1]
            mods.append(cur)
            for m in mods:
                if m[0]:
                    if m[1] != 1:
                        buf.write(f"<td class=\"black\" colspan=\"{m[1]}\" />")
                    else:
                        buf.write("<td class=\"black\" />")
                else:
                    if m[1] != 1:
                        buf.write(f"<td class=\"white\" colspan=\"{m[1]}\" />")
                    else:
                        buf.write("<td class=\"white\" />")
            buf.write("</tr>\n")
        buf.write(html_post)
        return HTMLResponse(content=buf.getvalue())
    else:
        buf = io.BytesIO()
        img = qr.make_image()
        img.save(buf)
    res = Response(content=buf.getvalue(), status_code=200,
                   media_type=type_map.get(format, def_type))
    return res


def _del_none(kv):
    return {k: v for k, v in kv.items() if v is not None}


def _del_none_list(kv):
    return [(k, v) for k, v in kv if v is not None]


class WifiType(str, Enum):
    wep = "WEP"
    wpa = "WPA"
    wpa2_eap = "WPA2-EAP"
    nopass = "nopass"


@api.get("/")
def do_doc(request: Request):
    return RedirectResponse(urllib.parse.urljoin(str(request.url), "docs"))


@api.get("/wifi")
@api.get("/wifi/{fmt}")
@base_args
def do_wifi(type: WifiType = None, ssid: str = None,
            password: str = None, hidden: bool = None, eap: str = None,
            anonymous: str = None, identity: str = None, phase2: str = None,
            fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """WiFi Connection"""
    params = _del_none({
        "T": type, "S": ssid, "P": password, "H": hidden, "E": eap,
        "A": anonymous, "I": identity, "PH2": phase2,
    })
    return "WIFI:" + \
        ";".join([f"{k}:{_wifi_escape(v)}" for k, v in params.items()]) + ";;"


@api.get("/text")
@api.get("/text/{fmt}")
@base_args
def do_text(v: str,
            fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """raw text"""
    return v


@api.get("/url")
@api.get("/url/{fmt}")
@base_args
def do_url(url: str, title: str = None,
           fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """URL or Bookmark"""
    if title:
        return f"MEBKM:TITLE:{_wifi_escape(title)};URL:{_wifi_escape(url)};;"
    return url


@api.get("/mail")
@api.get("/mail/{fmt}")
@base_args
def do_mail(addr: str, subject: str = None, cc: str = None, bcc: str = None, body: str = None,
            fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """EMAIL"""
    params = _del_none({
        "subject": subject, "cc": cc, "bcc": bcc, "body": body
    })
    q = urllib.parse.urlencode(params)
    if q:
        return f"mailto:{addr}?{q}"
    return f"mailto:{addr}"


@api.get("/tel")
@api.get("/tel/{fmt}")
@base_args
def do_tel(n: str,
           fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """Telephone number"""
    return f"tel:{n}"


@api.get("/sms")
@api.get("/sms/{fmt}")
@base_args
def do_sms(dst: str, msg: str = None,
           fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """SMS message"""
    if msg:
        return f"sms:{dst}:{urllib.parse.quote(msg)}"
    return f"sms:{dst}"


@api.get("/facetime")
@api.get("/facetime/{fmt}")
@base_args
def do_facetime(dst: str = None,
                fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """facetime"""
    return f"facetime:{dst}"


@api.get("/facetime-audio")
@api.get("/facetime-audio/{fmt}")
@base_args
def do_facetime_audio(dst: str,
                      fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """facetime audio"""
    return f"facetime-audio:{dst}"


@api.get("/map")
@api.get("/map/{fmt]")
@api.get("/geo")
@api.get("/geo/{fmt}")
@base_args
def do_geo(lat: float, lon: float, size: int = None,
           fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """geo location"""
    if size:
        return f"geo:{lat},{lon},{size}"
    return f"geo:{lat},{lon}"


@api.get("/youtube")
@api.get("/youtube/{fmt}")
@base_args
def do_youtube(vid: str,
               fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """YouTube link"""
    return f"https://www.youtube.com/v/{vid}"


@api.get("/googleplay")
@api.get("/googleplay/{fmt}")
@base_args
def do_googleplay(id: str,
                  fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """google play link"""
    return f"market://details?id={id}"


def fix_date(k, dtstr):
    if len(dtstr) <= 9:
        return f"{k};VALUE=DATE:{dtstr}"
    return f"{k}:{dtstr}"


@api.get("/event")
@api.get("/event/{fmt}")
@base_args
def do_event(summary: str, uid: str, transp: str, dtstart: str, dtend: str,
             fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """vEvent(WIP)"""
    params = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"TRANSP:{transp}",
        fix_date("DTSTART", dtstart),
        fix_date("DTEND", dtend),
        "END:VEVENT",
    ]
    return "\r\n".join(params)


@api.get("/addr")
@api.get("/addr/{fmt}")
@base_args
def do_address(name: str = None, sound: str = None,
               tel: list[str] = Query(default=[]),
               telav: list[str] = Query(default=[]),
               email: list[str] = Query(default=[]),
               note: str = None, bday: str = None,
               adr: list[str] = Query(default=[]),
               url: list[str] = Query(default=[]),
               nickname: str = None,
               fmt: Format = Format.png, err: ErrorCorrect = ErrorCorrect.M):
    """DoCoMo MECARD"""
    params = _del_none_list([
        ("N", name),
        ("SOUND", sound),
        ("NOTE", note),
        ("BDAY", bday),
        ("NICKNAME", nickname),
    ])
    params.extend([("TEL", x) for x in tel])
    params.extend([("TEL-AV", x) for x in telav])
    params.extend([("EMAIL", x) for x in email])
    params.extend([("ADR", x) for x in adr])
    params.extend([("URL", x) for x in url])
    return "MECARD:"+";".join([f"{k}:{v}" for k, v in params])+";;"
