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

st.set_page_config(page_title="Medicine Shop Invoice", page_icon="💊", layout="centered")
st.title("💊 Medicine Shop Invoice Generator")

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
json_path = "../data/price_list.json"

default_medicine_data = {
    "Paracetamol:Dolo 650": 12.0,
    "Cetrizine:Okacet": 8.0,
    "Azithromycin:AZI 500": 15.0,
    "Amoxicillin:Mox 500": 10.0,
    "Vitamin C:Celin 500": 6.0
}

# Load existing JSON if present
if os.path.exists(json_path):
    with open(json_path, "r") as f:
        try:
            saved_data = json.load(f)
            default_medicine_data.update(saved_data)
        except:
            st.warning("Saved JSON is invalid, using defaults.")

with st.expander("📦 Upload Medicine Price JSON (optional)"):
    uploaded_file = st.file_uploader("Upload JSON", type="json")
    if uploaded_file:
        try:
            uploaded_data = json.load(uploaded_file)
            if isinstance(uploaded_data, dict):
                default_medicine_data.update(uploaded_data)
                with open(json_path, "w") as f:
                    json.dump(default_medicine_data, f, indent=2)
                st.success("✅ Medicine price list updated successfully!")
            else:
                st.error("JSON must be a dictionary like { 'name:brand': price }")
        except Exception as e:
            st.error(f"Failed to load JSON: {e}")

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
# -------------------------------
# LOG Generation Function
# -------------------------------

def log_invoice_to_csv(items, subtotal, discount, discount_amount, final_total,invoice_number):
    
    csv_file = "../invoice/invoices_log.csv"
    invoice_no = invoice_number #f"INV{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item_list = "; ".join([f"{i['Medicine']} x {i['Quantity']}" for i in items])

    record = {
        "Invoice No": invoice_no,
        "DateTime": date_time,
        "Items": item_list,
        "Subtotal": round(subtotal, 2),
        "Discount (%)": discount,
        "Discount Amount": round(discount_amount, 2),
        "Final Total": round(final_total, 2)
    }

    file_exists = os.path.exists(csv_file)
    with open(csv_file, mode="a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=record.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)
# -------------------------------
# PDF Generation Function
# -------------------------------
def generate_invoice_pdf(items_df, subtotal, discount, discount_amount, final_total, invoice_number,
                         customer_name="", customer_phone=""):
                             
    now = datetime.now()
    folder_path = os.path.join("..", "invoice", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    os.makedirs(folder_path, exist_ok=True)  # Automatically create folders if missing

    # Build filename inside that folder
    filename = os.path.join(folder_path, f"Invoice_{invoice_number}.pdf")
    
    #filename = f"../invoice/Invoice_{invoice_number}.pdf"
    pdf = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Logo
    if LOGO_FILE:
        elements.append(Image(LOGO_FILE, width=80, height=60))
        elements.append(Spacer(1, 8))

    # Shop Details
    elements.append(Paragraph(f"<b>{SHOP_NAME}</b>", styles["Title"]))
    elements.append(Paragraph(SHOP_ADDRESS, styles["Normal"]))
    elements.append(Paragraph(f"Registration No: {SHOP_REG}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Customer Details (optional)
    if customer_name:
        elements.append(Paragraph(f"Customer Name: {customer_name}", styles["Normal"]))
    if customer_phone:
        elements.append(Paragraph(f"Customer Phone: {customer_phone}", styles["Normal"]))

    # Invoice Number & Date
    elements.append(Paragraph(f"Invoice Number: {invoice_number}", styles["Normal"]))
    elements.append(Paragraph(f"Invoice Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    # Items Table
    if not items_df.empty:
        data = [["Medicine", "Unit Price", "Quantity", "Total"]] + items_df.values.tolist()
        table = Table(data, colWidths=[200, 80, 80, 80])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
            ("TEXTCOLOR", (0,0), (-1,0), colors.black),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

    # Totals Table
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
    return filename
    
# -------------------------------
# Discount and Final Total
# -------------------------------
discount = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, value=18.0,step=0.5)
discount_amount = subtotal * discount / 100

if st.button("💰 Generate Bill"):
    final_total = subtotal - discount_amount

    if (final_total>0): 
        log_invoice_to_csv(st.session_state.invoice_items, subtotal, discount, discount_amount, final_total,invoice_number)

    st.write(f"**Subtotal:** ₹{subtotal:.2f}")
    st.write(f"**Discount ({discount}%):** ₹{discount_amount:.2f}")
    st.write(f"### 💰 Final Amount: ₹{final_total:.2f}")
        
    if not df.empty:
        pdf_file = generate_invoice_pdf(df, subtotal, discount, discount_amount, final_total,
                                        invoice_number, customer_name, customer_phone)
        with open(pdf_file, "rb") as f:
            st.download_button("⬇️ Download Invoice PDF", f, file_name=pdf_file)
    else:
        st.error("Add at least one item before generating the invoice.")

