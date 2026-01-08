import streamlit as st
import pandas as pd
import numpy as np  # <--- IMPORTANTE: Necesario para redondear hacia arriba
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Plan de Guerra - Cloud", layout="wide", page_icon="🛡️")
st.title("🛡️ Panel de Control: Lista de Compras (Nube)")

# --- CONEXIÓN CON GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGA DE DATOS ---
def cargar_datos():
    try:
        # Leemos directo de la nube con ttl=0
        prod = conn.read(worksheet="productos", ttl=0)
        menu = conn.read(worksheet="menu_semanal", ttl=0)
        
        # Limpieza de Precios
        prod['Precio'] = pd.to_numeric(prod['Precio'], errors='coerce').fillna(0)
        
        # Aseguramos que exista la columna Unidad
        if 'Unidad' not in prod.columns:
            prod['Unidad'] = "Unidad"
        prod['Unidad'] = prod['Unidad'].fillna("Unidad")

        # ### NUEVO: Aseguramos que exista la columna Rendimiento
        if 'Rendimiento' not in prod.columns:
            prod['Rendimiento'] = 1
        
        # Limpieza de Rendimiento (convertir a número y evitar ceros)
        prod['Rendimiento'] = pd.to_numeric(prod['Rendimiento'], errors='coerce').fillna(1)
        prod.loc[prod['Rendimiento'] <= 0, 'Rendimiento'] = 1

        # Limpieza de Menú
        menu['Cantidad_Estimada'] = pd.to_numeric(menu['Cantidad_Estimada'], errors='coerce').fillna(0)
        
        return prod, menu
    except Exception as e:
        st.error(f"⚠️ Error conectando con Google Sheets. Verifica las hojas. Detalle: {e}")
        st.stop()

df_productos, df_menu = cargar_datos()

