import re
from pathlib import Path

import requests
import streamlit as st

API_URL = "https://document-automation-app-production.up.railway.app"

st.set_page_config(page_title="Document Automation", page_icon="📄", layout="centered")

st.sidebar.title("📄 Document Automation")
screen = st.sidebar.radio(
    "Navigate",
    ["Upload Template", "Fill & Download Form"],
)


def is_header(entry: str) -> bool:
    return entry.startswith("#")


def is_note(entry: str) -> bool:
    return entry.startswith("~")


def is_field(entry: str) -> bool:
    return not is_header(entry) and not is_note(entry)


def default_label(entry: str) -> str:
    return entry.replace("_", " ").title()


def display_label(entry: str) -> str:
    if is_header(entry):
        return f"🏷️ {entry[1:]}"
    if is_note(entry):
        return f"📝 {entry[1:]}"
    return default_label(entry)


def cell_ref_to_row_col(ref: str) -> tuple[int, int] | tuple[None, None]:
    """Convert Excel cell reference like 'B5' to (row=5, col=2)."""
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", ref.strip())
    if not m:
        return None, None
    col_str, row_str = m.groups()
    col = 0
    for ch in col_str.upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(row_str), col


# ─── Screen 1: Business uploads and configures a template ─────────────────────
if screen == "Upload Template":
    st.title("Upload a Template")

    st.info(
        "📋 **Supported formats: .docx, .pdf, .jpg, .jpeg, .png, .xlsx, .xls**\n\n"
        "- **Word (.docx)** → Add `{{placeholder}}` tags where fields should go\n"
        "- **PDF, image or Excel** → Upload directly — fields are detected automatically\n"
        "- **Starting fresh?** Create your form in Google Docs, add `{{placeholder}}` tags, then download as .docx"
    )

    with st.form("upload_form"):
        client_id = st.text_input("Business ID", placeholder="e.g. law_firm_001")
        uploaded_file = st.file_uploader(
            "Choose a template file",
            type=["docx", "pdf", "jpg", "jpeg", "png", "xlsx", "xls"],
        )
        submitted = st.form_submit_button("Upload Template")

    if submitted:
        if not client_id:
            st.error("Please enter a Business ID.")
        elif uploaded_file is None:
            st.error("Please select a file.")
        else:
            with st.spinner("Uploading and extracting fields..."):
                response = requests.post(
                    f"{API_URL}/templates",
                    data={"client_id": client_id, "variables": "{}"},
                    files={"file": (uploaded_file.name, uploaded_file, uploaded_file.type)},
                )
            if response.status_code == 201:
                data = response.json()
                st.success(f"Template uploaded! (ID: {data['id']}) — {len([e for e in data['field_order'] if is_field(e)])} fields detected.")
                st.session_state["uploaded_template"] = data
                st.session_state["field_order"] = data["field_order"]
            else:
                try:
                    detail = response.json().get("detail", "Unknown error")
                except Exception:
                    detail = f"Server error (status {response.status_code})."
                st.error(f"Upload failed: {detail}")

    # ── Config UI shown after upload ──────────────────────────────────────────
    if "uploaded_template" in st.session_state:
        data = st.session_state["uploaded_template"]
        field_order = st.session_state["field_order"]
        tid = data["id"]
        file_type = data.get("file_type", "docx")

        st.divider()
        tab_order, tab_config, tab_add = st.tabs(["Arrange Order", "Rename & Visibility", "Add Fields"])

        # ── Tab 1: Arrange order ──────────────────────────────────────────────
        with tab_order:
            st.write("Move fields with arrows. Add section headers or notes.")
            for i, entry in enumerate(field_order):
                col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
                col1.write(f"**{i + 1}.** {display_label(entry)}")
                if col2.button("↑", key=f"up_{i}", disabled=i == 0):
                    field_order[i], field_order[i - 1] = field_order[i - 1], field_order[i]
                    st.session_state["field_order"] = field_order
                    st.rerun()
                if col3.button("↓", key=f"down_{i}", disabled=i == len(field_order) - 1):
                    field_order[i], field_order[i + 1] = field_order[i + 1], field_order[i]
                    st.session_state["field_order"] = field_order
                    st.rerun()
                if col4.button("✕", key=f"del_{i}", disabled=is_field(entry)):
                    field_order.pop(i)
                    st.session_state["field_order"] = field_order
                    st.rerun()

            st.divider()
            col_a, col_b = st.columns(2)
            with col_a:
                with st.form("add_header_form"):
                    header_text = st.text_input("Section header", placeholder="e.g. Address Details")
                    if st.form_submit_button("+ Add Section Header") and header_text.strip():
                        field_order.append(f"#{header_text.strip()}")
                        st.session_state["field_order"] = field_order
                        st.rerun()
            with col_b:
                with st.form("add_note_form"):
                    note_text = st.text_area("Note or instruction", placeholder="e.g. Please attach a copy of your ID", height=80)
                    if st.form_submit_button("+ Add Note") and note_text.strip():
                        field_order.append(f"~{note_text.strip()}")
                        st.session_state["field_order"] = field_order
                        st.rerun()

        # ── Tab 2: Rename & hide ──────────────────────────────────────────────
        with tab_config:
            st.write("Set a display label customers see, and hide fields you don't want shown.")
            st.caption("Hidden fields stay in the template — they just won't appear in the customer form.")

            fields_only = [e for e in field_order if is_field(e)]
            if not fields_only:
                st.info("No fields detected in this template.")
            else:
                col_h1, col_h2, col_h3 = st.columns([3, 4, 1])
                col_h1.markdown("**Field (internal name)**")
                col_h2.markdown("**Display label for customers**")
                col_h3.markdown("**Hide**")

                for entry in fields_only:
                    col1, col2, col3 = st.columns([3, 4, 1])
                    col1.write(default_label(entry))
                    col2.text_input(
                        "label",
                        key=f"lbl_{tid}_{entry}",
                        placeholder=default_label(entry),
                        label_visibility="collapsed",
                    )
                    col3.checkbox(
                        "hide",
                        key=f"hid_{tid}_{entry}",
                        label_visibility="collapsed",
                    )

        # ── Tab 3: Add fields ─────────────────────────────────────────────────
        with tab_add:
            st.write("Add a field that doesn't exist in the template yet.")
            if file_type == "excel":
                st.caption("For Excel: specify a cell reference (e.g. B5) so the value is written to that cell.")
            elif file_type == "docx":
                st.caption("For Word: the field name must match a `{{placeholder}}` already in the document.")
            else:
                st.caption("For image/PDF templates: the value will be collected but not overlaid automatically (use a docx template for full control).")

            with st.form("add_field_form"):
                new_name = st.text_input("Field name (internal)", placeholder="e.g. purchase_order_number")
                new_label = st.text_input("Display label", placeholder="e.g. Purchase Order #")
                new_cell = ""
                if file_type == "excel":
                    new_cell = st.text_input("Cell reference (optional)", placeholder="e.g. B5")
                add_submitted = st.form_submit_button("Add Field")

            if add_submitted:
                raw = new_name.strip().lower()
                raw = re.sub(r"[^a-z0-9\s]", "", raw)
                raw = re.sub(r"\s+", "_", raw).strip("_")[:50]
                if not raw:
                    st.error("Please enter a valid field name.")
                elif raw in field_order:
                    st.warning(f"Field '{raw}' already exists.")
                else:
                    field_order.append(raw)
                    st.session_state["field_order"] = field_order
                    if new_label.strip():
                        st.session_state[f"lbl_{tid}_{raw}"] = new_label.strip()
                    if new_cell.strip() and file_type == "excel":
                        row, col = cell_ref_to_row_col(new_cell.strip())
                        if row:
                            st.session_state[f"pos_{tid}_{raw}"] = {"name": raw, "row": row, "col": col, "sheet": 0, "placeholder": False}
                        else:
                            st.warning("Cell reference not recognised — field added without a position.")
                    st.success(f"Field '{raw}' added. Click 'Save Configuration' below to save.")
                    st.rerun()

        # ── Save all configuration ────────────────────────────────────────────
        st.divider()
        if st.button("Save Configuration", type="primary"):
            fields_only = [e for e in field_order if is_field(e)]

            field_labels = {}
            hidden_fields = []
            for entry in fields_only:
                lbl = st.session_state.get(f"lbl_{tid}_{entry}", "").strip()
                if lbl:
                    field_labels[entry] = lbl
                if st.session_state.get(f"hid_{tid}_{entry}", False):
                    hidden_fields.append(entry)

            extra_positions = [
                st.session_state[f"pos_{tid}_{entry}"]
                for entry in fields_only
                if f"pos_{tid}_{entry}" in st.session_state
            ]

            payload = {
                "field_order": field_order,
                "field_labels": field_labels,
                "hidden_fields": hidden_fields,
                "extra_positions": extra_positions or None,
            }
            response = requests.put(f"{API_URL}/templates/{tid}/config", json=payload)
            if response.status_code == 200:
                n_hidden = len(hidden_fields)
                n_renamed = len(field_labels)
                st.success(
                    f"Configuration saved! "
                    f"{n_renamed} field(s) renamed, {n_hidden} hidden."
                )
                for key in list(st.session_state.keys()):
                    if key not in ("uploaded_template",):
                        del st.session_state[key]
                st.session_state.pop("uploaded_template", None)
            else:
                st.error("Failed to save. Please try again.")


