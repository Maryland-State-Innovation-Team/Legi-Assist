import os
import pymupdf
from typing import Optional

def convert_pdfs_to_md(session_year: int, bill_number: str, state_manager):
    """
    Converts downloaded PDFs for a bill into Markdown.
    """
    md_dir = os.path.abspath(f'data/{session_year}rs/md')
    os.makedirs(md_dir, exist_ok=True)
    
    bill_state = state_manager.get_bill(bill_number)
    files = bill_state.get('files', {})
    
    # Convert Main Bill
    bill_pdf = files.get('bill_pdf')
    any_changes = False
    
    if bill_pdf and os.path.exists(bill_pdf):
        md_path = os.path.join(md_dir, f"{bill_number}.md")
        if _convert_single(bill_pdf, md_path):
            any_changes = True
    
    # Convert Amendments
    amd_files = files.get('amendments', [])
    # If list of strings (paths)
    for amd_pdf in amd_files:
        if os.path.exists(amd_pdf):
            base = os.path.basename(amd_pdf).replace('.pdf', '.md')
            md_path = os.path.join(md_dir, base)
            if _convert_single(amd_pdf, md_path):
                any_changes = True

    # Convert Fiscal Note
    fn_pdf = files.get('fiscal_note')
    if fn_pdf and os.path.exists(fn_pdf):
        base = os.path.basename(fn_pdf).replace('.pdf', '.md')
        md_path = os.path.join(md_dir, base)
        if _convert_single_simple(fn_pdf, md_path):
            any_changes = True
            
    # Update State
    state_manager.update_bill(bill_number, {"needs_convert": False})
    
    if any_changes:
        # Logic: If we have amendments, we need to run the Amender
        if amd_files:
            state_manager.update_bill(bill_number, {"needs_amend": True})
        else:
            # If no amendments, we might still need QA if the main bill changed
            state_manager.update_bill(bill_number, {"needs_qa": True, "amended_status": "original"})
    else:
        state_manager.update_bill(bill_number, {"needs_amend": False, "needs_qa": False})


def _convert_single(pdf_path, md_path) -> bool:
    text = pdf_text(pdf_path)
    return _write_if_changed(text, md_path)


def _convert_single_simple(pdf_path, md_path) -> bool:
    text = pdf_text_simple(pdf_path)
    return _write_if_changed(text, md_path)


def _write_if_changed(text, path) -> bool:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            existing_text = f.read()
        if existing_text == text:
            return False
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True


def pdf_text_simple(pdf_file):
    page_texts = list()
    doc = pymupdf.open(pdf_file) # open a document
    for index, page in enumerate(doc):
        page_text = f'START OF PAGE {index + 1}\n{page.get_text()}\nEND OF PAGE {index + 1}'
        page_texts.append(page_text)
    return "\n\n".join(page_texts)


def get_struck_word_rects(page: pymupdf.Page, height_threshold: float = 1.5) -> set[pymupdf.Rect]:
    """
    Identifies the bounding boxes of words that intersect with potential
    strikethrough drawings (thin, black, filled rectangles).

    Args:
        page: The pymupdf.Page object to analyze.
        height_threshold: Max height for a drawing rect to be considered a strike line.

    Returns:
        A set containing the pymupdf.Rect objects of words identified as struck through.
    """
    strikethrough_line_rects = []
    drawings = page.get_drawings()

    # 1. Filter drawings for potential strikethrough lines
    for drawing in drawings:
        if drawing.get("type") == "f" and drawing.get("fill") == (0.0, 0.0, 0.0):
            for item in drawing.get("items", []):
                if item[0] == "re":
                    rect = pymupdf.Rect(item[1])
                    if 0 < rect.height < height_threshold and rect.width > rect.height * 2: # Check aspect ratio
                        strikethrough_line_rects.append(rect)

    # 2. Get words and their bounding boxes
    words = page.get_text("words")  # List of (x0, y0, x1, y1, word, ...)

    struck_word_bounding_boxes = set()

    # 3. Check for intersections
    for word_data in words:
        word_rect = pymupdf.Rect(word_data[:4])
        word_text = word_data[4]

        if word_rect.is_empty or not word_text.strip():
            continue

        for strike_rect in strikethrough_line_rects:
            intersect_rect = word_rect & strike_rect
            if not intersect_rect.is_empty:
                 # Check vertical alignment and horizontal overlap
                 word_v_center = word_rect.y0 + word_rect.height / 2
                 strike_v_center = strike_rect.y0 + strike_rect.height / 2
                 if (abs(word_v_center - strike_v_center) < (word_rect.height / 4)) and \
                    (intersect_rect.width > word_rect.width * 0.5 or intersect_rect.width > 5):
                     struck_word_bounding_boxes.add(word_rect)
                     break # Word is struck, no need to check other lines

    return struck_word_bounding_boxes

