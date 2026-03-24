import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from math import ceil

st.set_page_config(page_title="Logistics Control Tower V2", layout="wide")

st.title("Logistics Control Tower V2")
st.caption("Forecasting, inventory allocation, warehouse capacity, route cost logic, transporter selection, alerts, and KPI dashboard.")

# =========================================================
# DEFAULT MASTER DATA
# =========================================================
REGIONS = ["North", "South", "West", "East"]
PRIORITIES = ["High", "Medium", "Low"]

# =========================================================
# FUNCTIONS
# =========================================================
def validate_po(po_qty):
    if po_qty <= 0:
        return False, "Invalid PO quantity"
    if po_qty > 1000:
        return False, "PO exceeds threshold"
    return True, "Valid"

def forecast_demand(po_qty, region, market_intelligence):
    multiplier = market_intelligence.get(region, 1.0)
    return round(po_qty * multiplier)

def allocate_inventory(required_qty, plants_data):
    allocation = {}
    remaining = required_qty

    for plant_name, details in plants_data.items():
        available_stock = details["stock"]
        available_wh_capacity = details["warehouse_capacity"]

        allocatable = min(available_stock, available_wh_capacity, remaining)

        if allocatable > 0:
            allocation[plant_name] = allocatable
            plants_data[plant_name]["stock"] -= allocatable
            plants_data[plant_name]["warehouse_capacity"] -= allocatable
            remaining -= allocatable

        if remaining == 0:
            break

    return allocation, remaining

def get_transporters_for_region(transporters_df, region):
    eligible = transporters_df[
        transporters_df["Regions Served"].str.contains(region, case=False, na=False)
    ].copy()
    return eligible

def optimize_truck_loading(total_qty, region, transporters_df, route_cost_df):
    if total_qty <= 0:
        return [], 0, 0, "No transporter used"

    route_row = route_cost_df[route_cost_df["Region"] == region]
    route_multiplier = 1.0 if route_row.empty else float(route_row.iloc[0]["Route Cost Multiplier"])

    eligible = get_transporters_for_region(transporters_df, region)

    if eligible.empty:
        return [], 0, 0, "No eligible transporter"

    best_plan = None
    best_cost = float("inf")
    best_utilization = 0
    best_transporter = None

    for _, truck in eligible.iterrows():
        capacity = int(truck["Capacity"])
        base_cost = float(truck["Cost Per Trip"])

        trips = ceil(total_qty / capacity)
        total_capacity = trips * capacity
        utilization = (total_qty / total_capacity) * 100 if total_capacity > 0 else 0
        adjusted_trip_cost = base_cost * route_multiplier
        total_cost = trips * adjusted_trip_cost

        plan = [{
            "transporter": truck["Transporter"],
            "capacity_per_trip": capacity,
            "trips": trips,
            "qty_moved": total_qty,
            "total_capacity": total_capacity,
            "utilization_pct": round(utilization, 2),
            "route_multiplier": round(route_multiplier, 2),
            "cost": round(total_cost, 2)
        }]

        if total_cost < best_cost:
            best_cost = total_cost
            best_plan = plan
            best_utilization = utilization
            best_transporter = truck["Transporter"]

    return best_plan, round(best_cost, 2), round(best_utilization, 2), best_transporter

def root_cause_analysis(unfulfilled_qty, transport_cost, forecast_qty, po_qty, utilization_pct, warehouse_block, po_status, transporter_name):
    issues = []

    if po_status != "Valid":
        issues.append("PO validation failure")

    if unfulfilled_qty > 0:
        issues.append("Stock or warehouse capacity shortage")

    if warehouse_block > 0:
        issues.append("Warehouse capacity constraint")

    if forecast_qty > po_qty * 1.15:
        issues.append("Demand spike from market intelligence")

    if transport_cost > 15000:
        issues.append("High transportation cost")

    if utilization_pct < 70 and utilization_pct > 0:
        issues.append("Low truck utilization")

    if transporter_name == "No eligible transporter":
        issues.append("No transporter available for region")

    if not issues:
        issues.append("No major issue detected")

    return issues

def priority_rank(priority):
    mapping = {"High": 1, "Medium": 2, "Low": 3}
    return mapping.get(priority, 3)

