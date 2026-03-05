import streamlit as st
import sqlite3
import pandas as pd
import base64
import io
from PIL import Image

# ==========================================
# 0. 基础配置与工具函数
# ==========================================

st.set_page_config(page_title="车载生态标准库 Pro", layout="wide", page_icon="🚗")
DB_FILE = "vehicle_eco_std.db"


def process_image_to_base64(uploaded_file):
    """将上传的图片压缩并转换为 Base64 字符串存入数据库"""
    if uploaded_file is not None:
        try:
            img = Image.open(uploaded_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # 压缩图片，防止数据库过大
            img.thumbnail((300, 300))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            st.error(f"图片处理失败: {e}")
            return None
    return None


def display_base64_image(base64_str):
    """在界面上显示 Base64 图片"""
    if base64_str and pd.notna(base64_str):
        try:
            img_bytes = base64.b64decode(base64_str)
            st.image(img_bytes, use_container_width=True)
        except:
            st.info("图片解析失败")
    else:
        st.info("暂无图片")


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 注意：字段名改为了 image_base64
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    cost REAL, revenue REAL, image_base64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interfaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    data_spec TEXT, cost REAL, size_spec TEXT, image_base64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interface_product_link (
                    interface_id INTEGER, product_id INTEGER,
                    FOREIGN KEY(interface_id) REFERENCES interfaces(id),
                    FOREIGN KEY(product_id) REFERENCES products(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vehicle_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id INTEGER,
                    interface_id INTEGER, count INTEGER, location TEXT,
                    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
                    FOREIGN KEY(interface_id) REFERENCES interfaces(id))''')
    conn.commit()
    conn.close()


def run_query(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()


def get_df(query):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


# ==========================================
# 1. 界面逻辑
# ==========================================

init_db()
st.title("🚗 车载生态标准库管理系统 (云端版)")

tab1, tab2, tab3, tab4 = st.tabs(["📦 生态产品库", "🔌 接口标准库", "🚙 车型配置管理", "📊 成本收益分析"])

# --- Tab 1: 生态产品库 ---
with tab1:
    st.header("1. 生态产品管理")
    with st.expander("➕ 新增生态产品", expanded=False):
        c1, c2, c3 = st.columns(3)
        p_name = c1.text_input("产品名称", "例如：香氛胶囊")
        p_cost = c2.number_input("BOM成本 (¥)", 0.0, step=10.0)
        p_rev = c3.number_input("预期单体收益 (¥)", 0.0, step=10.0)
        p_img_file = st.file_uploader("上传产品图片", type=['png', 'jpg', 'jpeg'])

        if st.button("添加产品"):
            img_b64 = process_image_to_base64(p_img_file)
            run_query("INSERT INTO products (name, cost, revenue, image_base64) VALUES (?, ?, ?, ?)",
                      (p_name, p_cost, p_rev, img_b64))
            st.success(f"已添加: {p_name}")
            st.rerun()

    st.subheader("📋 产品数据总表")
    q_products = """
    SELECT p.id, p.image_base64, p.name as 产品名称, p.cost as 成本, p.revenue as 收益, 
           (p.revenue - p.cost) as 利润, GROUP_CONCAT(DISTINCT i.name) as 适配接口类型
    FROM products p
    LEFT JOIN interface_product_link l ON p.id = l.product_id
    LEFT JOIN interfaces i ON l.interface_id = i.id
    GROUP BY p.id
    """
    df_p = get_df(q_products)

    if not df_p.empty:
        st.dataframe(
            df_p.drop(columns=['id', 'image_base64']),
            use_container_width=True,
            column_config={"成本": st.column_config.NumberColumn(format="¥ %.2f"),
                           "收益": st.column_config.NumberColumn(format="¥ %.2f"),
                           "利润": st.column_config.NumberColumn(format="¥ %.2f")}
        )

        st.divider()
        st.subheader("🖼️ 产品视觉图库")
        cols = st.columns(4)
        for index, row in df_p.iterrows():
            with cols[index % 4]:
                st.markdown(f"**{row['产品名称']}**")
                display_base64_image(row['image_base64'])
                st.caption(f"利润: ¥{row['利润']} | 成本: ¥{row['成本']}")
                st.write("")

        st.divider()
        with st.expander("🗑️ 删除产品"):
            del_p_name = st.selectbox("选择要删除的产品", df_p['产品名称'].tolist())
            if st.button("确认删除产品"):
                del_id = int(df_p[df_p['产品名称'] == del_p_name]['id'].values[0])
                run_query("DELETE FROM products WHERE id=?", (del_id,))
                run_query("DELETE FROM interface_product_link WHERE product_id=?", (del_id,))
                st.success("删除成功！")
                st.rerun()

# --- Tab 2: 接口标准库 ---
with tab2:
    st.header("2. 接口标准管理")
    products_df = get_df("SELECT id, name FROM products")
    product_options = {row['name']: row['id'] for index, row in products_df.iterrows()} if not products_df.empty else {}

    with st.expander("➕ 新增接口定义", expanded=False):
        c1, c2 = st.columns(2)
        i_name = c1.text_input("接口名称", "例如：Type-C拓展口")
        i_cost = c2.number_input("接口硬件成本 (¥)", 0.0, step=5.0)
        i_data = c1.text_input("数据协议", "USB 3.0")
        i_size = c2.text_input("尺寸规格", "20mm x 10mm")
        i_img_file = st.file_uploader("上传接口示意图", type=['png', 'jpg', 'jpeg'])
        selected_products = st.multiselect("可安装的生态产品 (多选)", list(product_options.keys()))

        if st.button("添加接口"):
            img_b64 = process_image_to_base64(i_img_file)
            run_query("INSERT INTO interfaces (name, data_spec, cost, size_spec, image_base64) VALUES (?, ?, ?, ?, ?)",
                      (i_name, i_data, i_cost, i_size, img_b64))
            new_i_id = get_df("SELECT last_insert_rowid() as id").iloc[0]['id']
            for p_name in selected_products:
                run_query("INSERT INTO interface_product_link (interface_id, product_id) VALUES (?, ?)",
                          (int(new_i_id), int(product_options[p_name])))
            st.success(f"已添加接口: {i_name}")
            st.rerun()

    st.subheader("📋 接口数据总表")
    q_interfaces = """
    SELECT i.id, i.image_base64, i.name as 接口名称, i.cost as 成本, i.data_spec as 协议, 
           i.size_spec as 尺寸, GROUP_CONCAT(DISTINCT v.model_name) as 已搭载车型
    FROM interfaces i
    LEFT JOIN vehicle_configs vc ON i.id = vc.interface_id
    LEFT JOIN vehicles v ON vc.vehicle_id = v.id
    GROUP BY i.id
    """
    df_i = get_df(q_interfaces)

    if not df_i.empty:
        st.dataframe(
            df_i.drop(columns=['id', 'image_base64']),
            use_container_width=True,
            column_config={"成本": st.column_config.NumberColumn(format="¥ %.2f")}
        )

        st.divider()
        st.subheader("🖼️ 接口视觉图库")
        cols_i = st.columns(4)
        for index, row in df_i.iterrows():
            with cols_i[index % 4]:
                st.markdown(f"**{row['接口名称']}**")
                display_base64_image(row['image_base64'])
                st.caption(f"成本: ¥{row['成本']} | 尺寸: {row['尺寸']}")
                st.write("")

        st.divider()
        with st.expander("🗑️ 删除接口"):
            del_i_name = st.selectbox("选择要删除的接口", df_i['接口名称'].tolist())
            if st.button("确认删除接口"):
                del_id = int(df_i[df_i['接口名称'] == del_i_name]['id'].values[0])
                run_query("DELETE FROM interfaces WHERE id=?", (del_id,))
                run_query("DELETE FROM interface_product_link WHERE interface_id=?", (del_id,))
                run_query("DELETE FROM vehicle_configs WHERE interface_id=?", (del_id,))
                st.success("删除成功！")
                st.rerun()

# --- Tab 3: 车型配置管理 ---
with tab3:
    st.header("3. 车型配置")
    c_left, c_right = st.columns([1, 2])

    with c_left:
        st.info("🛠️ 新增操作区")
        new_model = st.text_input("新建车型名称", placeholder="例如：Model Y 2026款")
        if st.button("创建车型"):
            try:
                run_query("INSERT INTO vehicles (model_name) VALUES (?)", (new_model,))
                st.success("创建成功")
                st.rerun()
            except:
                st.error("车型已存在")

        st.divider()
        vehicles = get_df("SELECT * FROM vehicles")
        interfaces = get_df("SELECT * FROM interfaces")

        if not vehicles.empty and not interfaces.empty:
            sel_vehicle = st.selectbox("选择车型", vehicles['model_name'])
            v_id = int(vehicles[vehicles['model_name'] == sel_vehicle]['id'].values[0])
            sel_interface = st.selectbox("选择接口", interfaces['name'])
            i_id = int(interfaces[interfaces['name'] == sel_interface]['id'].values[0])
            count = st.number_input("数量", min_value=1, value=1)
            location = st.text_input("布置位置", "中控台")

            if st.button("保存配置"):
                run_query("INSERT INTO vehicle_configs (vehicle_id, interface_id, count, location) VALUES (?, ?, ?, ?)",
                          (v_id, i_id, int(count), str(location)))
                st.success("配置已保存！")
                st.rerun()

        st.divider()
        st.error("🗑️ 删除操作区")
        del_type = st.radio("选择删除类型", ["删除单条配置", "删除整个车型"])

        if del_type == "删除整个车型" and not vehicles.empty:
            del_v_name = st.selectbox("选择要删除的车型", vehicles['model_name'].tolist())
            if st.button("确认删除车型"):
                del_v_id = int(vehicles[vehicles['model_name'] == del_v_name]['id'].values[0])
                run_query("DELETE FROM vehicles WHERE id=?", (del_v_id,))
                run_query("DELETE FROM vehicle_configs WHERE vehicle_id=?", (del_v_id,))
                st.success("车型及相关配置已清空！")
                st.rerun()

        elif del_type == "删除单条配置":
            q_conf_list = """
            SELECT vc.id, v.model_name || ' - ' || i.name || ' (' || vc.location || ')' as display_name
            FROM vehicle_configs vc
            JOIN vehicles v ON vc.vehicle_id = v.id
            JOIN interfaces i ON vc.interface_id = i.id
            """
            df_conf_list = get_df(q_conf_list)
            if not df_conf_list.empty:
                del_conf_name = st.selectbox("选择要删除的配置", df_conf_list['display_name'].tolist())
                if st.button("确认删除配置"):
                    del_c_id = int(df_conf_list[df_conf_list['display_name'] == del_conf_name]['id'].values[0])
                    run_query("DELETE FROM vehicle_configs WHERE id=?", (del_c_id,))
                    st.success("配置已删除！")
                    st.rerun()

    with c_right:
        st.subheader("📋 车型配置总表")
        q_config_full = """
        SELECT v.model_name as 车型, i.name as 接口类型, vc.location as 布置位置, vc.count as 数量,
               GROUP_CONCAT(DISTINCT p.name) as 兼容生态产品
        FROM vehicle_configs vc
        JOIN vehicles v ON vc.vehicle_id = v.id
        JOIN interfaces i ON vc.interface_id = i.id
        LEFT JOIN interface_product_link l ON i.id = l.interface_id
        LEFT JOIN products p ON l.product_id = p.id
        GROUP BY vc.id ORDER BY v.model_name
        """
        df_config = get_df(q_config_full)
        if not df_config.empty:
            filter_car = st.multiselect("筛选车型", df_config['车型'].unique(), default=df_config['车型'].unique())
            st.dataframe(df_config[df_config['车型'].isin(filter_car)], use_container_width=True, hide_index=True)
        else:
            st.info("暂无配置数据")

# --- Tab 4: 成本收益分析 ---
with tab4:
    st.header("4. 成本收益分析")
    vehicles = get_df("SELECT * FROM vehicles")
    if not vehicles.empty:
        target_car = st.selectbox("选择分析车型", vehicles['model_name'], key="analysis_car")
        v_id_tgt = int(vehicles[vehicles['model_name'] == target_car]['id'].values[0])

        df_cost = get_df(
            f"SELECT SUM(i.cost * c.count) as total_hw_cost FROM vehicle_configs c JOIN interfaces i ON c.interface_id = i.id WHERE c.vehicle_id = {v_id_tgt}")
        total_hw_cost = df_cost['total_hw_cost'].values[0] or 0

        rev_query = f"""
        SELECT c.location as 布置位置, i.name as 接口名称, c.count as 数量,
               MAX(p.revenue - p.cost) as 最大单体利润, p.name as 最佳推荐产品,
               (MAX(p.revenue - p.cost) * c.count) as 潜在总利润
        FROM vehicle_configs c
        JOIN interfaces i ON c.interface_id = i.id
        LEFT JOIN interface_product_link l ON i.id = l.interface_id
        LEFT JOIN products p ON l.product_id = p.id
        WHERE c.vehicle_id = {v_id_tgt} GROUP BY c.id
        """
        df_rev = get_df(rev_query)
        total_potential_profit = df_rev['潜在总利润'].sum() if not df_rev.empty else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("🚗 分析车型", target_car)
        col2.metric("💸 接口硬件投入 (成本)", f"¥ {total_hw_cost:,.2f}")
        col3.metric("💰 潜在生态利润 (收益)", f"¥ {total_potential_profit:,.2f}",
                    delta=f"ROI: {((total_potential_profit / total_hw_cost) * 100 if total_hw_cost > 0 else 0):.1f}%")

        st.divider()
        st.subheader("收益潜力明细")
        st.dataframe(df_rev, use_container_width=True, hide_index=True)
    else:
        st.warning("请先配置车型数据")