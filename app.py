import random
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Logistics Control Tower",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------
# STYLING
# ---------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #08111f 0%, #0b1728 100%);
        color: #e8eef7;
    }

    section[data-testid="stSidebar"] {
        background: #0a1424;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1.5rem;
    }

    h1, h2, h3, h4 {
        color: #f4f8ff !important;
    }

    .hero {
        background: linear-gradient(135deg, rgba(15,30,49,0.95), rgba(8,17,31,0.95));
        border: 1px solid rgba(103,232,249,0.15);
        border-radius: 20px;
        padding: 20px 22px;
        margin-bottom: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.20);
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        color: #f4f8ff;
        margin-bottom: 6px;
    }

    .hero-sub {
        color: #8ea3bd;
        font-size: 1rem;
    }

    .metric-card {
        background: rgba(14, 26, 43, 0.95);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 18px 18px 14px 18px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        min-height: 108px;
    }

    .metric-label {
        color: #8ea3bd;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .metric-value {
        color: #f4f8ff;
        font-size: 1.9rem;
        font-weight: 700;
        margin-top: 8px;
        line-height: 1.1;
    }

    .metric-delta {
        color: #67e8f9;
        font-size: 0.82rem;
        margin-top: 6px;
    }

    .panel {
        background: rgba(14, 26, 43, 0.95);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 16px 16px 10px 16px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.16);
        margin-bottom: 14px;
    }

    .status-chip {
        display: inline-block;
        padding: 0.28rem 0.62rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 6px;
        margin-bottom: 4px;
    }

    .chip-low {
        background: rgba(34,197,94,0.16);
        color: #7ee787;
        border: 1px solid rgba(34,197,94,0.30);
    }

    .chip-medium {
        background: rgba(245,158,11,0.16);
        color: #fbbf24;
        border: 1px solid rgba(245,158,11,0.30);
    }

    .chip-high {
        background: rgba(239,68,68,0.16);
        color: #f87171;
        border: 1px solid rgba(239,68,68,0.30);
    }

    .chip-normal {
        background: rgba(34,197,94,0.14);
        color: #7ee787;
        border: 1px solid rgba(34,197,94,0.25);
    }

    .chip-congested {
        background: rgba(245,158,11,0.16);
        color: #fbbf24;
        border: 1px solid rgba(245,158,11,0.30);
    }

    .chip-severe {
        background: rgba(239,68,68,0.16);
        color: #f87171;
        border: 1px solid rgba(239,68,68,0.30);
    }

    .alert-banner {
        background: linear-gradient(90deg, rgba(127,29,29,0.92), rgba(146,64,14,0.92));
        border: 1px solid rgba(248,113,113,0.35);
        color: #fff7ed;
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 14px;
        font-weight: 600;
    }

    .good-banner {
        background: linear-gradient(90deg, rgba(6,78,59,0.95), rgba(8,47,73,0.95));
        border: 1px solid rgba(45,212,191,0.28);
        color: #ecfeff;
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 14px;
        font-weight: 600;
    }

    .decision-box {
        background: rgba(9, 20, 35, 0.95);
        border-left: 4px solid #67e8f9;
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 10px;
        color: #d9e7f7;
    }

    .mini-label {
        color: #8ea3bd;
        font-size: 0.82rem;
        margin-bottom: 4px;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# MASTER DATA
# ---------------------------------------------------
city_coords = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Bangalore": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Kolkata": (22.5726, 88.3639),
    "Bhubaneswar": (20.2961, 85.8245),
    "Nagpur": (21.1458, 79.0882),
    "Indore": (22.7196, 75.8577),
}

lanes = [
    ("Delhi", "Mumbai"),
    ("Pune", "Bangalore"),
    ("Chennai", "Hyderabad"),
    ("Ahmedabad", "Jaipur"),
    ("Kolkata", "Bhubaneswar"),
    ("Nagpur", "Indore"),
    ("Delhi", "Jaipur"),
    ("Mumbai", "Pune"),
]

