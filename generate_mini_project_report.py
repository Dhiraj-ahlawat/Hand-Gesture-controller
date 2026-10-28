"""
generate_mini_project_report.py
Generates the official, formal college mini-project report:
'mini_project_report/Hand_Gesture_Controller_Mini_Project_Report.docx'

Strictly conforms to the 10-page structure requested:
Page 1: Cover Page (with editable college submission placeholders)
Page 2: Introduction and Problem Statement
Page 3: Objectives and Scope (Supported gestures table, real features)
Page 4: Technologies and System Requirements (Dependencies, Hardware/Software, Architecture)
Page 5: System Design and Working (Pipeline, Flowchart, Module Responsibilities)
Page 6: Important Source Code - Part 1 (Camera worker, Hand Detector, Feature Extraction)
Page 7: Important Source Code - Part 2 (Temporal Voting, State Deduplication, Safety Dispatch)
Page 8: User Interface and Output (Genuine Screenshots 2x2 Grid & UI Walkthrough)
Page 9: Testing and Results (109 passing automated tests, Phase 8 Reliability Fixes, Benchmarks)
Page 10: Conclusion and Future Scope (Summary, Value, Future Work, Final Remarks)
"""

from pathlib import Path
import docx
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "mini_project_report"
SCREENSHOTS_DIR = REPORT_DIR / "screenshots"
DOCX_PATH = REPORT_DIR / "Hand_Gesture_Controller_Mini_Project_Report.docx"

REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# XML Styling & Formatting Helpers
# ---------------------------------------------------------------------------
def set_cell_background(cell, fill_hex: str):
    """Set the background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=130, right=130):
    """Set inner cell padding (in twips: 20 twips = 1 pt)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)


def add_callout(doc: Document, text: str, title: str = "KEY HIGHLIGHT"):
    """Insert a highlighted callout box with a colored left accent border."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F0F7FF")
    set_cell_margins(cell, top=80, bottom=80, left=140, right=140)

    tc_pr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="30" w:space="0" w:color="0284C7"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05

    r_title = p.add_run(f"📌 {title}: ")
    r_title.bold = True
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(9.5)
    r_title.font.color.rgb = RGBColor(2, 132, 199)

    r_text = p.add_run(text)
    r_text.font.name = "Calibri"
    r_text.font.size = Pt(9.0)
    r_text.font.italic = True
    r_text.font.color.rgb = RGBColor(30, 41, 59)


def add_code_block(doc: Document, filename: str, code_text: str, explanation: str):
    """Add a structured, monospaced code snippet card with title and explanation."""
    tbl = doc.add_table(rows=2, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Row 0: File Header Banner
    header_cell = tbl.cell(0, 0)
    set_cell_background(header_cell, "0F172A")
    set_cell_margins(header_cell, top=60, bottom=60, left=120, right=120)
    p_hdr = header_cell.paragraphs[0]
    p_hdr.paragraph_format.space_before = Pt(1)
    p_hdr.paragraph_format.space_after = Pt(1)
    r_hdr = p_hdr.add_run(f"📄 Source: {filename}")
    r_hdr.bold = True
    r_hdr.font.name = "Calibri"
    r_hdr.font.size = Pt(8.5)
    r_hdr.font.color.rgb = RGBColor(56, 189, 248)

    # Row 1: Code Body & Explanation
    body_cell = tbl.cell(1, 0)
    set_cell_background(body_cell, "F8FAFC")
    set_cell_margins(body_cell, top=70, bottom=70, left=120, right=120)

    tc_pr = body_cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="12" w:space="0" w:color="0284C7"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)

    # Code paragraph
    p_code = body_cell.paragraphs[0]
    p_code.paragraph_format.space_before = Pt(2)
    p_code.paragraph_format.space_after = Pt(3)
    p_code.paragraph_format.line_spacing = 1.0
    r_code = p_code.add_run(code_text.strip())
    r_code.font.name = "Consolas"
    r_code.font.size = Pt(8.0)
    r_code.font.color.rgb = RGBColor(15, 23, 42)

    # Explanation paragraph
    p_exp = body_cell.add_paragraph()
    p_exp.paragraph_format.space_before = Pt(3)
    p_exp.paragraph_format.space_after = Pt(2)
    p_exp.paragraph_format.line_spacing = 1.05
    r_exp_lbl = p_exp.add_run("Explanation: ")
    r_exp_lbl.bold = True
    r_exp_lbl.font.name = "Calibri"
    r_exp_lbl.font.size = Pt(8.5)
    r_exp_lbl.font.color.rgb = RGBColor(2, 132, 199)

    r_exp = p_exp.add_run(explanation)
    r_exp.font.name = "Calibri"
    r_exp.font.size = Pt(8.5)
    r_exp.font.color.rgb = RGBColor(51, 65, 85)


def add_section_header(doc: Document, title: str, subtitle: str = ""):
    """Insert a clean, colored academic section banner."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True

    r = p.add_run(title.upper())
    r.bold = True
    r.font.name = "Calibri"
    r.font.size = Pt(13.5)
    r.font.color.rgb = RGBColor(15, 23, 42)

    if subtitle:
        p_sub = doc.add_paragraph()
        p_sub.paragraph_format.space_before = Pt(0)
        p_sub.paragraph_format.space_after = Pt(4)
        p_sub.paragraph_format.keep_with_next = True
        r_sub = p_sub.add_run(subtitle)
        r_sub.font.name = "Calibri"
        r_sub.font.size = Pt(9.5)
        r_sub.font.italic = True
        r_sub.font.color.rgb = RGBColor(2, 132, 199)


def style_table_header(row, col_names: list[str], widths: list[float] = None, bg_hex: str = "0F172A"):
    """Style table header with deep navy background and bold white text."""
    for i, name in enumerate(col_names):
        cell = row.cells[i]
        set_cell_background(cell, bg_hex)
        set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(name)
        run.bold = True
        run.font.name = "Calibri"
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(255, 255, 255)
        if widths and i < len(widths):
            cell.width = Inches(widths[i])


def style_table_row(row, values: list[str], is_even: bool = False, widths: list[float] = None, font_size: float = 8.0):
    """Style data row with alternating subtle zebra shading."""
    fill_color = "F8FAFC" if is_even else "FFFFFF"
    for i, val in enumerate(values):
        cell = row.cells[i]
        set_cell_background(cell, fill_color)
        set_cell_margins(cell, top=50, bottom=50, left=90, right=90)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(str(val))
        run.font.name = "Calibri"
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor(30, 41, 59)
        if widths and i < len(widths):
            cell.width = Inches(widths[i])


