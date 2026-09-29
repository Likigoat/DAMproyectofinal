# Informe de cierre — Red de Donaciones

**Tipo de entrega:** prototipo funcional con validación local; cierre condicionado a los análisis externos pendientes.

**Estudiante:** [Completar nombre]  
**Asignatura y grupo:** [Completar]  
**Docente:** [Completar]  
**Fecha de entrega:** [Completar]

## 1. Objetivo y alcance

Desarrollar un módulo básico para registrar donantes que colaboran con empresas y organizaciones sociales, incorporando autenticación, control de acceso, pruebas, automatización del despliegue y evaluación de calidad.

El alcance ejecutado es el registro de cuentas y donantes, consulta con control de propiedad y eliminación administrativa. No se incluyeron inventarios, asignación de alimentos, logística de entregas ni reportes de negocio. Se utilizó Swagger como interfaz de demostración de la API.

## 2. Diseño e implementación

Se separó la API (`app/api.py`) del núcleo de persistencia y seguridad (`app/core.py`). SQLite almacena dos entidades: usuarios y donantes. Cada donante referencia un usuario propietario mediante una clave foránea. Los correos son únicos en cada tabla.

La autenticación usa JWT firmado con HS256 y expiración de 30 minutos. La validación exige firma, algoritmo permitido, emisor, audiencia y campos temporales. La clave se obtiene del entorno; el arranque falla si falta o tiene menos de 32 caracteres. Las contraseñas se guardan como hashes Argon2.

El registro público asigna siempre el rol `usuario` y rechaza campos adicionales. El administrador se crea mediante una herramienta local. Los permisos se verifican consultando el rol actual en la base: el usuario sólo consulta sus donantes y el administrador puede consultar todos y eliminarlos.

Para reducir riesgo de SQLi se utilizan consultas parametrizadas. Los campos de nombre y organización rechazan etiquetas HTML y caracteres nulos; las respuestas de negocio son JSON y contienen la cabecera `nosniff`. Estas medidas no sustituyen un análisis dinámico completo.

## 3. Planificado frente a ejecutado

Las nueve horas corresponden al presupuesto de la actividad. No se registró un parte horario de trabajo humano, por lo que no se presentan como horas realmente consumidas ni se inventan retrasos en días.

| Fase | Plan | Ejecución comprobada | Diferencia y acción pendiente |
|---|---|---|---|
| Implementación y seguridad | 4 h; JWT, roles, módulo y CI/CD | Código implementado; pruebas locales aprobadas; workflow escrito | CI/CD pendiente de ejecución en un repositorio GitHub |
| Pruebas y calidad | 3 h; ZAP y SonarQube | Pruebas unitarias, de integración y HTTP ejecutadas; herramientas configuradas | Faltan reportes reales de ZAP y SonarQube; no se declara ausencia de vulnerabilidades ni deuda técnica cero |
| Cierre y evaluación | 2 h; comparación y lecciones | Informe, instrucciones y evidencias locales elaborados | Cierre definitivo condicionado a completar los análisis y adjuntar sus resultados |

La limitación observada inicialmente fue la ausencia de un motor Docker activo. El CLI estaba instalado, pero no había un endpoint del daemon disponible. Por ello se diseñó un pipeline que inicia sus herramientas en runners Linux de GitHub. Su configuración aún requiere validarse mediante una ejecución real.

## 4. Evidencias de pruebas ejecutadas

Entorno local: Windows, Python 3.14.2, Pytest 9.1.1 y pytest-cov 7.1.0. Las versiones de dependencias están registradas en `requirements-dev.txt`.

| Verificación | Resultado real | Evidencia |
|---|---|---|
| Suite completa | 47 aprobadas, 0 fallidas | `reports/junit.xml`, `reports/pytest-result.txt` |
| Cobertura de aplicación, suite completa | 100 %: 134 sentencias y 18 salidas de rama cubiertas | `reports/coverage.xml`, `reports/htmlcov/index.html` |
| Suite unitaria separada | 26 aprobadas | `reports/junit-unit.xml`, `reports/unit-result.txt` |
| Cobertura unitaria de aplicación | 100 % de `app/`: 134 sentencias y 18 salidas de rama | `reports/coverage-unit.xml` |
| Prueba HTTP del servidor local | 7 comprobaciones aprobadas | `reports/smoke.json`, `reports/local-server.log` |

El umbral automatizado es 80 %. La suite unitaria incluye 16 casos del núcleo y validación, y diez casos de controladores llamados directamente, sin HTTP y con dependencias simuladas. Los casos de persistencia del núcleo usan una base SQLite temporal. La suite de integración verifica adicionalmente el enrutamiento, serialización, validación y composición de dependencias reales mediante TestClient. Se conservan las dos mediciones de cobertura, ambas sobre `app/`, y ambas alcanzan el 100 %.

Las 26 pruebas unitarias ya forman parte de las 47 de la suite completa: no deben sumarse como si fueran 73 casos distintos. Las siete comprobaciones HTTP constituyen una validación adicional.

Se verificaron registro duplicado, credenciales incorrectas, contraseñas con hash, JWT vencido o manipulado, emisor y audiencia incorrectos, campos obligatorios, intento de asignar rol administrador, restricciones de propiedad, cambio de rol durante una sesión, paginación y eliminación restringida.

Las pruebas de SQLi enviaron nombres como `' OR 1=1 --` y `Robert'); DROP TABLE donors;--`; se almacenaron como texto y la tabla permaneció operativa. Las pruebas de XSS enviaron etiquetas como `<script>alert(1)</script>` y recibieron un error de validación. Son pruebas de regresión de casos concretos, no equivalen al reporte de OWASP ZAP.

