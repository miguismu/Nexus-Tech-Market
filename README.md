# NEXUS Tech Market

Tienda académica de hardware y tecnología con frontend en HTML, CSS y JavaScript, API en Python/Flask y persistencia SQL mediante SQLAlchemy. La base local predeterminada es SQLite; el mismo backend puede conectarse a PostgreSQL.

**Autor:** Miguel Alejandro Muñoz Suárez  
**Institución:** Politécnico Superior de Occidente  
**Área:** Desarrollo web · **Semestre:** 2  
**Presentado a:** Dioni Rodallega Murillo

## Qué contiene

- `index.html`: catálogo, búsqueda, filtros, carrito, solicitud simulada, panel de revisión y asistente.
- `vision.html`: lema, misión, visión y principios de NEXUS.
- `styles.css`: diseño adaptable, oscuro en morado profundo con acentos dorados moderados, orb animado y controles accesibles.
- `app.js`: catálogo, carrito persistente en el navegador y comunicación con la API.
- `assistant.js`: asistente local por reglas; admite dictado y lectura en voz alta cuando el navegador ofrece Web Speech API. No llama a una IA externa.
- `server.py`: API Flask, validación de entradas, CSRF, sesión de revisión y decisiones de compra.
- `catalog.json`: productos demostrativos compartidos por el backend y el modo visual local.
- `schema.sql`: esquema SQL para PostgreSQL.
- `tests/test_server.py`: pruebas automatizadas del flujo principal de la API.

El catálogo contiene productos sin fichas duplicadas. Sus precios e imágenes son referencias: cambian según tienda, variante, inventario y fecha de consulta. Las fichas de cotización generan un archivo descargable con código de referencia; al registrar una solicitud, la página genera una constancia de simulación. Ninguno de esos documentos es recibo fiscal, comprobante de pago ni confirmación de compra.

## Ejecutarlo en Visual Studio Code

1. Abre esta carpeta en VS Code y autoriza las tareas automáticas cuando se solicite.
2. Al abrir el proyecto, la tarea **NEXUS: abrir sitio seguro en Chrome** inicia la API y el host HTTPS y abre `https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/` en Chrome. Para iniciar todo manualmente, instala dependencias y ejecuta:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   py -m pip install -r requirements.txt
   py iniciar_nexus.py
   dotnet run --no-launch-profile --project .\secure-host\NexusHttpsHost.csproj
   ```

   `iniciar_nexus.py` mantiene la API local activa, guarda el código administrativo en `.admin-code` y conserva la clave de firma de sesión en `.session-secret`. No compartas esos archivos ni el código del panel.
3. La dirección de desarrollo con el nombre NEXUS es **<https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5500/>**. El subdominio usa DNS de sslip.io para apuntar a `127.0.0.1` en este equipo; no publica el sitio en Internet ni es un dominio propio. La base SQLite `nexus.db` conserva productos y solicitudes; la API solo escucha en el equipo local.
4. Para usar **Open with Live Server**, abre `index.html` y pulsa **Open with Live Server**. La dirección será **<https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5501/>**; VS Code está configurado para servir desde la raíz, usar HTTPS y abrir Chrome con ese nombre. El puerto `5501` evita conflicto con el host HTTPS de la API en `5500`. La URL `https://localhost:5500/` sigue disponible como alternativa local.
5. Para abrir el panel de administración desde “Nuestra visión”, usa la pestaña **Administrador**. Para misión y visión, usa el enlace correspondiente de la navegación.

La comprobación local de la API está en `http://127.0.0.1:5000/api/health` (solo loopback). En otro equipo, configura primero Python, sus dependencias, el SDK de .NET y el certificado local.

## Usar PostgreSQL

