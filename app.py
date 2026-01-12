import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Dieta", layout="wide", page_icon="🛒")

# CSS: Ajustes para que se vea bien en ambos
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    /* Esto ayuda a que el checkbox se vea bien en modo oscuro */
    .ag-checkbox-input-wrapper {
        font-size: 16px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Supermercado Inteligente")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos_nube():
    try:
        df = conn.read(worksheet="plan_dieta_unificado")
        
        if "Cantidad_Diaria" in df.columns:
            df = df.rename(columns={"Cantidad_Diaria": "Cantidad_Semanal"})
            
        df["Activo"] = df["Activo"].astype(str).str.upper() == "TRUE"
        
        cols_num = ["Cantidad_Semanal", "Rendimiento_Paquete", "Precio_Paquete"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        if "Rendimiento_Paquete" in df.columns:
            df.loc[df["Rendimiento_Paquete"] <= 0, "Rendimiento_Paquete"] = 1
            
        if "Tipo_Compra" not in df.columns:
            df["Tipo_Compra"] = "Semanal" 
        else:
            df["Tipo_Compra"] = df["Tipo_Compra"].fillna("Semanal").astype(str).str.title()
            
        # REORDENAR COLUMNAS: Forzamos que Activo y Producto sean las primeras en el DataFrame
        # Esto ayuda a que AgGrid las muestre en orden por defecto
        cols_order = ['Activo', 'Producto', 'Categoria', 'Precio_Paquete', 'Tipo_Compra', 'Cantidad_Semanal', 'Unidad_Consumo']
        # Agregamos el resto de columnas que no estén en la lista
        rest_cols = [c for c in df.columns if c not in cols_order]
        df = df[cols_order + rest_cols]
            
        return df
    except Exception as e:
        st.error(f"⚠️ Error al conectar: {e}")
        return pd.DataFrame()

# --- MEMORIA ---
if 'df_live' not in st.session_state:
    st.session_state.df_live = cargar_datos_nube()

if 'grid_key' not in st.session_state:
    st.session_state.grid_key = 0

def recargar_datos():
    st.cache_data.clear()
    st.session_state.df_live = cargar_datos_nube()
    st.session_state.grid_key += 1

# ==========================================
# 🎨 ESTILOS (Verde si está activo)
# ==========================================
getRowStyle = JsCode("""
function(params) {
    if (params.data.Activo === true) {
        return {'backgroundColor': '#d1fae5', 'color': '#064e3b', 'fontWeight': 'bold'};
    }
    return null;
};
""")

# ==========================================
# 🛠️ EDITOR VISUAL (HÍBRIDO PC/MÓVIL)
# ==========================================
with st.expander("📝 LISTA DE COMPRA (Click aquí)", expanded=True):
    
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ Marcar TODO"):
        st.session_state.df_live["Activo"] = True
        st.session_state.grid_key += 1 
        st.rerun()
    if col_btn2.button("❌ Desmarcar TODO"):
        st.session_state.df_live["Activo"] = False
        st.session_state.grid_key += 1 
        st.rerun()

    # Configuración AgGrid
    gb = GridOptionsBuilder.from_dataframe(st.session_state.df_live)
    
    gb.configure_default_column(
        groupable=True, value=True, enableRowGroup=True, editable=True, 
        filterable=True, sortable=True, resizable=True, minWidth=100
    )

    # --- 1. EL CHECKBOX (SIEMPRE PRIMERO) ---
    gb.configure_column("Activo", 
                        headerName="OK", 
                        cellDataType='boolean', 
                        pinned='left',    # Fijo a la izquierda
                        width=70,         # Ancho fijo
                        suppressSizeToFit=True) # Que no cambie de tamaño

    # --- 2. EL PRODUCTO (ELÁSTICO) ---
    # Aquí está el truco: 'flex=1' hace que en PC ocupe todo el espacio libre
    # 'minWidth=150' asegura que en celular no se aplaste.
    gb.configure_column("Producto", 
                        pinned='left', 
                        minWidth=160,
                        flex=1) 

    # --- 3. RESTO DE COLUMNAS ---
    gb.configure_column("Categoria", cellEditor='agSelectCellEditor', cellEditorParams={'values': ["Almacén", "Verduleria", "Carniceria", "Dietetica", "Lácteos"]}, width=110)
    gb.configure_column("Tipo_Compra", cellEditor='agSelectCellEditor', cellEditorParams={'values': ["Semanal", "Quincenal", "Mensual"]}, width=110)
    gb.configure_column("Precio_Paquete", headerName="Precio", type=["numericColumn"], valueFormatter="'$' + x.toLocaleString()", width=100)

    # Aplicar Estilos
    gb.configure_grid_options(getRowStyle=getRowStyle)

    grid_options = gb.build()
    grid_options['rowHeight'] = 45 # Altura equilibrada

    grid_response = AgGrid(
        st.session_state.df_live,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED, 
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED, 
        
        # IMPORTANTE: Dejamos False para permitir scroll en celular.
        # Gracias al 'flex=1' en Producto, en PC se verá bien igual.
        fit_columns_on_grid_load=False, 
        
        allow_unsafe_jscode=True,
        theme='streamlit', 
        height=500,
        key=f'my_grid_{st.session_state.grid_key}'
    )

    df_aggrid = grid_response['data']
    st.session_state.df_live = df_aggrid 

    col_s1, col_s2 = st.columns([1, 4])
    if col_s1.button("💾 GUARDAR"):
        try:
            conn.update(worksheet="plan_dieta_unificado", data=st.session_state.df_live)
            st.cache_data.clear()
            st.toast("✅ Guardado", icon="💾")
        except Exception as e:
            st.error(f"Error: {e}")
            
    if col_s2.button("🔄 DESHACER"):
        recargar_datos()
        st.rerun()

st.divider()

# ==========================================
# 📊 RESUMEN 
# ==========================================
if not st.session_state.df_live.empty:
    st.subheader("💰 Resumen")
    
    periodo = st.select_slider("", options=["1 Semana", "2 Semanas", "3 Semanas", "1 Mes (4 Semanas)"])
    map_sem = {"1 Semana": 1, "2 Semanas": 2, "3 Semanas": 3, "1 Mes (4 Semanas)": 4}
    multiplicador = map_sem[periodo]

    df_calc = st.session_state.df_live[st.session_state.df_live["Activo"] == True].copy()
    
    if not df_calc.empty:
        df_calc["Total_Necesario"] = df_calc["Cantidad_Semanal"] * multiplicador
        df_calc["Paquetes"] = np.ceil(df_calc["Total_Necesario"] / df_calc["Rendimiento_Paquete"])
        df_calc["Subtotal"] = df_calc["Paquetes"] * df_calc["Precio_Paquete"]
        
        total = df_calc['Subtotal'].sum()
        
        # Diseño limpio
        col_res1, col_res2 = st.columns([1, 2])
        with col_res1:
            st.metric("Total a Pagar", f"${total:,.0f}")
        with col_res2:
            st.caption(f"Desglose para {periodo}")
            st.dataframe(df_calc[["Producto", "Paquetes", "Subtotal"]], hide_index=True, use_container_width=True, height=200)

    else:
        st.info("👆 Selecciona productos en la lista.")