def run_control_tower(retailers_df, plants_input_df, transporters_df, route_cost_df, market_intelligence):
    plants_state = {
        row["Plant"]: {
            "stock": int(row["Stock"]),
            "warehouse_capacity": int(row["Warehouse Capacity"])
        }
        for _, row in plants_input_df.iterrows()
    }

    work_df = retailers_df.copy()
    work_df["Priority Rank"] = work_df["Priority"].apply(priority_rank)
    work_df = work_df.sort_values(by=["Priority Rank", "PO_Qty"], ascending=[True, False])

    results = []

    for _, row in work_df.iterrows():
        retailer_name = row["Retailer"]
        region = row["Region"]
        po_qty = int(row["PO_Qty"])
        priority = row["Priority"]

        is_valid, po_status = validate_po(po_qty)

        if not is_valid:
            results.append({
                "Retailer": retailer_name,
                "Region": region,
                "Priority": priority,
                "PO Qty": po_qty,
                "PO Status": po_status,
                "Forecast Qty": 0,
                "Allocated Qty": 0,
                "Unfulfilled Qty": po_qty,
                "Warehouse Block Qty": 0,
                "Selected Transporter": "None",
                "Transport Cost": 0,
                "Truck Utilization %": 0,
                "Service Level %": 0,
                "Issues": "PO validation failure",
                "Allocation Detail": {},
                "Truck Plan": []
            })
            continue

        forecast_qty = forecast_demand(po_qty, region, market_intelligence)

        total_available_stock = sum([x["stock"] for x in plants_state.values()])
        total_available_wh = sum([x["warehouse_capacity"] for x in plants_state.values()])
        theoretical_allocatable = min(forecast_qty, total_available_stock, total_available_wh)
        warehouse_block = max(0, min(forecast_qty, total_available_stock) - theoretical_allocatable)

        allocation, unfulfilled_qty = allocate_inventory(forecast_qty, plants_state)
        allocated_total = sum(allocation.values())

        truck_plan, transport_cost, utilization_pct, transporter_name = optimize_truck_loading(
            allocated_total, region, transporters_df, route_cost_df
        )

        service_level = round((allocated_total / forecast_qty) * 100, 2) if forecast_qty > 0 else 0

        issues = root_cause_analysis(
            unfulfilled_qty=unfulfilled_qty,
            transport_cost=transport_cost,
            forecast_qty=forecast_qty,
            po_qty=po_qty,
            utilization_pct=utilization_pct,
            warehouse_block=warehouse_block,
            po_status=po_status,
            transporter_name=transporter_name
        )

        results.append({
            "Retailer": retailer_name,
            "Region": region,
            "Priority": priority,
            "PO Qty": po_qty,
            "PO Status": po_status,
            "Forecast Qty": forecast_qty,
            "Allocated Qty": allocated_total,
            "Unfulfilled Qty": unfulfilled_qty,
            "Warehouse Block Qty": warehouse_block,
            "Selected Transporter": transporter_name,
            "Transport Cost": transport_cost,
            "Truck Utilization %": utilization_pct,
            "Service Level %": service_level,
            "Issues": " | ".join(issues),
            "Allocation Detail": allocation,
            "Truck Plan": truck_plan
        })

    results_df = pd.DataFrame(results)

    remaining_stock_df = pd.DataFrame([
        {
            "Plant": plant,
            "Remaining Stock": vals["stock"],
            "Remaining Warehouse Capacity": vals["warehouse_capacity"]
        }
        for plant, vals in plants_state.items()
    ])

    return results_df, remaining_stock_df

def plot_bar_chart(data, x_col, y_col, title, ylabel):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(data[x_col], data[y_col])
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45)
    st.pyplot(fig)

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.header("Scenario Controls")

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
# MASTER DATA INPUTS
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
    plants_input_df = st.data_editor(
        pd.DataFrame([
            {"Plant": "Plant_A", "Stock": 500, "Warehouse Capacity": 350},
            {"Plant": "Plant_B", "Stock": 300, "Warehouse Capacity": 250},
        ]),
        num_rows="dynamic",
        use_container_width=True
    )

