"""
Dashboard: Streamlit App — NYC Ride-Hailing Analytics 2025
Bao gồm:
1. 📊 Tổng quan (Overview KPIs)
2. 🗺️ Heatmap theo Giờ (Density map)
3. 📈 Dự báo Demand AI (XGBoost Top 5 Zones)
4. 🔍 Phân tích SQL (Spark SQL 5 queries)
5. 💰 Doanh Thu & Tiền Tip (Revenue & Tips)
6. 🚏 Cung Đường Vàng O-D (Top Routes & Inter-Borough)
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import os
import json
import plotly.express as px
import folium
from folium.plugins import HeatMap

st.set_page_config(
    page_title="NYC Ride-Hailing Analytics 2025",
    page_icon="🚖",
    layout="wide"
)

DATA_PATH = os.getenv("DATA_PATH", r"D:\nyc_data\processed\demand_features_2025.parquet")
SQL_DIR = os.getenv("SQL_RESULTS_DIR", r"D:\nyc_data\output\sql_results")
MODELS_DIR = os.getenv("MODELS_DIR", r"D:\nyc_data\output\models")
PLOTS_DIR = os.getenv("PLOTS_DIR", r"D:\nyc_data\output\plots")

# ---- Sidebar ----
st.sidebar.title("🚖 NYC Ride-Hailing")
st.sidebar.markdown("**Hệ Thống Phân Tích & Dự Báo Dữ Liệu Lớn 2025**")
page = st.sidebar.radio("Chọn nghiệp vụ phân tích:", [
    "📊 Tổng quan Hệ thống",
    "💰 Doanh Thu & Tiền Tip",
    "🚏 Cung Đường Vàng (O-D)",
    "📈 Dự Báo AI (Top 5 Zones)",
    "🔍 Phân Tích Spark SQL",
    "🗺️ Heatmap theo Giờ"
])

@st.cache_data
def load_demand():
    if not os.path.exists(DATA_PATH):
        return None
    return pd.read_parquet(DATA_PATH)

df = load_demand()

# ==================== 1. TỔNG QUAN ====================
if page == "📊 Tổng quan Hệ thống":
    st.title("🚖 NYC Ride-Hailing Big Data Dashboard 2025")
    st.markdown("Hệ thống phân tích giao dịch gọi xe taxi quy mô lớn trên nền tảng **HDFS, PySpark, XGBoost và MLflow**.")

    if df is None:
        st.warning("⚠️ Chưa tìm thấy file Parquet xử lý. Vui lòng kiểm tra lại pipeline!")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    total_trips = df['demand_count'].sum()
    c1.metric("Tổng lượt phục vụ (Cleaned)", f"{total_trips:,.0f} chuyến")
    c2.metric("Số Khu Vực Phân Tích", f"{df['PULocationID'].nunique()} Zones")
    c3.metric("Số Giờ Dữ Liệu", f"{len(df):,} khung giờ")
    c4.metric("Nhu Cầu Trung Bình/Giờ", f"{df['demand_count'].mean():.1f} chuyến")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⏰ Nhu cầu trung bình theo 24 giờ")
        hourly = df.groupby("pickup_hour")["demand_count"].mean().reset_index()
        hourly.columns = ["Giờ trong ngày", "Số chuyến trung bình"]
        fig_hour = px.bar(hourly, x="Giờ trong ngày", y="Số chuyến trung bình", color="Số chuyến trung bình",
                          color_continuous_scale="Viridis", text_auto=".1f")
        st.plotly_chart(fig_hour, use_container_width=True)

    with col2:
        st.subheader("📅 Nhu cầu theo ngày trong tuần")
        dow_names = {1: "Chủ nhật", 2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7"}
        weekly = df.groupby("pickup_dow")["demand_count"].sum().reset_index()
        weekly["Thứ"] = weekly["pickup_dow"].map(dow_names)
        fig_week = px.pie(weekly, values="demand_count", names="Thứ", title="Thị phần chuyến đi theo ngày trong tuần",
                          color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_week, use_container_width=True)

# ==================== 2. DOANH THU & TIỀN TIP ====================
elif page == "💰 Doanh Thu & Tiền Tip":
    st.title("💰 Phân Tích Tài Chính: Doanh Thu, Giá Cước & Tiền Tip")
    st.markdown("Khai phá hành vi chi tiêu, tỷ lệ boa tiền tip và hiệu quả kinh tế trên mỗi dặm vận chuyển.")

    h_path = os.path.join(SQL_DIR, "q6_revenue_tips", "revenue_by_hour.csv")
    p_path = os.path.join(SQL_DIR, "q6_revenue_tips", "revenue_by_payment.csv")

    if os.path.exists(h_path) and os.path.exists(p_path):
        h_df = pd.read_csv(h_path)
        p_df = pd.read_csv(p_path)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Giá cước trung bình", f"${h_df['avg_fare'].mean():.2f}")
        k2.metric("Tiền Tip trung bình", f"${h_df['avg_tip'].mean():.2f}")
        k3.metric("Tỷ lệ Tip (Thẻ tín dụng)", f"{h_df['avg_tip_pct'].mean():.1f}%")
        k4.metric("Doanh thu / Dặm xe", f"${h_df['avg_fare_per_mile'].mean():.2f}/mile")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 Tỷ lệ tiền tip & Doanh thu theo khung giờ")
            fig = px.line(h_df, x="pickup_hour", y=["avg_tip_pct", "avg_fare_per_mile"],
                          labels={"value": "Giá trị ($ hoặc %)", "pickup_hour": "Khung giờ trong ngày", "variable": "Chỉ số"},
                          title="Tỷ lệ Tip (%) vs Doanh thu trên mỗi dặm ($)", markers=True)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("💳 Cơ cấu Phương thức Thanh toán")
            fig_p = px.pie(p_df, names="payment_name", values="trip_count", title="Tỷ lệ chuyến đi theo phương thức thanh toán",
                           hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)

        st.subheader("📋 Bảng tổng hợp số liệu chi tiết theo 24 giờ")
        st.dataframe(h_df, use_container_width=True)
    else:
        st.warning("⚠️ Chưa có bảng kết quả doanh thu. Vui lòng chạy script nghiệp vụ trước!")

# ==================== 3. CUNG ĐƯỜNG VÀNG (O-D) ====================
elif page == "🚏 Cung Đường Vàng (O-D)":
    st.title("🚏 Phân Tích Cung Đường Vàng & Luồng Di Chuyển Liên Quận")
    st.markdown("Xác định các hành lang di chuyển mật độ cao nhất thành phố New York (Sân bay JFK/LaGuardia ➡️ Trung tâm).")

    c_path = os.path.join(SQL_DIR, "q7_od_corridors", "top_corridors.csv")
    b_path = os.path.join(SQL_DIR, "q7_od_corridors", "borough_matrix.csv")

    if os.path.exists(c_path) and os.path.exists(b_path):
        c_df = pd.read_csv(c_path)
        b_df = pd.read_csv(b_path)

        st.subheader("🏆 Top 10 Tuyến Đường Đông Khách Nhất New York City")
        c_df["Tuyến đường (Origin ➡️ Destination)"] = c_df["pu_zone"] + " ➡️ " + c_df["do_zone"]
        st.dataframe(c_df[["Tuyến đường (Origin ➡️ Destination)", "pu_borough", "do_borough", "trip_count", "avg_distance", "avg_fare", "total_revenue"]].head(10), use_container_width=True)

        st.divider()

        centroids_path = os.path.join(r"D:\nyc_data\zone", "taxi_zones_centroids.csv")
        routes_json_path = os.path.join(r"D:\nyc_data\zone", "top_corridors_routes.json")

        if os.path.exists(centroids_path):
            st.subheader("🗺️ Bản Đồ Tuyến Đường Di Chuyển Thực Tế (Origin ➡️ Destination)")

            tab_sat, tab_plotly = st.tabs([
                "🛰️ Bản Đồ Vệ Tinh & Lộ Trình Đường Bộ Thật (Esri Satellite & Road Network)",
                "📊 Bản Đồ Trực Quan Vector (Plotly)"
            ])

            with tab_sat:
                st.caption("💡 *Ảnh vệ tinh chụp thật thành phố New York (độ phân giải cao) kết hợp lộ trình xe chạy uốn lượn thực tế qua mạng lưới đại lộ, đường cao tốc và cầu vượt (OSRM Routing). Click vào từng tuyến đường hoặc điểm dừng để xem chi tiết.*")

                m_od = folium.Map(location=[40.765, -73.965], zoom_start=12, tiles=None)

                # 1. Esri Satellite (Ảnh vệ tinh thật)
                folium.TileLayer(
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri World Imagery",
                    name="🛰️ Vệ Tinh Chân Thực (Esri Satellite)",
                    overlay=False,
                    control=True
                ).add_to(m_od)

                # 2. Esri Street Map (Đường phố chi tiết)
                folium.TileLayer(
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri Streets",
                    name="🛣️ Đường Phố Chi Tiết (Esri Streets)",
                    overlay=False,
                    control=True
                ).add_to(m_od)

                # 3. OpenStreetMap
                folium.TileLayer(
                    tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr="OpenStreetMap",
                    name="🗺️ Giao Thông Đô Thị (OpenStreetMap)",
                    overlay=False,
                    control=True
                ).add_to(m_od)

                if os.path.exists(routes_json_path):
                    with open(routes_json_path, "r", encoding="utf-8") as f:
                        cached_routes = json.load(f)

                    route_group = folium.FeatureGroup(name="🛣️ Lộ Trình Xe Chạy Thực Tế (Top Corridors)")
                    pin_group = folium.FeatureGroup(name="📍 Điểm Đón (Xanh Lá) & Trả (Xanh Dương)")

                    colors = ["#ff1744", "#ff9100", "#d500f9", "#00e676", "#2979ff", "#ff0055", "#00b0ff", "#76ff03", "#f50057", "#651fff"]

                    for idx, r in enumerate(cached_routes[:12]):
                        coords = r["road_coords"]
                        c = colors[idx % len(colors)]
                        w = max(4, min(9, int(r["trip_count"] / 3000)))

                        popup_html = f"""
                        <div style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.5; width: 230px;">
                            <h4 style="margin: 0 0 6px 0; color: {c};">🚖 {r['pu_zone']} ➡️ {r['do_zone']}</h4>
                            <b>🚗 Cự ly đường bộ:</b> {r['road_distance_km']} km<br>
                            <b>⏱️ Thời gian di chuyển:</b> ~{r['road_duration_min']} phút<br>
                            <b>📊 Số chuyến phục vụ:</b> {r['trip_count']:,} chuyến<br>
                            <b>💰 Tổng doanh thu:</b> ${r['total_revenue']:,.0f}<br>
                            <b>💵 Cước bình quân:</b> ${r['avg_fare']:.2f}
                        </div>
                        """
                        folium.PolyLine(
                            locations=coords,
                            color=c,
                            weight=w,
                            opacity=0.9,
                            tooltip=f"Tuyến #{idx+1}: {r['pu_zone']} ➡️ {r['do_zone']} ({r['trip_count']:,} chuyến)",
                            popup=folium.Popup(popup_html, max_width=320)
                        ).add_to(route_group)

                        # Origin Pin
                        folium.CircleMarker(
                            location=[r["pu_lat"], r["pu_lon"]],
                            radius=6,
                            color="#00e676",
                            weight=2,
                            fill=True,
                            fill_color="#00e676",
                            fill_opacity=0.9,
                            tooltip=f"Điểm đón: {r['pu_zone']}"
                        ).add_to(pin_group)

                        # Destination Pin
                        folium.CircleMarker(
                            location=[r["do_lat"], r["do_lon"]],
                            radius=6,
                            color="#2979ff",
                            weight=2,
                            fill=True,
                            fill_color="#2979ff",
                            fill_opacity=0.9,
                            tooltip=f"Điểm trả: {r['do_zone']}"
                        ).add_to(pin_group)

                    route_group.add_to(m_od)
                    pin_group.add_to(m_od)

                folium.LayerControl(position="topright", collapsed=False).add_to(m_od)
                components.html(m_od._repr_html_(), height=580)

            with tab_plotly:
                import plotly.graph_objects as go
                centroids_map = pd.read_csv(centroids_path).set_index("LocationID")
                top10_map = c_df.head(10).copy()
                top10_map["pu_lat"] = top10_map["PULocationID"].map(centroids_map["lat"])
                top10_map["pu_lon"] = top10_map["PULocationID"].map(centroids_map["lon"])
                top10_map["do_lat"] = top10_map["DOLocationID"].map(centroids_map["lat"])
                top10_map["do_lon"] = top10_map["DOLocationID"].map(centroids_map["lon"])

                ScatterMap = getattr(go, "Scattermap", getattr(go, "Scattermapbox", None))
                map_key = "map" if hasattr(go, "Scattermap") else "mapbox"

                fig_routes = go.Figure()
                for _, r in top10_map.iterrows():
                    if pd.notna(r["pu_lat"]) and pd.notna(r["do_lat"]):
                        fig_routes.add_trace(ScatterMap(
                            mode="lines",
                            lon=[r["pu_lon"], r["do_lon"]],
                            lat=[r["pu_lat"], r["do_lat"]],
                            line=dict(width=max(3, min(8, r["trip_count"] / 2500)), color="#ff1744"),
                            hoverinfo="text",
                            text=f"Tuyến: {r['pu_zone']} ➡️ {r['do_zone']}<br>Lưu lượng: {r['trip_count']:,} chuyến<br>Doanh thu: ${r['total_revenue']:,.0f}",
                            showlegend=False
                        ))

                fig_routes.add_trace(ScatterMap(
                    mode="markers+text",
                    lon=top10_map["pu_lon"],
                    lat=top10_map["pu_lat"],
                    marker=dict(size=12, color="#00e676"),
                    hoverinfo="text",
                    text=top10_map["pu_zone"],
                    name="Điểm đón (Origin)",
                    showlegend=True
                ))

                fig_routes.add_trace(ScatterMap(
                    mode="markers",
                    lon=top10_map["do_lon"],
                    lat=top10_map["do_lat"],
                    marker=dict(size=10, color="#2979ff"),
                    hoverinfo="text",
                    text=top10_map["do_zone"],
                    name="Điểm trả (Destination)",
                    showlegend=True
                ))

                layout_dict = {
                    map_key: dict(
                        style="open-street-map",
                        zoom=11,
                        center={"lat": 40.755, "lon": -73.965}
                    ),
                    "margin": {"r": 0, "t": 0, "l": 0, "b": 0},
                    "height": 520,
                    "legend": dict(yanchor="top", y=0.98, xanchor="left", x=0.02, bgcolor="rgba(255,255,255,0.8)")
                }
                fig_routes.update_layout(**layout_dict)
                st.plotly_chart(fig_routes, use_container_width=True)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Top 10 Hành lang theo Tổng doanh thu ($)")
            top_rev = c_df.sort_values(by="total_revenue", ascending=False).head(10)
            fig_rev = px.bar(top_rev, x="total_revenue", y="Tuyến đường (Origin ➡️ Destination)", orientation="h",
                             color="total_revenue", color_continuous_scale="Sunset", title="Doanh thu mang lại từ từng tuyến ($)")
            fig_rev.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_rev, use_container_width=True)

        with col2:
            st.subheader("🏙️ Ma trận luồng di chuyển liên quận")
            top_boro = b_df.head(8)
            fig_boro = px.bar(top_boro, x="total_trips", y=top_boro["pu_borough"] + " ➡️ " + top_boro["do_borough"], orientation="h",
                              color="pct_trips", color_continuous_scale="Teal", title="Các luồng di chuyển chủ đạo (%)")
            fig_boro.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_boro, use_container_width=True)
    else:
        st.warning("⚠️ Chưa có dữ liệu O-D Corridors!")

# ==================== 4. DỰ BÁO MACHINE LEARNING ====================
elif page == "📈 Dự Báo AI (Top 5 Zones)":
    st.title("📈 Dự Báo Nhu Cầu Gọi Xe Đa Khu Vực (XGBoost Regressor)")
    st.markdown("Mô hình AI dự báo nhu cầu đặt xe trước theo từng giờ cho các khu vực trọng điểm của New York.")

    summary_file = os.path.join(MODELS_DIR, "multizone_results.json")
    if os.path.exists(summary_file):
        with open(summary_file, "r", encoding="utf-8") as f:
            models_data = json.load(f)

        zone_options = {f"Zone {k} — {v['name']}": k for k, v in models_data.items()}
        selected_zone_label = st.selectbox("Chọn khu vực trọng điểm để xem dự báo:", list(zone_options.keys()))
        selected_zone_id = zone_options[selected_zone_label]
        info = models_data[selected_zone_id]

        m1, m2, m3 = st.columns(3)
        m1.metric("Sai số RMSE (Chuyến/giờ)", f"{info['rmse']:.2f}")
        m2.metric("Sai số Tuyệt đối MAE", f"{info['mae']:.2f}")
        m3.metric("Độ sai lệch MAPE", f"{info['mape']:.1f}%", delta="Rất Tốt" if info['mape'] < 25 else "Bình thường")

        st.subheader("📉 Biểu đồ so sánh: Nhu cầu Thực tế vs AI Dự báo (Từng giờ)")
        chart_df = pd.DataFrame({
            "Khung giờ kiểm thử": range(len(info["actual"])),
            "Thực tế (Ground Truth)": info["actual"],
            "XGBoost Dự Báo (AI Predicted)": info["pred"]
        }).set_index("Khung giờ kiểm thử")
        st.line_chart(chart_df)

        plot_path = os.path.join(PLOTS_DIR, f"xgboost_pred_zone_{selected_zone_id}.png")
        if os.path.exists(plot_path):
            st.image(plot_path, caption=f"Đồ thị dự báo chi tiết cho {info['name']}", use_container_width=True)

        st.divider()

        # ---- Bảng So Sánh Thực Nghiệm Đa Mô Hình ----
        st.subheader("🔬 Bảng Đánh Giá Hiệu Năng Mô Hình Học Máy (Model Benchmark)")
        st.caption("So sánh thực nghiệm giữa mô hình cơ sở (Linear Regression), mô hình đóng bao (Random Forest) và mô hình đề xuất (XGBoost Regressor) trên tập dữ liệu kiểm thử độc lập:")
        benchmark_file = os.path.join(MODELS_DIR, "model_benchmark_comparison.csv")
        if os.path.exists(benchmark_file):
            bm_df = pd.read_csv(benchmark_file)
            bm_df.columns = ["Mô hình thử nghiệm", "RMSE (Sai số toàn phương)", "MAE (Sai số tuyệt đối)", "Hệ số xác định R²", "Thời gian huấn luyện (giây)"]
            st.dataframe(bm_df, use_container_width=True)
        else:
            st.info("Chưa có file benchmark đa mô hình.")

        st.divider()

        # ---- Công cụ Gợi ý Điều phối Tài xế ----
        st.subheader("🚕 Hệ Thống Gợi Ý Điều Phối Đội Xe Thông Minh (Smart Driver Dispatch Advisor)")
        st.caption("Ứng dụng kết quả dự báo AI để phân bổ đội xe tối ưu cho các khu vực trọng điểm, giải quyết bài toán thiếu hụt xe vào giờ cao điểm và giảm thiểu tỷ lệ chuyến xe rỗng (empty cruising trips).")

        col_d1, col_d2 = st.columns([2, 1])
        with col_d1:
            fleet_size = st.slider("🚗 Nhập tổng số xe sẵn sàng điều phối trong mạng lưới:", min_value=200, max_value=3000, value=1200, step=50)
        with col_d2:
            weather_sim = st.selectbox("🌧️ Điều kiện thời tiết giả định:", ["Bình thường / Nắng ráo", "Mưa to (Nhu cầu tăng 25%)", "Bão tuyết (Nhu cầu tăng 45%)"])

        weather_multiplier = 1.0
        if "Mưa to" in weather_sim:
            weather_multiplier = 1.25
        elif "Bão tuyết" in weather_sim:
            weather_multiplier = 1.45

        dispatch_rows = []
        for zid, zdata in models_data.items():
            avg_pred = float(np.mean(zdata["pred"])) * weather_multiplier
            dispatch_rows.append({
                "Zone_ID": zid,
                "Zone_Name": zdata["name"],
                "Predicted_Demand": avg_pred
            })
        
        disp_df = pd.DataFrame(dispatch_rows)
        total_pred = disp_df["Predicted_Demand"].sum()
        disp_df["Demand_Share"] = (disp_df["Predicted_Demand"] / total_pred)
        disp_df["Allocated_Drivers"] = (disp_df["Demand_Share"] * fleet_size).round().astype(int)
        disp_df["Coverage_Ratio"] = (disp_df["Allocated_Drivers"] / disp_df["Predicted_Demand"]).map(lambda x: f"{x:.1f}x (Đáp ứng đủ)" if x >= 0.9 else f"{x:.1f}x (Cảnh báo thiếu xe)")

        disp_col1, disp_col2 = st.columns([3, 2])
        with disp_col1:
            st.markdown(f"**Bảng Phân Bổ Xe Cho {len(disp_df)} Khu Vực Nóng Nhất (Tổng đội xe: {fleet_size:,} xe):**")
            disp_view = disp_df.copy()
            disp_view.columns = ["Mã Zone", "Tên Khu Vực", "Nhu cầu dự báo (cuốc/h)", "Tỷ trọng (%)", "Số xe khuyến nghị điều động", "Tỷ lệ đáp ứng cung-cầu"]
            disp_view["Tỷ trọng (%)"] = (disp_view["Tỷ trọng (%)"] * 100).round(1).astype(str) + "%"
            disp_view["Nhu cầu dự báo (cuốc/h)"] = disp_view["Nhu cầu dự báo (cuốc/h)"].round(1)
            st.dataframe(disp_view, use_container_width=True)

        with disp_col2:
            fig_disp = px.pie(disp_df, names="Zone_Name", values="Allocated_Drivers",
                              title=f"Tỷ lệ phân bổ {fleet_size:,} xe điều phối",
                              color_discrete_sequence=px.colors.sequential.Inferno)
            st.plotly_chart(fig_disp, use_container_width=True)
    else:
        st.info("Chưa có kết quả mô hình đa khu vực.")

# ==================== 5. PHÂN TÍCH SPARK SQL ====================
elif page == "🔍 Phân Tích Spark SQL":
    st.title("🔍 Kết Quả Phân Tích Nghiệp Vụ Spark SQL")
    queries = {
        "q1_top10_zones": "🏆 Top 10 Zone bận nhất",
        "q2_hourly_pattern": "⏰ Phân bố theo giờ",
        "q3_weekday_pattern": "📅 Phân bố theo ngày trong tuần",
        "q4_rush_vs_offpeak": "🚦 Rush Hour vs Off-Peak",
        "q5_holiday_effect": "🎉 Tác động ngày lễ",
    }
    selected = st.selectbox("Chọn câu truy vấn:", list(queries.values()))
    name = [k for k, v in queries.items() if v == selected][0]
    path = os.path.join(SQL_DIR, name)

    if os.path.exists(path):
        csv_files = [f for f in os.listdir(path) if f.endswith(".csv")]
        if csv_files:
            result = pd.read_csv(os.path.join(path, csv_files[0]))
            st.dataframe(result, use_container_width=True)
            col = result.columns[1] if len(result.columns) > 1 else result.columns[0]
            st.bar_chart(result.set_index(result.columns[0])[col])
    else:
        st.info(f"Chưa có kết quả: {name}")

# ==================== 6. BẢN ĐỒ TƯƠNG TÁC & HEATMAP ====================
elif page == "🗺️ Heatmap theo Giờ":
    st.title("🗺️ Bản Đồ Địa Lý Tương Tác: Mật Độ Nhu Cầu Theo Khung Giờ")
    st.markdown("Nhúng bản đồ số New York City (OpenStreetMap) phân tích lưu lượng gọi xe theo thời gian thực và vị trí địa lý.")

    centroids_path = os.path.join(r"D:\nyc_data\zone", "taxi_zones_centroids.csv")
    if not os.path.exists(centroids_path):
        st.warning("Chưa có file tọa độ taxi_zones_centroids.csv!")
        st.stop()

    centroids = pd.read_csv(centroids_path)

    if df is not None:
        c_filter1, c_filter2 = st.columns([2, 1])
        with c_filter1:
            hour = st.slider("🕒 Chọn khung giờ xem mật độ đón xe (0h - 23h):", 0, 23, 18)
        with c_filter2:
            borough_list = ["Tất cả các quận"] + sorted(list(centroids["Borough"].dropna().unique()))
            selected_boro = st.selectbox("🏙️ Lọc theo Quận (Borough):", borough_list)

        # Lọc dữ liệu theo giờ
        h_df = df[df["pickup_hour"] == hour]
        zone_demand = h_df.groupby("PULocationID")["demand_count"].sum().reset_index()
        zone_demand.columns = ["LocationID", "Số lượt đón xe"]

        # Ghép với tọa độ
        geo_df = pd.merge(centroids, zone_demand, on="LocationID", how="inner")

        if selected_boro != "Tất cả các quận":
            geo_df = geo_df[geo_df["Borough"] == selected_boro]

        # Metric tóm tắt
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Khung Giờ Đang Xem", f"{hour}:00 - {hour}:59")
        m2.metric("Tổng Lượt Đón Trong Giờ", f"{geo_df['Số lượt đón xe'].sum():,}")
        m3.metric("Số Điểm Đón Hoạt Động", f"{len(geo_df)} Zones")
        top_zone_now = geo_df.sort_values(by="Số lượt đón xe", ascending=False).iloc[0] if len(geo_df) > 0 else None
        if top_zone_now is not None:
            m4.metric("Khu Vực Đông Nhất", f"{top_zone_now['Zone']}", f"{top_zone_now['Số lượt đón xe']:,} chuyến")

        if len(geo_df) > 0:
            st.subheader(f"📍 Bản đồ nhiệt tương tác tại New York City ({hour}:00)")

            tab_sat_heat, tab_plotly_scatter = st.tabs([
                "🛰️ Bản Đồ Vệ Tinh Nhiệt Thực Tế (Esri Satellite & Folium Heatmap)",
                "📊 Bản Đồ Điểm Trực Quan (Plotly Scatter)"
            ])

            with tab_sat_heat:
                st.caption("💡 *Ảnh vệ tinh chụp thật thành phố New York (độ phân giải cao) kết hợp hiệu ứng nhiệt phát sáng (Thermal Gradient) thể hiện mật độ tập trung xe đón khách lúc này. Có thể đổi qua lại giữa bản đồ Vệ Tinh và Đường Phố ở góc phải trên.*")
                m_heat = folium.Map(location=[40.75, -73.97], zoom_start=11, tiles=None)

                # 1. Esri Satellite
                folium.TileLayer(
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri World Imagery",
                    name="🛰️ Vệ Tinh Chân Thực (Esri Satellite)",
                    overlay=False,
                    control=True
                ).add_to(m_heat)

                # 2. Esri Streets
                folium.TileLayer(
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri Streets",
                    name="🛣️ Đường Phố Chi Tiết (Esri Streets)",
                    overlay=False,
                    control=True
                ).add_to(m_heat)

                # 3. OpenStreetMap
                folium.TileLayer(
                    tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                    attr="OpenStreetMap",
                    name="🗺️ Giao Thông Đô Thị (OpenStreetMap)",
                    overlay=False,
                    control=True
                ).add_to(m_heat)

                # HeatMap Layer
                heat_data = [[row["lat"], row["lon"], float(row["Số lượt đón xe"])] for _, row in geo_df.iterrows() if pd.notna(row["lat"]) and pd.notna(row["lon"])]
                HeatMap(
                    heat_data,
                    name="🔥 Lớp Mật Độ Nhu Cầu (Heatmap)",
                    min_opacity=0.35,
                    max_zoom=14,
                    radius=19,
                    blur=15,
                    gradient={0.2: "#00e5ff", 0.4: "#00e676", 0.7: "#ffea00", 1.0: "#ff1744"}
                ).add_to(m_heat)

                # Top 10 Hotspots
                top10_heat = geo_df.sort_values(by="Số lượt đón xe", ascending=False).head(10)
                heat_markers = folium.FeatureGroup(name="🏆 Top 10 Điểm Nóng Nhất (Hotspots)")
                for rank, (_, r) in enumerate(top10_heat.iterrows(), 1):
                    p_html = f"""
                    <div style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.5; width: 200px;">
                        <b style="color: #d50000;">#{rank}. {r['Zone']}</b><br>
                        <b>Quận:</b> {r['Borough']}<br>
                        <b>Lưu lượng lúc {hour}h:</b> <span style="color: #d50000; font-weight: bold;">{r['Số lượt đón xe']:,} chuyến</span>
                    </div>
                    """
                    folium.CircleMarker(
                        location=[r["lat"], r["lon"]],
                        radius=8,
                        color="#ff1744",
                        weight=3,
                        fill=True,
                        fill_color="#ffea00",
                        fill_opacity=0.9,
                        tooltip=f"#{rank} {r['Zone']} ({r['Borough']}): {r['Số lượt đón xe']:,} lượt",
                        popup=folium.Popup(p_html, max_width=250)
                    ).add_to(heat_markers)
                heat_markers.add_to(m_heat)

                folium.LayerControl(position="topright", collapsed=False).add_to(m_heat)
                components.html(m_heat._repr_html_(), height=650)

            with tab_plotly_scatter:
                scatter_map_func = getattr(px, "scatter_map", getattr(px, "scatter_mapbox", None))
                style_param = "map_style" if hasattr(px, "scatter_map") else "mapbox_style"
                map_kwargs = {
                    "lat": "lat",
                    "lon": "lon",
                    "size": "Số lượt đón xe",
                    "color": "Số lượt đón xe",
                    "hover_name": "Zone",
                    "hover_data": {
                        "Borough": True,
                        "Số lượt đón xe": True,
                        "LocationID": True,
                        "lat": False,
                        "lon": False
                    },
                    "color_continuous_scale": "Turbo",
                    "size_max": 35,
                    "zoom": 10.5,
                    "center": {"lat": 40.75, "lon": -73.97},
                    style_param: "open-street-map",
                    "height": 650
                }
                fig_map = scatter_map_func(geo_df, **map_kwargs)
                fig_map.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
                st.plotly_chart(fig_map, use_container_width=True)

            # Bảng xếp hạng chi tiết
            st.subheader(f"🏆 Top 10 Khu Vực Nóng Nhất Lúc {hour}:00")
            st.dataframe(
                geo_df.sort_values(by="Số lượt đón xe", ascending=False)[["Zone", "Borough", "Số lượt đón xe", "lat", "lon"]].head(10),
                use_container_width=True
            )
        else:
            st.info("Không có dữ liệu cho bộ lọc đã chọn.")
