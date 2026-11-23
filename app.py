import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# Set page layout to wide for a nice dashboard look
st.set_page_config(layout="wide")

# 1. Load Data from Google Sheets
@st.cache_data(ttl=86400, show_spinner=False) 
def load_data():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    
    sheet_id = st.secrets["my_secure_sheet_id"]
    sh = gc.open_by_key(sheet_id) 
 
    ws_cluster = sh.worksheet("Cluster Profile")
    df_cluster = pd.DataFrame(ws_cluster.get_all_values()[1:], columns=ws_cluster.get_all_values()[0]) 
    
    ws_fca = sh.worksheet("FCA Profile") 
    df_fca = pd.DataFrame(ws_fca.get_all_values()[1:], columns=ws_fca.get_all_values()[0]) 
    
    ws_commodity = sh.worksheet("Commodity Profile") 
    df_commodity = pd.DataFrame(ws_commodity.get_all_values()[1:], columns=ws_commodity.get_all_values()[0]) 
    
    ws_cdp = sh.worksheet("CDP CLUSTER PROFILE")
    df_cdp = pd.DataFrame(ws_cdp.get_all_values()[1:], columns=ws_cdp.get_all_values()[0])

    for d in [df_cluster, df_fca, df_commodity, df_cdp]:
        d.columns = [str(c).strip() for c in d.columns]
        rename_map = {
            'Province': 'PROVINCE', 'Municipality': 'MUNICIPALITY', 'Barangay': 'BARANGAY',
            'Total members': 'Total Members', 'TOTAL MEMBERS': 'Total Members',
            'Male ': 'Male', 'Female ': 'Female'
        }
        d.rename(columns=rename_map, inplace=True)

    if 'NAME OF CLUSTER' in df_cluster.columns: df_cluster = df_cluster[df_cluster['NAME OF CLUSTER'].astype(str).str.strip() != '']
    if 'NAME OF FCA MEMBERS' in df_fca.columns: df_fca = df_fca[df_fca['NAME OF FCA MEMBERS'].astype(str).str.strip() != '']
    if 'NAME OF FCA MEMBERS' in df_commodity.columns: df_commodity = df_commodity[df_commodity['NAME OF FCA MEMBERS'].astype(str).str.strip() != '']

    if 'NAME OF CLUSTER' in df_cluster.columns: df_cluster['NAME OF CLUSTER'] = df_cluster['NAME OF CLUSTER'].astype(str).str.strip()
    if 'NAME OF CLUSTER' in df_fca.columns: df_fca['NAME OF CLUSTER'] = df_fca['NAME OF CLUSTER'].astype(str).str.strip()
    if 'NAME OF FCA MEMBERS' in df_fca.columns: df_fca['NAME OF FCA MEMBERS'] = df_fca['NAME OF FCA MEMBERS'].astype(str).str.strip()
    if 'NAME OF FCA MEMBERS' in df_commodity.columns: df_commodity['NAME OF FCA MEMBERS'] = df_commodity['NAME OF FCA MEMBERS'].astype(str).str.strip()

    df_fca['_FCA_ID'] = range(len(df_fca))

    df = df_fca.copy()

    if 'NAME OF CLUSTER' in df.columns and 'NAME OF CLUSTER' in df_cluster.columns:
        cluster_cols_to_keep = ['NAME OF CLUSTER'] + [col for col in df_cluster.columns if col not in df.columns]
        df_cluster_clean = df_cluster[cluster_cols_to_keep].drop_duplicates(subset=['NAME OF CLUSTER']) 
        df = pd.merge(df, df_cluster_clean, on='NAME OF CLUSTER', how='left', suffixes=('', '_cluster'))
        
        for col in ['PROVINCE', 'MUNICIPALITY', 'BARANGAY']:
            if col in df.columns and f'{col}_cluster' in df.columns:
                df[col] = df[col].replace('', pd.NA).fillna(df[f'{col}_cluster'])
        df.drop(columns=[c for c in df.columns if c.endswith('_cluster')], inplace=True)

    if 'NAME OF FCA MEMBERS' in df.columns and 'NAME OF FCA MEMBERS' in df_commodity.columns:
        comm_cols_to_keep = ['NAME OF FCA MEMBERS'] + [col for col in df_commodity.columns if col not in df.columns]
        df_commodity_clean = df_commodity[comm_cols_to_keep]
        df = pd.merge(df, df_commodity_clean, on='NAME OF FCA MEMBERS', how='left', suffixes=('', '_comm'))
        df.drop(columns=[c for c in df.columns if c.endswith('_comm')], inplace=True)

    if 'PROVINCE' in df.columns: df['PROVINCE'] = df['PROVINCE'].astype(str).str.strip().str.title()
    if 'MUNICIPALITY' in df.columns: df['MUNICIPALITY'] = df['MUNICIPALITY'].astype(str).str.strip().str.title()
    
    if 'PROVINCE' in df_cdp.columns: df_cdp['PROVINCE'] = df_cdp['PROVINCE'].astype(str).str.strip().str.title()

    math_cols = ['Production Area\n (Has.)', 'Production Area\n (Trees, Heads)', 'Male', 'Female', 'Total Members']
    for col in math_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)

    return df, df_cdp

with st.spinner("Fetching live data from Google Sheets..."):
    df, df_cdp = load_data()


# ==========================================
# --- VALIDATION HELPER ---
# ==========================================
def get_valid_mask(series):
    return ~series.astype(str).str.strip().str.lower().isin(['', 'nan', 'none', 'n/a', '<na>'])

def get_text_card(title, target_df, col_name, subset_col):
    if col_name not in target_df.columns or subset_col not in target_df.columns:
        return ""
    
    valid_mask = get_valid_mask(target_df[subset_col])
    clean_df = target_df[valid_mask].copy()
    
    clean_df = clean_df.drop_duplicates(subset=[subset_col])
    clean_df[col_name] = clean_df[col_name].fillna("")
    clean_df[col_name] = clean_df[col_name].astype(str).str.strip()
    
    clean_df.loc[clean_df[col_name].str.lower().isin(['', 'none', 'nan', 'na', 'n/a', '<na>']), col_name] = 'To Be Verified'
    clean_df[col_name] = clean_df[col_name].apply(lambda x: x if x == 'To Be Verified' else x.title())
    
    counts = clean_df[col_name].value_counts()
    
    lines_html = ""
    for label, count in counts.items():
        lines_html += f"<div style='margin-bottom: 20px; text-align: center;'><h2 style='margin:0; font-size: 26px; color: #222; line-height: 1;'>{count:,}</h2><p style='margin:0; font-size: 15px; color: #555; font-weight: bold;'>{label}</p></div>"
        
    return f"""
    <div style="border: 1px solid #ccc; border-radius: 5px; background-color: #ffffff; height: 380px; overflow-y: auto;">
        <div style="padding: 8px; text-align: center; border-bottom: 1px solid #ccc; background-color: #fafafa; margin-bottom: 15px; position: sticky; top: 0; z-index: 10;">
            <p style="margin: 0; font-size: 11px; color: #222; font-weight: bold; text-transform: uppercase;">{title}</p>
        </div>
        <div style="padding: 0 15px 15px 15px;">
            {lines_html}
        </div>
    </div>
    """