carriers = ["FastMove", "RoadAxis", "FleetGo", "TransEdge"]
modes = ["FTL", "LTL"]
yards = ["North DC", "West Hub", "South FC", "East Crossdock"]

# ---------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------
st.sidebar.markdown("## Scenario Controls")
seed = st.sidebar.number_input("Random Seed", min_value=1, max_value=999, value=44)
num_shipments = st.sidebar.slider("Number of Shipments", 6, 60, 24)
demand_shock_percent = st.sidebar.slider("Demand Shock %", 0, 100, 10)
avg_delay_shock_hours = st.sidebar.slider("Extra Delay Shock (hrs)", 0, 10, 1)
dock_capacity_reduction = st.sidebar.slider("Dock Capacity Reduction", 0, 3, 0)
detention_cost_per_hour = st.sidebar.number_input("Detention Cost / Hour (INR)", min_value=100, value=1200, step=100)
otif_tolerance_hours = st.sidebar.slider("OTIF Tolerance (hrs)", 0, 5, 1)

# Business levers
st.sidebar.markdown("## Value Levers")
expedite_cost_per_high_risk = st.sidebar.number_input("Expedite Cost / High-Risk Load (INR)", min_value=100, value=4000, step=500)
recovery_rate_high_risk = st.sidebar.slider("High-Risk Recovery % if Action Taken", 0, 100, 35)
yard_capacity_improvement_pct = st.sidebar.slider("Capacity Improvement % from Added Docks", 0, 50, 15)

random.seed(seed)
np.random.seed(seed)

# ---------------------------------------------------
# LOGIC
# ---------------------------------------------------
def calculate_risk(delay):
    if delay <= 1:
        return "Low"
    elif delay <= 4:
        return "Medium"
    return "High"

def calculate_otif(planned_eta, predicted_eta, tolerance=1):
    return "Yes" if predicted_eta <= planned_eta + tolerance else "No"

def calculate_yard_status(capacity, waiting):
    if waiting <= capacity:
        return "Normal"
    elif waiting <= capacity * 1.5:
        return "Congested"
    return "Severely Congested"

def reschedule_dock(yard_status, risk, current_dock):
    if yard_status == "Severely Congested" or risk == "High":
        alt_dock_num = (int(current_dock.split("-")[1]) % 4) + 1
        return f"Dock-{alt_dock_num}"
    return current_dock

def suggested_action(risk, yard_status):
    if risk == "High" and yard_status == "Severely Congested":
        return "Expedite + Open backup dock + Escalate"
    elif risk == "High":
        return "Expedite shipment + Notify customer"
    elif yard_status == "Severely Congested":
        return "Reschedule dock + Reduce queue"
    elif risk == "Medium":
        return "Monitor closely + Prepare mitigation"
    return "No major action"

def shipment_status(delay):
    if delay == 0:
        return "On Track"
    elif delay <= 3:
        return "At Risk"
    return "Delayed"

def detention_hours(waiting, capacity):
    extra = max(0, waiting - capacity)
    return round(extra * 0.75, 2)