Se observó un aviso de deprecación de Starlette respecto a `httpx` en TestClient. No provocó fallos. Se conserva como observación de mantenimiento.

## 5. CI/CD y despliegue

El workflow de GitHub Actions está implementado en `.github/workflows/ci-cd.yml`. Primero ejecuta pruebas y conserva la cobertura. Después inicia SonarQube Community, realiza el análisis y espera la puerta de calidad. Si ambas etapas aprueban, un push a `main` o una ejecución manual construye la imagen Docker y la despliega en el entorno de prueba `staging` del runner.

En staging se ejecuta una prueba HTTP y un escaneo de API con ZAP autenticado. Se consideran bloqueantes las alertas medias y altas. Los errores del escáner también hacen fallar la etapa; no se ignoran con una salida exitosa. Los reportes se conservan incluso si falla el job.

El entorno es efímero y se elimina al terminar. Este diseño permite demostrar despliegue automático en prueba, pero no proporciona alojamiento permanente ni una URL pública. No se ha ejecutado ni validado este workflow en GitHub en la presente entrega.

## 6. Resultados de seguridad y calidad pendientes

| Herramienta / métrica | Estado en esta entrega | Dato que debe incorporarse |
|---|---|---|
| ZAP: alertas altas, medias, bajas e informativas | No medido | Conteos reales de `zap-summary.json` y evidencia de cada alerta |
| ZAP: alcance autenticado | Configurado, no verificado por escaneo | Rutas, respuestas y revisión de autenticación |
| SonarQube: deuda técnica (`sqale_index`) | No medido | Minutos estimados por el analizador |
| SonarQube: code smells | No medido | Cantidad, reglas y correcciones |
| SonarQube: bugs y vulnerabilidades | No medido | Cantidades reales y hallazgos |
| SonarQube: duplicación | No medido | Porcentaje reportado |
| SonarQube: cobertura importada | Pendiente de importación | Valor del análisis, distinto del resultado local de Pytest |
| SonarQube: Quality Gate | No ejecutado | Estado y condiciones |

Las instrucciones del README describen cómo descargar los artefactos. Si la versión de SonarQube utiliza métricas diferentes, se deben documentar sus nombres y no convertir ausencias en ceros.

ZAP API Scan no está orientado a detectar XSS de una interfaz web. Si en una fase posterior se desarrolla un frontend, se requiere un escaneo web y validación de codificación de salida. La autenticación, el rechazo de payloads y el control de acceso se verificaron aquí con las pruebas automatizadas locales.

## 7. Lecciones aprendidas

1. **Verificar el entorno al inicio evita comprometer evidencias que no se podrán generar.** La falta de un motor Docker activo afectó los análisis previstos; conviene comprobar Docker y la memoria disponible antes de reservar las horas de calidad.
2. **Definir permisos por operación permite probarlos de forma concreta.** La separación entre consultar donantes propios y eliminar registros produjo casos verificables de 401, 403 y éxito.
3. **Separar el núcleo facilita las pruebas unitarias.** El manejo de JWT, hashing y transacciones se verificó independientemente de las rutas HTTP; las pruebas de integración completaron la evaluación de permisos y persistencia.
4. **La cobertura debe interpretarse junto con el tipo de prueba.** Un 100 % combinado no significa que todo esté probado de forma aislada ni que el sistema no tenga vulnerabilidades.
5. **La automatización necesita una ejecución que la valide.** Escribir el YAML constituye una implementación de configuración; el despliegue sólo se confirma cuando el workflow y sus comprobaciones terminan correctamente.
6. **Un cierre transparente distingue resultados y pendientes.** No se sustituyeron mediciones de SonarQube por estimaciones ni se presentó la regresión de SQLi como un escaneo dinámico completo.

## 8. Riesgos y acciones siguientes

| Pendiente | Responsable propuesto | Criterio de terminación |
|---|---|---|
| Subir proyecto y ejecutar Actions | Estudiante | URL de ejecución y jobs terminados |
| Revisar ZAP y corregir hallazgos | Desarrollo / estudiante | Alertas documentadas; sin medias o altas pendientes para aprobar el gate |
| Completar SonarQube | Desarrollo / estudiante | Métricas exportadas, problemas revisados y Quality Gate aprobado |
| Aclarar si se requiere staging permanente | Estudiante / docente | Alcance de despliegue aceptado o alojamiento configurado |
| Actualizar este informe y añadir capturas | Estudiante | Datos medidos y evidencias anexadas |

Antes de un uso público también se requieren HTTPS, limitación de intentos, revocación de sesiones, recuperación de contraseñas y auditoría. No forman parte del prototipo entregado.

## 9. Evaluación de cierre

El módulo funciona y sus verificaciones locales cumplen el umbral de cobertura definido. La automatización de calidad y despliegue está preparada. **La actividad completa aún requiere la ejecución de ZAP, SonarQube y CI/CD y la incorporación de sus evidencias.** Se propone un cierre técnico local y un cierre académico definitivo después de comprobar esas etapas.

## 10. Anexos que debe completar el estudiante

- Captura de Swagger registrando un donante con respuesta 201.
- Captura del rechazo 403 al eliminar con un usuario normal.
- Captura de Pytest y del reporte HTML de cobertura.
- URL y captura de la ejecución de GitHub Actions.
- Reporte ZAP con revisión de alertas y alcance.
- Métricas y Quality Gate de SonarQube.

Las referencias técnicas oficiales se encuentran al final del README del proyecto.
