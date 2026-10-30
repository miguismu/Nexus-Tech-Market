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

1. Abre esta carpeta en VS Code.
2. En la terminal integrada crea y activa un entorno virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   py -m pip install -r requirements.txt
   ```

3. Inicia la API en una terminal y conserva abierta la ventana:

   ```powershell
   py server.py
   ```

   La terminal muestra el código temporal del panel de revisión. Es generado al iniciar el backend si no definiste `NEXUS_ADMIN_CODE`; úsalo desde “Panel de revisión”. No lo publiques ni lo compartas.

4. Con Flask activo, abre `http://127.0.0.1:5000/` para cargar la tienda y la API desde el mismo servidor. También puedes abrir `index.html` con la extensión **Live Server**; si usa el puerto 5501, la API admite ese origen. Si el backend está apagado, Live Server muestra el modo visual de solo lectura.
5. Para ver misión y visión, abre **Nuestra visión** desde la navegación.

La API responde en `http://127.0.0.1:5000/api/health`. El archivo `nexus.db` se crea al ejecutar el backend por primera vez y no se incluye en el proyecto. La tarea automática de VS Code puede iniciar el backend al abrir la carpeta; en otro equipo, configura primero el entorno y las dependencias.

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

Además, el guardian `nexus-siempre-activo.ps1` (tarea programada **NEXUS-SiempreActivo**) verifica cada 60 segundos que la página responda y la reinicia sola si llega a caer; también arranca al iniciar sesión de Windows. Registro del guardian: `nexus-guardian.log`.

Si el equipo se reinicia, vuelve a ejecutar `py iniciar_nexus.py`. El código del panel y la base de datos no cambian. Para crear el certificado local (candado en Chrome) usa `py make_cert.py` una sola vez.

**Dirección oficial del proyecto:** <https://nexus.con> (dominio propio pendiente de registro; localmente la tienda corre en <http://localhost:5000>).

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

Live Server tiene configurado el certificado local en `.vscode/settings.json`. Inicia la tarea de VS Code **NEXUS: iniciar API HTTPS segura**, luego inicia Live Server y abre `https://localhost:5500` (usa el puerto HTTPS que muestre la extension). La API funciona en `https://localhost:5443`; asi el carrito y el asistente de voz no hacen solicitudes HTTP inseguras desde la pagina segura.

Si Chrome no confia en el certificado, deten el proceso `run_https.py`, ejecuta `py make_cert.py` desde la misma cuenta de Windows que usa Chrome, reinicia la tarea de API y Live Server y, al final, reinicia Chrome. El certificado solo sirve para desarrollo local; publicar el sitio requiere un dominio y un certificado TLS valido.

La ficha del Galaxy A57 5G usa la imagen correspondiente al modelo de 256 GB de Ktronix Colombia. Las cotizaciones incluyen descripcion, vendedor, precio de referencia en COP, fecha y enlace de la tienda. El boton **Descargar constancia** crea un registro local de una solicitud simulada; no acredita un pago.