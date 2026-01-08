import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Guerra - Cloud", layout="wide", page_icon="🛡️")
st.title("🛡️ Panel de Control: Lista de Compras (Nube)")

# --- CONEXIÓN CON GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS ---
def cargar_datos():
    try:
        # Leemos directo de la nube con ttl=0 para no guardar caché vieja
        prod = conn.read(worksheet="productos", ttl=0)
        menu = conn.read(worksheet="menu_semanal", ttl=0)
        
        # Limpieza básica para evitar errores de cálculo
        prod['Precio'] = pd.to_numeric(prod['Precio'], errors='coerce').fillna(0)
        menu['Cantidad_Estimada'] = pd.to_numeric(menu['Cantidad_Estimada'], errors='coerce').fillna(0)
        
        return prod, menu
    except Exception as e:
        st.error(f"⚠️ Error conectando con Google Sheets. Verifica que existan las hojas 'productos' y 'menu_semanal'. Detalle: {e}")
        st.stop()

df_productos, df_menu = cargar_datos()

# ==========================================
# 🛠️ SECCIÓN DE ADMINISTRACIÓN (GUARDADO EN LA NUBE)
# ==========================================
with st.expander("🛠️ Administrar Datos (Editar Precios, Productos y Menú)", expanded=False):
    st.info("💡 Los cambios que hagas aquí se guardarán directamente en tu Google Sheet.")
    
    tab_prod, tab_menu = st.tabs(["📝 Base de Productos", "📅 Menú Semanal"])
    
    # --- EDITOR DE PRODUCTOS ---
    with tab_prod:
        st.write("Edita precios, agrega productos nuevos o cambia lugares de compra.")
        df_productos_editado = st.data_editor(
            df_productos,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_productos_cloud",
            column_config={
                "Precio": st.column_config.NumberColumn(format="$%d")
            }
        )
        
        if st.button("💾 Guardar Cambios en Productos (Nube)"):
            try:
                # AQUÍ ESTÁ LA MAGIA: Actualizamos Google Sheets
                conn.update(worksheet="productos", data=df_productos_editado)
                st.success("✅ ¡Google Sheet 'productos' actualizado! Recargando...")
                st.cache_data.clear() # Limpiamos memoria
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # --- EDITOR DE MENÚ ---
    with tab_menu:
        st.write("Modifica las cantidades de las recetas o agrega comidas.")
        df_menu_editado = st.data_editor(
            df_menu,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_menu_cloud"
        )
        
        if st.button("💾 Guardar Cambios en Menú (Nube)"):
            try:
                conn.update(worksheet="menu_semanal", data=df_menu_editado)
                st.success("✅ ¡Google Sheet 'menu_semanal' actualizado! Recargando...")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

st.divider()

# --- BARRA SUPERIOR DE MODOS ---
modo = st.radio("Modo de Uso:", 
                ["🛒 Armar Carrito de Compra", "🍱 Ver Recetas (Cocina)"], 
                horizontal=True)

