import streamlit as st
import osmnx as ox
import networkx as nx
import pulp
import folium
from streamlit_folium import st_folium
import random
import numpy as np
from folium import plugins
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Optimización de Rutas de Ambulancias", layout="wide")

# Título
st.title("🚑 Sistema de Optimización de Rutas de Ambulancias")
st.markdown("### Modelo de Flujo Multiflujo para Emergencias Médicas Urbanas")

# ===========================
# PARÁMETROS Y CONFIGURACIÓN
# ===========================

# Sidebar para configuración
st.sidebar.header("⚙️ Configuración del Sistema")

# Zona de estudio - Laureles, Medellín (zona urbana densa)
center_lat = st.sidebar.number_input("Latitud del centro", value=6.2442, format="%.4f")
center_lon = st.sidebar.number_input("Longitud del centro", value=-75.5890, format="%.4f")
radius = st.sidebar.slider("Radio de estudio (metros)", 400, 800, 560)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Parámetros de Velocidad")

# Parámetros de velocidad requerida (km/h)
col1, col2 = st.sidebar.columns(2)
R_min = col1.number_input("R_min (km/h)", value=30.0, min_value=10.0, max_value=50.0)
R_max = col2.number_input("R_max (km/h)", value=80.0, min_value=50.0, max_value=120.0)

# Parámetros de capacidad de vías (km/h)
C_min = col1.number_input("C_min (km/h)", value=20.0, min_value=10.0, max_value=40.0)
C_max = col2.number_input("C_max (km/h)", value=60.0, min_value=40.0, max_value=100.0)

st.sidebar.markdown("---")
st.sidebar.subheader("🚑 Tipos de Emergencias")

# Número de emergencias por tipo
n_leve = st.sidebar.number_input("Emergencias Leves", value=2, min_value=1, max_value=5)
n_media = st.sidebar.number_input("Emergencias Medias", value=2, min_value=1, max_value=5)
n_critica = st.sidebar.number_input("Emergencias Críticas", value=2, min_value=1, max_value=5)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Costos Operativos")

# Costos por tipo de ambulancia ($/km)
costo_leve = st.sidebar.number_input("Costo Ambulancia Leve ($/km)", value=1000, min_value=500, max_value=3000)
costo_media = st.sidebar.number_input("Costo Ambulancia Media ($/km)", value=2000, min_value=1000, max_value=5000)
costo_critica = st.sidebar.number_input("Costo Ambulancia Crítica ($/km)", value=4000, min_value=2000, max_value=8000)

# ===========================
# FUNCIONES AUXILIARES
# ===========================

@st.cache_data
def obtener_red_vial(lat, lon, dist):
    """Obtiene la red vial de OSMnx"""
    try:
        # Descargar red de calles
        G = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
        # Proyectar a sistema métrico
        G = ox.project_graph(G)
        return G
    except Exception as e:
        st.error(f"Error al obtener red vial: {e}")
        return None

def asignar_capacidades(G, c_min, c_max):
    """Asigna capacidades aleatorias a las aristas"""
    for u, v, k in G.edges(keys=True):
        G[u][v][k]['capacity'] = random.uniform(c_min, c_max)
    return G

def seleccionar_nodos_destino(G, n_total, origen):
    """Selecciona nodos destino aleatorios diferentes del origen"""
    nodos = list(G.nodes())
    nodos_disponibles = [n for n in nodos if n != origen]
    if len(nodos_disponibles) < n_total:
        n_total = len(nodos_disponibles)
    return random.sample(nodos_disponibles, n_total)

def generar_emergencias(G, origen, n_leve, n_media, n_critica, r_min, r_max):
    """Genera lista de emergencias con sus características"""
    n_total = n_leve + n_media + n_critica
    destinos = seleccionar_nodos_destino(G, n_total, origen)
    
    emergencias = []
    idx = 0
    
    # Emergencias leves
    for i in range(n_leve):
        emergencias.append({
            'id': f'leve_{i+1}',
            'tipo': 'Leve',
            'destino': destinos[idx],
            'velocidad_req': random.uniform(r_min, r_max),
            'costo_km': costo_leve,
            'color': 'green'
        })
        idx += 1
    
    # Emergencias medias
    for i in range(n_media):
        emergencias.append({
            'id': f'media_{i+1}',
            'tipo': 'Media',
            'destino': destinos[idx],
            'velocidad_req': random.uniform(r_min, r_max),
            'costo_km': costo_media,
            'color': 'orange'
        })
        idx += 1
    
    # Emergencias críticas
    for i in range(n_critica):
        emergencias.append({
            'id': f'critica_{i+1}',
            'tipo': 'Crítica',
            'destino': destinos[idx],
            'velocidad_req': random.uniform(r_min, r_max),
            'costo_km': costo_critica,
            'color': 'red'
        })
        idx += 1
    
    return emergencias

