import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from math import ceil

st.set_page_config(page_title="Logistics Control Tower V3", layout="wide")

st.title("Logistics Control Tower V3")
st.caption("Multi-plant allocation, split transport planning, ETA risk, aging risk, exception scoring, and recommendation engine.")

REGIONS = ["North", "South", "West", "East"]
PRIORITIES = ["High", "Medium", "Low"]


# =========================================================
# HELPERS
# =========================================================
def validate_po(po_qty):
    if pd.isna(po_qty):
        return False, "PO missing"
    if po_qty <= 0:
        return False, "Invalid PO quantity"
    if po_qty > 5000:
        return False, "PO exceeds threshold"
    return True, "Valid"


def priority_rank(priority):
    mapping = {"High": 1, "Medium": 2, "Low": 3}
    return mapping.get(priority, 3)


def forecast_demand(po_qty, region, market_intelligence):
    multiplier = market_intelligence.get(region, 1.0)
    return round(po_qty * multiplier)


def plant_region_cost_multiplier(plant_region, retailer_region):
    if plant_region == retailer_region:
        return 1.0
    region_pairs = {
        ("North", "East"): 1.05,
        ("East", "North"): 1.05,
        ("North", "West"): 1.15,
        ("West", "North"): 1.15,
        ("North", "South"): 1.25,
        ("South", "North"): 1.25,
        ("South", "West"): 1.10,
        ("West", "South"): 1.10,
        ("South", "East"): 1.20,
        ("East", "South"): 1.20,
        ("West", "East"): 1.15,
        ("East", "West"): 1.15,
    }
    return region_pairs.get((plant_region, retailer_region), 1.2)


def get_eta_days(plant_region, retailer_region):
    if plant_region == retailer_region:
        return 1
    eta_map = {
        ("North", "East"): 2,
        ("East", "North"): 2,
        ("North", "West"): 3,
        ("West", "North"): 3,
        ("North", "South"): 4,
        ("South", "North"): 4,
        ("South", "West"): 2,
        ("West", "South"): 2,
        ("South", "East"): 3,
        ("East", "South"): 3,
        ("West", "East"): 3,
        ("East", "West"): 3,
    }
    return eta_map.get((plant_region, retailer_region), 4)


def aging_risk_bucket(days):
    if days <= 30:
        return "Fresh"
    elif days <= 60:
        return "Moderate"
    else:
        return "Aging Risk"


def alert_color(score):
    if score >= 70:
        return "🔴 Red"
    elif score >= 40:
        return "🟠 Amber"
    return "🟢 Green"


# =========================================================
# ALLOCATION ENGINE
# =========================================================
def allocate_inventory_multi_plant(required_qty, retailer_region, plants_df):
    """
    Allocates from multiple plants based on:
    1. same-region preference
    2. lower aging first if risk exists? no - better to ship older first
    3. available stock and warehouse dispatch capacity
    """
    working = plants_df.copy()

    working["Region Match"] = working["Region"].apply(lambda x: 0 if x == retailer_region else 1)
    working["Aging Priority"] = working["Inventory Age Days"].apply(lambda x: -x)  # older inventory first
    working["Lane Cost"] = working["Region"].apply(lambda x: plant_region_cost_multiplier(x, retailer_region))

    working = working.sort_values(
        by=["Region Match", "Lane Cost", "Aging Priority"],
        ascending=[True, True, True]
    )

    allocation_rows = []
    remaining = required_qty
    warehouse_block = 0

    for idx, row in working.iterrows():
        if remaining <= 0:
            break

        available_stock = int(row["Stock"])
        dispatch_cap = int(row["Warehouse Capacity"])
        allocatable = min(available_stock, dispatch_cap, remaining)

        if allocatable > 0:
            allocation_rows.append({
                "Plant": row["Plant"],
                "Plant Region": row["Region"],
                "Allocated Qty": allocatable,
                "Inventory Age Days": row["Inventory Age Days"],
                "ETA Days": get_eta_days(row["Region"], retailer_region),
                "Lane Cost Multiplier": plant_region_cost_multiplier(row["Region"], retailer_region)
            })

            working.at[idx, "Stock"] -= allocatable
            working.at[idx, "Warehouse Capacity"] -= allocatable
            remaining -= allocatable

    # theoretical stock block
    total_stock_possible = min(required_qty, int(working["Stock"].sum()) + sum(x["Allocated Qty"] for x in allocation_rows))
    total_dispatch_possible = min(required_qty, int(working["Warehouse Capacity"].sum()) + sum(x["Allocated Qty"] for x in allocation_rows))
    actual_allocated = sum(x["Allocated Qty"] for x in allocation_rows)

    if total_stock_possible > actual_allocated and total_dispatch_possible < total_stock_possible:
        warehouse_block = total_stock_possible - actual_allocated

    return allocation_rows, remaining, warehouse_block, working.drop(columns=["Region Match", "Aging Priority", "Lane Cost"])