def pdf_page_to_markdown(page: pymupdf.Page, include_struck: bool = True) -> str:
    """
    Converts a PDF page to Markdown text, handling strikethroughs.

    Args:
        page: The pymupdf.Page object to convert.
        include_struck: If True, include struck text wrapped in '~~'.
                        If False, omit struck text.

    Returns:
        A string containing the Markdown representation of the page.
    """
    struck_rects = get_struck_word_rects(page)
    words = page.get_text("words") # (x0, y0, x1, y1, word, block_no, line_no, word_no)

    if not words:
        return ""

    # Sort words primarily by vertical position (y0), then horizontal (x0)
    # This helps approximate the reading order
    words.sort(key=lambda w: (w[1], w[0]))
    # Refine vertical alignment
    if words:
        # 1. Estimate distinct row y-coordinates by finding clusters
        unique_y0s = sorted(list(set(w[1] for w in words)))
        row_y_estimates = []
        if unique_y0s:
            current_row_group = [unique_y0s[0]]
            for y in unique_y0s[1:]:
                # Group y-coordinates that are close together (e.g., within 3 points)
                if y - current_row_group[-1] < 3:
                    current_row_group.append(y)
                else:
                    # Calculate the average y for the completed group
                    row_y_estimates.append(sum(current_row_group) / len(current_row_group))
                    current_row_group = [y]
            # Add the last group
            row_y_estimates.append(sum(current_row_group) / len(current_row_group))

        # Ensure row_y_estimates is not empty if unique_y0s was not
        if not row_y_estimates and unique_y0s:
             row_y_estimates.append(unique_y0s[0])


        # 2. Snap each word's y0 to the nearest estimated row center
        snapped_words_data = []
        for word_data in words:
            original_y0 = word_data[1]
            # Find the closest row y-coordinate estimate
            if row_y_estimates:
                closest_row_y = min(row_y_estimates, key=lambda row_y: abs(original_y0 - row_y))
                # Create a new list for the word data with the snapped y0
                # Keep original y1 for bounding box purposes if needed elsewhere,
                # but use snapped y0 for sorting and line breaking.
                snapped_data = list(word_data)
                snapped_data[1] = closest_row_y # Update y0
                snapped_words_data.append(snapped_data)
            else:
                # Should not happen if words list is not empty, but handle defensively
                 snapped_words_data.append(list(word_data))


        # 3. Resort words based on snapped y0, then original x0
        snapped_words_data.sort(key=lambda w: (w[1], w[0]))
        words = snapped_words_data # Use the list with snapped y0 values

    markdown_output = []
    current_line = ""
    last_y0 = words[0][1] # Y-coordinate of the first word
    last_x1 = words[0][0] # X-coordinate to track horizontal spacing

    # Define a threshold for detecting line breaks (adjust as needed)
    # A bit more than typical line spacing
    line_break_threshold = 10

    for i, word_data in enumerate(words):
        x0, y0, x1, y1, word_text, _, _, _ = word_data
        word_rect = pymupdf.Rect(x0, y0, x1, y1)

        # Check for line break based on vertical distance
        if y0 > last_y0 + line_break_threshold:
            markdown_output.append(current_line.strip())
            current_line = ""
            # Add extra newline for larger gaps (potential paragraph break)
            if y0 > last_y0 + line_break_threshold * 2:
                 markdown_output.append("") # Add blank line
            last_x1 = x0 # Reset horizontal position for new line

        # Add space if it's not the start of a line and there's a gap
        if current_line and x0 > last_x1 + 2: # Add space if gap > 2 points
             current_line += " "

        is_struck = word_rect in struck_rects

        if is_struck:
            if include_struck:
                current_line += f"~~{word_text}~~"
            else:
                # Omit the word - effectively adds nothing to current_line
                pass
        else:
            current_line += word_text

        last_y0 = y0
        last_x1 = x1 # Update the end position of the last added word/strikeout

        # Handle the last word/line
        if i == len(words) - 1:
            markdown_output.append(current_line.strip())


    return "\n".join(markdown_output)


def pdf_text(pdf_file):
    page_texts = list()
    doc = pymupdf.open(pdf_file) # open a document
    for index, page in enumerate(doc):
        page_text = f'START OF PAGE {index + 1}\n{pdf_page_to_markdown(page)}\nEND OF PAGE {index + 1}'
        page_texts.append(page_text)
    return "\n\n".join(page_texts)
