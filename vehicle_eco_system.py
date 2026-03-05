import streamlit as st
import sqlite3
import pandas as pd
import base64
import io
from PIL import Image

# ==========================================
# 0. 密码保护逻辑
# ==========================================
def check_password():
    def password_entered():
        try:
            correct_password = st.secrets["app_password"]
        except Exception:
            correct_password = "123"  # 本地测试默认密码

        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 请输入内部访问密码", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 请输入内部访问密码", type="password", on_change=password_entered, key="password")
        st.error("❌ 密码错误，请重试。")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# 1. 基础配置与工具函数
# ==========================================
st.set_page_config(page_title="车载生态标准库 Pro", layout="wide", page_icon="🚗")
DB_FILE = "vehicle_eco_std.db"

def process_image_to_base64(uploaded_file):
    if uploaded_file is not None:
        try:
            img = Image.open(uploaded_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((300, 300))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            return None
    return None

def display_base64_image(base64_str):
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
# 2. 界面逻辑
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
        col_edit, col_del = st.columns(2)
        
        with col_edit:
            with st.expander("✏️ 编辑产品信息"):
                edit_p_name = st.selectbox("选择要修改的产品", df_p['产品名称'].tolist(), key="edit_p_select")
                if edit_p_name:
                    target_p = df_p[df_p['产品名称'] == edit_p_name].iloc  [0]
                    p_id = int(target_p['id'])
                    
                    # 【修复核心】：给每个输入框加上基于 ID 的动态 key，防止数据卡死
                    with st.form(f"edit_p_form_{p_id}"):
                        new_p_name = st.text_input("产品名称", target_p['产品名称'], key=f"ep_name_{p_id}")
                        new_p_cost = st.number_input("BOM成本 (¥)", value=float(target_p['成本']), step=10.0, key=f"ep_cost_{p_id}")
                        new_p_rev = st.number_input("预期单体收益 (¥)", value=float(target_p['收益']), step=10.0, key=f"ep_rev_{p_id}")
                        new_p_img = st.file_uploader("更新图片 (不上传则保留原图)", type=['png', 'jpg', 'jpeg'], key=f"ep_img_{p_id}")
                        
                        if st.form_submit_button("保存修改"):
                            final_img = process_image_to_base64(new_p_img) if new_p_img else target_p['image_base64']
                            run_query("UPDATE products SET name=?, cost=?, revenue=?, image_base64=? WHERE id=?",
                                      (new_p_name, new_p_cost, new_p_rev, final_img, p_id))
                            st.success("修改成功！")
                            st.rerun()

        with col_del:
            with st.expander("🗑️ 删除产品"):
                del_p_name = st.selectbox("选择要删除的产品", df_p['产品名称'].tolist(), key="del_p_select")
                if st.button("确认删除产品"):
                    del_id = int(df_p[df_p['产品名称'] == del_p_name]['id'].values  [0])
                    run_query("DELETE FROM products WHERE id=?", (del_id,))
                    run_query("DELETE FROM interface_product_link WHERE product_id=?", (del_id,))
                    st.success("删除成功！")
                    st.rerun()

        st.divider()
        st.subheader("🖼️ 产品视觉图库")
        cols = st.columns(4)
        for index, row in df_p.iterrows():
            with cols[index % 4]:
                st.markdown(f"**{row['产品名称']}**")
                display_base64_image(row['image_base64'])
                st.caption(f"利润: ¥{row['利润']} | 成本: ¥{row['成本']}")
                st.write("")

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
            new_i_id = get_df("SELECT last_insert_rowid() as id").iloc  [0]['id']
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
        col_edit_i, col_del_i = st.columns(2)
        
        with col_edit_i:
            with st.expander("✏️ 编辑接口信息"):
                edit_i_name = st.selectbox("选择要修改的接口", df_i['接口名称'].tolist(), key="edit_i_select")
                if edit_i_name:
                    target_i = df_i[df_i['接口名称'] == edit_i_name].iloc  [0]
                    i_id = int(target_i['id'])
                    
                    curr_links = get_df(f"SELECT p.name FROM interface_product_link l JOIN products p ON l.product_id = p.id WHERE l.interface_id = {i_id}")
                    curr_linked_names = curr_links['name'].tolist() if not curr_links.empty else []
                    
                    # 【修复核心】：加入动态 key
                    with st.form(f"edit_i_form_{i_id}"):
                        new_i_name = st.text_input("接口名称", target_i['接口名称'], key=f"ei_name_{i_id}")
                        new_i_cost = st.number_input("接口硬件成本 (¥)", value=float(target_i['成本']), step=5.0, key=f"ei_cost_{i_id}")
                        new_i_data = st.text_input("数据协议", target_i['协议'], key=f"ei_data_{i_id}")
                        new_i_size = st.text_input("尺寸规格", target_i['尺寸'], key=f"ei_size_{i_id}")
                        new_selected_products = st.multiselect("可安装的生态产品", list(product_options.keys()), default=curr_linked_names, key=f"ei_prod_{i_id}")
                        new_i_img = st.file_uploader("更新图片 (不上传则保留原图)", type=['png', 'jpg', 'jpeg'], key=f"ei_img_{i_id}")
                        
                        if st.form_submit_button("保存修改"):
                            final_img = process_image_to_base64(new_i_img) if new_i_img else target_i['image_base64']
                            run_query("UPDATE interfaces SET name=?, data_spec=?, cost=?, size_spec=?, image_base64=? WHERE id=?",
                                      (new_i_name, new_i_data, new_i_cost, new_i_size, final_img, i_id))
                            run_query("DELETE FROM interface_product_link WHERE interface_id=?", (i_id,))
                            for p_name in new_selected_products:
                                run_query("INSERT INTO interface_product_link (interface_id, product_id) VALUES (?, ?)", 
                                          (i_id, int(product_options[p_name])))
                            st.success("修改成功！")
                            st.rerun()

        with col_del_i:
            with st.expander("🗑️ 删除接口"):
                del_i_name = st.selectbox("选择要删除的接口", df_i['接口名称'].tolist(), key="del_i_select")
                if st.button("确认删除接口"):
                    del_id = int(df_i[df_i['接口名称'] == del_i_name]['id'].values  [0])
                    run_query("DELETE FROM interfaces WHERE id=?", (del_id,))
                    run_query("DELETE FROM interface_product_link WHERE interface_id=?", (del_id,))
                    run_query("DELETE FROM vehicle_configs WHERE interface_id=?", (del_id,))
                    st.success("删除成功！")
                    st.rerun()

        st.divider()
        st.subheader("🖼️ 接口视觉图库")
        cols_i = st.columns(4)
        for index, row in df_i.iterrows():
            with cols_i[index % 4]:
                st.markdown(f"**{row['接口名称']}**")
                display_base64_image(row['image_base64'])
                st.caption(f"成本: ¥{row['成本']} | 尺寸: {row['尺寸']}")
                st.write("")

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
            v_id = int(vehicles[vehicles['model_name'] == sel_vehicle]['id'].values  [0])
            sel_interface = st.selectbox("选择接口", interfaces['name'])
            i_id = int(interfaces[interfaces['name'] == sel_interface]['id'].values  [0])
            count = st.number_input("数量", min_value=1, value=1)
            location = st.text_input("布置位置", "中控台")
            
            if st.button("保存配置"):
                run_query("INSERT INTO vehicle_configs (vehicle_id, interface_id, count, location) VALUES (?, ?, ?, ?)",
                          (v_id, i_id, int(count), str(location)))
                st.success("配置已保存！")
                st.rerun()
                
        st.divider()
        st.warning("✏️ 编辑操作区")
        q_conf_list = """
        SELECT vc.id, v.model_name || ' - ' || i.name || ' (' || vc.location || ')' as display_name
        FROM vehicle_configs vc
        JOIN vehicles v ON vc.vehicle_id = v.id
        JOIN interfaces i ON vc.interface_id = i.id
        """
        df_conf_list = get_df(q_conf_list)
        
        if not df_conf_list.empty:
            edit_conf_name = st.selectbox("选择要修改的配置", df_conf_list['display_name'].tolist(), key="edit_c_select")
            if edit_conf_name:
                target_c_id = int(df_conf_list[df_conf_list['display_name'] == edit_conf_name]['id'].values  [0])
                target_c_data = get_df(f"SELECT count, location FROM vehicle_configs WHERE id={target_c_id}").iloc  [0]
                
                # 【修复核心】：加入动态 key
                with st.form(f"edit_c_form_{target_c_id}"):
                    new_count = st.number_input("修改数量", min_value=1, value=int(target_c_data['count']), key=f"ec_count_{target_c_id}")
                    new_loc = st.text_input("修改布置位置", target_c_data['location'], key=f"ec_loc_{target_c_id}")
                    if st.form_submit_button("保存配置修改"):
                        run_query("UPDATE vehicle_configs SET count=?, location=? WHERE id=?", (new_count, new_loc, target_c_id))
                        st.success("修改成功！")
                        st.rerun()

        st.divider()
        st.error("🗑️ 删除操作区")
        del_type = st.radio("选择删除类型", ["删除单条配置", "删除整个车型"])
        
        if del_type == "删除整个车型" and not vehicles.empty:
            del_v_name = st.selectbox("选择要删除的车型", vehicles['model_name'].tolist())
            if st.button("确认删除车型"):
                del_v_id = int(vehicles[vehicles['model_name'] == del_v_name]['id'].values  [0])
                run_query("DELETE FROM vehicles WHERE id=?", (del_v_id,))
                run_query("DELETE FROM vehicle_configs WHERE vehicle_id=?", (del_v_id,))
                st.success("车型及相关配置已清空！")
                st.rerun()
                
        elif del_type == "删除单条配置" and not df_conf_list.empty:
            del_conf_name = st.selectbox("选择要删除的配置", df_conf_list['display_name'].tolist())
            if st.button("确认删除配置"):
                del_c_id = int(df_conf_list[df_conf_list['display_name'] == del_conf_name]['id'].values  [0])
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
        v_id_tgt = int(vehicles[vehicles['model_name'] == target_car]['id'].values  [0])
        
        df_cost = get_df(f"SELECT SUM(i.cost * c.count) as total_hw_cost FROM vehicle_configs c JOIN interfaces i ON c.interface_id = i.id WHERE c.vehicle_id = {v_id_tgt}")
        total_hw_cost = df_cost['total_hw_cost'].values  [0] or 0
        
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
                    delta=f"ROI: {((total_potential_profit/total_hw_cost)*100 if total_hw_cost>0 else 0):.1f}%")
        
        st.divider()
        st.subheader("收益潜力明细")
        st.dataframe(df_rev, use_container_width=True, hide_index=True)
    else:
        st.warning("请先配置车型数据")