# ==========================================
# --- TWIN SYNC FOR DASHBOARD & TABLE FILTERS ---
# ==========================================
sync_keys = ['prov', 'muni', 'clus', 'fca', 'comm', 'search']

for k in sync_keys:
    if f"m_{k}_dash" not in st.session_state: st.session_state[f"m_{k}_dash"] = "All" if k != 'search' else ""
    if f"m_{k}_table" not in st.session_state: st.session_state[f"m_{k}_table"] = "All" if k != 'search' else ""

def sync_from_dash():
    for k in sync_keys: st.session_state[f"m_{k}_table"] = st.session_state[f"m_{k}_dash"]

def sync_from_table():
    for k in sync_keys: st.session_state[f"m_{k}_dash"] = st.session_state[f"m_{k}_table"]

def render_main_filters(prefix, sync_func):
    st.write(f"**Main Filters** *(Selections are perfectly synced with the {'Data Tables' if prefix == 'dash' else 'Dashboard Overview'} tab)*")
    mf1, mf2, mf3, mf4, mf5, mf6 = st.columns(6)
    
    temp_df = df.copy()
    
    with mf1:
        opts_prov = ["All"] + list(temp_df['PROVINCE'].dropna().unique())
        st.selectbox("Province:", opts_prov, key=f"m_prov_{prefix}", on_change=sync_func)
        curr_prov = st.session_state.get(f"m_prov_{prefix}", "All")
        if curr_prov != "All": temp_df = temp_df[temp_df['PROVINCE'] == curr_prov]
        
    with mf2:
        opts_muni = ["All"] + list(temp_df['MUNICIPALITY'].dropna().unique())
        st.selectbox("Municipality:", opts_muni, key=f"m_muni_{prefix}", on_change=sync_func)
        curr_muni = st.session_state.get(f"m_muni_{prefix}", "All")
        if curr_muni != "All": temp_df = temp_df[temp_df['MUNICIPALITY'] == curr_muni]

    with mf3:
        opts_clus = ["All"] + list(temp_df['NAME OF CLUSTER'].dropna().unique())
        st.selectbox("Cluster:", opts_clus, key=f"m_clus_{prefix}", on_change=sync_func)
        curr_clus = st.session_state.get(f"m_clus_{prefix}", "All")
        if curr_clus != "All": temp_df = temp_df[temp_df['NAME OF CLUSTER'] == curr_clus]

    with mf4:
        opts_fca = ["All"] + list(temp_df['NAME OF FCA MEMBERS'].dropna().unique())
        st.selectbox("FCA Member:", opts_fca, key=f"m_fca_{prefix}", on_change=sync_func)
        curr_fca = st.session_state.get(f"m_fca_{prefix}", "All")
        if curr_fca != "All": temp_df = temp_df[temp_df['NAME OF FCA MEMBERS'] == curr_fca]

    with mf5:
        opts_comm = ["All"] + list(temp_df['COMMODITY'].dropna().unique())
        st.selectbox("Commodity:", opts_comm, key=f"m_comm_{prefix}", on_change=sync_func)
        curr_comm = st.session_state.get(f"m_comm_{prefix}", "All")
        if curr_comm != "All": temp_df = temp_df[temp_df['COMMODITY'] == curr_comm]

    with mf6:
        master_list = pd.concat([
            temp_df['NAME OF CLUSTER'], temp_df['PROVINCE'], temp_df['MUNICIPALITY'],
            temp_df['NAME OF BIG-BROTHER'], temp_df['NAME OF FCA MEMBERS'],
            temp_df['Status of Profiling'], temp_df['COMMODITY']
        ]).dropna().unique()
        opts_search = [""] + sorted(list(master_list))
        st.selectbox("Global Search:", opts_search, key=f"m_search_{prefix}", on_change=sync_func)
        
    curr_search = st.session_state.get(f"m_search_{prefix}", "")
    if curr_search != "":
        s_val = str(curr_search).strip().lower()
        mask = temp_df.astype(str).apply(lambda x: x.str.strip().str.lower() == s_val).any(axis=1)
        temp_df = temp_df[mask]
        
    return temp_df


