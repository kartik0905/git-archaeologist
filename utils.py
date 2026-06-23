import os
import shutil
import time
from urllib.parse import urlparse
from fpdf import FPDF

CHROMA_PATH = "/tmp/chroma_db"
TEMP_REPO_PATH = "/tmp/temp_repo_clone"


def remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, os.stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def cleanup_temp_data(*args, **kwargs) -> None:
    if os.path.exists(TEMP_REPO_PATH):
        try:
            shutil.rmtree(TEMP_REPO_PATH, onerror=remove_readonly)
        except Exception as e:
            print(
                f"[cleanup] Warning: could not entirely remove "
                f"{TEMP_REPO_PATH}: {e}"
            )


def inject_github_token(repo_url: str, token: str) -> str:
    if not token:
        return repo_url

    parsed = urlparse(repo_url)

    if parsed.scheme != "https":
        raise ValueError(
            "GitHub Token authentication requires an HTTPS repository URL."
        )

    netloc = parsed.netloc.split("@")[-1]
    authenticated_netloc = f"{token}@{netloc}"

    return parsed._replace(netloc=authenticated_netloc).geturl()


def create_pdf(repo_url: str, messages: list) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(
        200,
        10,
        "Git Archaeologist - Audit Report",
        ln=True,
        align="C"
    )

    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 10, f"Repository: {repo_url}", ln=True, align="C")
    pdf.cell(
        200,
        10,
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        ln=True,
        align="C"
    )

    pdf.ln(10)

    for msg in messages:
        role = "User" if msg["role"] == "user" else "Archaeologist"

        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, f"{role}:", ln=True)

        pdf.set_font("Arial", "", 11)
        pdf.set_text_color(0, 0, 0)

        clean_content = (
            msg["content"]
            .encode("latin-1", "replace")
            .decode("latin-1")
        )

        pdf.multi_cell(0, 7, clean_content)
        pdf.ln(5)

        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    output = pdf.output(dest="S")

    if isinstance(output, bytearray):
        return bytes(output)
    elif isinstance(output, bytes):
        return output
    elif output:
        return output.encode("latin-1")
    else:
        return b""