# Description

Vamos a definir una herramienta de simulación para el análisis de sensibilidad de una BESS (Batería de Almacenamiento Eléctrico) que permita a los usuarios introducir parámetros específicos para simular el retorno de la inversión al final de su vida útil. Esta herramienta se basará en datos históricos, que pueden ser sintéticos generados por IA, para proporcionar indicadores técnico-económicos del desempeño de la batería:


## Características principales:

- Cuadro de mando interactivo, donde el usuario introduce unos parámetros de contexto para simular el retorno de la inversión al final de su vida útil de una batería.

- Es un análisis de sensibilidad una herramienta de simulación según la política de operación de la batería como le impacta en desgaste y beneficios.

- Políticas de operación: Este simulador deberia poder evolucionar a que le meta los diferentes servicios que prestan las baterias y poder leer los precios de mercado.

- Para esto necesitaremos que generes datos sinteticos, casos de uso con distintos escenarios y RECOMENDACIONES

- Como funcionalidad adicional, esto si se pudiera hacer tambien en PBI.


## Requisitos Técnicos:

- Lenguaje de programación: Python para la simulación y análisis de datos.
- Aplicación ejecutable en local.
- Poder importar / exportar datos en formatos comunes (CSV, Excel).
- Interfaz de usuario amigable e intuitiva.
- Capacidad para generar gráficos y visualizaciones de los resultados.
- Posibilidad de exportar los resultados a Power BI para análisis adicionales.
- Generación de datos sintéticos para simular diferentes escenarios de operación de la batería.
- Incorporación de recomendaciones basadas en los resultados de la simulación para optimizar la operación de la batería y maximizar el retorno de la inversión (@docs\01-analysis\modulo 1\arbol-decisiones-bess.md).
- Usa buenas prácticas de programación y documentación para asegurar la mantenibilidad y escalabilidad del código.




**Nota adicional:** Para la generación de datos sintéticos que sustituyan a los historicos (1 primer año de: datos de carga, descarga, ciclos, round trip efficiency (RTE), precios, degradación) actua como experto tanto en precios de mercados de venta de energía como en tecnologias de generación de energía renovable basadas en BESS stand-alone. Los datos sinteticos generados por tí, constrúyelos respetando los parámetros fisicos de una instalación BESS ion litio y con operativa de carga y descarga para servicios de arbitraje como primer caso de uso para su pila de servicios. Sólo a partir del primer año de datos históricos, usa los parámetros de los inputs del dashboard para generar datos y simular las condiciones de funcionamiento, es decir hoy= primer día del segundo año, y por tanto todos los datos futuros son en base a parámetros de entrada en el dashboard por el usuario.
Genera una casilla para decidir cuando es HOY, de forma que desde HOY hacia atrás todos los datos sean sinteticos (en base a tu conocimiento experto en física y mercados de como funcionaria una bess), y hacia el futuro basados en parámetros de entrada del usuario.