# =========================================================
# TRANSPORT PLANNING ENGINE
# =========================================================
def get_eligible_transporters(transporters_df, region):
    return transporters_df[
        transporters_df["Regions Served"].str.contains(region, case=False, na=False)
    ].copy()


def split_shipment_transport_plan(total_qty, retailer_region, transporters_df, route_cost_df):
    if total_qty <= 0:
        return [], 0, 0, "No movement"

    route_row = route_cost_df[route_cost_df["Region"] == retailer_region]
    route_multiplier = 1.0 if route_row.empty else float(route_row.iloc[0]["Route Cost Multiplier"])

    eligible = get_eligible_transporters(transporters_df, retailer_region)
    if eligible.empty:
        return [], 0, 0, "No eligible transporter"

    eligible = eligible.copy()
    eligible["Cost Per Capacity"] = eligible["Cost Per Trip"] / eligible["Capacity"]
    eligible = eligible.sort_values(by=["Cost Per Capacity", "Capacity"], ascending=[True, False])

    remaining = total_qty
    plan = []
    total_cost = 0
    total_capacity_used = 0

    for _, row in eligible.iterrows():
        if remaining <= 0:
            break

        capacity = int(row["Capacity"])
        base_cost = float(row["Cost Per Trip"])
        max_trips = int(row["Max Trips"])

        if max_trips <= 0:
            continue

        possible_qty = capacity * max_trips
        moved_qty = min(remaining, possible_qty)
        trips_needed = ceil(moved_qty / capacity)

        actual_capacity_used = trips_needed * capacity
        adjusted_trip_cost = base_cost * route_multiplier
        movement_cost = trips_needed * adjusted_trip_cost

        plan.append({
            "Transporter": row["Transporter"],
            "Trips": trips_needed,
            "Qty Moved": moved_qty,
            "Capacity Per Trip": capacity,
            "Total Capacity Used": actual_capacity_used,
            "Adjusted Trip Cost": round(adjusted_trip_cost, 2),
            "Movement Cost": round(movement_cost, 2)
        })

        remaining -= moved_qty
        total_cost += movement_cost
        total_capacity_used += actual_capacity_used

    utilization = (total_qty - remaining) / total_capacity_used * 100 if total_capacity_used > 0 else 0
    transport_status = "Planned" if remaining == 0 else "Partial transporter capacity"

    return plan, round(total_cost, 2), round(utilization, 2), transport_status


# =========================================================
# RISK / ALERT / RECOMMENDATION ENGINE
# =========================================================
def compute_risk_score(unfulfilled_qty, warehouse_block, avg_eta, transport_cost, utilization_pct, avg_inventory_age):
    score = 0

    if unfulfilled_qty > 0:
        score += 35
    if warehouse_block > 0:
        score += 20
    if avg_eta >= 4:
        score += 15
    elif avg_eta >= 3:
        score += 8

    if transport_cost > 20000:
        score += 15
    elif transport_cost > 12000:
        score += 8

    if utilization_pct < 65 and utilization_pct > 0:
        score += 10
    elif utilization_pct < 80 and utilization_pct > 0:
        score += 5

    if avg_inventory_age > 60:
        score += 10
    elif avg_inventory_age > 30:
        score += 5

    return min(score, 100)


