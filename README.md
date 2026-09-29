# Red de Donaciones — proyecto académico

API para registrar personas donantes vinculadas con empresas u organizaciones. Implementada con Python 3.14, FastAPI, SQLite, JWT y Argon2. No incluye inventario de alimentos, entregas ni una interfaz gráfica propia: la interfaz interactiva de demostración es Swagger en `/docs`.

## Empieza aquí

1. Descomprime el paquete y abre una terminal en esta carpeta, donde está este README.
2. Ejecuta los siguientes comandos en PowerShell con Python 3.14 instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:JWT_SECRET = (.\.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))")
.\.venv\Scripts\python -m scripts.create_admin
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-server-header
```

La creación del administrador pide un correo y una contraseña de al menos 12 caracteres. Hazla sólo una vez por correo. Mantén la terminal del servidor abierta y entra en [la documentación interactiva](http://127.0.0.1:8000/docs).

La clave generada vive en la sesión de PowerShell. Regenerarla invalida los JWT anteriores. Para una instalación persistente guárdala fuera del repositorio, en la configuración privada del entorno. SQLite crea `donaciones.db` en la carpeta actual; no subas ese archivo con datos personales.

## Demostración en el navegador

1. Abre `POST /auth/register`, pulsa **Try it out** y registra `usuario@example.org` con una contraseña de 12 o más caracteres. El rol siempre será `usuario`.
2. Abre `POST /auth/login`, envía las mismas credenciales y copia el valor de `access_token`.
3. Pulsa **Authorize** y pega sólo el token, sin escribir `Bearer`.
4. Ejecuta `POST /donors` con este cuerpo:

```json
{
  "name": "Ana Pérez",
  "email": "ana@example.org",
  "organization": "Alimentos del Norte"
}
```

5. Consulta `GET /donors`. El usuario sólo ve sus registros. Intenta eliminarlos: recibirás `403`.
6. Inicia sesión con el administrador creado en la terminal, cambia el token en **Authorize**, consulta todos los donantes y elimina uno con `DELETE /donors/{donor_id}`.

## Reglas y endpoints

| Endpoint | Acceso | Resultado |
|---|---|---|
| `GET /health` | Público | Comprueba la conexión con SQLite |
| `POST /auth/register` | Público | Crea una cuenta de usuario; no admite el campo rol |
| `POST /auth/login` | Público | JWT con caducidad de 30 minutos |
| `GET /auth/me` | Autenticado | Identidad y rol vigentes |
| `POST /donors` | Autenticado | Registra un donante y asigna al usuario como propietario |
| `GET /donors` | Usuario / administrador | Lista propios / todos; paginación hasta 100 registros |
| `DELETE /donors/{id}` | Administrador | Elimina el registro o devuelve 404 |

No se devuelven hashes. Los roles se consultan en la base de datos en cada petición: un cambio de rol se aplica incluso con un JWT previamente emitido. Los correos se normalizan a minúsculas y no se repiten dentro de su tabla. Un correo de donante globalmente único es una regla simplificada de este prototipo.

## Ejecutar las pruebas

En otra terminal, desde esta misma carpeta:

```powershell
.\.venv\Scripts\python -m pytest
```

El comando falla si la cobertura de `app/`, incluidas sus ramas, baja del 80 %. Genera `reports/coverage.xml`, `reports/junit.xml` y `reports/htmlcov/index.html`.

La entrega incluye una ejecución real de **47 pruebas aprobadas**, cobertura combinada del **100 %** y una ejecución separada de **26 pruebas unitarias**, con **100 % sobre `app/`**. Los controladores se prueban sin HTTP y con dependencias simuladas; el núcleo se prueba directamente, incluida su persistencia en SQLite temporal. Las otras 21 pruebas ejercitan la API mediante TestClient con una base temporal. Ambas mediciones se conservan por separado.

Para repetir sólo la medición unitaria:

```powershell
.\.venv\Scripts\python -m pytest tests/test_core.py tests/test_controllers_unit.py -o addopts="" --cov=app --cov-branch --cov-report=term-missing --cov-report=xml:reports/coverage-unit.xml --cov-fail-under=80
```

Con el servidor iniciado también puedes comprobar el funcionamiento por HTTP real:

```powershell
.\.venv\Scripts\python -m scripts.smoke
```

Este último comando crea datos sintéticos; úsalo sólo en pruebas. La evidencia incluida se ejecutó en una base temporal y en el puerto local 8123, que ya fue cerrado.

## CI/CD en GitHub Actions

Sube **el contenido de esta carpeta** a la raíz de un repositorio; `.github/workflows/ci-cd.yml` debe quedar en la raíz del repositorio, no dentro de otra carpeta. Utiliza la rama `main` y habilita GitHub Actions. No se necesita un token personal ni un servidor de pago para este diseño.

El workflow implementa:

1. **Test:** instala las versiones fijadas, ejecuta Pytest y conserva cobertura y JUnit.
2. **SonarQube:** inicia un servidor Community temporal en el runner, cambia su contraseña inicial, crea un token temporal y un proyecto, importa la cobertura, analiza y espera la puerta de calidad. Exporta métricas y estado como artefactos.
3. **Staging:** después de pruebas y SonarQube, construye la imagen Docker del commit y despliega en el entorno `staging` del runner. Comprueba la API con tráfico HTTP real y ejecuta ZAP autenticado. Un hallazgo medio o alto bloquea el job. Guarda evidencias y retira el contenedor.

Las pull requests ejecutan pruebas y SonarQube. Los pushes a `main` y la ejecución manual también despliegan. En GitHub, entra a **Actions → Pruebas, calidad y despliegue de prueba → Run workflow** para una ejecución manual en `main`.

**Alcance del despliegue:** es automático y efímero. Está disponible dentro del runner durante el job y se elimina al finalizar. No entrega una URL pública permanente. Si tu docente exige un servidor de staging persistente, este diseño necesita ampliarse con un alojamiento y sus credenciales. No se ha ejecutado el workflow en GitHub durante esta entrega.

Los contenedores de herramientas usan etiquetas `community`, `stable` y la etiqueta predeterminada del scanner; sus versiones pueden cambiar. Para una ejecución reproducible de entrega conserva el log con sus versiones y fija los digest de las imágenes probadas. Las dependencias Python de desarrollo sí están fijadas en `requirements-dev.txt`.

## Seguridad y calidad: cómo cerrar las evidencias

Después del workflow, descarga los artefactos de Actions:

| Artefacto | Evidencia |
|---|---|
| `pytest-coverage` | Pruebas, cobertura XML y HTML |
| `sonarqube-evidence` | `sonar-metrics.json`, `sonar-quality-gate.json`, identificación del análisis |
| `staging-zap-evidence` | `smoke.json`, `zap.html`, `zap.json`, `zap-summary.json`, logs |

Abre `zap.html`, verifica las rutas alcanzadas, revisa alertas, evidencia, solución y posibles falsos positivos. La precomprobación y la comprobación final de autenticación ayudan a detectar un token no válido; no prueban por sí solas que ZAP haya ejercitado todas las operaciones. Revisa también el tráfico y las respuestas `401`/`422` del reporte. El escaneo se limita a `/donors`; autenticación y autorización tienen pruebas automatizadas propias.

**XSS:** el escáner de API de ZAP se centra en ataques contra APIs y no busca XSS como un escaneo web completo. Este proyecto devuelve JSON y prueba el rechazo de etiquetas en sus campos de texto. Si añades una interfaz HTML, será necesario probar codificación de salida y XSS reflejado/almacenado en esa interfaz; no extrapoles estas pruebas a un frontend inexistente.

En `sonar-metrics.json`, `sqale_index` indica deuda técnica estimada en minutos; `code_smells` indica el número de problemas de mantenibilidad en las métricas clásicas. Conserva las métricas que tu versión realmente devuelva: un campo ausente no equivale a cero. Anota también `coverage`, `bugs`, `vulnerabilities`, `duplicated_lines_density`, `security_hotspots` y el estado de la puerta de calidad.

Completa el [informe de cierre](INFORME_CIERRE.md) con los resultados reales y adjunta las capturas. Un job fallido es evidencia de un problema por resolver, no un análisis aprobado.

## Docker local, opcional

Con Docker Desktop iniciado y la variable `JWT_SECRET` definida:

```powershell
docker compose up --build -d
docker compose exec api python -m scripts.create_admin
docker compose logs api
docker compose down
```

El volumen conserva los datos al detener el contenedor. La imagen ejecuta la API con un usuario sin privilegios. El comando `docker compose exec` crea el administrador en la base del contenedor; ejecuta ese paso sólo una vez por correo. El script ejecutado directamente en el host trabaja con una base local diferente.

## Estructura

```text
app/                  API, JWT, contraseñas y persistencia
tests/                Pruebas unitarias y de integración
scripts/              Alta administrativa, smoke, preparación y gate de ZAP
.github/workflows/    Pipeline CI/CD
reports/              Evidencias reales incluidas y nuevas ejecuciones
Dockerfile            Imagen de la API
compose.yaml          Ejecución local con volumen
sonar-project.properties
INFORME_CIERRE.md      Informe editable con estado verificable
```

## Límites conocidos

Prototipo académico para un entorno controlado. Antes de exponerlo públicamente faltan HTTPS en el proxy, límites de intentos de inicio de sesión, recuperación de contraseña, revocación anticipada de tokens, auditoría persistente y una política de protección de datos. La prueba de SQLi cubre ejemplos concretos; no demuestra ausencia de toda vulnerabilidad. Los códigos 409 permiten conocer si un correo ya está registrado. Swagger utiliza recursos externos; la CSP estricta de la API no se aplica a `/docs` y `/redoc`.

La ejecución local produjo un aviso de deprecación de Starlette sobre `httpx` en TestClient; las pruebas pasan, pero una actualización futura requerirá revisar esa dependencia.

## Referencias oficiales

- [FastAPI: OAuth2 y JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [GitHub: despliegues con Actions](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments)
- [ZAP: escaneo de API y códigos de salida](https://www.zaproxy.org/docs/docker/api-scan/)
- [ZAP: autenticación mediante cabeceras](https://www.zaproxy.org/docs/getting-further/authentication/handling-auth-yourself/)
- [SonarQube: cobertura de Python](https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/test-coverage/python-test-coverage)
- [SonarQube Community: instalación](https://docs.sonarsource.com/sonarqube-community-build/server-installation/introduction)