# ==========================================
# MODO 1: ARMAR CARRITO
# ==========================================
if modo == "🛒 Armar Carrito de Compra":
    
    # --- A. CONFIGURACIÓN ---
    with st.expander("📅 Configuración de Días (Opcional)", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            dias_a_calcular = st.number_input("Días a cubrir", min_value=1, value=30, step=1)
        with col_b:
            dia_inicio = st.selectbox("Día de inicio del menú", options=[1,2,3,4,5,6,7])

    # --- B. MOTOR DE CÁLCULO ---
    if df_menu.empty:
        st.warning("⚠️ Tu hoja de 'menu_semanal' está vacía. Ve a 'Administrar Datos' para agregar comidas.")
        st.stop()

    conteo_dias = {i: 0 for i in range(1, 8)}
    dia_actual = dia_inicio
    for _ in range(dias_a_calcular):
        conteo_dias[dia_actual] += 1
        dia_actual += 1
        if dia_actual > 7: dia_actual = 1
            
    df_calculo = df_menu.copy()
    # Mapeo seguro de repeticiones
    df_calculo["Repeticiones"] = df_calculo["Dia"].map(conteo_dias).fillna(0)
    df_calculo["Consumo_Total"] = df_calculo["Cantidad_Estimada"] * df_calculo["Repeticiones"]
    
    df_resumen = df_calculo.groupby("Producto")["Consumo_Total"].sum().reset_index()
    
    # Unimos con los productos
    df_base = pd.merge(df_resumen, df_productos, on="Producto", how="left")
    df_base["Precio"] = df_base["Precio"].fillna(0)
    df_base = df_base.sort_values("Producto")

    # --- C. GESTIÓN DE MEMORIA (SESSION STATE) ---
    if 'df_carrito' not in st.session_state:
        df_base["Incluir"] = False
        df_base["Cantidad_a_Comprar"] = df_base["Consumo_Total"]
        st.session_state.df_carrito = df_base
    else:
        # Actualizamos lógica preservando selecciones
        df_viejo = st.session_state.df_carrito[["Producto", "Incluir", "Cantidad_a_Comprar"]]
        df_nuevo = df_base[["Producto", "Consumo_Total", "Precio", "Lugar_Compra"]]
        df_final = pd.merge(df_nuevo, df_viejo, on="Producto", how="left")
        df_final["Incluir"] = df_final["Incluir"].fillna(False)
        df_final["Cantidad_a_Comprar"] = df_final["Cantidad_a_Comprar"].fillna(df_final["Consumo_Total"])
        st.session_state.df_carrito = df_final

    # --- D. FILTROS Y BOTONES ---
    st.subheader("🔍 Buscador y Selección")
    col_search, col_actions = st.columns([2, 1])
    
    with col_search:
        # --- AQUÍ ESTABA EL ERROR, YA CORREGIDO ---
        try:
            opciones = st.session_state.df_carrito["Producto"].unique()
        except KeyError:
            opciones = []
            
        filtro_usuario = st.multiselect(
            "Filtrar productos:",
            options=opciones,
            placeholder="Escribe para buscar..."
        )

    if filtro_usuario:
        df_view = st.session_state.df_carrito[st.session_state.df_carrito["Producto"].isin(filtro_usuario)]
    else:
        df_view = st.session_state.df_carrito

    with col_actions:
        st.write("Acciones:")
        c1, c2 = st.columns(2)
        if c1.button("✅ Todo"):
            st.session_state.df_carrito.loc[df_view.index, "Incluir"] = True
            st.rerun()
        if c2.button("❌ Nada"):
            st.session_state.df_carrito.loc[df_view.index, "Incluir"] = False
            st.rerun()

    # --- E. TABLA PRINCIPAL ---
    edited_df = st.data_editor(
        df_view[["Incluir", "Producto", "Consumo_Total", "Cantidad_a_Comprar", "Precio", "Lugar_Compra"]],
        column_config={
            "Incluir": st.column_config.CheckboxColumn("¿Comprar?", default=False),
            "Consumo_Total": st.column_config.NumberColumn("Necesitas", format="%.2f", disabled=True),
            "Cantidad_a_Comprar": st.column_config.NumberColumn("Llevas ✏️", format="%.2f"),
            "Precio": st.column_config.NumberColumn("Precio ($)", format="$%d"),
            "Lugar_Compra": st.column_config.SelectboxColumn("Lugar", options=["Coto", "Verduleria", "Carniceria", "Dietetica", "Otro"])
        },
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="editor_carrito_final"
    )
    
    st.session_state.df_carrito.update(edited_df)

    # --- F. RESULTADOS ---
    df_total = st.session_state.df_carrito
    df_seleccionado = df_total[df_total["Incluir"] == True]
    
    costo_carrito = (df_seleccionado["Cantidad_a_Comprar"] * df_seleccionado["Precio"]).sum()
    
    st.divider()
    col1, col2 = st.columns(2)
    col1.metric("🛒 Total a Pagar", f"${costo_carrito:,.2f}")
    col2.metric("📦 Productos", f"{len(df_seleccionado)}")

# ==========================================
# MODO 2: COCINA
# ==========================================
elif modo == "🍱 Ver Recetas (Cocina)":
    st.subheader("Guía de Cocina")
    
    if df_menu.empty:
         st.info("No hay menú cargado aún.")
    else:
        # Aseguramos que 'Dia' sea numérico para ordenar bien
        # Si tienes problemas aquí, podemos quitar el 'sorted'
        try:
            dias = sorted(df_menu["Dia"].unique())
        except:
            dias = df_menu["Dia"].unique()

        if len(dias) > 0:
            tabs = st.tabs([f"Día {d}" for d in dias])
            for i, d in enumerate(dias):
                with tabs[i]:
                    dd = df_menu[df_menu["Dia"] == d]
                    for m in ["Desayuno", "Almuerzo", "Colacion", "Merienda", "Cena"]:
                        ing = dd[dd["Momento"] == m]
                        if not ing.empty:
                            st.markdown(f"**{m}**")
                            st.dataframe(ing[["Producto", "Cantidad_Estimada"]], hide_index=True)
        else:
            st.warning("Hay datos en el menú, pero no columna 'Dia' válida.")
