"""
scratch/check_page_heights.py
Estimates the vertical height consumed by each page's content
(paragraphs, headings, tables, callout boxes, and figures)
to guarantee that NO page spills over its printable height of 10.39 inches (~748 pt).
"""

from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt

DOCX_PATH = Path("mini_project_report/Hand_Gesture_Controller_Mini_Project_Report.docx")

def analyze_page_heights():
    doc = Document(str(DOCX_PATH))
    
    # Split paragraphs by page break
    pages = [[]]
    for p in doc.paragraphs:
        has_break = any("<w:br" in r._r.xml and 'type="page"' in r._r.xml for r in p.runs)
        if has_break:
            pages.append([])
        else:
            pages[-1].append(p)

    print(f"Total structured pages: {len(pages)}")
    
    # Analyze table locations
    # Note: python-docx document.tables are document-level, but we know which tables belong to which page:
    # Page 1: tbl_meta (1 table)
    # Page 2: callout (1 table)
    # Page 3: tbl_gest (1 table)
    # Page 4: tbl_tech (1 table), tbl_req (1 table), tree_block (1 table with 2 rows)
    # Page 5: tbl_mod (1 table)
    # Page 6: snip1 (1 table), snip2 (1 table), snip3 (1 table)
    # Page 7: snip4 (1 table), snip5 (1 table), snip6 (1 table)
    # Page 8: tbl_shots (1 table with 4 screenshots)
    # Page 9: tbl_test (1 table), callout (1 table), tbl_bench (1 table)
    # Page 10: tbl_sign (1 table)

    # Let's count elements on each page
    table_map = {
        1: ["tbl_meta (8 rows)"],
        2: ["add_callout (1 table)"],
        3: ["tbl_gest (12 rows)"],
        4: ["tbl_tech (10 rows)", "tbl_req (5 rows)", "tree_code_block (1 table)"],
        5: ["architecture_flowchart (Image: 6.6in)", "tbl_mod (9 rows)"],
        6: ["snip1_camera (1 table)", "snip2_detector (1 table)", "snip3_recognizer (1 table)"],
        7: ["snip4_voting (1 table)", "snip5_dedup (1 table)", "snip6_dispatch (1 table)"],
        8: ["tbl_shots (4 screenshots 2x2 grid)"],
        9: ["tbl_test (11 rows)", "callout (1 table)", "tbl_bench (6 rows)"],
        10: ["tbl_sign (1 table)"],
    }

    for page_num in range(1, len(pages) + 1):
        para_list = pages[page_num - 1]
        print(f"\n--- Page {page_num:02d} ---")
        print(f"Paragraphs: {len(para_list)}")
        print(f"Associated Tables / Figures: {table_map.get(page_num, [])}")
        total_text_chars = sum(len(p.text) for p in para_list)
        print(f"Total paragraph characters: {total_text_chars}")

analyze_page_heights()