# 2. APP TITLE & REFRESH BUTTON
t_col1, t_col2 = st.columns([8, 1])
with t_col1: st.title("Department of Agriculture")
with t_col2: 
    if st.button("Refresh Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.header("Reports")

# ==========================================
# --- REORDERED TABS ---
# ==========================================
dash_tab, prov_tab, table_tab, cdp_tab = st.tabs(["Dashboard Overview", "Provincial Breakdown", "Data Tables", "CDP Profile"])

# --- HTML/CSS SHARED TEMPLATES ---
metric_card = """
<div style="border: 1px solid #ccc; border-radius: 5px; padding: 15px; background-color: #ffffff; text-align: center; height: 115px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
    <h2 style="margin: 0 0 5px 0; font-size: 28px; color: #222;">{value}</h2>
    <p style="margin: 0; font-size: 16px; color: #444; font-weight: bold;">{title}</p>
</div>
"""

gender_card = """
<div style="border: 1px solid #ccc; border-radius: 5px; padding: 15px; background-color: #ffffff; text-align: center; height: 115px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
    <p style="margin: 0 0 5px 0; font-size: 16px; color: #222; font-weight: bold;">TOTAL MALE: <span style="font-size: 20px;">{male_val}</span></p>
    <p style="margin: 0; font-size: 16px; color: #222; font-weight: bold;">TOTAL FEMALE: <span style="font-size: 20px;">{female_val}</span></p>
</div>
"""

middle_left_card = """
<div style="border: 1px solid #ccc; border-radius: 5px; padding: 20px; background-color: #ffffff; height: 100%; min-height: 750px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
    <div>
        <h2 style="margin:0; font-size: 26px; color: #222;">{val1}</h2>
        <p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">Production Area (CROPS)</p>
    </div>
    <div style="margin-top: 20px;">
        <h2 style="margin:0; font-size: 26px; color: #222;">{val2}</h2>
        <p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">Production Area (FISHERIES)</p>
    </div>
    <div style="margin-top: 20px;">
        <h2 style="margin:0; font-size: 26px; color: #222;">{val3}</h2>
        <p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">TOTAL TREES</p>
    </div>
    <div style="margin-top: 20px;">
        <h2 style="margin:0; font-size: 26px; color: #222;">{val4}</h2>
        <p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">TOTAL HEADS</p>
    </div>
</div>
"""

chart_header = """
<div style="padding: 8px; text-align: center; border-bottom: 1px solid #ccc; background-color: #fafafa;">
    <p style="margin: 0; font-size: 11px; color: #222; font-weight: bold;">{title}</p>
</div>
"""

def make_chart(target_df, column_name, subset_col, is_donut=True):
    if column_name in target_df.columns and subset_col in target_df.columns:
        valid_mask = get_valid_mask(target_df[subset_col])
        clean_df = target_df[valid_mask].drop_duplicates(subset=[subset_col]).copy()
        
        clean_df[column_name] = clean_df[column_name].astype(str).str.strip().str.title()
        clean_df = clean_df[clean_df[column_name].isin(['None', 'Nan', '']) == False]
        clean_df = clean_df.dropna(subset=[column_name])
        
        if clean_df.empty: return None
        
        counts = clean_df[column_name].value_counts().reset_index()
        counts.columns = [column_name, 'Count']
        
        fig = go.Figure()
        hole_size = 0.6 if is_donut else 0
        custom_colors = ['#2CA02C', '#FFD700', '#1F77B4', '#FF7F0E', '#9467BD', '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF']
        
        fig.add_trace(go.Pie(
            labels=counts[column_name], values=counts['Count'], hole=hole_size,
            textinfo='value', textposition='outside', textfont=dict(color='black', size=14),
            marker=dict(colors=custom_colors, line=dict(color='#000000', width=1)), 
            sort=False, direction='clockwise', showlegend=True   
        ))
        
        fig.add_trace(go.Pie(
            labels=counts[column_name], values=counts['Count'], hole=hole_size,
            textinfo='percent', textposition='inside', insidetextfont=dict(color='black', size=14), 
            marker=dict(colors=custom_colors, line=dict(color='#000000', width=1)), 
            sort=False, direction='clockwise', hoverinfo='skip', showlegend=False  
        ))

        fig.update_layout(
            margin=dict(t=40, b=10, l=10, r=10), height=240, showlegend=True, 
            legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10, color='black')),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color='black') 
        )
        return fig
    return None


