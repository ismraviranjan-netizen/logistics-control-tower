import streamlit as st
import pandas as pd
from math import ceil

st.set_page_config(page_title="Mini Logistics Control Tower", layout="wide")

st.title("Mini Logistics Control Tower")
st.caption("A simple simulation of forecasting, inventory allocation, truck planning, alerts, and reporting.")

# -------------------------------------------------
# DEFAULT MASTER DATA
# -------------------------------------------------
default_plants = {
    "Plant_A": {"stock": 500},
    "Plant_B": {"stock": 300}
}

default_transporters = [
    {"name": "Truck_1", "capacity": 100, "cost_per_trip": 5000},
    {"name": "Truck_2", "capacity": 150, "cost_per_trip": 7000},
    {"name": "Truck_3", "capacity": 200, "cost_per_trip": 9000},
]

default_market_intelligence = {
    "North": 1.10,
    "South": 0.95,
    "West": 1.20,
    "East": 1.05
}

# -------------------------------------------------
# FUNCTIONS
# -------------------------------------------------
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
        available = details["stock"]
        allocated = min(available, remaining)

        if allocated > 0:
            allocation[plant_name] = allocated
            plants_data[plant_name]["stock"] -= allocated
            remaining -= allocated

        if remaining == 0:
            break

    return allocation, remaining

def optimize_truck_loading(total_qty, transporters):
    if total_qty <= 0:
        return [], 0, 0

    # sort by cost efficiency
    sorted_trucks = sorted(
        transporters,
        key=lambda x: x["cost_per_trip"] / x["capacity"]
    )

    best_plan = None
    best_cost = float("inf")
    best_utilization = 0

    for truck in sorted_trucks:
        trips = ceil(total_qty / truck["capacity"])
        moved_qty = total_qty
        total_capacity_used = trips * truck["capacity"]
        utilization = moved_qty / total_capacity_used if total_capacity_used > 0 else 0
        cost = trips * truck["cost_per_trip"]

        plan = [{
            "truck": truck["name"],
            "capacity_per_trip": truck["capacity"],
            "trips": trips,
            "qty_moved": moved_qty,
            "total_capacity_used": total_capacity_used,
            "utilization_pct": round(utilization * 100, 2),
            "cost": cost
        }]

        if cost < best_cost:
            best_cost = cost
            best_plan = plan
            best_utilization = utilization

    return best_plan, best_cost, round(best_utilization * 100, 2)

def root_cause_analysis(unfulfilled_qty, transport_cost, forecast_qty, po_qty, utilization_pct):
    issues = []

    if unfulfilled_qty > 0:
        issues.append("Stock shortage at plant level")

    if forecast_qty > po_qty * 1.15:
        issues.append("Demand spike from market intelligence")

    if transport_cost > 15000:
        issues.append("High transportation cost")

    if utilization_pct < 70:
        issues.append("Low truck utilization")

    if not issues:
        issues.append("No major issue detected")

    return issues

def run_control_tower(retailers_df, plants_input, transporters_input, market_intelligence):
    plants = {k: {"stock": v["stock"]} for k, v in plants_input.items()}
    results = []

    for _, row in retailers_df.iterrows():
        retailer_name = row["Retailer"]
        region = row["Region"]
        po_qty = int(row["PO_Qty"])

        is_valid, status = validate_po(po_qty)

        if not is_valid:
            results.append({
                "Retailer": retailer_name,
                "Region": region,
                "PO Qty": po_qty,
                "PO Status": status,
                "Forecast Qty": 0,
                "Allocated Qty": 0,
                "Unfulfilled Qty": po_qty,
                "Transport Cost": 0,
                "Truck Utilization %": 0,
                "Issues": "PO validation failure",
                "Allocation Detail": {},
                "Truck Plan": []
            })
            continue

        forecast_qty = forecast_demand(po_qty, region, market_intelligence)
        allocation, unfulfilled_qty = allocate_inventory(forecast_qty, plants)
        allocated_total = sum(allocation.values())

        truck_plan, transport_cost, utilization_pct = optimize_truck_loading(
            allocated_total, transporters_input
        )

        issues = root_cause_analysis(
            unfulfilled_qty, transport_cost, forecast_qty, po_qty, utilization_pct
        )

        results.append({
            "Retailer": retailer_name,
            "Region": region,
            "PO Qty": po_qty,
            "PO Status": status,
            "Forecast Qty": forecast_qty,
            "Allocated Qty": allocated_total,
            "Unfulfilled Qty": unfulfilled_qty,
            "Transport Cost": transport_cost,
            "Truck Utilization %": utilization_pct,
            "Issues": " | ".join(issues),
            "Allocation Detail": allocation,
            "Truck Plan": truck_plan
        })

    remaining_stock = pd.DataFrame([
        {"Plant": plant, "Remaining Stock": data["stock"]}
        for plant, data in plants.items()
    ])

    results_df = pd.DataFrame(results)
    return results_df, remaining_stock

# -------------------------------------------------
# SIDEBAR INPUTS
# -------------------------------------------------
st.sidebar.header("Master Inputs")

