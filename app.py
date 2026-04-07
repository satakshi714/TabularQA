import streamlit as st
import pandas as pd
import plotly.express as px
import re
from difflib import get_close_matches
import google.generativeai as genai

st.set_page_config(page_title="AI Sales Dashboard", layout="wide")

st.title("📊 AI-Powered Sales Dashboard & QA System")

# -------------------------
# LOAD FILE
# -------------------------
uploaded_file = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])

if uploaded_file:

    # Read file
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Clean columns
    df.columns = [c.strip() for c in df.columns]

    # Convert numeric
    num_cols = ["Unit price", "Quantity", "Total", "gross income", "Rating"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert date
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    df.dropna(how="all", inplace=True)

    # -------------------------
    # DASHBOARD SECTION
    # -------------------------
    st.header("📊 Dashboard")

    col1, col2, col3 = st.columns(3)

    if "Total" in df.columns:
        col1.metric("Total Sales", f"{df['Total'].sum():,.2f}")

    if "Quantity" in df.columns:
        col2.metric("Total Orders", int(df["Quantity"].count()))

    if "gross income" in df.columns:
        col3.metric("Total Profit", f"{df['gross income'].sum():,.2f}")

    # Charts
    if "Product line" in df.columns:
        st.subheader("Top Products")
        prod = df.groupby("Product line")["Total"].sum().reset_index()
        fig = px.bar(prod, x="Product line", y="Total", color="Product line")
        st.plotly_chart(fig, use_container_width=True)

    if "City" in df.columns:
        st.subheader("Sales by City")
        city = df.groupby("City")["Total"].sum().reset_index()
        fig = px.pie(city, names="City", values="Total")
        st.plotly_chart(fig, use_container_width=True)

    if "Date" in df.columns:
        st.subheader("Sales Trend")
        trend = df.groupby("Date")["Total"].sum().reset_index()
        fig = px.line(trend, x="Date", y="Total")
        st.plotly_chart(fig, use_container_width=True)

    # -------------------------
    # QA SYSTEM
    # -------------------------
    st.header("🤖 Ask Questions")

    def best_match(query, values):
        values = [str(v) for v in values if pd.notna(v)]
        lower_map = {v.lower(): v for v in values}

        for k, v in lower_map.items():
            if k in query:
                return v

        matches = get_close_matches(query, list(lower_map.keys()), n=1, cutoff=0.6)
        if matches:
            return lower_map[matches[0]]
        return None

    def extract_number(query):
        nums = re.findall(r"\d+\.?\d*", query)
        return float(nums[0]) if nums else None

    def apply_filters(df, q):
        filtered = df.copy()

        text_cols = ["City", "Gender", "Product line", "Payment"]

        for col in text_cols:
            if col in filtered.columns:
                match = best_match(q, filtered[col].unique())
                if match:
                    filtered = filtered[filtered[col] == match]

        num = extract_number(q)

        if num is not None:
            if "quantity" in q and "Quantity" in df.columns:
                filtered = filtered[filtered["Quantity"] == int(num)]
            elif "price" in q:
                filtered = filtered[filtered["Unit price"].round(2) == round(num, 2)]
            elif "total" in q or "cost" in q:
                filtered = filtered[filtered["Total"].round(2) == round(num, 2)]

        return filtered

    def detect_intent(q):
        if "how many" in q: return "count"
        if "average" in q: return "avg"
        if "highest" in q: return "max"
        if "lowest" in q: return "min"
        if "recent" in q: return "latest"
        if "show" in q: return "show"
        if "total" in q: return "sum"
        return "unknown"

    def rule_based(df, query):
        q = query.lower()
        intent = detect_intent(q)
        filtered = apply_filters(df, q)

        if filtered.empty:
            return "No matching data found."

        if intent == "latest":
            latest = filtered.sort_values("Date", ascending=False).iloc[0]
            return f"Latest cost = {latest['Total']:.2f}"

        if intent == "count":
            return f"Count = {len(filtered)}"

        if intent == "sum":
            return f"Total = {filtered['Total'].sum():.2f}"

        if intent == "avg":
            return f"Average = {filtered['Total'].mean():.2f}"

        if intent == "max":
            return f"Max = {filtered['Total'].max():.2f}"

        if intent == "min":
            return f"Min = {filtered['Total'].min():.2f}"

        if intent == "show":
            return filtered.head(10)

        return "Could not understand."

    # -------------------------
    # AI FALLBACK
    # -------------------------
    def ai_answer(df, query):
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            model = genai.GenerativeModel("gemini-pro")

            sample = df.head(20).to_string()

            prompt = f"""
            Dataset:
            {sample}

            Question:
            {query}

            Answer clearly.
            """

            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"AI Error: {e}"

    # -------------------------
    # INPUT
    # -------------------------
    query = st.text_input("Ask anything about your data:")

    if query:
        st.write("Processing...")

        result = rule_based(df, query)

        if isinstance(result, str) and "could not" in result.lower():
            st.warning("Using AI...")
            result = ai_answer(df, query)

        if isinstance(result, pd.DataFrame):
            st.dataframe(result)
        else:
            st.success(result)