def build_recommendations(unfulfilled_qty, warehouse_block, avg_eta, utilization_pct, avg_inventory_age, transport_status):
    recs = []

    if unfulfilled_qty > 0:
        recs.append("Increase replenishment or rebalance stock across plants")
    if warehouse_block > 0:
        recs.append("Improve dispatch slotting or warehouse throughput")
    if avg_eta >= 4:
        recs.append("Use nearer plant or premium transport for urgent orders")
    if utilization_pct < 70 and utilization_pct > 0:
        recs.append("Consolidate loads to improve truck utilization")
    if avg_inventory_age > 60:
        recs.append("Prioritize aging inventory clearance")
    if transport_status != "Planned":
        recs.append("Add backup carriers or increase trip capacity")

    if not recs:
        recs.append("Execution looks stable; monitor and continue")

    return " | ".join(recs)


# =========================================================
# MAIN ENGINE
# =========================================================
def run_control_tower_v3(retailers_df, plants_df, transporters_df, route_cost_df, market_intelligence):
    plants_state = plants_df.copy()
    retailers_work = retailers_df.copy()
    retailers_work["Priority Rank"] = retailers_work["Priority"].apply(priority_rank)
    retailers_work = retailers_work.sort_values(by=["Priority Rank", "PO_Qty"], ascending=[True, False])

    results = []

    for _, row in retailers_work.iterrows():
        retailer = row["Retailer"]
        region = row["Region"]
        po_qty = int(row["PO_Qty"])
        priority = row["Priority"]

        is_valid, po_status = validate_po(po_qty)

        if not is_valid:
            results.append({
                "Retailer": retailer,
                "Region": region,
                "Priority": priority,
                "PO Qty": po_qty,
                "PO Status": po_status,
                "Forecast Qty": 0,
                "Allocated Qty": 0,
                "Unfulfilled Qty": po_qty,
                "Warehouse Block Qty": 0,
                "Transport Cost": 0,
                "Truck Utilization %": 0,
                "Avg ETA Days": 0,
                "Avg Inventory Age": 0,
                "Service Level %": 0,
                "Risk Score": 100,
                "Alert": "🔴 Red",
                "Recommendations": "Fix invalid order input",
                "Allocation Detail": [],
                "Transport Plan": []
            })
            continue

        forecast_qty = forecast_demand(po_qty, region, market_intelligence)

        allocation_rows, unfulfilled_qty, warehouse_block, plants_state = allocate_inventory_multi_plant(
            forecast_qty, region, plants_state
        )

        allocated_qty = sum(x["Allocated Qty"] for x in allocation_rows)

        transport_plan, transport_cost, utilization_pct, transport_status = split_shipment_transport_plan(
            allocated_qty, region, transporters_df, route_cost_df
        )

        avg_eta = round(
            sum(x["ETA Days"] * x["Allocated Qty"] for x in allocation_rows) / allocated_qty, 2
        ) if allocated_qty > 0 else 0

        avg_inventory_age = round(
            sum(x["Inventory Age Days"] * x["Allocated Qty"] for x in allocation_rows) / allocated_qty, 2
        ) if allocated_qty > 0 else 0

        service_level = round((allocated_qty / forecast_qty) * 100, 2) if forecast_qty > 0 else 0

        risk_score = compute_risk_score(
            unfulfilled_qty=unfulfilled_qty,
            warehouse_block=warehouse_block,
            avg_eta=avg_eta,
            transport_cost=transport_cost,
            utilization_pct=utilization_pct,
            avg_inventory_age=avg_inventory_age
        )

        recommendations = build_recommendations(
            unfulfilled_qty=unfulfilled_qty,
            warehouse_block=warehouse_block,
            avg_eta=avg_eta,
            utilization_pct=utilization_pct,
            avg_inventory_age=avg_inventory_age,
            transport_status=transport_status
        )

        results.append({
            "Retailer": retailer,
            "Region": region,
            "Priority": priority,
            "PO Qty": po_qty,
            "PO Status": po_status,
            "Forecast Qty": forecast_qty,
            "Allocated Qty": allocated_qty,
            "Unfulfilled Qty": unfulfilled_qty,
            "Warehouse Block Qty": warehouse_block,
            "Transport Cost": transport_cost,
            "Truck Utilization %": utilization_pct,
            "Avg ETA Days": avg_eta,
            "Avg Inventory Age": avg_inventory_age,
            "Service Level %": service_level,
            "Risk Score": risk_score,
            "Alert": alert_color(risk_score),
            "Recommendations": recommendations,
            "Allocation Detail": allocation_rows,
            "Transport Plan": transport_plan
        })

    results_df = pd.DataFrame(results)

    plants_remaining = plants_state.copy()
    plants_remaining["Aging Risk"] = plants_remaining["Inventory Age Days"].apply(aging_risk_bucket)

    return results_df, plants_remaining


