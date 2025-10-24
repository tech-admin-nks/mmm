import streamlit as st
import pandas as pd
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import os
import csv
import dropbox

# --------------------------------------
# Load environment variables
# --------------------------------------
#load_dotenv()

DROPBOX_APP_KEY = "q8xt5uwzuh99twt"
DROPBOX_APP_SECRET = "ohkka0khxy690fe"
DROPBOX_REFRESH_TOKEN = "xdW2XP72YyoAAAAAAAAAAfN0dkkbdqHnNwzzsz7eOl6pc9OM9Rjb2Cya7My4pmUl"

st.set_page_config(page_title="Medicine Shop Invoice", page_icon="💊", layout="centered")
st.title("💊 Medicine Shop Invoice Generator")


# -------------------------------------------------
# Dropbox Connection
# -------------------------------------------------
def ensure_dropbox_folder(dbx, folder_path):
    """
    Create a Dropbox folder if it doesn't exist.
    Silently ignores "folder already exists" errors.
    """
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError as e:
        # Check if error is "folder already exists"
        if (isinstance(e.error, dropbox.files.CreateFolderError) 
            and e.error.is_path() 
            and e.error.get_path().is_conflict()):
            pass  # Folder exists, no problem
        else:
            raise e  # Other errors, re-raise
            
def connect_to_dropbox():
    try:
        dbx = dropbox.Dropbox(
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
        )
        st.sidebar.success("✅ Connected to Dropbox")
        return dbx
    except Exception as e:
        st.sidebar.error(f"❌ Dropbox connection failed: {e}")
        return None

dbx = connect_to_dropbox()

# -------------------------------------------------
# Dropbox Helper Functions
# -------------------------------------------------
def download_json_from_dropbox(dbx, dropbox_path):
    """
    Download a JSON file from Dropbox and parse it.
    Returns a dictionary if successful, or None if file doesn't exist.
    """
    try:
        metadata, response = dbx.files_download(dropbox_path)
        return json.loads(response.content.decode("utf-8"))
    except dropbox.exceptions.ApiError:
        # File not found or other API errors
        return None

def upload_file_to_dropbox(dbx, local_path, dropbox_folder, dropbox_filename):
    """
    Upload a local file to Dropbox under the specified folder and filename.
    Automatically creates the folder if it doesn't exist.
    Returns the full Dropbox path.
    """
    ensure_dropbox_folder(dbx, dropbox_folder)
    dropbox_path = f"{dropbox_folder}/{dropbox_filename}"

    with open(local_path, "rb") as f:
        dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
    
    return dropbox_path

def upload_bytes_to_dropbox(data_bytes, dropbox_path):
    """Upload byte content directly (for PDFs)."""
    dbx.files_upload(data_bytes, dropbox_path, mode=dropbox.files.WriteMode("overwrite"))

# -------------------------------
# Static Shop Information
# -------------------------------
SHOP_NAME = "M.M. Medicine"
SHOP_ADDRESS = "Palishgram, Mongalkote, Purba Bardhaman, WB - 713147, Phone: 8918233696"
SHOP_REG = "REG-123456"
LOGO_FILE = "../data/logo2.png"  # Optional path to logo

# -------------------------------
# Customer Info Sidebar (optional)
# -------------------------------
st.sidebar.header("Customer Information (Optional)")
customer_name = st.sidebar.text_input("Customer Name")
customer_phone = st.sidebar.text_input("Customer Phone")

# -------------------------------
# Invoice Number
# -------------------------------
invoice_number = datetime.now().strftime("%Y%m%d%H%M%S%f")
st.sidebar.markdown(f"**Invoice Number:** {invoice_number}")

# -------------------------------
# Medicine List Upload (Optional Expander)
# -------------------------------

dropbox_json_path = "/mmm/data/price_list.json"

default_medicine_data = {
    "Paracetamol:Dolo 650": 12.0,
    "Cetrizine:Okacet": 8.0,
    "Azithromycin:AZI 500": 15.0,
    "Amoxicillin:Mox 500": 10.0,
    "Vitamin C:Celin 500": 6.0
}

saved_data = download_json_from_dropbox(dbx,dropbox_json_path)
if saved_data and isinstance(saved_data, dict):
    default_medicine_data.update(saved_data)
    st.success("💾 Loaded medicine data from Dropbox.")
else:
    st.warning("⚠️ No valid price list in Dropbox — using defaults.")

# Optional: Upload updated price list
with st.expander("📦 Upload Medicine Price JSON (optional)"):
    uploaded_file = st.file_uploader("Upload JSON", type="json")
    if uploaded_file:
        try:
            uploaded_data = json.load(uploaded_file)
            if isinstance(uploaded_data, dict):
                dbx.files_upload(
                    json.dumps(uploaded_data, indent=2).encode("utf-8"),
                    dropbox_json_path,
                    mode=dropbox.files.WriteMode("overwrite")
                )
                st.success("✅ Medicine price list updated to Dropbox!")
            else:
                st.error("❌ JSON must be a dictionary { 'name:brand': price }")
        except Exception as e:
            st.error(f"Error uploading JSON: {e}")

medicine_data = default_medicine_data
medicine_options = list(medicine_data.keys())

# -------------------------------
# Initialize session state safely
# -------------------------------
if "invoice_items" not in st.session_state or not isinstance(st.session_state.invoice_items, list):
    st.session_state.invoice_items = []

# -------------------------------
# Add Medicines Form
# -------------------------------
st.subheader("🧾 Add Medicines to Invoice")
with st.form("medicine_form", clear_on_submit=True):
    selected_medicine = st.selectbox("Select Medicine", medicine_options)
    qty = st.number_input("Quantity", min_value=1, step=1)
    add_button = st.form_submit_button("➕ Add Medicine")

    if add_button:
        st.session_state.invoice_items.append({
            "Medicine": selected_medicine,
            "Unit Price": medicine_data[selected_medicine],
            "Quantity": qty,
            "Total": medicine_data[selected_medicine] * qty
        })