# ----------------------------------------------------
# TAB 1: DASHBOARD OVERVIEW 
# ----------------------------------------------------
with dash_tab:
    st.write("---")
    filtered_dash_df = render_main_filters("dash", sync_from_dash)
    st.write("---")
        
    if filtered_dash_df.empty:
        st.warning("No data found matching your current filters.")
    else:
        clean_fca_df = filtered_dash_df.drop_duplicates(subset=['_FCA_ID'])
        
        total_members_count = clean_fca_df["Total Members"].sum()
        total_male = clean_fca_df["Male"].sum()
        total_female = clean_fca_df["Female"].sum()
        
        total_clusters = filtered_dash_df[get_valid_mask(filtered_dash_df['NAME OF CLUSTER'])]['NAME OF CLUSTER'].nunique()
        total_fca_groups = clean_fca_df['_FCA_ID'].nunique()
        total_commodities = filtered_dash_df[get_valid_mask(filtered_dash_df['COMMODITY'])]['COMMODITY'].nunique()

        is_fishery = filtered_dash_df['COMMODITY'].astype(str).str.contains('fishery|fish', case=False, na=False)
        crops_area = filtered_dash_df.loc[~is_fishery, 'Production Area\n (Has.)'].sum()
        fishery_area = filtered_dash_df.loc[is_fishery, 'Production Area\n (Has.)'].sum()

        is_tree = filtered_dash_df['Unit (Ha/s, Head, Trees)'].astype(str).str.contains('tree', case=False, na=False)
        total_trees = filtered_dash_df.loc[is_tree, 'Production Area\n (Trees, Heads)'].sum()
        total_heads = filtered_dash_df.loc[~is_tree, 'Production Area\n (Trees, Heads)'].sum()

        top1, top2, top3, top4, top5 = st.columns(5)
        with top1: st.markdown(metric_card.format(value=total_clusters, title="TOTAL CLUSTER"), unsafe_allow_html=True)
        with top2: st.markdown(metric_card.format(value=f"{total_fca_groups:,.0f}", title="TOTAL FCA MEMBERS"), unsafe_allow_html=True)
        with top3: st.markdown(metric_card.format(value=total_commodities, title="CLUSTER BY COMMODITY"), unsafe_allow_html=True)
        with top4: st.markdown(metric_card.format(value=f"{total_members_count:,.0f}", title="TOTAL MEMBERS"), unsafe_allow_html=True)
        with top5: st.markdown(gender_card.format(male_val=f"{total_male:,.0f}", female_val=f"{total_female:,.0f}"), unsafe_allow_html=True)

        st.write("---") 

        mid_left, mid_right = st.columns([1, 3])

        with mid_left:
            st.write("**Production Summaries**")
            st.markdown(middle_left_card.format(
                val1=f"{crops_area:,.2f}", val2=f"{fishery_area:,.2f}", 
                val3=f"{total_trees:,.0f}", val4=f"{total_heads:,.0f}"
            ), unsafe_allow_html=True)

        with mid_right:
            st.write("**FCA & Assessment Classifications**")
            
            # --- ROW 1 CHARTS ---
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="FCA CLASSIFICATION"), unsafe_allow_html=True)
                fig_fca = make_chart(filtered_dash_df, 'FCA Clasification\n(Association/Cooperative/Federation)', '_FCA_ID', is_donut=False)
                if fig_fca: st.plotly_chart(fig_fca, width="stretch", key="chart_fca_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r1c2:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="STATUS OF MOA"), unsafe_allow_html=True)
                fig_moa = make_chart(filtered_dash_df, 'STATUS OF MEMORANDUM OF AGREEMENT (MOA)', 'NAME OF CLUSTER', is_donut=True)
                if fig_moa: st.plotly_chart(fig_moa, width="stretch", key="chart_moa_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r1c3:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="STATUS OF CDP"), unsafe_allow_html=True)
                fig_cdp_ch = make_chart(filtered_dash_df, 'STATUS OF CDP', 'NAME OF CLUSTER', is_donut=True)
                if fig_cdp_ch: st.plotly_chart(fig_cdp_ch, width="stretch", key="chart_cdp_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r1c4:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="CSO ACCREDITED"), unsafe_allow_html=True)
                fig_cso = make_chart(filtered_dash_df, 'CSO ACCREDITATED\n(YES/NO)', '_FCA_ID', is_donut=False)
                if fig_cso: st.plotly_chart(fig_cso, width="stretch", key="chart_cso_d")
                st.markdown('</div>', unsafe_allow_html=True)
                
            st.write("<br>", unsafe_allow_html=True)
            
            # --- ROW 2 CHARTS ---
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="STATUS ASSESSMENT (RICE)"), unsafe_allow_html=True)
                fig_assessment = make_chart(filtered_dash_df, 'Status of Assessment\n(Rice)', '_FCA_ID', is_donut=True)
                if fig_assessment: st.plotly_chart(fig_assessment, width="stretch", key="chart_assessment_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r2c2:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="STATUS OF PROFILING"), unsafe_allow_html=True)
                fig_prof = make_chart(filtered_dash_df, 'Status of Profiling', '_FCA_ID', is_donut=True)
                if fig_prof: st.plotly_chart(fig_prof, width="stretch", key="chart_prof_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r2c3:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="FFEDIS REGISTERED"), unsafe_allow_html=True)
                fig_ffedis = make_chart(filtered_dash_df, 'FFEDIS Registered \n(YES/NO)', '_FCA_ID', is_donut=False)
                if fig_ffedis: st.plotly_chart(fig_ffedis, width="stretch", key="chart_ffedis_d")
                st.markdown('</div>', unsafe_allow_html=True)
            with r2c4:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="RCEF ACCREDITED"), unsafe_allow_html=True)
                fig_rcef = make_chart(filtered_dash_df, 'RCEF Accredited \n(YES/NO)', '_FCA_ID', is_donut=False)
                if fig_rcef: st.plotly_chart(fig_rcef, width="stretch", key="chart_rcef_d")
                st.markdown('</div>', unsafe_allow_html=True)

            st.write("<br>", unsafe_allow_html=True)

            # --- ROW 3 CHARTS ---
            r3c1, r3c2, r3c3, r3c4 = st.columns(4)
            with r3c1:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="REGISTRATION"), unsafe_allow_html=True)
                fig_reg = make_chart(filtered_dash_df, 'Registration\n(CDA/SEC/DOLE/DSWD)', '_FCA_ID', is_donut=False)
                if fig_reg: st.plotly_chart(fig_reg, width="stretch", key="chart_registration_d")
                st.markdown('</div>', unsafe_allow_html=True)
                
            with r3c2:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="FFORIS/FFEDIS REGISTERED"), unsafe_allow_html=True)
                fig_fforis = make_chart(filtered_dash_df, 'STATUS OF FFEDIS REGISTRATION\n(Active or Not Active)', '_FCA_ID', is_donut=True)
                if fig_fforis: st.plotly_chart(fig_fforis, width="stretch", key="chart_fforis_reg_d")
                st.markdown('</div>', unsafe_allow_html=True)

            with r3c3:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="RSBSA REGISTRATION"), unsafe_allow_html=True)
                
                col_rsbsa, col_non = 'No. of Members Registered in RSBSA', 'Non-RSBSA Registred'
                val_rsbsa, val_non = 0, 0
                if col_rsbsa in clean_fca_df.columns:
                    val_rsbsa = pd.to_numeric(clean_fca_df[col_rsbsa].astype(str).str.replace(',', '', regex=False), errors='coerce').sum()
                if col_non in clean_fca_df.columns:
                    val_non = pd.to_numeric(clean_fca_df[col_non].astype(str).str.replace(',', '', regex=False), errors='coerce').sum()
                
                if (val_rsbsa + val_non) > 0:
                    fig_rsbsa = go.Figure()
                    custom_colors = ['#2CA02C', '#FFD700']
                    
                    fig_rsbsa.add_trace(go.Pie(
                        labels=['Registered', 'Non-Registered'], values=[val_rsbsa, val_non], hole=0.6,
                        textinfo='value', textposition='outside', textfont=dict(color='black', size=14),
                        marker=dict(colors=custom_colors, line=dict(color='#000000', width=1)), sort=False, direction='clockwise', showlegend=True   
                    ))
                    fig_rsbsa.add_trace(go.Pie(
                        labels=['Registered', 'Non-Registered'], values=[val_rsbsa, val_non], hole=0.6,
                        textinfo='percent', textposition='inside', insidetextfont=dict(color='black', size=14), 
                        marker=dict(colors=custom_colors, line=dict(color='#000000', width=1)), sort=False, direction='clockwise', hoverinfo='skip', showlegend=False  
                    ))
                    fig_rsbsa.update_layout(
                        margin=dict(t=40, b=10, l=10, r=10), height=240, showlegend=True, 
                        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10, color='black')),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color='black') 
                    )
                    st.plotly_chart(fig_rsbsa, width="stretch", key="chart_rsbsa_custom_d")
                st.markdown('</div>', unsafe_allow_html=True)
                
            with r3c4:
                st.markdown('<div style="border: 1px solid #ccc; border-radius: 5px; background-color: #fff; overflow: hidden; height: 100%;">', unsafe_allow_html=True)
                st.markdown(chart_header.format(title="CLASSIFICATION CATEGORY"), unsafe_allow_html=True)
                col_class = 'CLUSTER CATEGORY\nClassification based on the Asset: \n1 - Start-up (Less than 500,000)\n2- Micro (500,001 - 3,000,000)\n3 - Small (3,000,001 - 15,000,000)\n4 - Medium (15,000,001 - 100,000,000)\n5 - Large ( more than 100,000,000)'
                fig_class = make_chart(filtered_dash_df, col_class, '_FCA_ID', is_donut=True)
                if fig_class: st.plotly_chart(fig_class, width="stretch", key="chart_classification_d")
                st.markdown('</div>', unsafe_allow_html=True)

        st.write("---")

        bot_left, bot_right = st.columns(2)
        
        with bot_left:
            st.write("**Demography (By Municipality)**")
            muni_grouped = filtered_dash_df.groupby('MUNICIPALITY', as_index=False).agg(
                Area_Has=('Production Area\n (Has.)', 'sum'),
                Area_Trees=('Production Area\n (Trees, Heads)', 'sum')      
            )
            
            muni_melted = muni_grouped.melt(id_vars='MUNICIPALITY', value_vars=['Area_Has', 'Area_Trees'], var_name='Type', value_name='Area')
            muni_melted['Type'] = muni_melted['Type'].map({'Area_Has': 'Production Area (Has.)', 'Area_Trees': 'Production Area (Trees, Heads)'})
            muni_melted = muni_melted[muni_melted['Area'] > 0] 
            
            fig_demo = px.bar(
                muni_melted, x='MUNICIPALITY', y='Area', color='Type',
                barmode='group', color_discrete_map={'Production Area (Has.)': '#2CA02C', 'Production Area (Trees, Heads)': '#FFD700'}, 
                text_auto='.2s'
            ) 
            fig_demo.update_layout(
                margin=dict(t=30, b=10, l=10, r=10), height=600, legend_title_text='',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10, color='black')),
                yaxis_title="", xaxis_title="Municipality", font=dict(color='black') 
            )
            fig_demo.update_yaxes(tickformat=",")
            st.plotly_chart(fig_demo, width="stretch", key="bar_demo_d")
            
        with bot_right:
            st.write("**Commodities Production Area**")
            comm_grouped = filtered_dash_df.groupby('COMMODITY', as_index=False).agg(
                Area_Has=('Production Area\n (Has.)', 'sum'),
                Area_Trees=('Production Area\n (Trees, Heads)', 'sum')
            )
            
            comm_melted = comm_grouped.melt(id_vars='COMMODITY', value_vars=['Area_Has', 'Area_Trees'], var_name='Type', value_name='Area')
            comm_melted['Type'] = comm_melted['Type'].map({'Area_Has': 'Production Area (Has.)', 'Area_Trees': 'Production Area (Trees, Heads)'})
            comm_melted = comm_melted[comm_melted['Area'] > 0] 
            
            fig_comm = px.bar(
                comm_melted, x='COMMODITY', y='Area', color='Type',
                barmode='group', color_discrete_map={'Production Area (Has.)': '#2CA02C', 'Production Area (Trees, Heads)': '#FFD700'}, 
                text_auto='.2s'
            ) 
            fig_comm.update_layout(
                margin=dict(t=30, b=10, l=10, r=10), height=600, legend_title_text='',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10, color='black')),
                yaxis_title="", xaxis_title="Commodity", font=dict(color='black') 
            )
            fig_comm.update_yaxes(tickformat=",")
            st.plotly_chart(fig_comm, width="stretch", key="bar_comm_d")