PostgreSQL no es necesario para la demostración local: SQLite ya guarda solicitudes y decisiones. Para usar PostgreSQL, instala PostgreSQL desde su sitio oficial, crea una base llamada `nexus` y configura `DATABASE_URL` en la terminal antes de iniciar el backend:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/nexus"
py server.py
```

Las tablas se crean al arrancar mediante SQLAlchemy; `schema.sql` documenta el esquema equivalente para PostgreSQL. Descargas e información oficial: [postgresql.org/download](https://www.postgresql.org/download/). No se descarga ni se instala el servidor PostgreSQL automáticamente al ejecutar este proyecto.

## Seguridad y límites de la simulación

- El servidor calcula el precio usando el catálogo de la base de datos; el navegador no puede decidir el total final.
- Las solicitudes usan validación, límite de tamaño, token CSRF, comparación constante del código administrativo, cookies `HttpOnly`/`SameSite`, sesión con expiración y cabeceras HTTP de seguridad.
- El código administrativo de desarrollo se genera al arrancar y se informa solo en la terminal local. Puedes fijarlo con la variable `NEXUS_ADMIN_CODE`.
- En `localhost` **no hay un candado HTTPS real**. El backend admite marcar cookies como `Secure` con `NEXUS_HTTPS=true` solamente cuando se despliegue detrás de HTTPS; no actives esa opción para el HTTP local.
- Esta demo no procesa pagos, no envía correos y no crea órdenes en comercios externos. El panel únicamente registra una aprobación o un rechazo local.
- Los precios del catálogo son cotizaciones de referencia observadas en las fuentes enlazadas y llevan fecha; no son garantía de precio o inventario actual. Confirma modelo, variante, impuestos, disponibilidad y derechos de uso directamente con la tienda antes de comprar.
- Las descargas de cotización y constancia son documentos HTML generados localmente para esta simulación. La constancia se crea al enviar una solicitud pendiente; no representa un pago real.
- El asistente ofrece respuestas por reglas locales; reconocimiento y síntesis de voz dependen del navegador y sus permisos. No es una IA generativa ni usa una voz propia entrenada.
- La portada usa la imagen generada por `make_cover.py` (orbe dorado-morado sobre paisaje aubergine).
- TensorFlow no se incluye: este asistente no ejecuta un modelo de aprendizaje automático y agregar esa dependencia sin un modelo entrenado no aportaría una función real.
- Para producción faltan, entre otros, HTTPS, gestión de identidad, limitación de intentos, política de privacidad, protección de datos, pruebas de seguridad y una fuente verificada para precios e inventario.

## Probar el backend

Con dependencias instaladas, ejecuta:

```powershell
py -m unittest discover -s tests -v
```

Las pruebas cubren el catálogo, CSRF, creación de solicitudes, autorización administrativa, rechazo con motivo y prevención de una segunda decisión.

## Mantener la página activa siempre

`iniciar_nexus.py` lanza el servidor en un proceso desasociado (sobrevive al cierre de VS Code y de la terminal), fija un **código de administrador permanente** (guardado en `.admin-code`) y escribe el log en `nexus-server.log`:

```powershell
py iniciar_nexus.py            # inicia NEXUS siempre activo en http://localhost:5000
py iniciar_nexus.py --detener  # detiene el servidor
```

Para registrar e iniciar la tarea automática de Windows, ejecuta una vez desde PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\registrar-tarea.ps1
```

La tarea **NEXUS-SiempreActivo** se ejecuta al iniciar sesión, mantiene activa la API y el sitio HTTPS, abre la página local en Chrome y reinicia ambos servicios si dejan de responder. Si Windows deniega el registro de la tarea por permisos, el script instala el acceso directo `NEXUS-SiempreActivo.lnk` en la carpeta de inicio del usuario, con el mismo comportamiento. Al apagar Windows los procesos se detienen; al volver a iniciar sesión se arrancan de nuevo. El guardián no requiere iniciar VS Code y registra actividad en `nexus-guardian.log`.

Si el equipo se reinicia, vuelve a ejecutar `py iniciar_nexus.py`. El código del panel y la base de datos no cambian. Para crear el certificado local (candado en Chrome) usa `py make_cert.py` una sola vez.

