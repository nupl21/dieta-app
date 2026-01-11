import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Dieta - Gestión Inteligente", layout="wide", page_icon="🧠")
st.title("🧠 Panel de Control: Compra Inteligente")

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
            
        # LIMPIEZA DE TIPO_COMPRA (Normalizamos mayúsculas/minúsculas)
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
# 🛠️ ADMINISTRACIÓN
# ==========================================
with st.expander("🛠️ Editar Productos y Frecuencia", expanded=True):
    st.info("💡 Frecuencia: Semanal (Frescos), Quincenal (Huevos/Papas), Mensual (Freezer/Latas).")
    
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("✅ Seleccionar TODO"):
        st.session_state.df_live["Activo"] = True
        st.rerun()
    if col_btn2.button("❌ Deseleccionar TODO"):
        st.session_state.df_live["Activo"] = False
        st.rerun()

    st.divider()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cats = st.session_state.df_live["Categoria"].unique() if not st.session_state.df_live.empty else []
        filtro_cat = st.multiselect("Filtrar Categoría:", cats)
    with col_f2:
        filtro_txt = st.text_input("Buscar:", placeholder="Pollo...")

    mask = pd.Series([True] * len(st.session_state.df_live))
    if filtro_cat: mask &= st.session_state.df_live["Categoria"].isin(filtro_cat)
    if filtro_txt: mask &= st.session_state.df_live["Producto"].str.contains(filtro_txt, case=False)

    df_vista = st.session_state.df_live[mask]

    # --- CAMBIO 1: AGREGAR "Quincenal" A LAS OPCIONES DEL EDITOR ---
    df_editado = st.data_editor(
        df_vista,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_inteligente",
        column_config={
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Almacén", "Verduleria", "Carniceria", "Dietetica", "Lácteos"]),
            "Tipo_Compra": st.column_config.SelectboxColumn("Frecuencia", options=["Semanal", "Quincenal", "Mensual"], help="Define cada cuánto compras esto."),
            "Precio_Paquete": st.column_config.NumberColumn("Precio $", format="$%d"),
            "Cantidad_Semanal": st.column_config.NumberColumn("Consumo 7 días", format="%.2f"),
            "Activo": st.column_config.CheckboxColumn("¿Incluir?")
        }
    )
    
    st.session_state.df_live.update(df_editado)
    
    col_s1, col_s2 = st.columns([1, 4])
    if col_s1.button("💾 Guardar"):
        try:
            conn.update(worksheet="plan_dieta_unificado", data=st.session_state.df_live)
            st.cache_data.clear()
            st.success("✅ Guardado!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
    if col_s2.button("🔄 Recargar"):
        recargar_datos()
        st.rerun()

st.divider()

# ==========================================
# 🛒 CÁLCULO INTELIGENTE (LOGICA DINÁMICA)
# ==========================================
if not st.session_state.df_live.empty:
    st.subheader("🛒 Planificador de Compra")
    
    periodo = st.select_slider("Selecciona período:", options=["1 Semana", "2 Semanas", "3 Semanas", "1 Mes (4 Semanas)"])
    map_sem = {"1 Semana": 1, "2 Semanas": 2, "3 Semanas": 3, "1 Mes (4 Semanas)": 4}
    multiplicador = map_sem[periodo]

    df_calc = st.session_state.df_live[st.session_state.df_live["Activo"] == True].copy()
    
    if not df_calc.empty:
        # Cálculos Base
        df_calc["Total_Necesario"] = df_calc["Cantidad_Semanal"] * multiplicador
        df_calc["Paquetes"] = np.ceil(df_calc["Total_Necesario"] / df_calc["Rendimiento_Paquete"])
        df_calc["Subtotal"] = df_calc["Paquetes"] * df_calc["Precio_Paquete"]
        
        cols_show = ["Categoria", "Producto", "Total_Necesario", "Paquetes", "Unidad_Compra", "Subtotal"]
        
        # --- CAMBIO 2: LÓGICA DINÁMICA PARA MOVER LO QUINCENAL ---
        if multiplicador > 1:
            
            if multiplicador >= 4: 
                # SI ES MES: Solo lo Mensual es Stock. Lo Quincenal se repone.
                condicion_stock = df_calc["Tipo_Compra"] == "Mensual"
                texto_fresco = "FRESCOS Y QUINCENALES (Reponer durante el mes)"
            else:
                # SI ES QUINCENA: Lo Mensual Y lo Quincenal son Stock (se compran hoy).
                condicion_stock = df_calc["Tipo_Compra"].isin(["Mensual", "Quincenal"])
                texto_fresco = "FRESCOS (Reponer semanalmente)"

            df_stock = df_calc[condicion_stock]
            df_fresco = df_calc[~condicion_stock]
            
            st.info(f"📊 Visualizando compra para {periodo}")
            col_stock, col_fresco = st.columns(2)
            
            with col_stock:
                st.success(f"🧊 **STOCK INICIAL (${df_stock['Subtotal'].sum():,.0f})**")
                st.caption("Compra todo esto HOY para cubrir el periodo.")
                st.dataframe(df_stock[cols_show], hide_index=True, use_container_width=True)
                
            with col_fresco:
                if not df_fresco.empty:
                    st.warning(f"🥗 **{texto_fresco} (${df_fresco['Subtotal'].sum():,.0f})**")
                    st.caption("Total estimado. Compra solo lo de la semana para que no se pudra.")
                    st.dataframe(df_fresco[cols_show], hide_index=True, use_container_width=True)
                else:
                    st.success("✅ ¡Todo entra en la compra inicial!")
                
        else:
            # 1 Semana = Todo junto
            st.dataframe(df_calc[cols_show], hide_index=True, use_container_width=True)

        st.divider()
        st.metric(f"💰 TOTAL ESTIMADO ({periodo})", f"${df_calc['Subtotal'].sum():,.2f}")
    else:
        st.warning("Selecciona productos arriba.")