# =========================================================
# CHARTS
# =========================================================
def plot_bar_chart(df, x_col, y_col, title, ylabel):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df[x_col], df[y_col])
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45)
    st.pyplot(fig)


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.header("Demand Signals")

north_multiplier = st.sidebar.slider("North Demand Multiplier", 0.5, 2.0, 1.10, 0.05)
south_multiplier = st.sidebar.slider("South Demand Multiplier", 0.5, 2.0, 0.95, 0.05)
west_multiplier = st.sidebar.slider("West Demand Multiplier", 0.5, 2.0, 1.20, 0.05)
east_multiplier = st.sidebar.slider("East Demand Multiplier", 0.5, 2.0, 1.05, 0.05)

market_intelligence = {
    "North": north_multiplier,
    "South": south_multiplier,
    "West": west_multiplier,
    "East": east_multiplier
}


# =========================================================
# INPUT TABS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "Retailer Orders",
    "Plant Master",
    "Transporter Master",
    "Route Cost Master"
])

with tab1:
    retailers_df = st.data_editor(
        pd.DataFrame([
            {"Retailer": "Retailer_1", "Region": "North", "PO_Qty": 180, "Priority": "High"},
            {"Retailer": "Retailer_2", "Region": "South", "PO_Qty": 220, "Priority": "Medium"},
            {"Retailer": "Retailer_3", "Region": "West", "PO_Qty": 140, "Priority": "High"},
            {"Retailer": "Retailer_4", "Region": "East", "PO_Qty": 100, "Priority": "Low"},
        ]),
        num_rows="dynamic",
        use_container_width=True
    )

with tab2:
    plants_df = st.data_editor(
        pd.DataFrame([
            {"Plant": "Plant_A", "Region": "North", "Stock": 300, "Warehouse Capacity": 250, "Inventory Age Days": 20},
            {"Plant": "Plant_B", "Region": "South", "Stock": 280, "Warehouse Capacity": 220, "Inventory Age Days": 45},
            {"Plant": "Plant_C", "Region": "West", "Stock": 240, "Warehouse Capacity": 180, "Inventory Age Days": 70},
            {"Plant": "Plant_D", "Region": "East", "Stock": 200, "Warehouse Capacity": 160, "Inventory Age Days": 35},
        ]),
        num_rows="dynamic",
        use_container_width=True
    )

with tab3:
    transporters_df = st.data_editor(
        pd.DataFrame([
            {"Transporter": "Truck_1", "Capacity": 100, "Cost Per Trip": 5000, "Max Trips": 2, "Regions Served": "North,East"},
            {"Transporter": "Truck_2", "Capacity": 120, "Cost Per Trip": 6200, "Max Trips": 2, "Regions Served": "South,West"},
            {"Transporter": "Truck_3", "Capacity": 150, "Cost Per Trip": 7600, "Max Trips": 3, "Regions Served": "North,South,West,East"},
            {"Transporter": "Truck_4", "Capacity": 80, "Cost Per Trip": 3900, "Max Trips": 3, "Regions Served": "East,West"},
        ]),
        num_rows="dynamic",
        use_container_width=True
    )

with tab4:
    route_cost_df = st.data_editor(
        pd.DataFrame([
            {"Region": "North", "Route Cost Multiplier": 1.00},
            {"Region": "South", "Route Cost Multiplier": 1.10},
            {"Region": "West", "Route Cost Multiplier": 1.20},
            {"Region": "East", "Route Cost Multiplier": 0.95},
        ]),
        num_rows="dynamic",
        use_container_width=True
    )

run_button = st.button("Run Control Tower V3")