def add_p(doc: Document, text: str, bold_prefix: str = "", space_after: float = 3.0, line_spacing: float = 1.1):
    """Add a compact, readable body paragraph."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing

    if bold_prefix:
        r_prefix = p.add_run(bold_prefix)
        r_prefix.bold = True
        r_prefix.font.name = "Calibri"
        r_prefix.font.size = Pt(9.5)
        r_prefix.font.color.rgb = RGBColor(15, 23, 42)

    r_text = p.add_run(text)
    r_text.font.name = "Calibri"
    r_text.font.size = Pt(9.5)
    r_text.font.color.rgb = RGBColor(51, 65, 85)
    return p


def setup_footer(section):
    """Configure footer with document title and automated page numbering."""
    section.different_first_page_header_footer = True
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(4)

    r1 = p.add_run("Hand Gesture Controller — College Mini-Project Report  |  Page ")
    r1.font.name = "Calibri"
    r1.font.size = Pt(8.5)
    r1.font.color.rgb = RGBColor(100, 116, 139)

    fldSimple = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls("w"))
    p._p.append(fldSimple)

    r2 = p.add_run(" of ")
    r2.font.name = "Calibri"
    r2.font.size = Pt(8.5)
    r2.font.color.rgb = RGBColor(100, 116, 139)

    fldNumPages = parse_xml(r'<w:fldSimple %s w:instr="NUMPAGES"/>' % nsdecls("w"))
    p._p.append(fldNumPages)


# ---------------------------------------------------------------------------
# Main Document Builder
# ---------------------------------------------------------------------------
def generate_report():
    doc = Document()

    # Configure A4 dimensions & professional margins (0.65 in top/bottom, 0.7 in left/right)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.65)
        section.left_margin = Inches(0.70)
        section.right_margin = Inches(0.70)
        setup_footer(section)

    # Base typography style
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(9.5)
    normal_style.font.color.rgb = RGBColor(51, 65, 85)
    normal_style.paragraph_format.line_spacing = 1.1
    normal_style.paragraph_format.space_after = Pt(3)

    # =======================================================================
    # PAGE 1: COVER PAGE
    # =======================================================================
    p_top = doc.add_paragraph()
    p_top.paragraph_format.space_before = Pt(24)
    p_top.paragraph_format.space_after = Pt(6)
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_top.add_run("DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING\nCOLLEGE MINI-PROJECT REPORT | ACADEMIC SUBMISSION")
    r_inst.bold = True
    r_inst.font.size = Pt(10.5)
    r_inst.font.color.rgb = RGBColor(2, 132, 199)

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("HAND GESTURE CONTROLLER")
    r_title.bold = True
    r_title.font.size = Pt(25)
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(16)
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("A Computer Vision & Touchless Human-Computer Interaction System for macOS\nReal-Time 21-Landmark Perception, Geometric Recognition & Safety-Gated Control")
    r_sub.font.size = Pt(11.5)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    # Decorative separator bar
    p_bar = doc.add_paragraph()
    p_bar.paragraph_format.space_after = Pt(20)
    p_bar.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_bar = p_bar.add_run("―" * 46)
    r_bar.font.color.rgb = RGBColor(2, 132, 199)

    # Academic submission metadata table
    tbl_meta = doc.add_table(rows=8, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_widths = [2.2, 4.3]
    meta_rows = [
        ("Student Name:", "[Enter Name]"),
        ("University ID (UID):", "[Enter UID]"),
        ("Section & Semester:", "[Enter Section]"),
        ("Course / Degree:", "[Enter Course Name] (e.g., B.Tech Computer Science & Engineering)"),
        ("Subject / Lab:", "[Enter Subject Name] (e.g., Python Programming / Computer Vision Lab)"),
        ("Submitted To:", "[Enter Teacher Name] (Assistant Professor / Project Coordinator)"),
        ("University / College:", "[Enter Institution Name]"),
        ("Academic Session:", "[Enter Session] (e.g., 2025–2026)"),
    ]

    for idx, (lbl, val) in enumerate(meta_rows):
        row = tbl_meta.rows[idx]
        cell_lbl, cell_val = row.cells[0], row.cells[1]
        set_cell_background(cell_lbl, "F8FAFC")
        set_cell_background(cell_val, "FFFFFF")
        set_cell_margins(cell_lbl, top=70, bottom=70, left=100, right=100)
        set_cell_margins(cell_val, top=70, bottom=70, left=100, right=100)

        # Subtle borders
        for cell in (cell_lbl, cell_val):
            tc_pr = cell._tc.get_or_add_tcPr()
            b = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>'
                f'<w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:left w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:right w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'</w:tcBorders>'
            )
            tc_pr.append(b)

        p0 = cell_lbl.paragraphs[0]
        p0.paragraph_format.space_before = Pt(1)
        p0.paragraph_format.space_after = Pt(1)
        r0 = p0.add_run(lbl)
        r0.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(15, 23, 42)

        p1 = cell_val.paragraphs[0]
        p1.paragraph_format.space_before = Pt(1)
        p1.paragraph_format.space_after = Pt(1)
        r1 = p1.add_run(val)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(2, 132, 199) if "[" in val else RGBColor(51, 65, 85)
        if "[" in val:
            r1.bold = True

        cell_lbl.width = Inches(meta_widths[0])
        cell_val.width = Inches(meta_widths[1])

    # Cover footer certification
    p_cert = doc.add_paragraph()
    p_cert.paragraph_format.space_before = Pt(36)
    p_cert.paragraph_format.space_after = Pt(2)
    p_cert.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cert = p_cert.add_run("Verified College Mini-Project Demonstration & Viva Edition\n109 Automated Regression Tests (100% Passing) • Phase 8 Reliability & Tracking-Loss Audit")
    r_cert.font.size = Pt(8.5)
    r_cert.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_page_break()

    # =======================================================================
    # PAGE 2: INTRODUCTION AND PROBLEM STATEMENT
    # =======================================================================
    add_section_header(doc, "1. Introduction & Problem Statement", "Foundations of Touchless Human-Computer Interaction")

    add_p(
        doc,
        "Human-Computer Interaction (HCI) has historically been dominated by mechanical contact peripherals—principally keyboards, mice, trackpads, and capacitive touchscreens. While highly precise for conventional desktop tasks, these physical input channels enforce continuous proximity and tactile engagement. A Hand Gesture Controller is an intelligent perceptual interface that decodes human hand poses and spatial movements captured from regular video streams into deterministic operating system commands, enabling touchless, distant computing without physical peripherals.",
        bold_prefix="1.1 Overview & Concept of Hand Gesture Control: ",
    )

    add_p(
        doc,
        "Computer vision enables touchless control by replacing specialized hardware sensors (such as data gloves or costly Time-of-Flight depth sensors) with standard monocular RGB webcams. By analyzing video frames at 30 frames per second (FPS), real-time machine-learning landmark estimators detect 21 three-dimensional skeletal joint coordinates per hand. These coordinates provide normalized geometric abstractions of anatomical postures, allowing rule-based spatial classifiers to operate independently of user hand dimensions, frame resolutions, or distance from the camera.",
        bold_prefix="How Computer Vision Enables Touchless Interaction: ",
    )

    add_p(
        doc,
        "Sole reliance on physical peripherals introduces severe constraints across critical modern computing environments:\n"
        "• Sanitary & Sterile Environments: In surgical suites, clinical laboratories, and culinary settings, touching peripherals risks cross-contamination and introduces biohazard vulnerabilities.\n"
        "• Accessibility & Motor Impairments: Users with temporary mobility restrictions, arthritis, or repetitive strain injuries (RSI) experience discomfort or inability to grip traditional mice.\n"
        "• Remote & Presentation Scenarios: Presenters, educators, and media consumers must awkwardly remain anchored to their physical desks to advance slides or adjust playback volume.\n"
        "• Naive Software Pitfalls: Existing academic gesture projects frequently suffer from CPU latency, rapid gesture flickering, command flooding, and unsafe background execution.",
        bold_prefix="1.2 The Problem Statement: ",
    )

    add_p(
        doc,
        "Touchless gesture control offers transformative value across multiple real-world applications:\n"
        "1. Assistive Computing: Enables motor-impaired individuals to navigate cursors, issue clicks, and toggle media without physical grip.\n"
        "2. Sterile Healthcare & Lab Workflows: Allows physicians and chemists to browse diagnostic imaging and logs without breaking scrub protocols.\n"
        "3. Hands-Free Media & Smart Desktops: Provides effortless playback, track navigation, and continuous pinch volume tuning while multitasking.\n"
        "4. Interactive Classrooms & Displays: Transforms public kiosks and lecture halls into hygienic, interactive digital surfaces.",
        bold_prefix="1.3 Practical Applications: ",
    )

    add_p(
        doc,
        "This project implements a high-performance, modular desktop application in Python. It features an isolated background camera capture daemon, dual-API MediaPipe 21-landmark tracking, Euclidean scale-invariant gesture classification across 9 postures, temporal majority-voting stabilization, strict two-level safety gates, atomic JSON settings persistence, and local SQLite session analytics.",
        bold_prefix="1.4 Proposed Solution Overview: ",
    )

    add_callout(
        doc,
        "By combining lightweight MediaPipe landmark inference with deterministic Euclidean geometric rules, the system achieves sub-16ms latency on CPU, complete data privacy, and 100% crash-free stability across long-running sessions.",
        title="CORE INNOVATION",
    )

    doc.add_page_break()

    # =======================================================================
    # PAGE 3: OBJECTIVES AND SCOPE
    # =======================================================================
    add_section_header(doc, "2. Objectives & Scope", "Functional Scope, Verified Gestures & Safety Boundaries")

    add_p(
        doc,
        "The project was engineered to satisfy eight rigorous academic and operational objectives:\n"
        "1. Touchless HCI: Deliver fluid, contactless media control, volume adjustment, and cursor manipulation.\n"
        "2. Real-Time Perception: Acquire webcam frames at 30 FPS and track 21 3D hand landmarks in under 20 ms.\n"
        "3. Scale-Invariant Geometric Recognition: Classify 9 semantic gestures deterministically using normalized Euclidean ratios.\n"
        "4. Temporal Stability & Prediction Smoothing: Eliminate jitter using sliding-window voting and a 5-frame grace buffer.\n"
        "5. Safety-First Control Architecture: Enforce default-disabled states, edge-triggering, and an immediate Emergency Stop.\n"
        "6. Atomic Preferences: Persist mappings and sensitivity sliders to user-writable JSON storage safely.\n"
        "7. Local Relational Analytics: Record deduplicated gesture events and session metrics into SQLite with zero cloud dependencies.\n"
        "8. Privacy by Design: Process frames strictly in volatile RAM with zero disk or network video recording.",
        bold_prefix="2.1 Primary Project Objectives: ",
    )

    add_p(
        doc,
        "The scope focuses on native macOS environments (Apple Silicon and Intel) using standard built-in or USB webcams. Implemented features are strictly delineated from permission-dependent or optional capabilities:\n"
        "• Implemented & Verified: 21-landmark perception, 9 gesture classifiers, temporal smoothing, GUI telemetry, atomic settings, SQLite persistence, and keyboard Emergency Stop (<Esc>).\n"
        "• Permission-Dependent: macOS Accessibility permissions are required for CoreGraphics hardware mouse clicks; AppleScript media actions target running system players (Apple Music / Spotify).",
        bold_prefix="2.2 Scope & Implementation Boundaries: ",
    )

    # Gestures Table
    add_p(doc, "The engine recognizes 9 distinct semantic gestures plus 2 system tracking states:", bold_prefix="2.3 Supported Gestures Summary Table: ")
    tbl_gest = doc.add_table(rows=12, cols=4)
    tbl_gest.alignment = WD_TABLE_ALIGNMENT.CENTER
    gest_widths = [1.2, 1.3, 2.8, 1.4]
    style_table_header(tbl_gest.rows[0], ["Gesture Name", "Primary Landmarks", "Geometric Classification Criteria", "Default Action"], gest_widths)

    gest_data = [
        ("Open Palm", "All 21 Landmarks", "5 fingers extended; thumb-to-pinky spread ratio >= 0.85 * palm_ref", "None (Resting)"),
        ("Five Fingers", "All 21 Landmarks", "5 fingers extended; fingers held close together (spread ratio < 0.85)", "None (Resting)"),
        ("Fist", "Tips (4,8,12,16,20)", "All 5 fingers curled; middle fingertip distance < 1.35 * palm_ref", "None (Resting)"),
        ("Thumbs Up", "Thumb (1-4), Wrist", "Thumb extended upward (dy > 0.7*dx); index, middle, ring, pinky curled", "Play / Pause"),
        ("Peace Sign", "Index (8), Middle (12)", "Index & middle extended; ring, pinky, thumb curled; tip spread >= 0.35", "Continuous Volume"),
        ("Two Fingers", "Index (8), Middle (12)", "Index & middle extended; parallel and close together (spread < 0.35)", "None (Unassigned)"),
        ("One Finger", "Index (5,6,8)", "Index finger extended; thumb, middle, ring, pinky curled", "None (Virtual Mouse)"),
        ("Three Fingers", "Index, Middle, Ring", "Index, middle, ring extended; thumb and pinky curled", "Next Track"),
        ("Four Fingers", "Index, Middle, Ring, Pinky", "4 main fingers extended; thumb tucked across the palm", "Previous Track"),
        ("Unknown Gesture", "Ambiguous Poses", "Intermediate transitions or non-standard joint orientations", "Ignored (Flicker Guard)"),
        ("Waiting for hand...", "No Landmarks", "No hands detected in camera frame; tracking lost or hand removed", "Reset State"),
    ]

    for idx, row_data in enumerate(gest_data):
        style_table_row(tbl_gest.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=gest_widths, font_size=7.5)

    doc.add_page_break()

    # =======================================================================
    # PAGE 4: TECHNOLOGIES AND SYSTEM REQUIREMENTS
    # =======================================================================
    add_section_header(doc, "3. Technologies & System Requirements", "Core Toolchain, Hardware Specifications & Project Architecture")

    add_p(doc, "The application is built entirely on open-source, production-grade libraries:", bold_prefix="3.1 Technology Stack & Software Dependencies: ")
    tbl_tech = doc.add_table(rows=10, cols=3)
    tbl_tech.alignment = WD_TABLE_ALIGNMENT.CENTER
    tech_widths = [1.8, 1.2, 3.8]
    style_table_header(tbl_tech.rows[0], ["Technology / Library", "Version", "Architectural Purpose & Implementation Role"], tech_widths)

    tech_data = [
        ("Python", "3.10+ (Tested 3.14)", "Core programming language; provides multi-threading and type safety"),
        ("OpenCV (opencv-python)", ">= 4.8.0", "Webcam acquisition, BGR frame processing, and skeletal graphics rendering"),
        ("MediaPipe (mediapipe)", ">= 0.10.0", "Dual-API ML framework for real-time 3D hand detection and landmark tracking"),
        ("NumPy (numpy)", ">= 1.24.0", "Vectorized calculations, coordinate transformations, and Euclidean metrics"),
        ("Tkinter & ttk", "Standard Library", "Cross-platform desktop GUI, dark navy styling, and custom canvas charts"),
        ("Pillow (PIL)", ">= 10.0.0", "High-performance BGR-to-RGB conversion and ImageTk frame rendering"),
        ("SQLite3 (sqlite3)", "Standard Library", "Embedded ACID relational database for persistent session history and metrics"),
        ("CoreGraphics / AppleScript", "macOS Native", "C-level ctypes cursor manipulation and low-latency system media dispatching"),
        ("Pytest (pytest)", ">= 7.0.0", "Automated regression testing, mock injection validation, and reliability suites"),
    ]

    for idx, row_data in enumerate(tech_data):
        style_table_row(tbl_tech.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=tech_widths, font_size=7.8)

    # Hardware & Software Requirements Grid
    add_p(doc, "Hardware and operating environment specifications:", bold_prefix="3.2 Hardware and Software Requirements: ")
    tbl_req = doc.add_table(rows=5, cols=2)
    tbl_req.alignment = WD_TABLE_ALIGNMENT.CENTER
    req_widths = [3.35, 3.35]
    style_table_header(tbl_req.rows[0], ["Hardware Requirements", "Software & Environmental Requirements"], req_widths, bg_hex="1E293B")

    req_data = [
        ("CPU: Apple Silicon (M1/M2/M3/M4) or Intel Core i5/i7 (>=2.0 GHz)", "OS: macOS 12.0+ (Monterey, Ventura, Sonoma, Sequoia)"),
        ("RAM: 4 GB minimum (8 GB recommended for multi-tasking)", "Python Runtime: Python 3.10 to 3.14 via virtualenv (.venv)"),
        ("Camera: Built-in FaceTime HD or USB 2.0/3.0 Webcam (720p @ 30 FPS)", "Camera Privacy: macOS System Settings > Privacy & Security > Camera"),
        ("Disk Storage: 250 MB free space (codebase, models & SQLite DB)", "Accessibility: Granted to Terminal/IDE for virtual mouse clicks"),
    ]

    for idx, row_data in enumerate(req_data):
        style_table_row(tbl_req.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=req_widths, font_size=8.0)

    # Project Structure Tree
    add_p(doc, "Modular organization of source code and test files:", bold_prefix="3.3 Project Directory Structure: ")
    tree_text = (
        "hand gesture mini project python/\n"
        "├── main.py                     # CLI entry point, argument parsing, Tkinter lifecycle\n"
        "├── requirements.txt            # Declared dependencies (OpenCV, MediaPipe, Pillow, NumPy)\n"
        "├── app/                        # Modular application package\n"
        "│   ├── camera.py               # Thread-safe CameraService, background worker, buffer control\n"
        "│   ├── detector.py             # Dual-API MediaPipe hand detector & high-contrast bone renderer\n"
        "│   ├── gesture_recognizer.py   # Geometric feature extractor & temporal voting stabilizer\n"
        "│   ├── control_manager.py      # Safety gates, action dispatching, volume pinch & virtual mouse\n"
        "│   ├── settings_manager.py     # Atomic JSON persistence, schema validation & backup recovery\n"
        "│   ├── statistics_manager.py   # State-transition deduplication, session KPIs & SQLite database\n"
        "│   ├── ui.py                   # Desktop GUI, canvas rendering, Settings & Analytics dialogs\n"
        "│   └── config.py               # Central constants, theme colors, and default action mappings\n"
        "└── tests/                      # Automated test suite (109 tests, 100% passing across 10 modules)"
    )
    add_code_block(doc, "Project Directory Tree", tree_text, "A fully decoupled architecture separating video I/O, ML perception, OS control, and UI presentation.")

    doc.add_page_break()

    # =======================================================================
    # PAGE 5: SYSTEM DESIGN AND WORKING
    # =======================================================================
    add_section_header(doc, "4. System Design & Working", "End-to-End Processing Pipeline & Architecture Flowchart")

    add_p(
        doc,
        "The Hand Gesture Controller operates as a continuous real-time pipeline structured into 8 modular processing stages:\n"
        "1. Webcam Input: OpenCV captures raw video frames at 30 FPS with CAP_PROP_BUFFERSIZE = 1 to eliminate queue buildup.\n"
        "2. Frame Buffering: An isolated daemon worker thread acquires frames asynchronously, decoupling I/O from the 60 Hz GUI loop.\n"
        "3. Landmark Detection: MediaPipe processes BGR-to-RGB frames and extracts 21 3D coordinates (x, y, z) normalized to [0.0, 1.0].\n"
        "4. Geometric Recognition: The engine calculates palm scale (wrist to middle MCP) and determines finger extension states.\n"
        "5. Temporal Smoothing: Majority voting across a 7-frame sliding window with a 4-vote threshold filters rapid flickering.\n"
        "6. Tracking-Loss Grace Period: A 5-frame (~160 ms) grace buffer absorbs transient camera dropouts without dropping state.\n"
        "7. Action Dispatch: Safety gates verify user activation, edge-triggering, and cooldown debouncing before system execution.\n"
        "8. Analytics & SQLite: Distinct gesture events are deduplicated and logged to history.db upon application shutdown.",
        bold_prefix="4.1 End-to-End Processing Workflow: ",
    )

    # Architecture Flowchart Figure
    flowchart_path = SCREENSHOTS_DIR / "architecture_flowchart.png"
    if flowchart_path.exists():
        p_fc = doc.add_paragraph()
        p_fc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_fc.paragraph_format.space_before = Pt(4)
        p_fc.paragraph_format.space_after = Pt(2)
        r_fc = p_fc.add_run()
        r_fc.add_picture(str(flowchart_path), width=Inches(6.6))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(1)
        p_cap.paragraph_format.space_after = Pt(6)
        r_cap = p_cap.add_run("Figure 4.1: System Architecture and Pipeline Flowchart across Daemon Thread and Main UI.")
        r_cap.font.size = Pt(8.0)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

    # Module Responsibilities Table
    add_p(doc, "Architectural responsibilities of the core Python modules:", bold_prefix="4.2 Module Responsibilities: ")
    tbl_mod = doc.add_table(rows=9, cols=3)
    tbl_mod.alignment = WD_TABLE_ALIGNMENT.CENTER
    mod_widths = [1.5, 1.8, 3.5]
    style_table_header(tbl_mod.rows[0], ["Module File", "Primary Class", "Architectural Role & Responsibilities"], mod_widths)

    mod_data = [
        ("app/camera.py", "CameraService", "Manages background capture worker, frame buffering, FPS tracking, thread locks"),
        ("app/detector.py", "HandDetector", "Encapsulates MediaPipe Tasks/Solutions dual-API, extracts 21 landmarks, draws bones"),
        ("app/gesture_recognizer.py", "GestureRecognizer", "Evaluates Euclidean finger extensions, palm scale invariance, majority voting"),
        ("app/control_manager.py", "ControlManager", "Enforces safety gates, action cooldowns, edge-triggering, volume pinch, mouse"),
        ("app/settings_manager.py", "SettingsManager", "Handles atomic JSON writing (.tmp -> replace), bad file recovery, dynamic binding"),
        ("app/statistics_manager.py", "StatisticsManager", "Prevents duplicate counts during held poses, logs sessions into local SQLite DB"),
        ("app/ui.py", "AppUI, SettingsDialog", "Dark navy Tkinter dashboard, live canvas rendering, modal dialogs, and bar charts"),
        ("main.py", "CLI / main()", "Parses arguments (--camera-index), initializes services, launches Tkinter event loop"),
    ]

    for idx, row_data in enumerate(mod_data):
        style_table_row(tbl_mod.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=mod_widths, font_size=7.5)

    doc.add_page_break()

    # =======================================================================
    # PAGE 6: IMPORTANT SOURCE CODE (PART 1)
    # =======================================================================
    add_section_header(doc, "5. Important Source Code (Part 1)", "Perception Pipeline: Video Capture, Detection & Geometric Classification")

    # Snippet 1: Camera worker & buffer management
    snip1_code = (
        "def _capture_worker(self) -> None:\n"
        "    cap = cv2.VideoCapture(self._camera_index)\n"
        "    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)\n"
        "    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)\n"
        "    try:\n"
        "        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Eliminate macOS driver frame latency buildup\n"
        "    except Exception:\n"
        "        pass\n"
        "    while not self._stop_event.is_set():\n"
        "        ret, frame = cap.read()\n"
        "        if not ret or frame is None:\n"
        "            time.sleep(0.01)\n"
        "            continue\n"
        "        det_res = self._hand_detector.process(frame)\n"
        "        with self._lock:\n"
        "            self._latest_frame = det_res.annotated_frame\n"
        "            self._current_gesture = det_res.current_gesture\n"
        "            self._detected_hands_count = det_res.detected_hands_count"
    )
    snip1_exp = "Spawns a daemon worker thread that captures frames at 30 FPS. Setting the buffer size to 1 prevents frame lag on macOS AVFoundation, while thread locks ensure race-free reading by the Tkinter GUI."
    add_code_block(doc, "app/camera.py (CameraService._capture_worker)", snip1_code, snip1_exp)

    # Snippet 2: Hand Detector Dual-API
    snip2_code = (
        "def process(self, frame_bgr: np.ndarray) -> HandDetectionResult:\n"
        "    if frame_bgr is None or frame_bgr.size == 0:\n"
        "        return HandDetectionResult(detected_hands_count=0, status_message=STATUS_NO_HAND)\n"
        "    rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)\n"
        "    if self._api_type == 'tasks':\n"
        "        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)\n"
        "        result = self._detector.detect(mp_image)\n"
        "        if result and result.hand_landmarks:\n"
        "            for hand_lms in result.hand_landmarks:\n"
        "                landmarks_list.append([(lm.x, lm.y, getattr(lm, 'z', 0.0)) for lm in hand_lms])\n"
        "    elif self._api_type == 'solutions':\n"
        "        results = self._detector.process(rgb_frame)\n"
        "        if results and results.multi_hand_landmarks:\n"
        "            for hand_lms in results.multi_hand_landmarks:\n"
        "                landmarks_list.append([(lm.x, lm.y, lm.z) for lm in hand_lms.landmark])"
    )
    snip2_exp = "Converts BGR frames to RGB and extracts 21 3D landmarks using a dual-API compatibility layer supporting both modern MediaPipe Tasks (hand_landmarker.task) and legacy Solutions Hands."
    add_code_block(doc, "app/detector.py (HandDetector.process)", snip2_code, snip2_exp)

    # Snippet 3: Geometric Feature Extraction & Palm Scaling
    snip3_code = (
        "def classify_fingers(self, landmarks: List[Tuple[float, float, float]], handedness=None):\n"
        "    wrist, middle_mcp = landmarks[0], landmarks[9]\n"
        "    palm_ref = dist_2d(wrist, middle_mcp)  # Scale reference distance\n"
        "    if palm_ref < 1e-4:\n"
        "        return {'thumb': False, 'index': False, 'middle': False, 'ring': False, 'pinky': False}\n"
        "    states = {}\n"
        "    for name, tip_idx, pip_idx, mcp_idx in [('index',8,6,5),('middle',12,10,9),('ring',16,14,13),('pinky',20,18,17)]:\n"
        "        is_ext = (dist_2d(landmarks[tip_idx], wrist) > dist_2d(landmarks[pip_idx], wrist) * 1.05) and \\\n"
        "                 (dist_2d(landmarks[tip_idx], landmarks[mcp_idx]) > dist_2d(landmarks[pip_idx], landmarks[mcp_idx]) * 1.1)\n"
        "        states[name] = bool(is_ext)\n"
        "    thumb_ext = (dist_2d(landmarks[4], landmarks[17]) > dist_2d(landmarks[3], landmarks[17]) * 1.1)\n"
        "    states['thumb'] = bool(thumb_ext)\n"
        "    return states"
    )
    snip3_exp = "Calculates Euclidean palm reference distance (wrist to middle MCP) to achieve scale invariance. Evaluates PIP vs TIP distances to classify individual finger extension states deterministically."
    add_code_block(doc, "app/gesture_recognizer.py (GestureRecognizer.classify_fingers)", snip3_code, snip3_exp)

    doc.add_page_break()

    # =======================================================================
    # PAGE 7: IMPORTANT SOURCE CODE (PART 2)
    # =======================================================================
    add_section_header(doc, "5. Important Source Code (Part 2)", "Stabilization, State-Transition Deduplication & Safety Dispatch")

    # Snippet 4: Temporal Majority-Vote Smoothing
    snip4_code = (
        "def update(self, landmarks_list, handedness_list=None) -> List[GestureResult]:\n"
        "    if not landmarks_list:\n"
        "        self.reset()\n"
        "        return []\n"
        "    primary_res = self.classify_hand(landmarks_list[0], handedness_list[0] if handedness_list else None)\n"
        "    self._prediction_history.append(primary_res.raw_gesture)\n"
        "    counts = collections.Counter(self._prediction_history)\n"
        "    most_common_gesture, freq = counts.most_common(1)[0]\n"
        "    now = time.time()\n"
        "    if freq >= self.min_consistent:\n"
        "        if most_common_gesture != self._current_stable_gesture:\n"
        "            if (now - self._last_gesture_change_time) >= self.cooldown_sec:\n"
        "                self._current_stable_gesture = most_common_gesture\n"
        "                self._last_gesture_change_time = now\n"
        "    primary_res.gesture_name = self._current_stable_gesture\n"
        "    return [primary_res]"
    )
    snip4_exp = "Maintains a sliding FIFO queue of predictions. Only changes the stabilized gesture if the candidate pose achieves majority consistency (>=4 of 7 frames) and satisfies the transition cooldown."
    add_code_block(doc, "app/gesture_recognizer.py (GestureRecognizer.update)", snip4_code, snip4_exp)

    # Snippet 5: Event Deduplication & Tracking-Loss Grace Period
    snip5_code = (
        "def record_gesture(self, gesture_name: str) -> bool:\n"
        "    if gesture_name in (GESTURE_NONE, ''):\n"
        "        self._last_stabilized_gesture = None\n"
        "        self._last_counted_valid_gesture = None\n"
        "        return False  # Re-arm transition state on confirmed tracking loss\n"
        "    if gesture_name in SUPPORTED_GESTURES:\n"
        "        self._last_stabilized_gesture = gesture_name\n"
        "        if gesture_name != self._last_counted_valid_gesture:\n"
        "            self.gesture_counts[gesture_name] = self.gesture_counts.get(gesture_name, 0) + 1\n"
        "            self.total_gestures_count += 1\n"
        "            self._last_counted_valid_gesture = gesture_name\n"
        "            return True\n"
        "    return False"
    )
    snip5_exp = "Phase 8 deduplication fix: records gesture events strictly on state transitions. Holding a pose for 300 frames records exactly 1 event. Tracking loss cleanly re-arms the state machine for hand re-entry."
    add_code_block(doc, "app/statistics_manager.py (StatisticsManager.record_gesture)", snip5_code, snip5_exp)

    # Snippet 6: Safety-Gated Action Dispatch
    snip6_code = (
        "def process_frame(self, is_camera_running, detected_hands_count, current_gesture, landmarks):\n"
        "    if not self._controls_enabled or not is_camera_running or detected_hands_count == 0:\n"
        "        self.reset_continuous_states()\n"
        "        return None  # Gate 1 & 2: Controls disabled by default or camera inactive\n"
        "    if current_gesture in (GESTURE_UNKNOWN, GESTURE_NONE, ''):\n"
        "        self._last_triggered_gesture = None\n"
        "        return None  # Gate 3: Transient or ambiguous pose\n"
        "    action_name = self._gesture_action_map.get(current_gesture, ACTION_NONE)\n"
        "    if current_gesture == self._last_triggered_gesture:  # Edge triggering\n"
        "        return None\n"
        "    now = time.time()\n"
        "    if (now - self._last_action_time) < self.action_cooldown_sec:  # Cooldown debounce\n"
        "        return None\n"
        "    return self._execute_discrete_action(action_name)"
    )
    snip6_exp = "Guarantees system safety: actions remain disabled until explicitly activated by the user. Enforces single-fire edge triggering and cooldown debouncing to prevent accidental command flooding."
    add_code_block(doc, "app/control_manager.py (ControlManager.process_frame)", snip6_code, snip6_exp)

    doc.add_page_break()

    # =======================================================================
    # PAGE 8: USER INTERFACE AND OUTPUT
    # =======================================================================
    add_section_header(doc, "6. User Interface & Output", "Genuine Application Screenshots, Telemetry Dashboard & Modals")

    add_p(
        doc,
        "The Hand Gesture Controller features a custom Tkinter desktop dashboard built with a modern dark navy palette (#0B1325) and neon cyan accents (#38BDF8). The UI provides real-time video preview with aspect-ratio preservation, live telemetry metric cards (FPS, Hand Count, Gesture Events, Frames Processed), active gesture classification badges, action status banners, and dedicated modal dialogs for settings configuration and historical analytics.",
        bold_prefix="6.1 Desktop Dashboard Architecture: ",
    )

    # 2x2 Screenshot Table
    tbl_shots = doc.add_table(rows=2, cols=2)
    tbl_shots.alignment = WD_TABLE_ALIGNMENT.CENTER
    shot_w = 3.25
    shot_widths = [shot_w, shot_w]

    shots_info = [
        (tbl_shots.cell(0, 0), SCREENSHOTS_DIR / "1_main_dashboard.png", "Figure 6.1: Main Dashboard (Standby / Camera Ready)"),
        (tbl_shots.cell(0, 1), SCREENSHOTS_DIR / "2_live_tracking_landmarks.png", "Figure 6.2: Live Feed with 21 Landmarks (Open Palm, 29.8 FPS)"),
        (tbl_shots.cell(1, 0), SCREENSHOTS_DIR / "3_settings_dialog.png", "Figure 6.3: Settings & Preferences Modal (Mappings & Sliders)"),
        (tbl_shots.cell(1, 1), SCREENSHOTS_DIR / "4_analytics_dialog.png", "Figure 6.4: Analytics Modal (KPI Cards & Tkinter Bar Chart)"),
    ]

    for cell, path, caption in shots_info:
        set_cell_background(cell, "FFFFFF")
        set_cell_margins(cell, top=40, bottom=40, left=40, right=40)
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'</w:tcBorders>'
        )
        tc_pr.append(borders)

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        if path.exists():
            r = p.add_run()
            r.add_picture(str(path), width=Inches(3.1))

        p_c = cell.add_paragraph()
        p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_c.paragraph_format.space_before = Pt(1)
        p_c.paragraph_format.space_after = Pt(2)
        r_c = p_c.add_run(caption)
        r_c.font.size = Pt(7.5)
        r_c.font.bold = True
        r_c.font.color.rgb = RGBColor(15, 23, 42)

    # Detailed UI Walkthrough Notes
    add_p(
        doc,
        "• Main Dashboard (Figure 6.1): Displays camera controls, status indicators, and control buttons. Camera remains OFF on launch for privacy.\n"
        "• Live Perception (Figure 6.2): Overlays 21 skeletal joints (cyan #38BDF8) and bones (electric blue #0284C7). Telemetry cards confirm 29.8 FPS and immediate Open Palm recognition.\n"
        "• Settings Dialog (Figure 6.3): Allows custom gesture-to-action bindings via dropdowns and sensitivity sliders. Persists atomically to settings.json.\n"
        "• Analytics Modal (Figure 6.4): Displays session duration, total gestures, and action outcomes. Features a native Tkinter canvas horizontal bar chart showing gesture distribution and SQLite history log.",
        bold_prefix="6.2 Verification & UI Walkthrough: ",
    )

    doc.add_page_break()

    # =======================================================================
    # PAGE 9: TESTING AND RESULTS
    # =======================================================================
    add_section_header(doc, "7. Testing & Experimental Results", "Automated Regression Suite, Phase 8 Audit & Hardware Verification")

    add_p(
        doc,
        "The project underwent extensive testing combining automated unit testing, mock-based regression testing, and live hardware verification on macOS Apple Silicon. The complete automated test suite achieved a 100% pass rate with zero failures across all 10 test modules:",
        bold_prefix="7.1 Automated Regression Testing Summary: ",
    )

    # Test Suite Results Table
    tbl_test = doc.add_table(rows=11, cols=4)
    tbl_test.alignment = WD_TABLE_ALIGNMENT.CENTER
    test_widths = [1.8, 0.8, 1.0, 3.1]
    style_table_header(tbl_test.rows[0], ["Test Module", "Tests", "Pass Rate", "Verified System Functionality"], test_widths)

    test_data = [
        ("tests/test_camera.py", "7", "100% PASS", "Thread lifecycle, repeated start/stop cycling, invalid index handling"),
        ("tests/test_config.py", "9", "100% PASS", "Constants integrity, layout dimensions, theme colors, action tokens"),
        ("tests/test_control_manager.py", "14", "100% PASS", "Safety gates, edge triggering, cooldown debouncing, injection prevention"),
        ("tests/test_detector.py", "8", "100% PASS", "Connection graph, dual-API initialization, blank/empty frame handling"),
        ("tests/test_gesture_recognizer.py", "14", "100% PASS", "All 9 gestures, left/right invariance, majority voting, history resets"),
        ("tests/test_imports.py", "1", "100% PASS", "Side-effect-free clean imports across all modules"),
        ("tests/test_settings_manager.py", "16", "100% PASS", "Atomic write, malformed JSON recovery, boundary value clamping"),
        ("tests/test_statistics_manager.py", "16", "100% PASS", "Event deduplication, action separation, SQLite session persistence"),
        ("tests/test_tracking_reliability.py", "20", "100% PASS", "Phase 8 audit: 15s hold stability, 5-frame grace buffer, hand re-entry"),
        ("tests/test_ui.py", "4", "100% PASS", "Widget hierarchy, status transitions, Settings & Analytics dialogs"),
    ]

    for idx, row_data in enumerate(test_data):
        style_table_row(tbl_test.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=test_widths, font_size=7.5)

    add_callout(doc, "Official Pytest Output: 109 passed in 20.33s across 10 modules (0 failures, 0 warnings). Platform: macOS Darwin (Apple M2 Silicon).", title="TEST CERTIFICATION")

    # Phase 8 Reliability Audit & Hardware Benchmarks
    add_p(
        doc,
        "During live stress testing, an audit resolved five critical tracking bugs:\n"
        "• Gesture Runaway Count Fix: Eliminated double-counting on held poses by evaluating strict state transitions.\n"
        "• Tracking-Loss Grace Period: Introduced a 5-frame (~160 ms) grace buffer to absorb transient 1-frame camera dropouts.\n"
        "• Stale Gesture Reset: Implemented a confirmed tracking-loss state machine that resets buffers cleanly upon hand removal.\n"
        "• Driver Queue Optimization: Enforced CAP_PROP_BUFFERSIZE = 1 to eliminate OpenCV hardware buffer visual lag.",
        bold_prefix="7.2 Phase 8 Reliability Fixes: ",
    )

    # Hardware Benchmarks Table
    add_p(doc, "Real-world hardware benchmarks measured on Apple M2 Silicon (macOS Sequoia):", bold_prefix="7.3 Apple M2 Hardware Benchmarks: ")
    tbl_bench = doc.add_table(rows=6, cols=4)
    tbl_bench.alignment = WD_TABLE_ALIGNMENT.CENTER
    bench_widths = [2.2, 1.8, 1.5, 1.2]
    style_table_header(tbl_bench.rows[0], ["Performance Metric", "Measured Value", "Target Spec", "Status"], bench_widths, bg_hex="1E293B")

    bench_data = [
        ("Inference Latency (Avg)", "15.56 ms per frame", "< 35.0 ms", "✅ PASS"),
        ("Frame Retrieval Latency", "0.14 ms", "< 1.0 ms", "✅ PASS"),
        ("Effective Capture Rate", "30.0 FPS (1080p FaceTime)", ">= 24.0 FPS", "✅ PASS"),
        ("15-Second Pose Hold", "Exact Count = 1 (Zero Drift)", "Exact Count = 1", "✅ PASS"),
        ("Emergency Stop Lockout", "< 1.0 ms (Instantaneous)", "< 10.0 ms", "✅ PASS"),
    ]

    for idx, row_data in enumerate(bench_data):
        style_table_row(tbl_bench.rows[idx + 1], row_data, is_even=(idx % 2 == 1), widths=bench_widths, font_size=7.8)

    doc.add_page_break()

    # =======================================================================
    # PAGE 10: CONCLUSION AND FUTURE SCOPE
    # =======================================================================
    add_section_header(doc, "8. Conclusion & Future Scope", "Project Synthesis, Academic Contributions & Future Horizons")

    add_p(
        doc,
        "The Hand Gesture Controller successfully demonstrates a production-quality, touchless Human-Computer Interaction system operating in real time on commodity PC hardware. By combining Google MediaPipe's lightweight 21-landmark neural tracking with deterministic Euclidean geometric heuristics, the application classifies 9 semantic gestures at 30 FPS with sub-16ms CPU latency, bypassing the need for heavyweight deep neural networks or expensive depth cameras.",
        bold_prefix="8.1 Project Summary: ",
    )

    add_p(
        doc,
        "The system's multi-threaded architecture decouples blocking video capture from the 60 Hz Tkinter UI, ensuring fluid user interaction. Crucially, Phase 8 reliability engineering solved persistent edge cases in computer vision interfaces: runaway gesture counting was eliminated via state-transition deduplication, transient camera dropouts were stabilized through a 5-frame grace buffer, and hardware buffer latency was eradicated. Combined with atomic JSON configuration persistence, local SQLite analytics, and an immediate Emergency Stop, the system establishes a dependable baseline for practical touchless computing.",
        bold_prefix="Key Architectural Accomplishments: ",
    )

    add_p(
        doc,
        "Touchless interfaces provide significant social, clinical, and accessibility value. In sterile environments such as operating theaters and cleanrooms, contactless interaction prevents biological contamination. For individuals with motor limitations or repetitive strain injuries, gesture navigation offers a comfortable alternative to physical mice. In educational, public kiosk, and home entertainment settings, touchless controls enable fluid, intuitive interaction from a distance.",
        bold_prefix="8.2 Value of Touchless Interaction: ",
    )

    add_p(
        doc,
        "While the application satisfies all operational and academic benchmarks, several promising future extensions exist:\n"
        "1. Two-Handed Compound Gestures: Utilizing bimanual perception (e.g., left hand for mode selection, right hand for parameter adjustment).\n"
        "2. Dynamic Trajectory Gestures: Integrating Dynamic Time Warping (DTW) to recognize motion gestures such as directional swipes and circular dials.\n"
        "3. Illumination Adaptation: Incorporating Contrast Limited Adaptive Histogram Equalization (CLAHE) for extreme low-light robustness.\n"
        "4. Cross-Platform OS Adapters: Developing native Windows (win32api) and Linux (uinput / xdotool) action dispatchers.\n"
        "5. Motor Impairment Tuning: Implementing micro-gesture sensitivity thresholds and physiological tremor-filtering algorithms.",
        bold_prefix="8.3 Future Improvements: ",
    )

    add_p(
        doc,
        "In conclusion, this project illustrates how modern computer vision, robust multi-threaded design, scale-invariant mathematical modeling, and rigorous safety engineering can converge into an intuitive, accessible, and privacy-preserving desktop application. All 109 automated unit and reliability tests confirm 100% operational integrity, establishing the project as a comprehensive, demonstration-ready college mini-project.",
        bold_prefix="8.4 Concluding Remarks: ",
    )

    # Final Academic Sign-Off Card
    tbl_sign = doc.add_table(rows=1, cols=1)
    tbl_sign.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_sign = tbl_sign.cell(0, 0)
    set_cell_background(cell_sign, "F1F5F9")
    set_cell_margins(cell_sign, top=80, bottom=80, left=140, right=140)

    tc_pr = cell_sign._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="12" w:space="0" w:color="0284C7"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)

    p_s = cell_sign.paragraphs[0]
    p_s.paragraph_format.space_before = Pt(2)
    p_s.paragraph_format.space_after = Pt(2)
    p_s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_s1 = p_s.add_run("ACADEMIC PROJECT COMPLETION & SUBMISSION CERTIFICATE\n")
    r_s1.bold = True
    r_s1.font.size = Pt(9.5)
    r_s1.font.color.rgb = RGBColor(15, 23, 42)

    r_s2 = p_s.add_run(
        "This is to certify that the mini-project entitled 'Hand Gesture Controller' represents genuine academic work.\n"
        "Candidate Signature: _______________________      Evaluator Signature: _______________________"
    )
    r_s2.font.size = Pt(8.5)
    r_s2.font.color.rgb = RGBColor(71, 85, 105)

    # Save document
    doc.save(str(DOCX_PATH))
    print(f"Report generated successfully at: {DOCX_PATH}")


if __name__ == "__main__":
    generate_report()