with tab3:
    transporters_df = st.data_editor(
        pd.DataFrame([
            {"Transporter": "Truck_1", "Capacity": 100, "Cost Per Trip": 5000, "Regions Served": "North,East"},
            {"Transporter": "Truck_2", "Capacity": 150, "Cost Per Trip": 7000, "Regions Served": "South,West"},
            {"Transporter": "Truck_3", "Capacity": 200, "Cost Per Trip": 9000, "Regions Served": "North,South,West,East"},
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

run_button = st.button("Run Control Tower V2")

# =========================================================
# EXECUTION
# =========================================================
if run_button:
    results_df, remaining_stock_df = run_control_tower(
        retailers_df=retailers_df,
        plants_input_df=plants_input_df,
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
    avg_service_level = round(results_df["Service Level %"].mean(), 2) if not results_df.empty else 0
    avg_utilization = round(results_df["Truck Utilization %"].mean(), 2) if not results_df.empty else 0
    total_warehouse_block = int(results_df["Warehouse Block Qty"].sum()) if not results_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total PO", total_po)
    c2.metric("Forecast Qty", total_forecast)
    c3.metric("Allocated Qty", total_allocated)
    c4.metric("Transport Cost", f"₹{total_transport_cost:,.0f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Unfulfilled Qty", total_unfulfilled)
    c6.metric("Avg Service Level %", avg_service_level)
    c7.metric("Avg Truck Utilization %", avg_utilization)
    c8.metric("Warehouse Block Qty", total_warehouse_block)

    st.subheader("Order-Level Decision Table")
    st.dataframe(
        results_df[[
            "Retailer", "Region", "Priority", "PO Qty", "PO Status", "Forecast Qty",
            "Allocated Qty", "Unfulfilled Qty", "Warehouse Block Qty",
            "Selected Transporter", "Transport Cost", "Truck Utilization %",
            "Service Level %", "Issues"
        ]],
        use_container_width=True
    )

    st.subheader("Remaining Plant Position")
    st.dataframe(remaining_stock_df, use_container_width=True)

    st.subheader("Exception Dashboard")

    exception_df = results_df[
        (results_df["Unfulfilled Qty"] > 0) |
        (results_df["Warehouse Block Qty"] > 0) |
        (results_df["Truck Utilization %"] < 70) |
        (results_df["Transport Cost"] > 15000)
    ].copy()

    if exception_df.empty:
        st.success("No major exceptions. For once, supply chain chose peace.")
    else:
        st.warning("Exceptions detected")
        st.dataframe(
            exception_df[[
                "Retailer", "Region", "Priority", "Unfulfilled Qty",
                "Warehouse Block Qty", "Transport Cost",
                "Truck Utilization %", "Issues"
            ]],
            use_container_width=True
        )

    st.subheader("Charts")

    ch1, ch2 = st.columns(2)
    with ch1:
        plot_bar_chart(
            results_df,
            x_col="Retailer",
            y_col="Forecast Qty",
            title="Forecast by Retailer",
            ylabel="Forecast Qty"
        )

    with ch2:
        plot_bar_chart(
            results_df,
            x_col="Retailer",
            y_col="Allocated Qty",
            title="Allocation by Retailer",
            ylabel="Allocated Qty"
        )

    ch3, ch4 = st.columns(2)
    with ch3:
        plot_bar_chart(
            results_df,
            x_col="Retailer",
            y_col="Transport Cost",
            title="Transport Cost by Retailer",
            ylabel="Cost"
        )

    with ch4:
        plot_bar_chart(
            results_df,
            x_col="Retailer",
            y_col="Truck Utilization %",
            title="Truck Utilization by Retailer",
            ylabel="Utilization %"
        )

    st.subheader("Cost Leakage View")
    leakage_df = results_df.copy()
    leakage_df["Potential Revenue Risk Qty"] = leakage_df["Unfulfilled Qty"] + leakage_df["Warehouse Block Qty"]
    leakage_df["Cost Leakage Flag"] = leakage_df.apply(
        lambda x: "High"
        if (x["Transport Cost"] > 15000 or x["Truck Utilization %"] < 70 or x["Unfulfilled Qty"] > 0)
        else "Normal",
        axis=1
    )
    st.dataframe(
        leakage_df[[
            "Retailer", "Region", "Priority", "Transport Cost",
            "Unfulfilled Qty", "Warehouse Block Qty",
            "Potential Revenue Risk Qty", "Cost Leakage Flag"
        ]],
        use_container_width=True
    )

    st.subheader("Detailed Allocation and Truck Plan")
    for _, row in results_df.iterrows():
        with st.expander(f"{row['Retailer']} | {row['Region']} | {row['Priority']}"):
            st.write("**Allocation Detail:**", row["Allocation Detail"])
            st.write("**Truck Plan:**", row["Truck Plan"])
            st.write("**Issues:**", row["Issues"])

    csv = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Results CSV",
        data=csv,
        file_name="logistics_control_tower_v2_results.csv",
        mime="text/csv"
    )

else:
    st.info("Load your scenario and click 'Run Control Tower V2'.")
