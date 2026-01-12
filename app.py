import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Dieta", layout="wide", page_icon="🛒")

# CSS: Ajustes visuales
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
    }
    .ag-checkbox-input-wrapper {
        font-size: 18px !important;
        width: 20px !important;
        height: 20px !important;
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
        
        # 1. Normalización
        if "Cantidad_Diaria" in df.columns:
            df = df.rename(columns={"Cantidad_Diaria": "Cantidad_Semanal"})
            
        df["Activo"] = df["Activo"].astype(str).str.upper() == "TRUE"
        
        # 2. Conversión Numérica
        cols_num = ["Cantidad_Semanal", "Rendimiento_Paquete", "Precio_Paquete"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # Evitar división por cero
        if "Rendimiento_Paquete" in df.columns:
            df.loc[df["Rendimiento_Paquete"] <= 0, "Rendimiento_Paquete"] = 1
            
        # 3. Manejo de Textos (Unidades)
        if "Unidad_Compra" not in df.columns:
            df["Unidad_Compra"] = "Unidad"
        df["Unidad_Compra"] = df["Unidad_Compra"].fillna("u.")

        if "Unidad_Consumo" not in df.columns:
            df["Unidad_Consumo"] = "u."
        df["Unidad_Consumo"] = df["Unidad_Consumo"].fillna("")

        # 4. Orden de Columnas
        cols_order = ['Activo', 'Categoria', 'Producto', 'Precio_Paquete', 'Tipo_Compra', 'Cantidad_Semanal', 'Unidad_Consumo', 'Rendimiento_Paquete', 'Unidad_Compra']
        
        cols_existentes = [c for c in cols_order if c in df.columns]
        rest_cols = [c for c in df.columns if c not in cols_existentes]
        
        df = df[cols_existentes + rest_cols]
            
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
# 🎨 ESTILOS AG-GRID
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
# 🛠️ EDITOR VISUAL
# ==========================================
with st.expander("📝 LISTA DE COMPRA (Editar datos aquí)", expanded=True):
    
    col_tools1, col_tools2 = st.columns([2, 1])
    with col_tools1:
        filtro_txt = st.text_input("🔍 Buscar producto:", placeholder="Escribe aquí...")
    with col_tools2:
        st.write("") 
        st.write("") 
        if st.button("🔄 Recargar Todo"):
             recargar_datos()
             st.rerun()

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ Marcar TODO", use_container_width=True):
        st.session_state.df_live["Activo"] = True
        st.session_state.grid_key += 1 
        st.rerun()
    if col_btn2.button("❌ Desmarcar TODO", use_container_width=True):
        st.session_state.df_live["Activo"] = False
        st.session_state.grid_key += 1 
        st.rerun()

    # Configuración Tabla Editable
    gb = GridOptionsBuilder.from_dataframe(st.session_state.df_live)
    
    gb.configure_default_column(
        groupable=True, value=True, enableRowGroup=True, editable=True, 
        filterable=True, sortable=True, resizable=True, minWidth=100
    )

    gb.configure_column("Activo", headerName="OK", cellDataType='boolean', pinned='left', width=70, suppressSizeToFit=True)
    gb.configure_column("Categoria", width=120)
    gb.configure_column("Producto", pinned='left', minWidth=150, flex=1) 
    gb.configure_column("Precio_Paquete", headerName="Precio", type=["numericColumn"], valueFormatter="'$' + x.toLocaleString()", width=100)
    
    gb.configure_column("Rendimiento_Paquete", headerName="Contenido", width=100) 
    gb.configure_column("Unidad_Compra", headerName="Envase", width=90)

    gb.configure_grid_options(getRowStyle=getRowStyle)
    gb.configure_grid_options(quickFilterText=filtro_txt) 

    grid_options = gb.build()
    grid_options['rowHeight'] = 45

    grid_response = AgGrid(
        st.session_state.df_live,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED, 
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED, 
        fit_columns_on_grid_load=False, 
        allow_unsafe_jscode=True,
        theme='streamlit', 
        height=400,
        key=f'my_grid_{st.session_state.grid_key}'
    )

    st.session_state.df_live = grid_response['data']

    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
            try:
                conn.update(worksheet="plan_dieta_unificado", data=st.session_state.df_live)
                st.cache_data.clear()
                st.toast("✅ Guardado exitosamente", icon="💾")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col_s2:
        if st.button("↩️ DESHACER", use_container_width=True):
            recargar_datos()
            st.rerun()

st.divider()

# ==========================================
# 📊 RESUMEN DEL CARRITO (ESTILO CLÁSICO)
# ==========================================
if not st.session_state.df_live.empty:
    st.subheader("💰 Resumen del Carrito")
    
    periodo = st.select_slider("Proyección de gasto para:", options=["1 Semana", "2 Semanas", "3 Semanas", "1 Mes (4 Semanas)"])
    map_sem = {"1 Semana": 1, "2 Semanas": 2, "3 Semanas": 3, "1 Mes (4 Semanas)": 4}
    multiplicador = map_sem[periodo]

    df_calc = st.session_state.df_live[st.session_state.df_live["Activo"] == True].copy()
    
    if not df_calc.empty:
        # 1. Limpieza
        df_calc = df_calc.loc[:, ~df_calc.columns.duplicated()]

        # 2. Cálculos
        df_calc["Total_Necesario"] = df_calc["Cantidad_Semanal"] * multiplicador
        df_calc["Paquetes"] = np.ceil(df_calc["Total_Necesario"] / df_calc["Rendimiento_Paquete"])
        df_calc["Subtotal"] = df_calc["Paquetes"] * df_calc["Precio_Paquete"]
        
        # Aseguramos que Unidad_Compra tenga texto
        df_calc["Unidad_Compra"] = df_calc["Unidad_Compra"].fillna("u.")

        total = df_calc['Subtotal'].sum()
        st.metric("Total Estimado", f"${total:,.0f}")
        
        # --- TABLA EXACTA A LA IMAGEN ---
        # Orden: Categoria | Producto | Total_Necesario | Paquetes | Unidad_Compra | Subtotal
        cols_finales = ["Categoria", "Producto", "Total_Necesario", "Paquetes", "Unidad_Compra", "Subtotal"]
        
        cols_existentes = [c for c in cols_finales if c in df_calc.columns]
        df_final = df_calc[cols_existentes].copy()

        st.dataframe(
            df_final,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Categoria": st.column_config.TextColumn("Categoría"),
                "Producto": st.column_config.TextColumn("Producto"),
                "Total_Necesario": st.column_config.NumberColumn(
                    "Necesario", 
                    format="%.2f",
                    help="Tu consumo total calculado"
                ),
                "Paquetes": st.column_config.NumberColumn(
                    "Cant.",  # Cantidad de paquetes
                    format="%d",
                    help="Número de unidades a comprar"
                ),
                "Unidad_Compra": st.column_config.TextColumn(
                    "Envase", # Ejemplo: Frasco, Botella, Paquete
                    width="small"
                ),
                "Subtotal": st.column_config.NumberColumn("Total", format="$%d")
            }
        )

    else:
        st.info("👆 Selecciona productos en la lista de arriba para ver el cálculo.")