**Dirección local de demostración:** <https://miguismu-nexus-tech-market.127.0.0.1.sslip.io:5501/>. El nombre con `127.0.0.1` es solo un alias local para desarrollo; la dirección `.git` de GitHub es el repositorio de código y no ejecuta la aplicación. Para publicar NEXUS para otras personas hacen falta alojamiento para Flask, una base de datos accesible y un dominio público con certificado HTTPS.

**Repositorio del proyecto:** <https://github.com/miguismu/Nexus-Tech-Market>

**Administrador del panel:** Miguel Alejandro Muñoz Suárez (nombre completo + código de `.admin-code`).

## Archivos clave

| Archivo | Papel |
|---|---|
| `server.py` | Backend Flask: API, seguridad, códigos PAY con HMAC, verificador de compras |
| `app.js` | Tienda: catálogo, carrito, descargas de cotización/comprobante con imagen |
| `assistant.js` | Asistente Extremo NEXUS: orbe animado, voz (TTS) y dictado |
| `styles.css` | Tema morado oscuro + dorado, orbe con aro naranja |
| `catalog.json` | 40 fichas de productos con precios en COP |
| `make_cover.py`, `make_monitor.py` | Generan la imagen de portada y la del monitor |
| `iniciar_nexus.py` | Arranque persistente del servidor |
| `make_cert.py` | Certificado local para el candado HTTPS |

## Guion sugerido para sustentar el proyecto

1. **Problema:** presentar un catálogo claro y un flujo transparente para solicitar y revisar tecnología.
2. **Solución:** recorrer el catálogo, filtrar productos, agregarlos al carrito y crear una solicitud simulada.
3. **Frontend:** explicar HTML semántico y las dos páginas; CSS adaptable con tema oscuro; JavaScript para búsqueda, filtros, carrito, formulario y asistente.
4. **Backend:** mostrar `server.py`, `/api/products`, `/api/orders` y el panel de revisión. Explicar que el servidor valida la solicitud y calcula el valor desde el catálogo; luego una persona aprueba o rechaza y deja un motivo.
5. **Base de datos:** enseñar `schema.sql` y las tablas `products`, `purchase_requests` y `purchase_items`; SQLite permite empezar sin instalaciones y PostgreSQL es una alternativa de configuración.
6. **Seguridad:** mostrar token CSRF, validación, sesión protegida y código temporal de revisión. Aclarar que un candado auténtico requiere HTTPS en un servidor desplegado.
7. **Demostración:** iniciar Flask, abrir la página, descargar una cotización, crear una solicitud simulada y, en el panel, ingresar el código temporal de terminal para aprobarla o rechazarla. Probar el dictado/lectura de voz si el navegador lo permite.
8. **Alcance y mejoras:** enfatizar que no hay cobros, que precios e ilustraciones son demostrativos y que para comercializarlo harían falta cotizaciones verificadas, imágenes con licencia y controles de producción.

**Lema para la exposición:** “Una idea que conecta. Tecnología para lo que sigue.”

## Ejecutar con HTTPS local y candado

El certificado local está configurado en `.vscode/settings.json` para Live Server y en el host HTTPS. La tarea automática y **Open with Live Server** abren el nombre local `miguismu-nexus-tech-market.127.0.0.1.sslip.io` en Chrome. Live Server usa el puerto `5501`; el host seguro de la API usa `5500`. Ambos puertos enrutan a `127.0.0.1`, y el catálogo, carrito y asistente conservan las llamadas HTTPS.

Ejecuta `py make_cert.py` desde la cuenta de Windows que usa Chrome para crear y confiar un certificado que cubra `localhost` y el dominio local de NEXUS. Reinicia los servidores después. El certificado y el alias sirven para desarrollo en este equipo; publicar el sitio requiere un dominio propio y un certificado TLS público válido.

La ficha del Galaxy A57 5G usa la imagen correspondiente al modelo de 256 GB de Ktronix Colombia. Las cotizaciones incluyen descripcion, vendedor, precio de referencia en COP, fecha y enlace de la tienda. El boton **Descargar constancia** crea un registro local de una solicitud simulada; no acredita un pago.