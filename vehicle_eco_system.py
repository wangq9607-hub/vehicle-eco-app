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
            correct_password = "123"

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
    
    # 创建表 (产品表新增 take_rate 字段)
    c.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    cost REAL, revenue REAL, image_base64 TEXT, take_rate REAL DEFAULT 0.1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interfaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    data_spec TEXT, cost REAL, size_spec TEXT, image_base64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interface_product_link (
                    interface_id INTEGER, product_id INTEGER,
                    FOREIGN KEY(interface_id) REFERENCES interfaces(id),
                    FOREIGN KEY(product_id) REFERENCES products(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL UNIQUE,
                    volume INTEGER DEFAULT 10000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vehicle_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id INTEGER,
                    interface_id INTEGER, count INTEGER, location TEXT,
                    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id),
                    FOREIGN KEY(interface_id) REFERENCES interfaces(id))''')
    
    # 【无损升级脚本】：为旧的产品表添加转化率字段
    try:
        c.execute("ALTER TABLE products ADD COLUMN take_rate REAL DEFAULT 0.1")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE vehicles ADD COLUMN volume INTEGER DEFAULT 10000")
    except sqlite3.OperationalError:
        pass
        
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

init_db()

# ==========================================
# 2. 全局弹窗通知系统 (Toast)
# ==========================================
if 'success_msg' in st.session_state:
    st.toast(st.session_state['success_msg'], icon="✅")
    del st.session_state['success_msg']

# ==========================================
# 3. 左侧边栏导航
# ==========================================
st.sidebar.title("🚗 车载生态标准库")
st.sidebar.divider()
menu = st.sidebar.radio(
    "导航菜单",
    ["📦 生态产品库", "🔌 接口标准库", "🚙 车型配置管理", "📊 成本收益分析"]
)

# ==========================================
# 4. 页面内容渲染
# ==========================================

# ------------------------------------------
# 模块 1: 生态产品库 (转化率移至此处)
# ------------------------------------------
if menu == "📦 生态产品库":
    st.title("📦 生态产品库")
    view_mode = st.radio("选择视图模式", ["📋 数据总表", "🖼️ 视觉图库", "⚙️ 数据管理 (增删改)"], horizontal=True)
    st.divider()
    
    q_products = """
    SELECT p.id, p.image_base64, p.name as 产品名称, p.cost as 成本, p.revenue as 收益, 
           (p.revenue - p.cost) as 利润, (p.take_rate * 100) || '%' as 预计转化率,
           GROUP_CONCAT(DISTINCT i.name) as 适配接口类型
    FROM products p
    LEFT JOIN interface_product_link l ON p.id = l.product_id
    LEFT JOIN interfaces i ON l.interface_id = i.id
    GROUP BY p.id
    """
    df_p = get_df(q_products)

    if view_mode == "📋 数据总表":
        if not df_p.empty:
            st.dataframe(df_p.drop(columns=['id', 'image_base64']), use_container_width=True,
                         column_config={"成本": st.column_config.NumberColumn(format="¥ %.2f"),
                                        "收益": st.column_config.NumberColumn(format="¥ %.2f"),
                                        "利润": st.column_config.NumberColumn(format="¥ %.2f")})
        else:
            st.info("暂无数据，请前往【数据管理】添加。")

    elif view_mode == "🖼️ 视觉图库":
        if not df_p.empty:
            cols = st.columns(4)
            for index, row in df_p.iterrows():
                with cols[index % 4]:
                    st.markdown(f"**{row['产品名称']}**")
                    display_base64_image(row['image_base64'])
                    st.caption(f"利润: ¥{row['利润']} | 转化率: {row['预计转化率']}")
                    st.write("")
        else:
            st.info("暂无数据。")

    elif view_mode == "⚙️ 数据管理 (增删改)":
        col_add, col_edit = st.columns([1, 1])
        with col_add:
            st.subheader("➕ 新增产品")
            with st.container(border=True):
                p_name = st.text_input("产品名称", "例如：香氛胶囊 / 娱乐套装")
                col_p1, col_p2, col_p3 = st.columns(3)
                p_cost = col_p1.number_input("BOM成本 (¥)", 0.0, step=10.0)
                p_rev = col_p2.number_input("预期售价 (¥)", 0.0, step=10.0)
                p_tr = col_p3.number_input("预计转化率(%)", min_value=0.0, max_value=100.0, value=10.0, step=5.0)
                p_img_file = st.file_uploader("上传产品图片", type=['png', 'jpg', 'jpeg'])
                
                if st.button("添加产品", type="primary"):
                    img_b64 = process_image_to_base64(p_img_file)
                    run_query("INSERT INTO products (name, cost, revenue, take_rate, image_base64) VALUES (?, ?, ?, ?, ?)",
                              (p_name, p_cost, p_rev, p_tr/100.0, img_b64))
                    st.session_state['success_msg'] = f"成功新增产品：{p_name}"
                    st.rerun()

        with col_edit:
            st.subheader("✏️ 编辑 / 🗑️ 删除")
            if not df_p.empty:
                with st.container(border=True):
                    action_type = st.radio("操作类型", ["修改信息", "永久删除"], horizontal=True)
                    target_name = st.selectbox("选择目标产品", df_p['产品名称'].tolist())
                    if action_type == "修改信息":
                        target_p = df_p[df_p['产品名称'] == target_name].iloc  [0]
                        p_id = int(target_p['id'])
                        # 获取真实的 take_rate 数字用于回填
                        real_tr = get_df(f"SELECT take_rate FROM products WHERE id={p_id}").iloc  [0]['take_rate'] * 100
                        
                        with st.form(f"edit_p_form_{p_id}"):
                            new_p_name = st.text_input("产品名称", target_p['产品名称'])
                            col_e1, col_e2, col_e3 = st.columns(3)
                            new_p_cost = col_e1.number_input("BOM成本 (¥)", value=float(target_p['成本']), step=10.0)
                            new_p_rev = col_e2.number_input("预期售价 (¥)", value=float(target_p['收益']), step=10.0)
                            new_p_tr = col_e3.number_input("预计转化率(%)", min_value=0.0, max_value=100.0, value=float(real_tr), step=5.0)
                            new_p_img = st.file_uploader("更新图片 (不上传则保留原图)", type=['png', 'jpg', 'jpeg'])
                            
                            if st.form_submit_button("💾 保存修改"):
                                final_img = process_image_to_base64(new_p_img) if new_p_img else target_p['image_base64']
                                run_query("UPDATE products SET name=?, cost=?, revenue=?, take_rate=?, image_base64=? WHERE id=?",
                                          (new_p_name, new_p_cost, new_p_rev, new_p_tr/100.0, final_img, p_id))
                                st.session_state['success_msg'] = f"产品 {new_p_name} 修改成功！"
                                st.rerun()
                    else:
                        st.warning(f"您即将删除：**{target_name}**")
                        if st.button("⚠️ 确认永久删除", type="primary"):
                            del_id = int(df_p[df_p['产品名称'] == target_name]['id'].values  [0])
                            run_query("DELETE FROM products WHERE id=?", (del_id,))
                            run_query("DELETE FROM interface_product_link WHERE product_id=?", (del_id,))
                            st.session_state['success_msg'] = f"产品 {target_name} 已永久删除！"
                            st.rerun()
            else:
                st.info("暂无产品可供编辑。")

# ------------------------------------------
# 模块 2: 接口标准库 (保持不变)
# ------------------------------------------
elif menu == "🔌 接口标准库":
    st.title("🔌 接口标准库")
    view_mode = st.radio("选择视图模式", ["📋 数据总表", "🖼️ 视觉图库", "⚙️ 数据管理 (增删改)"], horizontal=True)
    st.divider()
    
    q_interfaces = """
    SELECT i.id, i.image_base64, i.name as 接口名称, i.cost as 成本, i.data_spec as 协议, 
           i.size_spec as 尺寸, GROUP_CONCAT(DISTINCT v.model_name) as 已搭载车型
    FROM interfaces i
    LEFT JOIN vehicle_configs vc ON i.id = vc.interface_id
    LEFT JOIN vehicles v ON vc.vehicle_id = v.id
    GROUP BY i.id
    """
    df_i = get_df(q_interfaces)
    products_df = get_df("SELECT id, name FROM products")
    product_options = {row['name']: row['id'] for index, row in products_df.iterrows()} if not products_df.empty else {}

    if view_mode == "📋 数据总表":
        if not df_i.empty:
            st.dataframe(df_i.drop(columns=['id', 'image_base64']), use_container_width=True,
                         column_config={"成本": st.column_config.NumberColumn(format="¥ %.2f")})
        else:
            st.info("暂无数据。")

    elif view_mode == "🖼️ 视觉图库":
        if not df_i.empty:
            cols_i = st.columns(4)
            for index, row in df_i.iterrows():
                with cols_i[index % 4]:
                    st.markdown(f"**{row['接口名称']}**")
                    display_base64_image(row['image_base64'])
                    st.caption(f"成本: ¥{row['成本']} | 尺寸: {row['尺寸']}")
                    st.write("")
        else:
            st.info("暂无数据。")

    elif view_mode == "⚙️ 数据管理 (增删改)":
        col_add, col_edit = st.columns([1, 1])
        with col_add:
            st.subheader("➕ 新增接口")
            with st.container(border=True):
                i_name = st.text_input("接口名称", "例如：Type-C拓展口")
                i_cost = st.number_input("接口硬件成本 (¥)", 0.0, step=5.0)
                i_data = st.text_input("数据协议", "USB 3.0")
                i_size = st.text_input("尺寸规格", "20mm x 10mm")
                selected_products = st.multiselect("可安装的生态产品", list(product_options.keys()))
                i_img_file = st.file_uploader("上传接口示意图", type=['png', 'jpg', 'jpeg'])
                if st.button("添加接口", type="primary"):
                    img_b64 = process_image_to_base64(i_img_file)
                    run_query("INSERT INTO interfaces (name, data_spec, cost, size_spec, image_base64) VALUES (?, ?, ?, ?, ?)",
                              (i_name, i_data, i_cost, i_size, img_b64))
                    new_i_id = get_df("SELECT last_insert_rowid() as id").iloc  [0]['id']
                    for p_name in selected_products:
                        run_query("INSERT INTO interface_product_link (interface_id, product_id) VALUES (?, ?)", 
                                  (int(new_i_id), int(product_options[p_name])))
                    st.session_state['success_msg'] = f"成功新增接口：{i_name}"
                    st.rerun()

        with col_edit:
            st.subheader("✏️ 编辑 / 🗑️ 删除")
            if not df_i.empty:
                with st.container(border=True):
                    action_type = st.radio("操作类型", ["修改信息", "永久删除"], horizontal=True, key="i_action")
                    target_name = st.selectbox("选择目标接口", df_i['接口名称'].tolist())
                    if action_type == "修改信息":
                        target_i = df_i[df_i['接口名称'] == target_name].iloc  [0]
                        i_id = int(target_i['id'])
                        curr_links = get_df(f"SELECT p.name FROM interface_product_link l JOIN products p ON l.product_id = p.id WHERE l.interface_id = {i_id}")
                        curr_linked_names = curr_links['name'].tolist() if not curr_links.empty else []
                        with st.form(f"edit_i_form_{i_id}"):
                            new_i_name = st.text_input("接口名称", target_i['接口名称'])
                            new_i_cost = st.number_input("接口硬件成本 (¥)", value=float(target_i['成本']), step=5.0)
                            new_i_data = st.text_input("数据协议", target_i['协议'])
                            new_i_size = st.text_input("尺寸规格", target_i['尺寸'])
                            new_selected_products = st.multiselect("可安装的生态产品", list(product_options.keys()), default=curr_linked_names)
                            new_i_img = st.file_uploader("更新图片 (不上传则保留原图)", type=['png', 'jpg', 'jpeg'])
                            if st.form_submit_button("💾 保存修改"):
                                final_img = process_image_to_base64(new_i_img) if new_i_img else target_i['image_base64']
                                run_query("UPDATE interfaces SET name=?, data_spec=?, cost=?, size_spec=?, image_base64=? WHERE id=?",
                                          (new_i_name, new_i_data, new_i_cost, new_i_size, final_img, i_id))
                                run_query("DELETE FROM interface_product_link WHERE interface_id=?", (i_id,))
                                for p_name in new_selected_products:
                                    run_query("INSERT INTO interface_product_link (interface_id, product_id) VALUES (?, ?)", 
                                              (i_id, int(product_options[p_name])))
                                st.session_state['success_msg'] = f"接口 {new_i_name} 修改成功！"
                                st.rerun()
                    else:
                        st.warning(f"您即将删除：**{target_name}**")
                        if st.button("⚠️ 确认永久删除", type="primary", key="del_i_btn"):
                            del_id = int(df_i[df_i['接口名称'] == target_name]['id'].values  [0])
                            run_query("DELETE FROM interfaces WHERE id=?", (del_id,))
                            run_query("DELETE FROM interface_product_link WHERE interface_id=?", (del_id,))
                            run_query("DELETE FROM vehicle_configs WHERE interface_id=?", (del_id,))
                            st.session_state['success_msg'] = f"接口 {target_name} 已永久删除！"
                            st.rerun()
            else:
                st.info("暂无接口可供编辑。")

# ------------------------------------------
# 模块 3: 车型配置管理 (移除转化率输入)
# ------------------------------------------
elif menu == "🚙 车型配置管理":
    st.title("🚙 车型配置管理")
    view_mode = st.radio("选择视图模式", ["📋 配置总表", "⚙️ 配置管理 (增删改)"], horizontal=True)
    st.divider()
    
    if view_mode == "📋 配置总表":
        q_config_full = """
        SELECT v.model_name as 车型, v.volume as 预期年销量, i.name as 接口类型, vc.location as 布置位置, 
               vc.count as 数量, GROUP_CONCAT(DISTINCT p.name) as 兼容生态产品
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

    elif view_mode == "⚙️ 配置管理 (增删改)":
        c_left, c_right = st.columns([1, 1])
        
        with c_left:
            st.subheader("➕ 新增车型与配置")
            with st.container(border=True):
                st.markdown("**1. 创建新车型**")
                col_m1, col_m2 = st.columns(2)
                new_model = col_m1.text_input("新建车型名称", placeholder="例如：Model Y")
                new_volume = col_m2.number_input("预期年销量 (辆)", min_value=1, value=100000, step=10000)
                if st.button("创建车型"):
                    try:
                        run_query("INSERT INTO vehicles (model_name, volume) VALUES (?, ?)", (new_model, new_volume))
                        st.session_state['success_msg'] = f"车型 {new_model} 创建成功！"
                        st.rerun()
                    except:
                        st.error("车型已存在")
                
                st.divider()
                st.markdown("**2. 为车型添加接口配置**")
                vehicles = get_df("SELECT * FROM vehicles")
                interfaces = get_df("SELECT * FROM interfaces")
                
                if not vehicles.empty and not interfaces.empty:
                    sel_vehicle = st.selectbox("选择车型", vehicles['model_name'])
                    v_id = int(vehicles[vehicles['model_name'] == sel_vehicle]['id'].values  [0])
                    sel_interface = st.selectbox("选择接口", interfaces['name'])
                    i_id = int(interfaces[interfaces['name'] == sel_interface]['id'].values  [0])
                    
                    col_c1, col_c2 = st.columns(2)
                    location = col_c1.text_input("布置位置", "中控台")
                    count = col_c2.number_input("接口数量", min_value=1, value=1)
                    
                    if st.button("保存配置", type="primary"):
                        run_query("INSERT INTO vehicle_configs (vehicle_id, interface_id, count, location) VALUES (?, ?, ?, ?)",
                                  (v_id, i_id, int(count), str(location)))
                        st.session_state['success_msg'] = f"已成功为 {sel_vehicle} 添加配置！"
                        st.rerun()
                else:
                    st.warning("请先在左侧菜单添加产品和接口。")

        with c_right:
            st.subheader("✏️ 编辑 / 🗑️ 删除")
            with st.container(border=True):
                action_type = st.radio("操作类型", ["修改车型基础信息", "修改单条配置", "删除单条配置", "删除整个车型"], horizontal=True, key="c_action")
                
                if action_type == "修改车型基础信息":
                    vehicles = get_df("SELECT * FROM vehicles")
                    if not vehicles.empty:
                        edit_v_name = st.selectbox("选择要修改的车型", vehicles['model_name'].tolist())
                        target_v = vehicles[vehicles['model_name'] == edit_v_name].iloc  [0]
                        with st.form("edit_v_form"):
                            new_v_name = st.text_input("车型名称", target_v['model_name'])
                            new_v_vol = st.number_input("预期年销量 (辆)", min_value=1, value=int(target_v['volume']), step=10000)
                            if st.form_submit_button("💾 保存车型修改"):
                                run_query("UPDATE vehicles SET model_name=?, volume=? WHERE id=?", (new_v_name, new_v_vol, int(target_v['id'])))
                                st.session_state['success_msg'] = "车型信息修改成功！"
                                st.rerun()

                elif action_type in ["修改单条配置", "删除单条配置"]:
                    q_conf_list = """
                    SELECT vc.id, v.model_name || ' - ' || i.name || ' (' || vc.location || ')' as display_name
                    FROM vehicle_configs vc
                    JOIN vehicles v ON vc.vehicle_id = v.id
                    JOIN interfaces i ON vc.interface_id = i.id
                    """
                    df_conf_list = get_df(q_conf_list)
                    if not df_conf_list.empty:
                        target_conf = st.selectbox("选择目标配置", df_conf_list['display_name'].tolist())
                        target_c_id = int(df_conf_list[df_conf_list['display_name'] == target_conf]['id'].values  [0])
                        
                        if action_type == "修改单条配置":
                            target_c_data = get_df(f"SELECT count, location FROM vehicle_configs WHERE id={target_c_id}").iloc  [0]
                            with st.form(f"edit_c_form_{target_c_id}"):
                                new_loc = st.text_input("修改布置位置", target_c_data['location'])
                                new_count = st.number_input("修改数量", min_value=1, value=int(target_c_data['count']))
                                if st.form_submit_button("💾 保存配置修改"):
                                    run_query("UPDATE vehicle_configs SET count=?, location=? WHERE id=?", 
                                              (new_count, new_loc, target_c_id))
                                    st.session_state['success_msg'] = "配置修改成功！"
                                    st.rerun()
                        else:
                            st.warning("确认删除这条配置吗？")
                            if st.button("⚠️ 确认删除配置", type="primary"):
                                run_query("DELETE FROM vehicle_configs WHERE id=?", (target_c_id,))
                                st.session_state['success_msg'] = "该条配置已删除！"
                                st.rerun()
                    else:
                        st.info("暂无配置数据。")
                        
                elif action_type == "删除整个车型":
                    vehicles = get_df("SELECT * FROM vehicles")
                    if not vehicles.empty:
                        del_v_name = st.selectbox("选择要删除的车型", vehicles['model_name'].tolist())
                        st.error("注意：这将清空该车型的所有接口配置！")
                        if st.button("⚠️ 确认删除车型", type="primary"):
                            del_v_id = int(vehicles[vehicles['model_name'] == del_v_name]['id'].values  [0])
                            run_query("DELETE FROM vehicles WHERE id=?", (del_v_id,))
                            run_query("DELETE FROM vehicle_configs WHERE vehicle_id=?", (del_v_id,))
                            st.session_state['success_msg'] = f"车型 {del_v_name} 及其所有配置已清空！"
                            st.rerun()

# ------------------------------------------
# 模块 4: 成本收益分析 (全新多产品收益算法)
# ------------------------------------------
elif menu == "📊 成本收益分析":
    st.title("📊 成本收益分析")
    st.caption("算法说明：总成本 = 接口单价 × 数量 × 车型销量 | 总收益 = ∑(产品单体利润 × 接口数量 × 车型销量 × 产品转化率)")
    st.divider()
    
    vehicles = get_df("SELECT * FROM vehicles")
    if not vehicles.empty:
        target_car = st.selectbox("选择分析车型", vehicles['model_name'], key="analysis_car")
        v_data = vehicles[vehicles['model_name'] == target_car].iloc  [0]
        v_id_tgt = int(v_data['id'])
        v_volume = int(v_data['volume'])
        
        # 成本计算：接口成本 * 数量 * 车型总销量
        cost_query = f"""
        SELECT SUM(i.cost * c.count * {v_volume}) as total_hw_cost
        FROM vehicle_configs c
        JOIN interfaces i ON c.interface_id = i.id
        WHERE c.vehicle_id = {v_id_tgt}
        """
        df_cost = get_df(cost_query)
        total_hw_cost = df_cost['total_hw_cost'].values  [0] or 0
        
        # 收益计算：列出该车型所有接口下，所有兼容产品的预期收益
        rev_query = f"""
        SELECT c.location as 布置位置, i.name as 接口名称, c.count as 接口数量,
               p.name as 适配生态产品,
               (p.take_rate * 100) || '%' as 产品转化率,
               (p.revenue - p.cost) as 单体利润,
               ((p.revenue - p.cost) * c.count * {v_volume} * p.take_rate) as 预期产品总收益
        FROM vehicle_configs c
        JOIN interfaces i ON c.interface_id = i.id
        JOIN interface_product_link l ON i.id = l.interface_id
        JOIN products p ON l.product_id = p.id
        WHERE c.vehicle_id = {v_id_tgt}
        """
        df_rev = get_df(rev_query)
        total_potential_profit = df_rev['预期产品总收益'].sum() if not df_rev.empty else 0
        
        # 顶部看板
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🚗 分析车型", target_car)
        col2.metric("📈 预期年销量", f"{v_volume:,} 辆")
        col3.metric("💸 硬件总投入 (BOM成本)", f"¥ {total_hw_cost:,.0f}")
        col4.metric("💰 生态总收益 (毛利)", f"¥ {total_potential_profit:,.0f}", 
                    delta=f"ROI: {((total_potential_profit/total_hw_cost)*100 if total_hw_cost>0 else 0):.1f}%")
        
        st.divider()
        st.subheader("收益潜力明细 (按产品拆解)")
        if not df_rev.empty:
            st.dataframe(df_rev, use_container_width=True, hide_index=True,
                         column_config={"预期产品总收益": st.column_config.NumberColumn(format="¥ %d"),
                                        "单体利润": st.column_config.NumberColumn(format="¥ %.2f")})
        else:
            st.info("该车型尚未配置任何带有生态产品的接口。")
    else:
        st.warning("请先在【车型配置管理】中添加车型数据")
