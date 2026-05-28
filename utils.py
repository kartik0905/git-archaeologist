import os
import shutil
import time
from fpdf import FPDF

TEMP_REPO_PATH = "./temp_repo_clone"
CHROMA_PATH = "./chroma_db"


def cleanup_temp_data(*args, **kwargs) -> None:
    """Remove cloned repo and vector DB from disk."""
    for path in [TEMP_REPO_PATH, CHROMA_PATH]:
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"[cleanup] Warning: could not remove {path}: {e}")


def create_pdf(repo_url: str, messages: list) -> bytes:
    """Generate a PDF audit report from the chat session."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Legacy Code Archaeologist - Audit Report", ln=True, align="C")

    # Metadata
    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 10, f"Repository: {repo_url}", ln=True, align="C")
    pdf.cell(200, 10, f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)

    for msg in messages:
        role = "User" if msg["role"] == "user" else "Archaeologist"

        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, f"{role}:", ln=True)

        pdf.set_font("Arial", "", 11)
        pdf.set_text_color(0, 0, 0)
        clean_content = msg["content"].encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 7, clean_content)
        pdf.ln(5)

        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    return pdf.output(dest="S").encode("latin-1")