# ==========================================
# 🛠️ SECCIÓN DE ADMINISTRACIÓN
# ==========================================
with st.expander("🛠️ Administrar Datos (Editar Precios, Productos y Menú)", expanded=False):
    st.info("💡 **Tip:** En 'Rendimiento' pon cuánto trae el paquete. Ej: Pan Lactal = 20 (rodajas), Huevos = 30 (maple), Carne = 1 (kg).")
    
    tab_prod, tab_menu = st.tabs(["📝 Base de Productos", "📅 Menú Semanal"])
    
    # --- EDITOR DE PRODUCTOS ---
    with tab_prod:
        st.write("Edita precios, unidades y rendimiento.")
        
        df_productos_editado = st.data_editor(
            df_productos,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_productos_cloud",
            column_config={
                "Precio": st.column_config.NumberColumn(format="$%d"),
                "Rendimiento": st.column_config.NumberColumn(
                    "Rendimiento (Trae x Paq)",
                    help="¿Cuántas unidades/gramos trae el paquete que compras?",
                    format="%.1f"
                ),
                "Unidad": st.column_config.SelectboxColumn(
                    "Unidad de Compra",
                    options=["Kg", "Litro", "Unidad", "Paquete", "Botella", "Lata", "Docena", "Maple"],
                    required=True
                )
            }
        )
        
        if st.button("💾 Guardar Cambios en Productos (Nube)"):
            try:
                conn.update(worksheet="productos", data=df_productos_editado)
                st.success("✅ ¡Actualizado! Recargando...")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # --- EDITOR DE MENÚ ---
    with tab_menu:
        st.write("Modifica las cantidades de las recetas.")
        df_menu_editado = st.data_editor(
            df_menu,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_menu_cloud"
        )
        
        if st.button("💾 Guardar Cambios en Menú (Nube)"):
            try:
                conn.update(worksheet="menu_semanal", data=df_menu_editado)
                st.success("✅ ¡Actualizado! Recargando...")
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
    with st.expander("📅 Configuración de Días", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            dias_a_calcular = st.number_input("Días a cubrir", min_value=1, value=30, step=1)
        with col_b:
            dia_inicio = st.selectbox("Día de inicio del menú", options=[1,2,3,4,5,6,7])

    # --- B. MOTOR DE CÁLCULO ---
    if df_menu.empty:
        st.warning("⚠️ Menú vacío.")
        st.stop()

    conteo_dias = {i: 0 for i in range(1, 8)}
    dia_actual = dia_inicio
    for _ in range(dias_a_calcular):
        conteo_dias[dia_actual] += 1
        dia_actual += 1
        if dia_actual > 7: dia_actual = 1
            
    df_calculo = df_menu.copy()
    df_calculo["Repeticiones"] = df_calculo["Dia"].map(conteo_dias).fillna(0)
    df_calculo["Consumo_Total"] = df_calculo["Cantidad_Estimada"] * df_calculo["Repeticiones"]
    
    df_resumen = df_calculo.groupby("Producto")["Consumo_Total"].sum().reset_index()
    
    # --- UNIÓN Y CÁLCULO INTELIGENTE (OPCIÓN 2) ---
    df_base = pd.merge(df_resumen, df_productos, on="Producto", how="left")
    
    # Rellenos de seguridad
    df_base["Precio"] = df_base["Precio"].fillna(0)
    df_base["Unidad"] = df_base["Unidad"].fillna("?")
    if "Rendimiento" not in df_base.columns:
        df_base["Rendimiento"] = 1
    df_base["Rendimiento"] = pd.to_numeric(df_base["Rendimiento"], errors='coerce').fillna(1)
    df_base.loc[df_base["Rendimiento"] <= 0, "Rendimiento"] = 1 # Evitar división por cero

    # FÓRMULA: Lo que como / Lo que trae el paquete
    df_base["Cantidad_Calculada"] = df_base["Consumo_Total"] / df_base["Rendimiento"]
    
    # REDONDEO: Hacia arriba (Ceiling)
    df_base["Cantidad_Calculada"] = np.ceil(df_base["Cantidad_Calculada"])

    df_base = df_base.sort_values("Producto")

    # --- C. GESTIÓN DE MEMORIA (SESSION STATE) ---
    if 'df_carrito' not in st.session_state:
        df_base["Incluir"] = False
        # Usamos la cantidad ya calculada en paquetes
        df_base["Cantidad_a_Comprar"] = df_base["Cantidad_Calculada"]
        st.session_state.df_carrito = df_base
    else:
        # Preservar estado
        df_viejo = st.session_state.df_carrito[["Producto", "Incluir", "Cantidad_a_Comprar"]]
        df_nuevo = df_base[["Producto", "Consumo_Total", "Cantidad_Calculada", "Precio", "Lugar_Compra", "Unidad", "Rendimiento"]]
        
        df_final = pd.merge(df_nuevo, df_viejo, on="Producto", how="left")
        df_final["Incluir"] = df_final["Incluir"].fillna(False)
        # Si es nuevo o recálculo, priorizamos el cálculo inteligente
        df_final["Cantidad_a_Comprar"] = df_final["Cantidad_a_Comprar"].fillna(df_final["Cantidad_Calculada"])
        
        # Opcional: Si quieres que se actualice siempre que cambias días, descomenta la siguiente línea:
        # df_final["Cantidad_a_Comprar"] = df_final["Cantidad_Calculada"] 
        
        st.session_state.df_carrito = df_final

    # --- D. FILTROS ---
    st.subheader("🔍 Buscador y Selección")
    col_search, col_actions = st.columns([2, 1])
    
    with col_search:
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
        df_view[["Incluir", "Producto", "Consumo_Total", "Rendimiento", "Cantidad_a_Comprar", "Unidad", "Precio", "Lugar_Compra"]],
        column_config={
            "Incluir": st.column_config.CheckboxColumn("¿Comprar?", default=False),
            "Consumo_Total": st.column_config.NumberColumn("Consumo Real", format="%.1f", disabled=True, help="Total de unidades/gramos que vas a comer"),
            "Rendimiento": st.column_config.NumberColumn("Rinde", disabled=True, help="Cuánto trae el paquete (según Admin)"),
            "Cantidad_a_Comprar": st.column_config.NumberColumn("Paquetes ✏️", format="%.1f"),
            "Precio": st.column_config.NumberColumn("Precio ($)", format="$%d"),
            "Unidad": st.column_config.TextColumn("Unidad", disabled=True),
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
    col2.metric("📦 Paquetes/Unidades", f"{df_seleccionado['Cantidad_a_Comprar'].sum():.1f}")

# ==========================================
# MODO 2: COCINA
# ==========================================
elif modo == "🍱 Ver Recetas (Cocina)":
    st.subheader("Guía de Cocina")
    if df_menu.empty:
         st.info("No hay menú cargado aún.")
    else:
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