def generate_data():
    rows = []
    for i in range(num_shipments):
        origin, destination = random.choice(lanes)
        carrier = random.choice(carriers)
        mode = random.choice(modes)
        yard = random.choice(yards)

        planned_eta = random.randint(10, 36)
        base_delay = random.choice([0, 1, 2, 3, 5, 8, 10])
        delay = base_delay + avg_delay_shock_hours
        predicted_eta = planned_eta + delay

        dock_capacity = max(1, random.randint(3, 8) - dock_capacity_reduction)
        trucks_waiting = random.randint(2, 14)
        trucks_waiting = int(round(trucks_waiting * (1 + demand_shock_percent / 100)))

        assigned_dock = random.randint(1, 4)
        load_value = random.randint(80000, 400000)

        rows.append({
            "Shipment ID": f"SHP-{100+i}",
            "Origin": origin,
            "Destination": destination,
            "Carrier": carrier,
            "Mode": mode,
            "Yard": yard,
            "Planned ETA (hrs)": planned_eta,
            "Predicted ETA (hrs)": predicted_eta,
            "Delay (hrs)": delay,
            "Dock Capacity": dock_capacity,
            "Trucks Waiting": trucks_waiting,
            "Assigned Dock": f"Dock-{assigned_dock}",
            "Load Value (INR)": load_value
        })

    df = pd.DataFrame(rows)
    df["Risk"] = df["Delay (hrs)"].apply(calculate_risk)
    df["OTIF"] = df.apply(
        lambda x: calculate_otif(x["Planned ETA (hrs)"], x["Predicted ETA (hrs)"], otif_tolerance_hours), axis=1
    )
    df["Yard Status"] = df.apply(
        lambda x: calculate_yard_status(x["Dock Capacity"], x["Trucks Waiting"]), axis=1
    )
    df["Recommended Dock"] = df.apply(
        lambda x: reschedule_dock(x["Yard Status"], x["Risk"], x["Assigned Dock"]), axis=1
    )
    df["Suggested Action"] = df.apply(
        lambda x: suggested_action(x["Risk"], x["Yard Status"]), axis=1
    )
    df["Shipment Status"] = df["Delay (hrs)"].apply(shipment_status)
    df["Detention Hours"] = df.apply(
        lambda x: detention_hours(x["Trucks Waiting"], x["Dock Capacity"]), axis=1
    )
    df["Detention Cost (INR)"] = df["Detention Hours"] * detention_cost_per_hour
    df["Service Risk Cost (INR)"] = np.where(
        df["Risk"] == "High", df["Load Value (INR)"] * 0.02,
        np.where(df["Risk"] == "Medium", df["Load Value (INR)"] * 0.0075, 0)
    ).round(2)
    df["Total Risk Cost (INR)"] = df["Detention Cost (INR)"] + df["Service Risk Cost (INR)"]
    return df

df = generate_data()

# ---------------------------------------------------
# VALUE SIMULATION
# ---------------------------------------------------
high_risk_count = int((df["Risk"] == "High").sum())
severe_yard_count = int((df["Yard Status"] == "Severely Congested").sum())
total_detention_cost = float(df["Detention Cost (INR)"].sum())
total_service_risk_cost = float(df["Service Risk Cost (INR)"].sum())
total_risk_cost = float(df["Total Risk Cost (INR)"].sum())

recoverable_service_risk = total_service_risk_cost * (recovery_rate_high_risk / 100)
yard_savings = total_detention_cost * (yard_capacity_improvement_pct / 100)
expedite_cost = high_risk_count * expedite_cost_per_high_risk
net_benefit = recoverable_service_risk + yard_savings - expedite_cost

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def chip_html(text, kind):
    return f'<span class="status-chip {kind}">{text}</span>'

def risk_chip(risk):
    return {
        "Low": chip_html("LOW", "chip-low"),
        "Medium": chip_html("MEDIUM", "chip-medium"),
        "High": chip_html("HIGH", "chip-high"),
    }.get(risk, chip_html(risk, "chip-low"))

def yard_chip(status):
    return {
        "Normal": chip_html("NORMAL", "chip-normal"),
        "Congested": chip_html("CONGESTED", "chip-congested"),
        "Severely Congested": chip_html("SEVERE", "chip-severe"),
    }.get(status, chip_html(status, "chip-normal"))

