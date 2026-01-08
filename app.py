import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Guerra - Cloud", layout="wide")
st.title("🛡️ Panel de Control: Dieta & Logística (Nube)")

# --- 1. CONEXIÓN A GOOGLE SHEETS ---
# Creamos la conexión usando los secretos que configuraremos luego
conn = st.connection("gsheets", type=GSheetsConnection)

# Función para cargar datos frescos desde Google
def cargar_datos():
    try:
        # ttl=0 significa "no guardes en caché, trae datos frescos siempre"
        df_prod = conn.read(worksheet="productos", ttl=0)
        df_men = conn.read(worksheet="menu", ttl=0)
        return df_prod, df_men
    except Exception as e:
        st.error(f"⚠️ Error conectando a Google Sheets: {e}")
        st.stop()

df_productos, df_menu = cargar_datos()

# ==========================================
# 🛠️ ADMINISTRAR DATOS (ESCRITURA EN LA NUBE)
# ==========================================
with st.expander("🛠️ Administrar Base de Datos (Google Sheets)", expanded=False):
    st.info("💡 Los cambios que hagas aquí se guardan en tu Google Sheet y se actualizan en el celular de tu pareja.")
    
    tab_prod, tab_menu = st.tabs(["📝 Productos", "📅 Menú"])
    
    # --- EDITOR PRODUCTOS ---
    with tab_prod:
        df_productos_editado = st.data_editor(
            df_productos,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_prod_cloud"
        )
        
        if st.button("💾 Guardar Cambios en Productos"):
            try:
                # Escribimos de vuelta a la hoja "productos"
                conn.update(worksheet="productos", data=df_productos_editado)
                st.success("✅ ¡Guardado en la nube! Tu pareja ya puede verlo.")
                st.cache_data.clear() # Limpiamos memoria para forzar recarga
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # --- EDITOR MENÚ ---
    with tab_menu:
        df_menu_editado = st.data_editor(
            df_menu,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_menu_cloud"
        )
        
        if st.button("💾 Guardar Cambios en Menú"):
            try:
                conn.update(worksheet="menu", data=df_menu_editado)
                st.success("✅ ¡Menú actualizado en la nube!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

st.divider()

# --- BARRA SUPERIOR ---
modo = st.radio("Modo:", ["🛒 Armar Carrito", "🍱 Cocina"], horizontal=True)

# ==========================================
# LÓGICA DE CARRITO (Igual que antes pero con datos de nube)
# ==========================================
if modo == "🛒 Armar Carrito":
    # ... (Aquí va la misma lógica de cálculo que tenías antes) ...
    # (He resumido esta parte para no hacer el código gigante, 
    #  pero usa la misma lógica de pd.merge con df_productos y df_menu que ya cargamos arriba)
    
    # CALCULADORA RÁPIDA (Ejemplo simplificado para verificar conexión)
    st.subheader("🛒 Tu Carrito (Nube)")
    # Hacemos el merge
    df_resumen = df_menu.groupby("Producto")["Cantidad_Estimada"].sum().reset_index()
    df_compra = pd.merge(df_resumen, df_productos, on="Producto", how="left")
    df_compra["Precio"] = df_compra["Precio"].fillna(0)
    df_compra["Total"] = df_compra["Cantidad_Estimada"] * df_compra["Precio"]
    
    st.dataframe(df_compra)
    st.metric("Total Estimado", f"${df_compra['Total'].sum():,.2f}")

elif modo == "🍱 Cocina":
    st.write("Vista de cocina conectada a Google Sheets...")
    st.dataframe(df_menu)