def resolver_modelo_multiflujo(G, origen, emergencias):
    """Resuelve el modelo de optimización multiflujo"""
    
    # Crear modelo
    modelo = pulp.LpProblem("Rutas_Ambulancias", pulp.LpMinimize)
    
    # Variables de decisión: flujo_{emergencia_id}_{u}_{v}_{k}
    flujos = {}
    for emerg in emergencias:
        for u, v, k in G.edges(keys=True):
            var_name = f"f_{emerg['id']}_{u}_{v}_{k}"
            flujos[(emerg['id'], u, v, k)] = pulp.LpVariable(var_name, lowBound=0, cat='Binary')
    
    # Función objetivo: minimizar costo total
    costo_total = []
    for emerg in emergencias:
        for u, v, k in G.edges(keys=True):
            longitud = G[u][v][k]['length'] / 1000  # convertir a km
            costo = longitud * emerg['costo_km']
            costo_total.append(costo * flujos[(emerg['id'], u, v, k)])
    
    modelo += pulp.lpSum(costo_total)
    
    # Restricciones de conservación de flujo
    for emerg in emergencias:
        for nodo in G.nodes():
            # Flujo entrante
            flujo_in = []
            for pred in G.predecessors(nodo):
                for k in G[pred][nodo].keys():
                    flujo_in.append(flujos[(emerg['id'], pred, nodo, k)])
            
            # Flujo saliente
            flujo_out = []
            for succ in G.successors(nodo):
                for k in G[nodo][succ].keys():
                    flujo_out.append(flujos[(emerg['id'], nodo, succ, k)])
            
            # Balance de flujo
            if nodo == origen:
                # Nodo origen: sale 1 unidad
                modelo += pulp.lpSum(flujo_out) - pulp.lpSum(flujo_in) == 1
            elif nodo == emerg['destino']:
                # Nodo destino: entra 1 unidad
                modelo += pulp.lpSum(flujo_in) - pulp.lpSum(flujo_out) == 1
            else:
                # Nodos intermedios: lo que entra = lo que sale
                modelo += pulp.lpSum(flujo_in) == pulp.lpSum(flujo_out)
    
    # Restricción de capacidad (simplificada)
    for u, v, k in G.edges(keys=True):
        flujo_arista = []
        for emerg in emergencias:
            flujo_arista.append(flujos[(emerg['id'], u, v, k)])
        modelo += pulp.lpSum(flujo_arista) <= 1  # Máximo 1 ambulancia por arista
    
    # Resolver
    modelo.solve(pulp.PULP_CBC_CMD(msg=0))
    
    # Extraer rutas
    rutas = {}
    for emerg in emergencias:
        ruta = []
        for u, v, k in G.edges(keys=True):
            if pulp.value(flujos[(emerg['id'], u, v, k)]) > 0.5:
                ruta.append((u, v, k))
        rutas[emerg['id']] = ruta
    
    return rutas, pulp.value(modelo.objective)

def calcular_metricas_ruta(G, ruta):
    """Calcula métricas de una ruta"""
    distancia_total = 0
    tiempo_total = 0
    
    for u, v, k in ruta:
        longitud = G[u][v][k]['length']  # metros
        capacidad = G[u][v][k]['capacity']  # km/h
        
        distancia_total += longitud
        tiempo_minutos = (longitud / 1000) / capacidad * 60
        tiempo_total += tiempo_minutos
    
    return distancia_total / 1000, tiempo_total  # km, minutos

def crear_mapa(G, origen, emergencias, rutas):
    """Crea mapa con Folium"""
    
    # Reproyectar a lat/lon
    G_latlon = ox.project_graph(G, to_crs='EPSG:4326')
    
    # Obtener coordenadas del origen
    origen_coords = (G_latlon.nodes[origen]['y'], G_latlon.nodes[origen]['x'])
    
    # Crear mapa base
    mapa = folium.Map(location=origen_coords, zoom_start=15, tiles='OpenStreetMap')
    
    # Agregar base de ambulancias
    folium.Marker(
        origen_coords,
        popup="🏥 Base de Ambulancias",
        tooltip="Base de Ambulancias",
        icon=folium.Icon(color='blue', icon='plus', prefix='fa')
    ).add_to(mapa)
    
    # Agregar emergencias y rutas
    for emerg in emergencias:
        destino_coords = (G_latlon.nodes[emerg['destino']]['y'], 
                         G_latlon.nodes[emerg['destino']]['x'])
        
        # Marcador de emergencia
        folium.Marker(
            destino_coords,
            popup=f"{emerg['tipo']}: {emerg['id']}<br>Vel. req: {emerg['velocidad_req']:.1f} km/h",
            tooltip=f"{emerg['tipo']}",
            icon=folium.Icon(color=emerg['color'], icon='ambulance', prefix='fa')
        ).add_to(mapa)
        
        # Dibujar ruta
        if emerg['id'] in rutas and rutas[emerg['id']]:
            ruta_coords = []
            for u, v, k in rutas[emerg['id']]:
                u_coords = (G_latlon.nodes[u]['y'], G_latlon.nodes[u]['x'])
                v_coords = (G_latlon.nodes[v]['y'], G_latlon.nodes[v]['x'])
                ruta_coords.extend([u_coords, v_coords])
            
            folium.PolyLine(
                ruta_coords,
                color=emerg['color'],
                weight=4,
                opacity=0.7,
                tooltip=f"Ruta {emerg['id']}"
            ).add_to(mapa)
    
    return mapa