# ---------------------------------------------------
# HERO
# ---------------------------------------------------
st.markdown("""
<div class="hero">
    <div class="hero-title">Logistics Control Tower</div>
    <div class="hero-sub">
        Executive visibility for shipment risk, yard congestion, dock reassignment, and simulated business impact.
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# EXECUTIVE BANNER
# ---------------------------------------------------
if high_risk_count > 0 or severe_yard_count > 0:
    st.markdown(
        f"""
        <div class="alert-banner">
            ⚠️ Immediate attention required: <b>{high_risk_count}</b> high-risk shipments and <b>{severe_yard_count}</b> severely congested yards are threatening service and cost performance.
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <div class="good-banner">
            ✅ Network stable: no major risk clusters detected across shipments and yard operations.
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------------------------------
# KPI CARDS
# ---------------------------------------------------
total_shipments = len(df)
avg_delay = round(df["Delay (hrs)"].mean(), 2)
otif_pct = round((df["OTIF"].eq("Yes").mean()) * 100, 2)

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Shipments</div>
        <div class="metric-value">{total_shipments}</div>
        <div class="metric-delta">Live network count</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Delay</div>
        <div class="metric-value">{avg_delay}h</div>
        <div class="metric-delta">Predicted drift</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">OTIF</div>
        <div class="metric-value">{otif_pct}%</div>
        <div class="metric-delta">Service reliability</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">High Risk Loads</div>
        <div class="metric-value">{high_risk_count}</div>
        <div class="metric-delta">Requires intervention</div>
    </div>
    """, unsafe_allow_html=True)

with c5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Severe Yards</div>
        <div class="metric-value">{severe_yard_count}</div>
        <div class="metric-delta">Capacity stress points</div>
    </div>
    """, unsafe_allow_html=True)

with c6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Risk Cost</div>
        <div class="metric-value">₹{total_risk_cost:,.0f}</div>
        <div class="metric-delta">Detention + service risk</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------
# DECISION RECOMMENDATIONS
# ---------------------------------------------------
rec1, rec2 = st.columns(2)

with rec1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Recommended Actions")
    recommendations = []

    if high_risk_count > 0:
        recommendations.append(f"Expedite {high_risk_count} high-risk loads to recover threatened service.")
    if severe_yard_count > 0:
        recommendations.append(f"Open backup capacity at {severe_yard_count} stressed yards to reduce queue pressure.")
    if (df["Assigned Dock"] != df["Recommended Dock"]).sum() > 0:
        recommendations.append("Reassign docks for disrupted shipments to smooth inbound flow.")
    if avg_delay > 4:
        recommendations.append("Investigate lane-level delay drivers and carrier reliability gaps.")

    if not recommendations:
        recommendations = ["No urgent actions recommended. Maintain network monitoring cadence."]

    for r in recommendations:
        st.markdown(f'<div class="decision-box">• {r}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with rec2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Simulated Business Impact")
    st.markdown(f'<div class="decision-box">Recoverable service-risk value: ₹{recoverable_service_risk:,.0f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="decision-box">Potential detention savings from added capacity: ₹{yard_savings:,.0f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="decision-box">Estimated expedite spend: ₹{expedite_cost:,.0f}</div>', unsafe_allow_html=True)

    banner_class = "good-banner" if net_benefit >= 0 else "alert-banner"
    msg = "Projected net benefit" if net_benefit >= 0 else "Projected net impact"
    st.markdown(
        f'<div class="{banner_class}" style="margin-top:12px;">{msg}: <b>₹{net_benefit:,.0f}</b></div>',
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# FILTERS
# ---------------------------------------------------
st.markdown('<div class="panel">', unsafe_allow_html=True)
st.markdown("### Network Filters")

f1, f2, f3, f4 = st.columns(4)

selected_carrier = f1.multiselect("Carrier", options=sorted(df["Carrier"].unique()), default=sorted(df["Carrier"].unique()))
selected_risk = f2.multiselect("Risk", options=["Low", "Medium", "High"], default=["Low", "Medium", "High"])
selected_yard = f3.multiselect("Yard", options=sorted(df["Yard"].unique()), default=sorted(df["Yard"].unique()))
selected_mode = f4.multiselect("Mode", options=sorted(df["Mode"].unique()), default=sorted(df["Mode"].unique()))

filtered_df = df[
    df["Carrier"].isin(selected_carrier) &
    df["Risk"].isin(selected_risk) &
    df["Yard"].isin(selected_yard) &
    df["Mode"].isin(selected_mode)
].copy()

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# TABS
# ---------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Operations Console",
    "Exception Manager",
    "Performance Insights",
    "Shipment Intelligence",
    "Network Map"
])

