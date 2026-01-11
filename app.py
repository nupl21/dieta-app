import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Dieta - Gestión Unificada", layout="wide", page_icon="⚖️")
st.title("⚖️ Panel de Control: Lista Semanal Única")

# --- CONEXIÓN CON GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS (LISTA SEMANAL) ---
@st.cache_data(ttl=600)
def cargar_datos_nube():
    try:
        df = conn.read(worksheet="plan_dieta_unificado")
        
        # VALIDACIONES DE SEGURIDAD
        # Manejo de booleanos para la columna Activo
        df["Activo"] = df["Activo"].astype(str).str.upper() == "TRUE"
        
        # MODIFICACIÓN 1: Usamos Cantidad_Semanal en lugar de Cantidad_Diaria
        cols_num = ["Cantidad_Semanal", "Rendimiento_Paquete", "Precio_Paquete"]
        for col in cols_num:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # Prevenir errores matemáticos
        df.loc[df["Rendimiento_Paquete"] <= 0, "Rendimiento_Paquete"] = 1
        
        return df
    except Exception as e:
        st.error(f"⚠️ Error al conectar con la nube: {e}")
        return pd.DataFrame()

# --- 2. GESTIÓN DE MEMORIA (SESSION STATE) ---
if 'df_live' not in st.session_state:
    st.session_state.df_live = cargar_datos_nube()

# Función para recargar si hay cambios externos
def recargar_datos():
    st.cache_data.clear()
    st.session_state.df_live = cargar_datos_nube()

# ==========================================
# 🛠️ SECCIÓN DE ADMINISTRACIÓN (EDITOR POTENCIADO)
# ==========================================
with st.expander("🛠️ Editar Productos y Precios", expanded=True):
    st.info("💡 Modifica el consumo total de 7 días. Usa los filtros para encontrar rápido.")
    
    # --- A. BOTONES GENERALES ---
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    
    if col_btn1.button("✅ Seleccionar TODO"):
        st.session_state.df_live["Activo"] = True
        st.rerun()
        
    if col_btn2.button("❌ Deseleccionar TODO"):
        st.session_state.df_live["Activo"] = False
        st.rerun()

    # --- B. FILTROS ---
    st.divider()
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        cats_disponibles = st.session_state.df_live["Categoria"].unique() if not st.session_state.df_live.empty else []
        filtro_categoria = st.multiselect("📂 Filtrar por Categoría:", cats_disponibles)
    with col_filtro2:
        filtro_producto = st.text_input("🔍 Buscar Producto:", placeholder="Ej: Pollo, Avena...")

    # --- C. APLICAR FILTROS (MÁSCARA) ---
    mask = pd.Series([True] * len(st.session_state.df_live))
    
    if filtro_categoria:
        mask = mask & st.session_state.df_live["Categoria"].isin(filtro_categoria)
    if filtro_producto:
        mask = mask & st.session_state.df_live["Producto"].str.contains(filtro_producto, case=False)

    df_vista = st.session_state.df_live[mask]

    # --- D. EDITOR DE DATOS ---
    # MODIFICACIÓN 2: Configuración de columnas adaptada a la lista unificada (sin Día)
    df_editado = st.data_editor(
        df_vista,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_unificado_final",
        column_config={
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Almacén", "Verduleria", "Carniceria", "Dietetica", "Lácteos"]),
            "Precio_Paquete": st.column_config.NumberColumn("Precio $", format="$%d"),
            "Cantidad_Semanal": st.column_config.NumberColumn("Consumo 7 días", format="%.2f"),
            "Activo": st.column_config.CheckboxColumn("¿Incluir?")
        }
    )

    # Actualizar memoria con los cambios del editor filtrado
    st.session_state.df_live.update(df_editado)
    
    # --- E. GUARDADO ---
    col_save1, col_save2 = st.columns([1, 4])
    if col_save1.button("💾 Guardar en Nube"):
        try:
            conn.update(worksheet="plan_dieta_unificado", data=st.session_state.df_live)
            st.cache_data.clear() 
            st.success("✅ ¡Nube actualizada!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
            
    if col_save2.button("🔄 Descartar cambios"):
        recargar_datos()
        st.rerun()

st.divider()

# ==========================================
# 🛒 CÁLCULO DE CARRITO (POR SEMANAS)
# ==========================================
if not st.session_state.df_live.empty:
    st.subheader("🛒 ¿Cuánto tiempo quieres presupuestar?")
    
    # Selector de tiempo (Semanas/Mes)
    periodo = st.select_slider(
        "Selecciona el período de compra:",
        options=["1 Semana", "2 Semanas", "3 Semanas", "1 Mes (4 Semanas)"]
    )
    
    mapeo_semanas = {"1 Semana": 1, "2 Semanas": 2, "3 Semanas": 3, "1 Mes (4 Semanas)": 4}
    multiplicador = mapeo_semanas[periodo]

    # Filtrar solo activos
    df_calc = st.session_state.df_live[st.session_state.df_live["Activo"] == True].copy()
    
    if not df_calc.empty:
        # CÁLCULOS
        # Cantidad Total = Semanal * Multiplicador
        df_calc["Total_Necesario"] = df_calc["Cantidad_Semanal"] * multiplicador
        
        # Paquetes = Total / Rendimiento (Redondeo hacia arriba)
        df_calc["Paquetes"] = np.ceil(df_calc["Total_Necesario"] / df_calc["Rendimiento_Paquete"])
        
        # Costo
        df_calc["Subtotal"] = df_calc["Paquetes"] * df_calc["Precio_Paquete"]
        
        # Ordenar
        df_calc = df_calc.sort_values(by=["Categoria", "Producto"])
        
        st.markdown(f"### 📋 Lista de Compras para {periodo}")
        st.dataframe(
            df_calc[["Categoria", "Producto", "Total_Necesario", "Paquetes", "Unidad_Compra", "Subtotal"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Subtotal": st.column_config.NumberColumn("Costo Estimado", format="$%d"),
                "Total_Necesario": st.column_config.NumberColumn("Cant. Total", format="%.2f")
            }
        )
        
        st.metric(f"💰 Presupuesto Total ({periodo})", f"${df_calc['Subtotal'].sum():,.2f}")
    else:
        st.warning("⚠️ No hay productos seleccionados. Usa los botones de arriba para seleccionar.")
else:
    st.info("Cargando datos...")
