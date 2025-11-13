# 🚑 Sistema de Optimización de Rutas de Ambulancias

Aplicación interactiva que implementa un modelo de optimización multiflujo para determinar las rutas óptimas de ambulancias en escenarios de emergencias simultáneas.

## 📋 Descripción del Proyecto

Este proyecto desarrolla un modelo matemático de optimización que permite determinar las rutas óptimas para ambulancias en una red vial real, considerando:

- **3 tipos de emergencias**: Leve, Media y Crítica
- **Costos operativos diferenciados** por tipo de ambulancia
- **Capacidades limitadas** en las vías (velocidades máximas)
- **Velocidades requeridas** para cada flujo
- **Red vial real** obtenida de OpenStreetMap vía OSMnx

## 🎯 Objetivo

Minimizar el costo total de respuesta de ambulancias en emergencias médicas urbanas, considerando el tiempo de viaje y los costos operativos diferenciados por tipo de ambulancia.

## 🏙️ Zona de Estudio

- **Ubicación**: Laureles, Medellín, Colombia
- **Coordenadas centrales**: (6.2442, -75.5890)
- **Área**: Aproximadamente 1 km² (radio de 560 metros)

## 🔧 Tecnologías Utilizadas

- **OSMnx**: Obtención de redes viales de OpenStreetMap
- **PuLP**: Modelado y resolución de problemas de optimización lineal
- **Streamlit**: Interfaz web interactiva
- **Folium**: Visualización de mapas
- **NetworkX**: Manipulación de grafos

## 📦 Instalación

1. Clonar el repositorio:
```bash
git clone <tu-repositorio>
cd proyecto-ambulancias
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecutar la aplicación:
```bash
streamlit run proyecto_multiflujo_ambulancias.py
```

## 🚀 Uso de la Aplicación

### Controles Principales

1. **Recalcular Capacidades**: Regenera valores aleatorios de capacidad (velocidad máxima) para cada vía
2. **Recalcular Flujos**: Ejecuta el modelo de optimización con los parámetros actuales

### Parámetros Configurables

- **R_min, R_max**: Rango de velocidades requeridas (km/h)
- **C_min, C_max**: Rango de capacidades de las vías (km/h)
- **Número de emergencias**: Por tipo (Leve, Media, Crítica)
- **Costos operativos**: Por tipo de ambulancia ($/km)

### Visualización

La aplicación muestra:
- **Mapa interactivo** con las rutas calculadas
- **Base de ambulancias** (marcador azul)
- **Emergencias** con código de colores:
  - 🟢 Verde: Leve
  - 🟠 Naranja: Media
  - 🔴 Rojo: Crítica
- **Rutas optimizadas** por emergencia
- **Tabla de resultados** con distancias, tiempos y costos

## 📐 Formulación Matemática

### Variables de Decisión

- `f_{i,u,v,k}`: Flujo binario de la emergencia `i` en la arista `(u,v,k)`

### Función Objetivo

Minimizar:
```
∑_{i} ∑_{(u,v,k)} (longitud_{u,v,k} × costo_km_i × f_{i,u,v,k})
```

### Restricciones

1. **Conservación de flujo**:
   - En el origen: sale 1 unidad
   - En el destino: entra 1 unidad
   - Nodos intermedios: flujo entrante = flujo saliente

2. **Capacidad de vías**:
   - Máximo 1 ambulancia por arista simultáneamente

## 📊 Escenarios de Prueba

Se recomienda probar al menos 3 escenarios:

1. **Escenario de baja demanda**:
   - 1 emergencia leve, 1 media, 1 crítica
   - Capacidades altas (30-70 km/h)

2. **Escenario de demanda media**:
   - 2 emergencias leve, 2 medias, 2 críticas
   - Capacidades moderadas (20-60 km/h)

3. **Escenario de alta demanda**:
   - 3 emergencias leve, 3 medias, 3 críticas
   - Capacidades bajas (15-50 km/h)

## 📝 Estructura del Código

```
proyecto_multiflujo_ambulancias.py
├── Configuración (Streamlit)
├── Funciones auxiliares
│   ├── obtener_red_vial()
│   ├── asignar_capacidades()
│   ├── generar_emergencias()
│   ├── resolver_modelo_multiflujo()
│   ├── calcular_metricas_ruta()
│   └── crear_mapa()
└── Ejecución principal
    ├── Controles interactivos
    ├── Resolución del modelo
    └── Visualización de resultados
```

## 🎓 Entregables del Proyecto

- ✅ Script Python con modelo implementado
- ✅ Aplicación Streamlit interactiva
- ✅ Visualización de mapas y resultados
- ✅ Repositorio GitHub con código documentado
- ✅ requirements.txt con dependencias
- 📄 Informe técnico (pendiente)

## 👨‍💻 Autor

[Tu nombre]

## 📄 Licencia

Este proyecto es desarrollado con fines académicos.

## 🙏 Agradecimientos

- OpenStreetMap por los datos viales
- Comunidades de OSMnx, PuLP y Streamlit