# ----------------------------------------------------
# TAB 2: PROVINCIAL BREAKDOWN (Unfiltered Base Data)
# ----------------------------------------------------
with prov_tab:
    st.write("### Provincial Breakdown")
    st.caption("*(Note: This tab shows full regional data and operates completely independently of the top filters)*")
    
    provinces = sorted([str(p) for p in df['PROVINCE'].unique() if pd.notnull(p) and str(p).strip() not in ['', 'Nan', 'None']])
    
    for prov in provinces:
        with st.expander(f"📍 {prov} Breakdown", expanded=False):
            p_df = df[df['PROVINCE'] == prov]
            
            p_fca = p_df.drop_duplicates(subset=['_FCA_ID'])
            p_mems = p_fca['Total Members'].sum()
            p_clust = p_df[get_valid_mask(p_df['NAME OF CLUSTER'])]['NAME OF CLUSTER'].nunique()
            p_fca_ct = p_fca['_FCA_ID'].nunique()
            p_comm = p_df[get_valid_mask(p_df['COMMODITY'])]['COMMODITY'].nunique()
            
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(metric_card.format(value=p_clust, title="TOTAL CLUSTER"), unsafe_allow_html=True)
            with c2: st.markdown(metric_card.format(value=f"{p_fca_ct:,.0f}", title="TOTAL FCA MEMBERS"), unsafe_allow_html=True)
            with c3: st.markdown(metric_card.format(value=p_comm, title="CLUSTER BY COMMODITY"), unsafe_allow_html=True)
            with c4: st.markdown(metric_card.format(value=f"{p_mems:,.0f}", title="TOTAL MEMBERS"), unsafe_allow_html=True)
            
            st.write("---")
            
            p_is_fish = p_df['COMMODITY'].astype(str).str.contains('fishery|fish', case=False, na=False)
            p_crops = p_df.loc[~p_is_fish, 'Production Area\n (Has.)'].sum()
            p_fish = p_df.loc[p_is_fish, 'Production Area\n (Has.)'].sum()
            
            p_is_tree = p_df['Unit (Ha/s, Head, Trees)'].astype(str).str.contains('tree', case=False, na=False)
            p_trees = p_df.loc[p_is_tree, 'Production Area\n (Trees, Heads)'].sum()
            p_heads = p_df.loc[~p_is_tree, 'Production Area\n (Trees, Heads)'].sum()
            
            col_prod, col_class_grid = st.columns([1, 3])
            
            with col_prod:
                st.write("**Production Summaries**")
                st.markdown(f"""
                <div style="border: 1px solid #ccc; border-radius: 5px; padding: 20px; background-color: #ffffff; height: 1045px; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box;">
                    <div><h2 style="margin:0; font-size: 26px; color: #222;">{p_crops:,.2f}</h2><p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">Production Area (CROPS)</p></div>
                    <div style="margin-top: 20px;"><h2 style="margin:0; font-size: 26px; color: #222;">{p_fish:,.2f}</h2><p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">Production Area (FISHERIES)</p></div>
                    <div style="margin-top: 20px;"><h2 style="margin:0; font-size: 26px; color: #222;">{p_trees:,.0f}</h2><p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">TOTAL TREES</p></div>
                    <div style="margin-top: 20px;"><h2 style="margin:0; font-size: 26px; color: #222;">{p_heads:,.0f}</h2><p style="margin:0; font-size: 15px; color: #555; font-weight: bold;">TOTAL HEADS</p></div>
                </div>
                """, unsafe_allow_html=True)
                
            with col_class_grid:
                st.write("**FCA & Assessment Classifications**")
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                r2c1, r2c2, r2c3, r2c4 = st.columns(4)
                r3c1, r3c2, r3c3, r3c4 = st.columns(4)
                
                with r1c1: st.markdown(get_text_card("FCA CLASSIFICATION", p_df, 'FCA Clasification\n(Association/Cooperative/Federation)', '_FCA_ID'), unsafe_allow_html=True)
                with r1c2: st.markdown(get_text_card("STATUS OF MOA", p_df, 'STATUS OF MEMORANDUM OF AGREEMENT (MOA)', 'NAME OF CLUSTER'), unsafe_allow_html=True)
                with r1c3: st.markdown(get_text_card("STATUS OF CDP", p_df, 'STATUS OF CDP', 'NAME OF CLUSTER'), unsafe_allow_html=True)
                with r1c4: st.markdown(get_text_card("CSO ACCREDITED", p_df, 'CSO ACCREDITATED\n(YES/NO)', '_FCA_ID'), unsafe_allow_html=True)
                
                st.write("<br>", unsafe_allow_html=True)
                
                with r2c1: st.markdown(get_text_card("STATUS ASSESSMENT (RICE)", p_df, 'Status of Assessment\n(Rice)', '_FCA_ID'), unsafe_allow_html=True)
                with r2c2: st.markdown(get_text_card("STATUS OF PROFILING", p_df, 'Status of Profiling', '_FCA_ID'), unsafe_allow_html=True)
                with r2c3: st.markdown(get_text_card("FFEDIS REGISTERED", p_df, 'FFEDIS Registered \n(YES/NO)', '_FCA_ID'), unsafe_allow_html=True)
                with r2c4: st.markdown(get_text_card("RCEF ACCREDITED", p_df, 'RCEF Accredited \n(YES/NO)', '_FCA_ID'), unsafe_allow_html=True)

                st.write("<br>", unsafe_allow_html=True)
                
                with r3c1: st.markdown(get_text_card("REGISTRATION", p_df, 'Registration\n(CDA/SEC/DOLE/DSWD)', '_FCA_ID'), unsafe_allow_html=True)
                with r3c2: st.markdown(get_text_card("FFORIS/FFEDIS REGISTERED", p_df, 'STATUS OF FFEDIS REGISTRATION\n(Active or Not Active)', '_FCA_ID'), unsafe_allow_html=True)
                
                with r3c3: 
                    v_rsbsa, v_non = 0, 0
                    if col_rsbsa in p_fca.columns: v_rsbsa = pd.to_numeric(p_fca[col_rsbsa].astype(str).str.replace(',', '', regex=False), errors='coerce').sum()
                    if col_non in p_fca.columns: v_non = pd.to_numeric(p_fca[col_non].astype(str).str.replace(',', '', regex=False), errors='coerce').sum()
                    custom_html = f"<div style='margin-bottom: 20px; text-align: center;'><h2 style='margin:0; font-size: 26px; color: #222; line-height: 1;'>{v_rsbsa:,.0f}</h2><p style='margin:0; font-size: 15px; color: #555; font-weight: bold;'>Registered</p></div>"
                    custom_html += f"<div style='margin-bottom: 20px; text-align: center;'><h2 style='margin:0; font-size: 26px; color: #222; line-height: 1;'>{v_non:,.0f}</h2><p style='margin:0; font-size: 15px; color: #555; font-weight: bold;'>Non-Registered</p></div>"
                    st.markdown(f"""
                        <div style="border: 1px solid #ccc; border-radius: 5px; background-color: #ffffff; height: 380px; overflow-y: auto;">
                            <div style="padding: 8px; text-align: center; border-bottom: 1px solid #ccc; background-color: #fafafa; margin-bottom: 15px; position: sticky; top: 0; z-index: 10;">
                                <p style="margin: 0; font-size: 11px; color: #222; font-weight: bold; text-transform: uppercase;">RSBSA REGISTRATION</p>
                            </div>
                            <div style="padding: 0 15px 15px 15px;">{custom_html}</div>
                        </div>
                    """, unsafe_allow_html=True)

                with r3c4: st.markdown(get_text_card("CLASSIFICATION CATEGORY", p_df, col_class, '_FCA_ID'), unsafe_allow_html=True)


