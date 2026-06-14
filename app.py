import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights

st.set_page_config(
    page_title="Samsung Egypt — Live Ads Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0a0a0f; }
    .block-container { padding-top: 1rem; }
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; font-weight: 500; }
    div[data-testid="metric-container"] {
        background: #18181f;
        border: 1px solid #252530;
        border-radius: 12px;
        padding: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")

    access_token = st.text_input(
        "Meta Access Token",
        type="password",
        help="Paste your EAA... token from Meta Graph API Explorer"
    )

    st.markdown("**Ad Account IDs**")
    acc_mx   = st.text_input("MX — Mobile",    placeholder="act_XXXXXXXXXX")
    acc_vd   = st.text_input("VD — TVs",        placeholder="act_XXXXXXXXXX")
    acc_da   = st.text_input("DA — Appliances", placeholder="act_XXXXXXXXXX")
    acc_corp = st.text_input("Corp — Corporate",placeholder="act_XXXXXXXXXX")

    st.markdown("---")
    date_preset = st.selectbox(
        "Date range",
        ["last_7d", "last_14d", "last_30d", "last_90d", "last_year", "this_year"],
        index=2
    )

    fetch_btn = st.button("🔄 Fetch live data", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("""
    **How to get your token:**
    1. Go to developers.facebook.com
    2. Tools → Graph API Explorer
    3. Add `ads_read` permission
    4. Click Generate Access Token
    5. Paste it above
    """)

# ── HELPERS ──────────────────────────────────────────────
def fmt_num(n):
    if n is None or (isinstance(n, float) and n != n): return "—"
    if n >= 1e9: return f"{n/1e9:.1f}B"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.0f}K"
    return f"{n:.0f}"

def get_purchases(actions):
    if not isinstance(actions, list): return 0
    for a in actions:
        if a.get("action_type") == "offsite_conversion.fb_pixel_purchase":
            return float(a.get("value", 0))
    return 0

def get_conv_value(action_values):
    if not isinstance(action_values, list): return 0
    for a in action_values:
        if a.get("action_type") == "offsite_conversion.fb_pixel_purchase":
            return float(a.get("value", 0))
    return 0

def pull_account(account_id, division, token, date_preset):
    FacebookAdsApi.init(access_token=token)
    account = AdAccount(account_id)
    fields = [
        AdsInsights.Field.campaign_name,
        AdsInsights.Field.objective,
        AdsInsights.Field.spend,
        AdsInsights.Field.impressions,
        AdsInsights.Field.reach,
        AdsInsights.Field.frequency,
        AdsInsights.Field.cpm,
        AdsInsights.Field.cpc,
        AdsInsights.Field.ctr,
        AdsInsights.Field.clicks,
        AdsInsights.Field.actions,
        AdsInsights.Field.action_values,
        AdsInsights.Field.date_start,
        AdsInsights.Field.date_stop,
    ]
    params = {
        "level": "campaign",
        "date_preset": date_preset,
    }
    insights = account.get_insights(fields=fields, params=params)
    rows = []
    for row in insights:
        d = dict(row)
        d["division"] = division
        d["purchases"] = get_purchases(d.get("actions"))
        d["conv_value"] = get_conv_value(d.get("action_values"))
        for col in ["spend","impressions","reach","frequency","cpm","cpc","ctr","clicks"]:
            d[col] = float(d.get(col, 0) or 0)
        rows.append(d)
    return rows

# ── FETCH DATA ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all(token, mx, vd, da, corp, preset):
    accounts = {"MX": mx, "VD": vd, "DA": da, "Corp": corp}
    all_rows = []
    errors = []
    for div, acc_id in accounts.items():
        if not acc_id or not acc_id.startswith("act_"):
            continue
        try:
            rows = pull_account(acc_id, div, token, preset)
            all_rows.extend(rows)
        except Exception as e:
            errors.append(f"{div}: {str(e)[:80]}")
    return all_rows, errors

# ── MAIN ─────────────────────────────────────────────────
st.markdown("## 📊 Samsung Egypt — Live Ads Dashboard")
st.markdown("Starcom · All divisions · Meta Ads Manager")

if not access_token:
    st.info("👈 Enter your Meta Access Token and Ad Account IDs in the sidebar, then click **Fetch live data**.")
    st.markdown("""
    ### What this dashboard shows
    - **Real-time** campaign performance across all 4 Samsung divisions
    - **MX** (Mobile), **VD** (TVs), **DA** (Appliances), **Corp** (Corporate)
    - Spend, impressions, reach, CPM, CTR, purchases and ROAS
    - Filterable by division, objective, and date range
    """)
    st.stop()

if fetch_btn or "df" not in st.session_state:
    if fetch_btn:
        st.cache_data.clear()
    with st.spinner("Fetching live data from Meta Ads Manager..."):
        rows, errors = fetch_all(
            access_token,
            acc_mx, acc_vd, acc_da, acc_corp,
            date_preset
        )
    if errors:
        for e in errors:
            st.warning(f"⚠️ {e}")
    if not rows:
        st.error("No data returned. Check your token and account IDs.")
        st.stop()
    df = pd.DataFrame(rows)
    st.session_state["df"] = df
    st.session_state["fetched_at"] = pd.Timestamp.now().strftime("%d %b %Y %H:%M")
else:
    df = st.session_state["df"]

fetched_at = st.session_state.get("fetched_at", "—")
st.caption(f"Last updated: {fetched_at} · {len(df)} campaign records")

# ── FILTERS ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    all_divs = ["All"] + sorted(df["division"].dropna().unique().tolist())
    sel_div = st.selectbox("Division", all_divs)
with col2:
    all_objs = ["All"] + sorted(df["objective"].dropna().unique().tolist())
    sel_obj = st.selectbox("Objective", all_objs)
with col3:
    search = st.text_input("Search campaign", placeholder="Type to filter...")

fdf = df.copy()
if sel_div != "All":
    fdf = fdf[fdf["division"] == sel_div]
if sel_obj != "All":
    fdf = fdf[fdf["objective"] == sel_obj]
if search:
    fdf = fdf[fdf["campaign_name"].str.contains(search, case=False, na=False)]

# ── DIVISION TABS ────────────────────────────────────────
st.markdown("---")
tabs = st.tabs(["🌐 All divisions", "📱 MX — Mobile", "📺 VD — TVs", "🏠 DA — Appliances", "🏢 Corp — Corporate"])

div_map = {0: "All", 1: "MX", 2: "VD", 3: "DA", 4: "Corp"}

for i, tab in enumerate(tabs):
    with tab:
        if div_map[i] == "All":
            tdf = fdf.copy()
        else:
            tdf = fdf[fdf["division"] == div_map[i]]

        if tdf.empty:
            st.info(f"No data for {div_map[i]}. Make sure this account ID is entered in the sidebar.")
            continue

        # KPIs
        total_spend = tdf["spend"].sum()
        total_impr  = tdf["impressions"].sum()
        total_reach = tdf["reach"].sum()
        total_purch = tdf["purchases"].sum()
        total_cv    = tdf["conv_value"].sum()
        avg_cpm     = tdf[tdf["cpm"]>0]["cpm"].mean()
        avg_ctr     = tdf[tdf["ctr"]>0]["ctr"].mean()
        roas_rows   = tdf[(tdf["purchases"]>0) & (tdf["spend"]>0)].copy()
        avg_roas    = (roas_rows["conv_value"].sum() / roas_rows["spend"].sum()) if not roas_rows.empty else 0

        k1,k2,k3,k4,k5,k6 = st.columns(6)
        k1.metric("Total spend",   f"${fmt_num(total_spend)}")
        k2.metric("Impressions",   fmt_num(total_impr))
        k3.metric("Reach",         fmt_num(total_reach))
        k4.metric("Purchases",     f"{int(total_purch):,}")
        k5.metric("Avg CPM",       f"${avg_cpm:.3f}" if avg_cpm else "—")
        k6.metric("Avg ROAS",      f"{avg_roas:.2f}x" if avg_roas else "—")

        st.markdown("")

        # Charts row 1
        c1, c2 = st.columns(2)

        with c1:
            obj_spend = tdf.groupby("objective")["spend"].sum().reset_index()
            fig = px.pie(obj_spend, values="spend", names="objective",
                        title="Spend by objective",
                        hole=0.6,
                        color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#f0f0f8", legend_font_size=11, height=300,
                            margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True, key=f"obj_{i}")

        with c2:
            if div_map[i] == "All":
                div_spend = tdf.groupby("division")["spend"].sum().reset_index()
                fig2 = px.bar(div_spend, x="division", y="spend",
                             title="Spend by division",
                             color="division",
                             color_discrete_map={"MX":"#4a9eff","VD":"#2ecc71","DA":"#f39c12","Corp":"#9b59b6"})
            else:
                camp_spend = tdf.groupby("campaign_name")["spend"].sum().reset_index()
                camp_spend = camp_spend.nlargest(10,"spend")
                camp_spend["campaign_name"] = camp_spend["campaign_name"].str[:40]
                fig2 = px.bar(camp_spend, x="spend", y="campaign_name",
                             orientation="h",
                             title="Top 10 campaigns by spend",
                             color_discrete_sequence=["#4a9eff"])
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#f0f0f8", showlegend=False, height=300,
                              margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True, key=f"div_{i}")

        # Charts row 2
        c3, c4, c5 = st.columns(3)

        with c3:
            obj_cpm = tdf[tdf["cpm"]>0].groupby("objective")["cpm"].mean().reset_index()
            fig3 = px.bar(obj_cpm, x="objective", y="cpm",
                         title="Avg CPM by objective",
                         color_discrete_sequence=["#e74c3c"])
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#f0f0f8",showlegend=False,height=250,
                              margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig3, use_container_width=True, key=f"cpm_{i}")

        with c4:
            obj_ctr = tdf[tdf["ctr"]>0].groupby("objective")["ctr"].mean().reset_index()
            fig4 = px.bar(obj_ctr, x="objective", y="ctr",
                         title="Avg CTR by objective",
                         color_discrete_sequence=["#1abc9c"])
            fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                              font_color="#f0f0f8",showlegend=False,height=250,
                              margin=dict(t=40,b=0,l=0,r=0))
            st.plotly_chart(fig4, use_container_width=True, key=f"ctr_{i}")

        with c5:
            if not roas_rows.empty:
                roas_obj = roas_rows.groupby("objective").apply(
                    lambda x: x["conv_value"].sum()/x["spend"].sum()
                ).reset_index(name="roas")
                colors = ["#2ecc71" if v>=5 else "#f39c12" if v>=2 else "#e74c3c" for v in roas_obj["roas"]]
                fig5 = px.bar(roas_obj, x="objective", y="roas",
                             title="ROAS by objective",
                             color_discrete_sequence=["#2ecc71"])
                fig5.update_traces(marker_color=colors)
                fig5.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#f0f0f8",showlegend=False,height=250,
                                  margin=dict(t=40,b=0,l=0,r=0))
                st.plotly_chart(fig5, use_container_width=True, key=f"roas_{i}")
            else:
                st.info("No ROAS data available for this selection.")

        # Campaign table
        st.markdown("#### Campaign breakdown")
        display_cols = ["campaign_name","division","objective","date_start","spend",
                       "impressions","reach","cpm","ctr","clicks","purchases","conv_value"]
        show_cols = [c for c in display_cols if c in tdf.columns]
        tbl = tdf[show_cols].copy()
        tbl = tbl.sort_values("spend", ascending=False)
        tbl["spend"]      = tbl["spend"].apply(lambda x: f"${x:,.2f}")
        tbl["impressions"]= tbl["impressions"].apply(lambda x: f"{int(x):,}")
        tbl["reach"]      = tbl["reach"].apply(lambda x: f"{int(x):,}")
        tbl["cpm"]        = tbl["cpm"].apply(lambda x: f"${x:.3f}" if x else "—")
        tbl["ctr"]        = tbl["ctr"].apply(lambda x: f"{x:.2f}%" if x else "—")
        tbl["clicks"]     = tbl["clicks"].apply(lambda x: f"{int(x):,}")
        tbl["purchases"]  = tbl["purchases"].apply(lambda x: f"{int(x):,}")
        tbl["conv_value"] = tbl["conv_value"].apply(lambda x: f"${x:,.2f}" if x else "—")
        tbl.columns = [c.replace("_"," ").title() for c in tbl.columns]
        st.dataframe(tbl, use_container_width=True, height=400)

