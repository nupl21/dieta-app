import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Guerra - Lista Única", layout="wide", page_icon="🛡️")
st.title("🛡️ Panel de Control: Plan de Dieta (Nube)")

# --- CONEXIÓN CON GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos_nube():
    try:
        df = conn.read(worksheet="plan_dieta_unificado")
        # Manejo seguro de booleanos
        df["Activo"] = df["Activo"].astype(str).str.upper() == "TRUE"
        # Limpieza numérica
        cols_numericas = ["Cantidad_Diaria", "Rendimiento_Paquete", "Precio_Paquete"]
        for col in cols_numericas:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df.loc[df["Rendimiento_Paquete"] <= 0, "Rendimiento_Paquete"] = 1
        return df
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        return pd.DataFrame()

df_plan = cargar_datos_nube()

# ==========================================
# 🛠️ SECCIÓN DE ADMINISTRACIÓN (EDITOR)
# ==========================================
with st.expander("🛠️ Administrar Plan Unificado", expanded=True): # Lo pongo abierto por defecto
    st.info("💡 Los cambios que hagas aquí se reflejan abajo al instante. Para que sean permanentes, pulsa 'Guardar'.")
    
    # IMPORTANTE: El editor ahora devuelve los datos a la variable 'df_plan'
    df_plan = st.data_editor(
        df_plan,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_nube_unico",
        column_config={
            "Dia": st.column_config.NumberColumn("Día", min_value=1, max_value=7),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Almacén", "Verduleria", "Carniceria", "Dietetica", "Lácteos"]),
            "Precio_Paquete": st.column_config.NumberColumn("Precio $", format="$%d"),
            "Activo": st.column_config.CheckboxColumn("¿Incluir?")
        }
    )
    
    if st.button("💾 Guardar Cambios en la Nube"):
        try:
            conn.update(worksheet="plan_dieta_unificado", data=df_plan)
            st.cache_data.clear() 
            st.success("✅ ¡Nube actualizada!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

st.divider()

# ==========================================
# 🛒 CÁLCULO DE CARRITO (AHORA EN TIEMPO REAL)
# ==========================================
if not df_plan.empty:
    col_a, col_b = st.columns(2)
    with col_a:
        dias_totales = st.number_input("¿Cuántos días cubrir?", min_value=1, value=30)
    with col_b:
        dia_inicio = st.selectbox("¿Qué día empiezas hoy?", options=[1,2,3,4,5,6,7])

    # Motor de repeticiones
    conteo_reps = {i: 0 for i in range(1, 8)}
    actual = dia_inicio
    for _ in range(dias_totales):
        conteo_reps[actual] += 1
        actual = actual + 1 if actual < 7 else 1
    
    # CAMBIO CLAVE: Aquí filtramos sobre df_plan, que ya tiene los cambios del editor
    df_calc = df_plan[df_plan["Activo"] == True].copy()
    
    if not df_calc.empty:
        df_calc["Veces"] = df_calc["Dia"].map(conteo_reps)
        df_calc["Total_Consumo"] = df_calc["Cantidad_Diaria"] * df_calc["Veces"]
        
        resumen = df_calc.groupby(["Categoria", "Producto", "Rendimiento_Paquete", "Unidad_Compra", "Precio_Paquete"])["Total_Consumo"].sum().reset_index()
        
        resumen["Paquetes"] = np.ceil(resumen["Total_Consumo"] / resumen["Rendimiento_Paquete"])
        resumen["Subtotal"] = resumen["Paquetes"] * resumen["Precio_Paquete"]
        
        resumen = resumen.sort_values(by=["Categoria", "Producto"])
        
        st.subheader("📋 Tu Lista de Compras Actual")
        st.dataframe(
            resumen[["Categoria", "Producto", "Total_Consumo", "Paquetes", "Unidad_Compra", "Subtotal"]],
            hide_index=True,
            use_container_width=True,
            column_config={"Subtotal": st.column_config.NumberColumn(format="$%d")}
        )
        
        st.metric("💰 Presupuesto Total", f"${resumen['Subtotal'].sum():,.2f}")
    else:
        # Esto sale si no hay ningún checkbox tildado arriba
        st.warning("⚠️ No hay productos seleccionados. Tilda la columna '¿Incluir?' en la tabla de arriba.")
