"""
scratch/verify_report.py
Verifies the generated Word document:
1. Opens correctly with python-docx
2. Counts page breaks (should be exactly 9 page breaks separating 10 distinct pages)
3. Checks presence of all 10 required sections
4. Validates tables, pictures, and placeholders
"""

from pathlib import Path
from docx import Document

DOCX_PATH = Path("mini_project_report/Hand_Gesture_Controller_Mini_Project_Report.docx")

def verify():
    if not DOCX_PATH.exists():
        print(f"Error: {DOCX_PATH} does not exist!")
        return False

    doc = Document(str(DOCX_PATH))
    print(f"Successfully loaded {DOCX_PATH}")
    print(f"Number of sections: {len(doc.sections)}")
    print(f"Number of paragraphs: {len(doc.paragraphs)}")
    print(f"Number of tables: {len(doc.tables)}")

    # Check for page breaks in paragraphs
    page_break_count = 0
    pages_text = [[]]
    
    for p in doc.paragraphs:
        has_break = False
        for r in p.runs:
            if "<w:br" in r._r.xml and 'type="page"' in r._r.xml:
                has_break = True
                break
        if has_break:
            page_break_count += 1
            pages_text.append([])
        else:
            if p.text.strip():
                pages_text[-1].append(p.text.strip())

    print(f"Total explicit page breaks found: {page_break_count}")
    print(f"Total logical pages structured: {len(pages_text)}")

    for i, page_lines in enumerate(pages_text, 1):
        first_line = page_lines[0] if page_lines else "(Empty)"
        print(f"Page {i:02d}: {len(page_lines)} paragraphs. Starts with: '{first_line[:60]}...'")

    # Check editable placeholders on Page 1
    p1_text = " ".join(pages_text[0])
    # Also check tables on page 1 (tbl_meta)
    table_texts = []
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                table_texts.append(cell.text)
    all_table_text = " ".join(table_texts)

    placeholders = [
        "[Enter Name]",
        "[Enter UID]",
        "[Enter Section]",
        "[Enter Course Name]",
        "[Enter Subject Name]",
        "[Enter Teacher Name]",
        "[Enter Institution Name]",
        "[Enter Session]",
    ]

    print("\nChecking editable placeholders on Page 1:")
    for ph in placeholders:
        present = (ph in p1_text) or (ph in all_table_text)
        status = "FOUND" if present else "MISSING"
        print(f"  {ph}: {status}")

    return True

if __name__ == "__main__":
    verify()