# ------------------------------------------
# TAB 3: SYSTEM DATA TABLES (Synced Filters)
# ------------------------------------------
with table_tab:
    st.write("---")
    filtered_table_df = render_main_filters("table", sync_from_table)
    st.write("---")
        
    if filtered_table_df.empty:
        st.warning("No data found matching your current filters.")
    else:
        st.write("### Master Data Tables")
        
        def get_existing_cols(df_in, desired_cols):
            return [col for col in desired_cols if col in df_in.columns]

        t1_cols = get_existing_cols(filtered_table_df, ['NAME OF CLUSTER', 'NAME OF BIG-BROTHER', 'TOTAL FCA MEMBER', 'YEAR OF ESTABLISHMENT', 'CLUSTER BY COMMODITY', 'STATUS OF MEMORANDUM OF AGREEMENT (MOA)', 'STATUS OF CDP'])
        table1 = filtered_table_df.drop_duplicates(subset=['NAME OF CLUSTER', 'NAME OF BIG-BROTHER'])[t1_cols]

        t2_cols = get_existing_cols(filtered_table_df, ['NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'Total Members', 'Contact Number', 'PROVINCE', 'MUNICIPALITY', 'BARANGAY', 'Contact Person', 'Status of Profiling'])
        table2 = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t2_cols]

        t3_cols = get_existing_cols(filtered_table_df, ['NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'Total Assets', 'Primary Activity\n(ex.Producer, Processor, Capitalization, Marketing[Buy and Sell], Producer of Meat/Poultry, Consolidator, farm/Agricultural Supply)'])
        t3_cols.extend([col for col in filtered_table_df.columns if "Classification based on the Asset" in col])
        t3_cols.extend([col for col in filtered_table_df.columns if "Classification based on the HARMONIZED" in col])
        table3 = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t3_cols]

        t4_cols = get_existing_cols(filtered_table_df, ['Registration\n(CDA/SEC/DOLE/DSWD)', 'NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'Date of Registration', 'Registration Number', 'STATUS OF REGISTRATION\n(Active or Not Active)'])
        table4 = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t4_cols]
        
        t5a_cols = get_existing_cols(filtered_table_df, ['CSO ACCREDITATED\n(YES/NO)', 'NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'CSO Date of Accreditation \n(Month-Year)', 'CSO Accreditation Number', 'VALIDITY'])
        table5a = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t5a_cols]

        t5b_cols = get_existing_cols(filtered_table_df, ['FFEDIS Registered \n(YES/NO)', 'NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'FFEDIS Registration Date \n(Month-Year)', 'FFEDIS Reg No. ', 'STATUS OF FFEDIS REGISTRATION\n(Active or Not Active)'])
        table5b = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t5b_cols]

        t5c_cols = get_existing_cols(filtered_table_df, ['RCEF Accredited \n(YES/NO)', 'NAME OF CLUSTER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'RCEF Date of Accredition\n(Month-Year)', 'RCEF Accreditation No.', 'Other Accrediation '])
        table5c = filtered_table_df.drop_duplicates(subset=['_FCA_ID'])[t5c_cols]

        t5d_cols = get_existing_cols(filtered_table_df, ['NAME OF CLUSTER', 'NAME OF BIG-BROTHER', 'NAME OF FCA MEMBERS', 'PROVINCE', 'MUNICIPALITY', 'BARANGAY', 'COMMODITY CATEGORY', 'COMMODITY', 'TYPE COMMODITY', 'Status of Assessment\n(Rice)',  'Production Area\n (Has.)', 'Production Area\n (Trees, Heads)', 'Unit (Ha/s, Head, Trees)'])
        table5d = filtered_table_df[t5d_cols].drop_duplicates()
        
        cdp_export_cols = [c for c in ['PROVINCE', 'NAME OF CLUSTER', 'NAME OF MEMBER FCA \n(Requesting FCA)', 'COMMODITY / SERVICES', 'PROGRAM /ACTIVITIES / PROJECTS', 'TYPE OF INTERVENTION', 'TOTAL QUANTITY', 'FUND SOURCE', 'YEAR 1', 'YEAR 2', 'YEAR 3', 'YEAR 4', 'YEAR 5'] if c in df_cdp.columns]
        table_cdp = df_cdp[cdp_export_cols]

        @st.cache_data(show_spinner=False)
        def generate_excel_report(df_hash, cdp_hash):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                worksheet = workbook.add_worksheet('System Reports')
                writer.sheets['System Reports'] = worksheet
                
                title_format = workbook.add_format({'bold': True, 'font_size': 12})
                current_row = 0
                
                def write_table_to_sheet(df_sheet, title, row_index):
                    worksheet.write_string(row_index, 0, title, title_format)
                    row_index += 2 
                    if not df_sheet.empty:
                        df_sheet.to_excel(writer, sheet_name='System Reports', startrow=row_index, index=False)
                        row_index += len(df_sheet) + 3 
                    else:
                        df_sheet.to_excel(writer, sheet_name='System Reports', startrow=row_index, index=False)
                        row_index += 4 
                    return row_index 
                        
                current_row = write_table_to_sheet(table1, "Table 1: CLUSTER PROFILE", current_row)
                current_row = write_table_to_sheet(table2, "Table 2: FCA PROFILE", current_row)
                current_row = write_table_to_sheet(table3, "Table 3: FCA FINANCIAL AND CAPACITY LEVEL", current_row)
                current_row = write_table_to_sheet(table4, "Table 4: FCA REGISTRATION", current_row)
                current_row = write_table_to_sheet(table5a, "Table 5A: FCA CSO ACCREDITATION", current_row)
                current_row = write_table_to_sheet(table5b, "Table 5B: FCA FFEDIS REGISTRATION", current_row)
                current_row = write_table_to_sheet(table5c, "Table 5C: FCA RCEF ACCREDITATION AND OTHERS", current_row)
                current_row = write_table_to_sheet(table5d, "Table 5D: FCA COMMODITY PROFILE", current_row)
                current_row = write_table_to_sheet(table_cdp, "Table 6: CDP PROFILE", current_row)
            return buffer.getvalue()

        excel_data = generate_excel_report(len(filtered_table_df), len(df_cdp))

        st.download_button(
            label=" Download All Table Reports (Excel)",
            data=excel_data,
            file_name="All_Table_Reports.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch"
        )
        st.divider()

        st.write("**Table 1: CLUSTER PROFILE**")
        st.dataframe(table1, width="stretch", hide_index=True)

        st.write("**Table 2: FCA Profile**")
        st.dataframe(table2, width="stretch", hide_index=True)

        st.write("**Table 3: FCA Financial and Capacity Level**")
        st.dataframe(table3, width="stretch", hide_index=True)

        st.write("**Table 4: FCA Registration**")
        st.dataframe(table4, width="stretch", hide_index=True)
        
        st.write("**Table 5A: FCA CSO Accreditation**")
        st.dataframe(table5a, width="stretch", hide_index=True)

        st.write("**Table 5B: FCA FFEDIS Registration**")
        st.dataframe(table5b, width="stretch", hide_index=True)

        st.write("**Table 5C: FCA RCEF Accreditation and Others**")
        st.dataframe(table5c, width="stretch", hide_index=True)

        st.write("**Table 5D: FCA Commodity Profile**")
        st.dataframe(table5d, width="stretch", hide_index=True)


# ----------------------------------------------------
# TAB 4: NEW CDP PROFILE ( Independent)
# ----------------------------------------------------
with cdp_tab:
    cdp_filtered = df_cdp.copy()
    
    st.write("---")
    st.write("**CDP Profile Filters**")
    fc0, fc00, fc1, fc2, fc3, fc4 = st.columns(6)
    
    with fc0:
        if 'PROVINCE' in cdp_filtered.columns:
            opts_prov = ["All"] + sorted([str(x) for x in cdp_filtered['PROVINCE'].dropna().unique() if str(x).strip() != ""])
            cdp_prov = st.selectbox("Province:", opts_prov, key="cdp_prov")
            if cdp_prov != "All": cdp_filtered = cdp_filtered[cdp_filtered['PROVINCE'] == cdp_prov]
            
    with fc00:
        if 'NAME OF CLUSTER' in cdp_filtered.columns:
            opts_clust = ["All"] + sorted([str(x) for x in cdp_filtered['NAME OF CLUSTER'].dropna().unique() if str(x).strip() != ""])
            cdp_clust = st.selectbox("Cluster:", opts_clust, key="cdp_clust")
            if cdp_clust != "All": cdp_filtered = cdp_filtered[cdp_filtered['NAME OF CLUSTER'] == cdp_clust]
            
    with fc1:
        if 'COMMODITY / SERVICES' in cdp_filtered.columns:
            opts_comm = ["All"] + sorted([str(x) for x in cdp_filtered['COMMODITY / SERVICES'].dropna().unique() if str(x).strip() != ""])
            cdp_comm = st.selectbox("Commodity / Services:", opts_comm, key="cdp_comm")
            if cdp_comm != "All": cdp_filtered = cdp_filtered[cdp_filtered['COMMODITY / SERVICES'] == cdp_comm]
                
    with fc2:
        if 'PROGRAM /ACTIVITIES / PROJECTS' in cdp_filtered.columns:
            opts_prog = ["All"] + sorted([str(x) for x in cdp_filtered['PROGRAM /ACTIVITIES / PROJECTS'].dropna().unique() if str(x).strip() != ""])
            cdp_prog = st.selectbox("Program / Activities:", opts_prog, key="cdp_prog")
            if cdp_prog != "All": cdp_filtered = cdp_filtered[cdp_filtered['PROGRAM /ACTIVITIES / PROJECTS'] == cdp_prog]
                
    with fc3:
        if 'TYPE OF INTERVENTION' in cdp_filtered.columns:
            opts_interv = ["All"] + sorted([str(x) for x in cdp_filtered['TYPE OF INTERVENTION'].dropna().unique() if str(x).strip() != ""])
            cdp_interv = st.selectbox("Type of Intervention:", opts_interv, key="cdp_interv")
            if cdp_interv != "All": cdp_filtered = cdp_filtered[cdp_filtered['TYPE OF INTERVENTION'] == cdp_interv]
                
    with fc4:
        year_options = ["All Years", "YEAR 1", "YEAR 2", "YEAR 3", "YEAR 4", "YEAR 5"]
        cdp_year = st.selectbox("Year:", year_options, key="cdp_year")
        if cdp_year != "All Years" and cdp_year in cdp_filtered.columns:
            cdp_filtered = cdp_filtered[get_valid_mask(cdp_filtered[cdp_year])]

    st.write("") 
    master_cdp_search = pd.concat([cdp_filtered[c] for c in cdp_filtered.columns]).dropna().unique()
    opts_cdp_search = [""] + sorted([str(x) for x in master_cdp_search if str(x).strip() != ""])
    cdp_search_query = st.selectbox("Global Search CDP Data:", opts_cdp_search, key="cdp_search_field")
    if cdp_search_query != "":
        search_val_cdp = str(cdp_search_query).strip().lower()
        mask_cdp = cdp_filtered.astype(str).apply(lambda x: x.str.strip().str.lower() == search_val_cdp).any(axis=1)
        cdp_filtered = cdp_filtered[mask_cdp]
    st.write("---")

    if cdp_filtered.empty:
        st.warning("No data found matching your CDP filters.")
    else:
        # --- 2. CHARTS ---
        ch1, ch2 = st.columns([1, 2])
        
        with ch1:
            st.write("**Commodity / Services Breakdown**")
            if 'COMMODITY / SERVICES' in cdp_filtered.columns:
                comm_series = cdp_filtered['COMMODITY / SERVICES'].dropna().astype(str).str.strip()
                valid_comm = comm_series[~comm_series.str.lower().isin(['', 'nan', 'none', 'n/a', '<na>'])]
                
                if not valid_comm.empty:
                    pie_counts = valid_comm.value_counts().reset_index()
                    pie_counts.columns = ['COMMODITY / SERVICES', 'Count']
                    
                    custom_colors = ['#2CA02C', '#FFD700', '#1F77B4', '#FF7F0E', '#9467BD']
                    
                    fig_cdp_pie = px.pie(
                        pie_counts,
                        names='COMMODITY / SERVICES',
                        values='Count',
                        hole=0.6,
                        color_discrete_sequence=custom_colors
                    )
                    fig_cdp_pie.update_traces(
                        textposition='inside',
                        textinfo='value',
                        insidetextorientation='horizontal',
                        textfont=dict(color='black', size=14),
                        marker=dict(line=dict(color='#000000', width=1))
                    )
                    fig_cdp_pie.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        showlegend=True,
                        height=400,
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.1,
                            xanchor="center",
                            x=0.5,
                            font=dict(color='black')
                        ),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color='black')
                    )
                    st.plotly_chart(fig_cdp_pie, width="stretch", key="cdp_pie_chart")
                else:
                    st.info("No non-blank Commodity / Services data to display.")
                
        with ch2:
            st.write("**Interventions Count per Year by Province**")
            years = ['YEAR 1', 'YEAR 2', 'YEAR 3', 'YEAR 4', 'YEAR 5']
            exist_years = [y for y in years if y in cdp_filtered.columns]
            
            if 'PROVINCE' in cdp_filtered.columns and exist_years:
                cdp_melted = cdp_filtered.melt(id_vars='PROVINCE', value_vars=exist_years, var_name='Year', value_name='Value')
                cdp_melted['Value'] = pd.to_numeric(cdp_melted['Value'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
                cdp_melted = cdp_melted[cdp_melted['Value'] > 0]
                
                cdp_grouped = cdp_melted.groupby(['Year', 'PROVINCE'])['Value'].sum().reset_index(name='Total Count')
                
                active_provs = cdp_grouped['PROVINCE'].dropna().unique()
                x_axis_title = ", ".join(active_provs) if len(active_provs) > 0 else "Province"
                
                fig_cdp_bar = px.bar(
                    cdp_grouped, x='Year', y='Total Count', color='PROVINCE', barmode='group',
                    text_auto='.0f', color_discrete_sequence=['#2CA02C', '#FFD700', '#1F77B4', '#FF7F0E', '#9467BD']
                )
                fig_cdp_bar.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=400,
                    xaxis_title=x_axis_title, yaxis_title="Total Interventions",
                    legend_title_text="Province", font=dict(color='black'),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_cdp_bar, width="stretch", key="cdp_bar_chart")
                
        st.write("---")
        
        # --- 3. DATA TABLE ---
        st.write("**CDP Profile Data Table**")
        req_cols = ['PROVINCE', 'NAME OF CLUSTER', 'NAME OF MEMBER FCA \n(Requesting FCA)', 'COMMODITY / SERVICES', 'TYPE OF INTERVENTION', 'TOTAL QUANTITY', 'FUND SOURCE']
        disp_cols = [c for c in req_cols if c in cdp_filtered.columns]
        
        st.dataframe(cdp_filtered[disp_cols], width="stretch", hide_index=True)