# -------------------------------
# Add Custom Medicine Form
# -------------------------------

with st.expander("### ➕ Add Custom Medicine (Manual Entry)"):
    with st.form("custom_form", clear_on_submit=True):
        custom_name = st.text_input("Custom Medicine Name")
        custom_price = st.number_input("Price", min_value=0.0, step=0.5)
        add_custom = st.form_submit_button("Add Custom Medicine")

        if add_custom:
            if custom_name and custom_price > 0:
                st.session_state.invoice_items.append({
                    "Medicine": custom_name,
                    "Unit Price": custom_price,
                    "Quantity": 1,
                    "Total": custom_price
                })
            else:
                st.error("Please enter both name and valid price.")

# -------------------------------
# Display Invoice Items (Defensive)
# -------------------------------
df = pd.DataFrame()
subtotal = 0.0
if "invoice_items" in st.session_state and st.session_state.invoice_items:
    if isinstance(st.session_state.invoice_items, list) and all(isinstance(i, dict) for i in st.session_state.invoice_items):
        df = pd.DataFrame(st.session_state.invoice_items)
        st.dataframe(df.round(2), hide_index=True)
        subtotal = df["Total"].sum()
    else:
        st.error("Internal error: Items list corrupted.")

if df.empty:
    st.info("No items added yet.")

# -------------------------------------------------
# Invoice Logging (to Dropbox)
# -------------------------------------------------
def log_invoice_to_dropbox(items, subtotal, discount, discount_amount, final_total, invoice_number):
    """Append invoice data to Dropbox CSV."""
    csv_dropbox_path = "/mmm/invoices"
    temp_csv = "temp_invoices_log.csv"

    # Try downloading existing CSV
    try:
        metadata, response = dbx.files_download(csv_dropbox_path)
        with open(temp_csv, "wb") as f:
            f.write(response.content)
    except dropbox.exceptions.ApiError:
        open(temp_csv, "w").close()

    # Append new record
    item_list = "; ".join([f"{i['Medicine']} x {i['Quantity']}" for i in items])
    record = {
        "Invoice No": invoice_number,
        "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Items": item_list,
        "Subtotal": round(subtotal, 2),
        "Discount (%)": discount,
        "Discount Amount": round(discount_amount, 2),
        "Final Total": round(final_total, 2)
    }

    file_exists = os.path.getsize(temp_csv) > 0
    with open(temp_csv, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=record.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

    # Upload back to Dropbox
    upload_file_to_dropbox(dbx,temp_csv, csv_dropbox_path,"invoices_log.csv")
    os.remove(temp_csv)
    
# -------------------------------
# PDF Generation Function
# -------------------------------
def generate_invoice_pdf(items_df, subtotal, discount, discount_amount, final_total, invoice_number,
                         customer_name="", customer_phone=""):
    from io import BytesIO
    pdf_buffer = BytesIO()
    pdf = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Logo
    if LOGO_FILE:
        elements.append(Image(LOGO_FILE, width=80, height=60))
        elements.append(Spacer(1, 8))
        
    elements.append(Paragraph(f"<b>{SHOP_NAME}</b>", styles["Title"]))
    elements.append(Paragraph(SHOP_ADDRESS, styles["Normal"]))
    elements.append(Paragraph(f"Registration No: {SHOP_REG}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    if customer_name:
        elements.append(Paragraph(f"Customer Name: {customer_name}", styles["Normal"]))
    if customer_phone:
        elements.append(Paragraph(f"Customer Phone: {customer_phone}", styles["Normal"]))

    elements.append(Paragraph(f"Invoice No: {invoice_number}", styles["Normal"]))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    data = [["Medicine", "Unit Price", "Quantity", "Total"]] + items_df.values.tolist()
    table = Table(data, colWidths=[200, 80, 80, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))

    summary = [
        ["Subtotal", f"{subtotal:.2f} INR"],
        [f"Discount ({discount}%)", f"-{discount_amount:.2f} INR"],
        ["Final Total", f"{final_total:.2f} INR"]
    ]
    sum_table = Table(summary, colWidths=[340, 100])
    sum_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("FONTNAME", (-1,-1), (-1,-1), "Helvetica-Bold")
    ]))
    elements.append(sum_table)
    pdf.build(elements)
    pdf_data = pdf_buffer.getvalue()

    # Upload to Dropbox
    folder_path = f"/mmm/invoices/{datetime.now():%Y/%m/%d}"
    ensure_dropbox_folder(dbx, folder_path)
    dropbox_file_path = f"{folder_path}/Invoice_{invoice_number}.pdf"
    upload_bytes_to_dropbox(pdf_data, dropbox_file_path)

    return pdf_data

    
# -------------------------------------------------
# Final Calculation & Buttons
# -------------------------------------------------
discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5)
discount_amount = subtotal * discount / 100

if st.button("💰 Generate Bill"):
    final_total = subtotal - discount_amount
    if final_total > 0 and not df.empty:
        log_invoice_to_dropbox(st.session_state.invoice_items, subtotal, discount, discount_amount, final_total, invoice_number)
        pdf_data = generate_invoice_pdf(df, subtotal, discount, discount_amount, final_total, invoice_number, customer_name, customer_phone)
        st.download_button("⬇️ Download Invoice PDF", pdf_data, file_name=f"Invoice_{invoice_number}.pdf")
        st.success("✅ Invoice saved to Dropbox and ready for download.")
    else:
        st.error("Please add items before generating an invoice.")