# ---------------------------------------------------
# TAB 1
# ---------------------------------------------------
with tab1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Operations Console")

    display_df = filtered_df[[
        "Shipment ID", "Origin", "Destination", "Carrier", "Mode", "Yard",
        "Planned ETA (hrs)", "Predicted ETA (hrs)", "Delay (hrs)", "Risk",
        "Yard Status", "Assigned Dock", "Recommended Dock", "OTIF"
    ]].copy()

    st.dataframe(display_df, use_container_width=True, height=420)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# TAB 2
# ---------------------------------------------------
with tab2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Exception Manager")

    exceptions = filtered_df[
        (filtered_df["Risk"] == "High") |
        (filtered_df["Yard Status"] == "Severely Congested") |
        (filtered_df["Assigned Dock"] != filtered_df["Recommended Dock"])
    ].copy()

    st.dataframe(
        exceptions[[
            "Shipment ID", "Origin", "Destination", "Carrier", "Risk",
            "Yard Status", "Assigned Dock", "Recommended Dock",
            "Detention Cost (INR)", "Suggested Action"
        ]],
        use_container_width=True,
        height=420
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# TAB 3
# ---------------------------------------------------
with tab3:
    a1, a2 = st.columns(2)

    with a1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Carrier Scorecard")

        carrier_scorecard = (
            filtered_df.groupby("Carrier", as_index=False)
            .agg(
                Shipments=("Shipment ID", "count"),
                Avg_Delay_Hrs=("Delay (hrs)", "mean"),
                OTIF_Pct=("OTIF", lambda s: round((s.eq("Yes").mean()) * 100, 2)),
                High_Risk_Shipments=("Risk", lambda s: int((s == "High").sum())),
                Detention_Cost=("Detention Cost (INR)", "sum")
            )
            .sort_values(by=["OTIF_Pct", "Avg_Delay_Hrs"], ascending=[False, True])
        )

        st.dataframe(carrier_scorecard, use_container_width=True, height=300)
        st.markdown("</div>", unsafe_allow_html=True)

    with a2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Lane Summary")

        lane_summary = (
            filtered_df.groupby(["Origin", "Destination"], as_index=False)
            .agg(
                Shipments=("Shipment ID", "count"),
                Avg_Delay_Hrs=("Delay (hrs)", "mean"),
                OTIF_Pct=("OTIF", lambda s: round((s.eq("Yes").mean()) * 100, 2)),
                Detention_Cost=("Detention Cost (INR)", "sum")
            )
            .sort_values(by="Avg_Delay_Hrs", ascending=False)
        )

        st.dataframe(lane_summary, use_container_width=True, height=300)
        st.markdown("</div>", unsafe_allow_html=True)

    b1, b2 = st.columns(2)

    with b1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Risk Distribution")
        risk_counts = filtered_df["Risk"].value_counts().reset_index()
        risk_counts.columns = ["Risk", "Count"]

        fig_risk = px.bar(
            risk_counts,
            x="Risk",
            y="Count",
            color="Risk",
            color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"},
            template="plotly_dark"
        )
        fig_risk.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), height=320)
        st.plotly_chart(fig_risk, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with b2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("### Yard Congestion")
        yard_chart = filtered_df.groupby("Yard", as_index=False)["Trucks Waiting"].mean()

        fig_yard = px.bar(yard_chart, x="Yard", y="Trucks Waiting", template="plotly_dark")
        fig_yard.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), height=320)
        st.plotly_chart(fig_yard, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# TAB 4
# ---------------------------------------------------
with tab4:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Shipment Intelligence")

    shipment_list = filtered_df["Shipment ID"].tolist()
    if shipment_list:
        selected_shipment = st.selectbox("Select Shipment", shipment_list)
        shipment_view = filtered_df[filtered_df["Shipment ID"] == selected_shipment].copy()
        row = shipment_view.iloc[0]

        d1, d2 = st.columns([1.2, 1])

        with d1:
            st.dataframe(shipment_view.T, use_container_width=True)

        with d2:
            st.markdown("#### Control Flags")
            st.markdown(risk_chip(row["Risk"]), unsafe_allow_html=True)
            st.markdown(yard_chip(row["Yard Status"]), unsafe_allow_html=True)
            st.markdown(f"**Assigned Dock:** {row['Assigned Dock']}")
            st.markdown(f"**Recommended Dock:** {row['Recommended Dock']}")
            st.markdown(f"**Suggested Action:** {row['Suggested Action']}")
            st.markdown(f"**Risk Cost:** ₹{row['Total Risk Cost (INR)']:,.0f}")

        milestone_df = pd.DataFrame([
            {"Milestone": "Order Created", "Hour": 0},
            {"Milestone": "Pickup", "Hour": 1},
            {"Milestone": "Gate Out", "Hour": 2},
            {"Milestone": "Mid Transit", "Hour": max(3, int(row["Predicted ETA (hrs)"] * 0.5))},
            {"Milestone": "Arrival at Yard", "Hour": row["Predicted ETA (hrs)"] - 1},
            {"Milestone": "Proof of Delivery", "Hour": row["Predicted ETA (hrs)"]},
        ])

        st.markdown("#### Milestone Timeline")
        fig_timeline = px.line(milestone_df, x="Milestone", y="Hour", markers=True, template="plotly_dark")
        fig_timeline.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), height=340)
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("No shipments available for selected filters.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# TAB 5
# ---------------------------------------------------
with tab5:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Live Network Map")

    india_center = [22.5, 79.0]
    m = folium.Map(location=india_center, zoom_start=5, tiles="CartoDB dark_matter")

    for _, row in filtered_df.iterrows():
        o_lat, o_lon = city_coords[row["Origin"]]
        d_lat, d_lon = city_coords[row["Destination"]]

        if row["Risk"] == "High":
            line_color = "#ef4444"
        elif row["Risk"] == "Medium":
            line_color = "#f59e0b"
        else:
            line_color = "#22c55e"

        popup_text = f"""
        <b>{row['Shipment ID']}</b><br>
        {row['Origin']} → {row['Destination']}<br>
        Carrier: {row['Carrier']}<br>
        Mode: {row['Mode']}<br>
        Delay: {row['Delay (hrs)']} hrs<br>
        Risk: {row['Risk']}<br>
        Yard: {row['Yard']}<br>
        Assigned Dock: {row['Assigned Dock']}<br>
        Recommended Dock: {row['Recommended Dock']}<br>
        Detention Cost: INR {row['Detention Cost (INR)']:,.0f}<br>
        Action: {row['Suggested Action']}
        """

        folium.CircleMarker(
            [o_lat, o_lon],
            radius=5,
            color="#67e8f9",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"Origin: {row['Origin']}"
        ).add_to(m)

        folium.CircleMarker(
            [d_lat, d_lon],
            radius=6,
            color=line_color,
            fill=True,
            fill_opacity=0.9,
            popup=popup_text,
            tooltip=f"{row['Shipment ID']} | {row['Destination']}"
        ).add_to(m)

        folium.PolyLine(
            locations=[(o_lat, o_lon), (d_lat, d_lon)],
            color=line_color,
            weight=4,
            opacity=0.85
        ).add_to(m)

    st_folium(m, width=1200, height=520)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------
# FOOTER
# ---------------------------------------------------
st.markdown(f"""
<div class="panel">
    <div class="mini-label">Scenario Inputs</div>
    <div style="color:#c8d6e5; font-size:0.95rem;">
        Demand Shock: <b>{demand_shock_percent}%</b> &nbsp;&nbsp;|&nbsp;&nbsp;
        Delay Shock: <b>{avg_delay_shock_hours} hrs</b> &nbsp;&nbsp;|&nbsp;&nbsp;
        Dock Capacity Reduction: <b>{dock_capacity_reduction}</b> &nbsp;&nbsp;|&nbsp;&nbsp;
        Detention Cost: <b>₹{detention_cost_per_hour:,.0f}/hr</b>
    </div>
</div>
""", unsafe_allow_html=True)