# ===========================
# EJECUCIÓN PRINCIPAL
# ===========================

# Botones de acción
col_btn1, col_btn2 = st.columns(2)

if 'G' not in st.session_state:
    st.session_state.G = None
    st.session_state.origen = None
    st.session_state.emergencias = None
    st.session_state.rutas = None

with col_btn1:
    if st.button("🔄 Recalcular Capacidades", use_container_width=True):
        if st.session_state.G is not None:
            st.session_state.G = asignar_capacidades(st.session_state.G, C_min, C_max)
            st.success("Capacidades recalculadas")
        else:
            st.warning("Primero debe cargar la red vial")

with col_btn2:
    if st.button("🚀 Recalcular Flujos", use_container_width=True):
        with st.spinner("Calculando rutas óptimas..."):
            # Cargar/actualizar red
            if st.session_state.G is None:
                st.session_state.G = obtener_red_vial(center_lat, center_lon, radius)
                if st.session_state.G is None:
                    st.stop()
                st.session_state.G = asignar_capacidades(st.session_state.G, C_min, C_max)
            
            # Seleccionar origen (nodo más central)
            if st.session_state.origen is None:
                nodos = list(st.session_state.G.nodes())
                st.session_state.origen = nodos[len(nodos)//2]
            
            # Generar emergencias
            st.session_state.emergencias = generar_emergencias(
                st.session_state.G, st.session_state.origen,
                n_leve, n_media, n_critica, R_min, R_max
            )
            
            # Resolver modelo
            st.session_state.rutas, costo_total = resolver_modelo_multiflujo(
                st.session_state.G, st.session_state.origen, st.session_state.emergencias
            )
            
            st.success(f"✅ Optimización completada. Costo total: ${costo_total:,.0f}")

# Mostrar resultados
if st.session_state.rutas is not None:
    
    # Crear tabs
    tab1, tab2, tab3 = st.tabs(["🗺️ Mapa", "📊 Resultados", "ℹ️ Información"])
    
    with tab1:
        mapa = crear_mapa(st.session_state.G, st.session_state.origen, 
                         st.session_state.emergencias, st.session_state.rutas)
        st_folium(mapa, width=1200, height=600)
    
    with tab2:
        st.subheader("Detalle de Rutas Calculadas")
        
        resultados = []
        for emerg in st.session_state.emergencias:
            if emerg['id'] in st.session_state.rutas:
                distancia, tiempo = calcular_metricas_ruta(
                    st.session_state.G, st.session_state.rutas[emerg['id']]
                )
                costo = distancia * emerg['costo_km']
                
                resultados.append({
                    'Emergencia': emerg['id'],
                    'Tipo': emerg['tipo'],
                    'Distancia (km)': f"{distancia:.2f}",
                    'Tiempo (min)': f"{tiempo:.1f}",
                    'Velocidad Req (km/h)': f"{emerg['velocidad_req']:.1f}",
                    'Costo ($)': f"${costo:,.0f}"
                })
        
        df_resultados = pd.DataFrame(resultados)
        st.dataframe(df_resultados, use_container_width=True)
        
        # Resumen estadístico
        col1, col2, col3 = st.columns(3)
        distancias = [float(r['Distancia (km)']) for r in resultados]
        tiempos = [float(r['Tiempo (min)']) for r in resultados]
        costos = [float(r['Costo ($)'].replace('$','').replace(',','')) for r in resultados]
        
        col1.metric("Distancia Total", f"{sum(distancias):.2f} km")
        col2.metric("Tiempo Promedio", f"{np.mean(tiempos):.1f} min")
        col3.metric("Costo Total", f"${sum(costos):,.0f}")
    
    with tab3:
        st.subheader("📍 Información de la Zona")
        st.write(f"**Centro:** ({center_lat}, {center_lon})")
        st.write(f"**Radio:** {radius} metros")
        st.write(f"**Nodos en la red:** {st.session_state.G.number_of_nodes()}")
        st.write(f"**Aristas en la red:** {st.session_state.G.number_of_edges()}")
        
        st.subheader("🎯 Parámetros Utilizados")
        st.write(f"- Velocidad requerida: [{R_min}, {R_max}] km/h")
        st.write(f"- Capacidad de vías: [{C_min}, {C_max}] km/h")
        st.write(f"- Emergencias: {n_leve} leves, {n_media} medias, {n_critica} críticas")

else:
    st.info("👆 Haz clic en 'Recalcular Flujos' para iniciar la optimización")

# Footer
st.markdown("---")
st.markdown("**Modelo de Optimización Multiflujo para Rutas de Ambulancias** | Desarrollado con OSMnx + PuLP + Streamlit")