# =========================================================
# RUN
# =========================================================
if run_button:
    results_df, plants_remaining_df = run_control_tower_v3(
        retailers_df=retailers_df,
        plants_df=plants_df,
        transporters_df=transporters_df,
        route_cost_df=route_cost_df,
        market_intelligence=market_intelligence
    )

    st.subheader("Executive KPI Dashboard")

    total_po = int(results_df["PO Qty"].sum()) if not results_df.empty else 0
    total_forecast = int(results_df["Forecast Qty"].sum()) if not results_df.empty else 0
    total_allocated = int(results_df["Allocated Qty"].sum()) if not results_df.empty else 0
    total_unfulfilled = int(results_df["Unfulfilled Qty"].sum()) if not results_df.empty else 0
    total_transport_cost = float(results_df["Transport Cost"].sum()) if not results_df.empty else 0
    avg_service = round(results_df["Service Level %"].mean(), 2) if not results_df.empty else 0
    avg_util = round(results_df["Truck Utilization %"].mean(), 2) if not results_df.empty else 0
    avg_risk = round(results_df["Risk Score"].mean(), 2) if not results_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total PO Qty", total_po)
    c2.metric("Forecast Qty", total_forecast)
    c3.metric("Allocated Qty", total_allocated)
    c4.metric("Transport Cost", f"₹{total_transport_cost:,.0f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Unfulfilled Qty", total_unfulfilled)
    c6.metric("Avg Service Level %", avg_service)
    c7.metric("Avg Utilization %", avg_util)
    c8.metric("Avg Risk Score", avg_risk)

    st.subheader("Control Tower Decision Table")
    st.dataframe(
        results_df[[
            "Retailer", "Region", "Priority", "PO Qty", "Forecast Qty",
            "Allocated Qty", "Unfulfilled Qty", "Warehouse Block Qty",
            "Transport Cost", "Truck Utilization %", "Avg ETA Days",
            "Avg Inventory Age", "Service Level %", "Risk Score",
            "Alert", "Recommendations"
        ]],
        use_container_width=True
    )

    st.subheader("Critical Exceptions")
    exception_df = results_df[
        (results_df["Risk Score"] >= 40) |
        (results_df["Unfulfilled Qty"] > 0) |
        (results_df["Warehouse Block Qty"] > 0)
    ].copy()

    if exception_df.empty:
        st.success("No material exceptions detected. Supply chain gods are calm today.")
    else:
        st.dataframe(
            exception_df[[
                "Retailer", "Region", "Priority", "Unfulfilled Qty",
                "Warehouse Block Qty", "Avg ETA Days", "Transport Cost",
                "Truck Utilization %", "Risk Score", "Alert"
            ]],
            use_container_width=True
        )

    st.subheader("Plant Residual Position")
    st.dataframe(
        plants_remaining_df[[
            "Plant", "Region", "Stock", "Warehouse Capacity",
            "Inventory Age Days", "Aging Risk"
        ]],
        use_container_width=True
    )

    st.subheader("Charts")

    col1, col2 = st.columns(2)
    with col1:
        plot_bar_chart(results_df, "Retailer", "Forecast Qty", "Forecast by Retailer", "Forecast Qty")
    with col2:
        plot_bar_chart(results_df, "Retailer", "Allocated Qty", "Allocation by Retailer", "Allocated Qty")

    col3, col4 = st.columns(2)
    with col3:
        plot_bar_chart(results_df, "Retailer", "Transport Cost", "Transport Cost by Retailer", "Cost")
    with col4:
        plot_bar_chart(results_df, "Retailer", "Risk Score", "Risk Score by Retailer", "Risk Score")

    st.subheader("Detailed Allocation + Transport Plan")

    for _, row in results_df.iterrows():
        with st.expander(f"{row['Retailer']} | {row['Region']} | {row['Alert']}"):
            st.write("**Allocation Detail**")
            if row["Allocation Detail"]:
                st.dataframe(pd.DataFrame(row["Allocation Detail"]), use_container_width=True)
            else:
                st.write("No allocation")

            st.write("**Transport Plan**")
            if row["Transport Plan"]:
                st.dataframe(pd.DataFrame(row["Transport Plan"]), use_container_width=True)
            else:
                st.write("No transport movement")

            st.write("**Recommendations**")
            st.write(row["Recommendations"])

    csv = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download V3 Results CSV",
        data=csv,
        file_name="logistics_control_tower_v3_results.csv",
        mime="text/csv"
    )

else:
    st.info("Set your scenario and click 'Run Control Tower V3'.")