# ─── Screen 2: Customer fills in the form and downloads ───────────────────────
elif screen == "Fill & Download Form":
    st.title("Fill in a Form")
    st.write("Select a template, fill in the fields, and download your completed document.")

    with st.spinner("Loading templates..."):
        response = requests.get(f"{API_URL}/templates")

    if response.status_code != 200:
        st.error("Could not load templates. Is the server running?")
        st.stop()

    templates = response.json()
    if not templates:
        st.info("No templates uploaded yet. Go to **Upload Template** first.")
        st.stop()

    template_options = {
        f"{t['file_name']} (ID: {t['id']}) — {t['client_id']}": t for t in templates
    }
    selected_label = st.selectbox("Choose a template", list(template_options.keys()))
    selected = template_options[selected_label]

    field_order = selected.get("field_order") or list(selected["variables"].keys())
    field_labels = selected.get("field_labels") or {}
    hidden_fields = set(selected.get("hidden_fields") or [])

    visible_fields = [e for e in field_order if not (is_field(e) and e in hidden_fields)]

    if not visible_fields:
        st.warning("This template has no visible fields.")
        st.stop()

    file_type = selected.get("file_type", "docx")
    is_excel = file_type == "excel"
    is_docx = file_type == "docx"
    output_format = "pdf"

    if is_docx:
        fmt_choice = st.radio(
            "Download format",
            ["PDF", "Word (.docx)"],
            horizontal=True,
        )
        output_format = "docx" if fmt_choice == "Word (.docx)" else "pdf"
    elif is_excel:
        fmt_choice = st.radio(
            "Download format",
            ["PDF", "Excel (.xlsx)"],
            horizontal=True,
        )
        output_format = "excel" if fmt_choice == "Excel (.xlsx)" else "pdf"

    # Auto-fill button for quick testing
    visible_field_keys = [e for e in visible_fields if is_field(e)]
    if st.button("Auto-fill with test data", help="Fills all fields with sample values for quick testing"):
        for entry in visible_field_keys:
            lbl = field_labels.get(entry, default_label(entry))
            st.session_state[f"val_{selected['id']}_{entry}"] = f"[{lbl}]"
        st.rerun()

    st.write("**Fill in the fields below:**")
    values = {}
    with st.form("fill_form"):
        for entry in visible_fields:
            if is_header(entry):
                st.markdown(f"### {entry[1:]}")
            elif is_note(entry):
                st.caption(f"ℹ️ {entry[1:]}")
            else:
                # Use the business-set label, fall back to auto-generated one
                label = field_labels.get(entry, default_label(entry))
                key = f"val_{selected['id']}_{entry}"
                default = st.session_state.get(key, "")
                values[entry] = st.text_input(label, value=default, placeholder=f"Enter {label.lower()}")
        generate = st.form_submit_button("Generate Document")

    if generate:
        with st.spinner("Generating your document..."):
            response = requests.post(
                f"{API_URL}/templates/{selected['id']}/generate?output_format={output_format}",
                json=values,
            )

        if response.status_code == 200:
            stem = Path(selected["file_name"]).stem
            if is_docx and output_format == "docx":
                output_name = f"{stem}_filled.docx"
                dl_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                dl_label = "⬇️ Download Filled Word Doc"
            elif is_excel and output_format == "excel":
                output_name = f"{stem}_filled.xlsx"
                dl_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                dl_label = "⬇️ Download Filled Excel"
            else:
                output_name = f"{stem}_filled.pdf"
                dl_mime = "application/pdf"
                dl_label = "⬇️ Download Filled PDF"
            st.success("Document generated!")
            st.download_button(
                label=dl_label,
                data=response.content,
                file_name=output_name,
                mime=dl_mime,
            )
        else:
            try:
                detail = response.json().get("detail", "Unknown error")
            except Exception:
                detail = f"Server error (status {response.status_code})."
            st.error(f"Generation failed: {detail}")
