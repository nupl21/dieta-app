import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Dieta - Gestión Excel", layout="wide", page_icon="🧠")
st.title("🧠 Panel de Control: Compra Inteligente (Modo Excel)")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos_nube():
    try:
        df = conn.read(worksheet="plan_dieta_unificado")
        
        # FIX DE COLUMNAS
        if "Cantidad_Diaria" in df.columns:
            df = df.rename(columns={"Cantidad_Diaria": "Cantidad_Semanal"})
            
        # VALIDACIONES
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
            
        return df
    except Exception as e:
        st.error(f"⚠️ Error al conectar: {e}")
        return pd.DataFrame()

# --- MEMORIA ---
if 'df_live' not in st.session_state:
    st.session_state.df_live = cargar_datos_nube()

def recargar_datos():
    st.cache_data.clear()
    st.session_state.df_live = cargar_datos_nube()

# ==========================================
# 🛠️ ADMINISTRACIÓN TIPO EXCEL (AgGrid)
# ==========================================
with st.expander("🛠️ Editar Productos (Menú en cabeceras)", expanded=True):
    
    # --- BOTONES DE SELECCIÓN MASIVA (Recuperados) ---
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ Seleccionar TODO"):
        st.session_state.df_live["Activo"] = True
        st.rerun()
        
    if col_btn2.button("❌ Deseleccionar TODO"):
        st.session_state.df_live["Activo"] = False
        st.rerun()
    # --------------------------------------------------

    st.info("💡 Haz clic en los encabezados de columna para **Ordenar** o **Filtrar** (Icono de filtro).")

    # 1. Configurar opciones de la grilla
    gb = GridOptionsBuilder.from_dataframe(st.session_state.df_live)
    
    # Habilitar paginación, ordenamiento y filtrado en TODAS las columnas
    gb.configure_default_column(
        groupable=True, 
        value=True, 
        enableRowGroup=True, 
        aggFunc='sum', 
        editable=True,   # ¡Todo editable!
        filterable=True, # ¡Habilita el filtro Excel!
        sortable=True,   # ¡Habilita ordenar A-Z!
        resizable=True
    )

    # Configuración específica para columnas desplegables (Dropdowns)
    gb.configure_column("Categoria", cellEditor='agSelectCellEditor', cellEditorParams={'values': ["Almacén", "Verduleria", "Carniceria", "Dietetica", "Lácteos"]})
    gb.configure_column("Tipo_Compra", cellEditor='agSelectCellEditor', cellEditorParams={'values': ["Semanal", "Quincenal", "Mensual"]})
    
    # Configuración para Checkbox (Activo)
    gb.configure_column("Activo", cellDataType='boolean', pinned='left') # Pinned deja el checkbox fijo a la izquierda

    # Construir opciones
    grid_options = gb.build()

    # 2. MOSTRAR LA TABLA TIPO EXCEL
    grid_response = AgGrid(
        st.session_state.df_live,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED, # Actualiza cuando cambias un dato
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED, 
        fit_columns_on_grid_load=True,
        theme='streamlit', # Tema visual limpio
        height=400,
        key='my_grid'
    )

    # 3. ACTUALIZAR DATOS EN MEMORIA
    # AgGrid devuelve los datos en 'data'. Los convertimos a DataFrame.
    df_aggrid = grid_response['data']
    st.session_state.df_live = df_aggrid # Actualizamos la memoria principal con lo que tocaste en la grilla

    col_s1, col_s2 = st.columns([1, 4])
    if col_s1.button("💾 Guardar Cambios"):
        try:
            conn.update(worksheet="plan_dieta_unificado", data=st.session_state.df_live)
            st.cache_data.clear()
            st.success("✅ Guardado en Google Sheets!")
        except Exception as e:
            st.error(f"Error: {e}")
            
    if col_s2.button("🔄 Recargar Original"):
        recargar_datos()
        st.rerun()

st.divider()

# ==========================================
# 🛒 CÁLCULO INTELIGENTE
# ==========================================
if not st.session_state.df_live.empty:
    st.subheader("🛒 Planificador de Compra")
    
    periodo = st.select_slider("Selecciona período:", options=["1 Semana", "2 Semanas", "3 Semanas", "1 Mes (4 Semanas)"])
    map_sem = {"1 Semana": 1, "2 Semanas": 2, "3 Semanas": 3, "1 Mes (4 Semanas)": 4}
    multiplicador = map_sem[periodo]

    # Usamos los datos que vienen directamente de la grilla de arriba (ya filtrados o editados)
    df_calc = st.session_state.df_live[st.session_state.df_live["Activo"] == True].copy()
    
    if not df_calc.empty:
        df_calc["Total_Necesario"] = df_calc["Cantidad_Semanal"] * multiplicador
        df_calc["Paquetes"] = np.ceil(df_calc["Total_Necesario"] / df_calc["Rendimiento_Paquete"])
        df_calc["Subtotal"] = df_calc["Paquetes"] * df_calc["Precio_Paquete"]
        
        cols_show = ["Categoria", "Producto", "Total_Necesario", "Paquetes", "Unidad_Compra", "Subtotal"]
        
        if multiplicador > 1:
            if multiplicador >= 4: 
                condicion_stock = df_calc["Tipo_Compra"] == "Mensual"
                texto_fresco = "FRESCOS Y QUINCENALES (Reponer durante el mes)"
            else:
                condicion_stock = df_calc["Tipo_Compra"].isin(["Mensual", "Quincenal"])
                texto_fresco = "FRESCOS (Reponer semanalmente)"

            df_stock = df_calc[condicion_stock]
            df_fresco = df_calc[~condicion_stock]
            
            col_stock, col_fresco = st.columns(2)
            with col_stock:
                st.success(f"🧊 STOCK (${df_stock['Subtotal'].sum():,.0f})")
                st.dataframe(df_stock[cols_show], hide_index=True, use_container_width=True)
            with col_fresco:
                st.warning(f"🥗 {texto_fresco} (${df_fresco['Subtotal'].sum():,.0f})")
                st.dataframe(df_fresco[cols_show], hide_index=True, use_container_width=True)
        else:
            st.dataframe(df_calc[cols_show], hide_index=True, use_container_width=True)

        st.metric(f"💰 TOTAL ESTIMADO", f"${df_calc['Subtotal'].sum():,.2f}")
    else:
        st.warning("No hay productos activos.")