plant_a_stock = st.sidebar.number_input("Plant_A Stock", min_value=0, value=500, step=10)
plant_b_stock = st.sidebar.number_input("Plant_B Stock", min_value=0, value=300, step=10)

truck_1_capacity = st.sidebar.number_input("Truck_1 Capacity", min_value=1, value=100, step=10)
truck_1_cost = st.sidebar.number_input("Truck_1 Cost/Trip", min_value=1, value=5000, step=500)

truck_2_capacity = st.sidebar.number_input("Truck_2 Capacity", min_value=1, value=150, step=10)
truck_2_cost = st.sidebar.number_input("Truck_2 Cost/Trip", min_value=1, value=7000, step=500)

truck_3_capacity = st.sidebar.number_input("Truck_3 Capacity", min_value=1, value=200, step=10)
truck_3_cost = st.sidebar.number_input("Truck_3 Cost/Trip", min_value=1, value=9000, step=500)

north_multiplier = st.sidebar.number_input("North Demand Multiplier", min_value=0.5, max_value=2.0, value=1.10, step=0.05)
south_multiplier = st.sidebar.number_input("South Demand Multiplier", min_value=0.5, max_value=2.0, value=0.95, step=0.05)
west_multiplier = st.sidebar.number_input("West Demand Multiplier", min_value=0.5, max_value=2.0, value=1.20, step=0.05)
east_multiplier = st.sidebar.number_input("East Demand Multiplier", min_value=0.5, max_value=2.0, value=1.05, step=0.05)

plants_input = {
    "Plant_A": {"stock": plant_a_stock},
    "Plant_B": {"stock": plant_b_stock}
}

transporters_input = [
    {"name": "Truck_1", "capacity": truck_1_capacity, "cost_per_trip": truck_1_cost},
    {"name": "Truck_2", "capacity": truck_2_capacity, "cost_per_trip": truck_2_cost},
    {"name": "Truck_3", "capacity": truck_3_capacity, "cost_per_trip": truck_3_cost},
]

market_intelligence = {
    "North": north_multiplier,
    "South": south_multiplier,
    "West": west_multiplier,
    "East": east_multiplier
}

# -------------------------------------------------
# RETAILER INPUT TABLE
# -------------------------------------------------
st.subheader("Retailer Orders")

default_retailers_df = pd.DataFrame([
    {"Retailer": "Retailer_1", "Region": "North", "PO_Qty": 180},
    {"Retailer": "Retailer_2", "Region": "South", "PO_Qty": 220},
    {"Retailer": "Retailer_3", "Region": "West", "PO_Qty": 140},
    {"Retailer": "Retailer_4", "Region": "East", "PO_Qty": 100},
])

retailers_df = st.data_editor(
    default_retailers_df,
    num_rows="dynamic",
    use_container_width=True
)

run_button = st.button("Run Control Tower")

# -------------------------------------------------
# EXECUTION
# -------------------------------------------------
if run_button:
    results_df, remaining_stock_df = run_control_tower(
        retailers_df, plants_input, transporters_input, market_intelligence
    )

    st.subheader("KPI Summary")
    col1, col2, col3, col4 = st.columns(4)

    total_po = int(results_df["PO Qty"].sum())
    total_forecast = int(results_df["Forecast Qty"].sum())
    total_allocated = int(results_df["Allocated Qty"].sum())
    total_transport_cost = int(results_df["Transport Cost"].sum())

    service_level = round((total_allocated / total_forecast) * 100, 2) if total_forecast > 0 else 0
    avg_utilization = round(results_df["Truck Utilization %"].mean(), 2) if len(results_df) > 0 else 0

    col1.metric("Total PO Qty", total_po)
    col2.metric("Forecast Qty", total_forecast)
    col3.metric("Allocated Qty", total_allocated)
    col4.metric("Transport Cost", f"₹{total_transport_cost:,}")

    col5, col6 = st.columns(2)
    col5.metric("Service Level %", service_level)
    col6.metric("Avg Truck Utilization %", avg_utilization)

    st.subheader("Order-Level Results")
    st.dataframe(
        results_df[
            [
                "Retailer", "Region", "PO Qty", "PO Status", "Forecast Qty",
                "Allocated Qty", "Unfulfilled Qty", "Transport Cost",
                "Truck Utilization %", "Issues"
            ]
        ],
        use_container_width=True
    )

    st.subheader("Remaining Plant Stock")
    st.dataframe(remaining_stock_df, use_container_width=True)

    st.subheader("Detailed Allocation and Truck Plan")

    for _, row in results_df.iterrows():
        with st.expander(f"{row['Retailer']} | {row['Region']}"):
            st.write("**Allocation Detail:**", row["Allocation Detail"])
            st.write("**Truck Plan:**", row["Truck Plan"])

    csv = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Results CSV",
        data=csv,
        file_name="control_tower_results.csv",
        mime="text/csv"
    )

else:
    st.info("Set inputs and click 'Run Control Tower' to simulate the architecture.")
