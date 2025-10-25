import streamlit as st
import pandas as pd
import json
from datetime import datetime
import os
import dropbox
from dotenv import load_dotenv

# --------------------------------------
# Load environment variables
# --------------------------------------
load_dotenv()

DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", st.secrets.get("DROPBOX_APP_KEY", ""))
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", st.secrets.get("DROPBOX_APP_SECRET", ""))
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", st.secrets.get("DROPBOX_REFRESH_TOKEN", ""))

# -------------------------------
# Connect to Dropbox
# -------------------------------
def connect_to_dropbox():
    dbx = dropbox.Dropbox(
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
    )
    st.sidebar.success("✅ Connected to Dropbox")
    return dbx

dbx = connect_to_dropbox()

# -------------------------------
# Dropbox helper functions
# -------------------------------
def ensure_dropbox_folder(dbx, folder_path):
    """Create folder in Dropbox if not exists"""
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError as e:
        if (isinstance(e.error, dropbox.files.CreateFolderError)
            and e.error.is_path() and e.error.get_path().is_conflict()):
            pass
        else:
            raise e

# def download_csv_from_dropbox(dbx, dropbox_file_path):
#     """Download CSV from Dropbox and return as DataFrame"""
#     try:
#         metadata, res = dbx.files_download(dropbox_file_path)
#         df = pd.read_csv(res.content)
#         st.sidebar.success(f"📦 Loaded CSV from Dropbox: {dropbox_file_path}")
#     except Exception:
#         df = pd.DataFrame(columns=["med_name", "unit_price", "quantity"])
#         st.sidebar.warning("⚠️ No CSV found in Dropbox. Created empty dataset.")
#     return df

def download_csv_from_dropbox(dbx, dropbox_file_path):
    """Download CSV from Dropbox and return as DataFrame"""
    try:
        metadata, res = dbx.files_download(dropbox_file_path)
        df = pd.read_csv(res.content)
        st.sidebar.success(f"📦 Loaded CSV from Dropbox: {dropbox_file_path}")
    except Exception:
        st.sidebar.warning("⚠️ No CSV found. Creating a blank one...")
        df = pd.DataFrame(columns=["med_name", "unit_price", "quantity"])
        # Save blank CSV immediately
        temp_csv = "temp_blank.csv"
        df.to_csv(temp_csv, index=False)
        folder = os.path.dirname(dropbox_file_path)
        if folder == "":
            folder = "/"
        ensure_dropbox_folder(dbx, folder)
        dbx.files_upload(open(temp_csv, "rb").read(), dropbox_file_path, mode=dropbox.files.WriteMode("overwrite"))
        os.remove(temp_csv)
        st.sidebar.info("✅ Blank CSV created in Dropbox.")
    return df

def upload_file_to_dropbox(dbx, local_file, dropbox_folder, dropbox_filename):
    """Upload a file to Dropbox"""
    ensure_dropbox_folder(dbx, dropbox_folder)
    dropbox_path = f"{dropbox_folder}/{dropbox_filename}"
    with open(local_file, "rb") as f:
        dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
    return dropbox_path

# -------------------------------
# File paths
# -------------------------------
dropbox_folder = "/mmm/sales"
dropbox_csv_file = f"{dropbox_folder}/main_sales.csv"
dropbox_json_file = f"/mmm/data/price_list.json"

# -------------------------------
# Load main CSV
# -------------------------------
st.title("💊 Daily Medicine Sales Tracker")

df = download_csv_from_dropbox(dbx, dropbox_csv_file)

if df.empty:
    st.error("No medicine data found in Dropbox. Please upload main_sales.csv first.")
    st.stop()

st.subheader("📊 Current Stock / Price Data")
st.dataframe(df, hide_index=True)

# -------------------------------
# Update Sales Quantity Only
# -------------------------------
st.subheader("🧾 Update Daily Sales")

with st.form("sales_form", clear_on_submit=True):
    med_name = st.selectbox("Select Medicine", options=df["med_name"].tolist())
    selected_price = df.loc[df["med_name"] == med_name, "unit_price"].values[0]
    st.markdown(f"**💰 Unit Price:** ₹{selected_price:.2f}")

    sold_qty = st.number_input("Quantity Sold Today", min_value=1, step=1)
    submit = st.form_submit_button("💾 Update Sales")

    if submit:
        # Add sold quantity to main CSV
        df.loc[df["med_name"] == med_name, "quantity"] += sold_qty
        st.success(f"✅ Updated {med_name} — added {sold_qty} units sold.")

# -------------------------------
# Save Updated CSV + JSON to Dropbox
# -------------------------------
if st.button("⬆️ Save Updates to Dropbox"):
    temp_csv = "temp_sales.csv"
    temp_json = "temp_price.json"

    # Save updated CSV
    df.to_csv(temp_csv, index=False)
    upload_file_to_dropbox(dbx, temp_csv, dropbox_folder, "main_sales.csv")

    # Save JSON {name: unit_price}
    json_dict = df.set_index("med_name")["unit_price"].to_dict()
    with open(temp_json, "w") as f:
        json.dump(json_dict, f, indent=2)
    upload_file_to_dropbox(dbx, temp_json, dropbox_folder, "price_list.json")

    os.remove(temp_csv)
    os.remove(temp_json)

    st.success("✅ Sales data and price list updated on Dropbox.")
