# Web de cerrajería (estática y orientada a SEO)

## Archivos que tienes que editar

| Archivo | Qué contiene |
|---|---|
| `config.json` | **Datos del negocio**: teléfono, WhatsApp, email, dirección, ciudad, zonas, horario, tiempo de llegada, dominio, datos legales, ID de Google Analytics |
| `contenido.json` | **Textos**: títulos SEO, descripciones, servicios, preguntas frecuentes |
| `assets/styles.css` | Diseño (los colores de marca están al principio, en `:root`) |

En los textos puedes usar estas variables: `{ciudad}`, `{provincia}`, `{telefono}`, `{nombre}`,
`{tiempo_llegada}`, `{horario}`, `{anios_experiencia}`, `{email}`. Se sustituyen al generar la web.

- `telefono`: tal y como quieres que se vea (`985 00 00 00`). El enlace `tel:+34985000000` se crea solo.
  Si no es un número español de 9 cifras, rellena `telefono_enlace` (ej. `+351...`).
- `whatsapp`: número con prefijo y sin espacios (`34600000000`). Déjalo vacío (`""`) para ocultar los botones de WhatsApp.
- `google_analytics_id`: si lo rellenas (`G-XXXX`), se registran como eventos los clics en *llamar* y *WhatsApp*.
  En ese caso necesitarás añadir un banner de consentimiento de cookies.

## Generar la web

```bash
python build.py           # genera la carpeta public/
python build.py --serve   # genera y abre una vista previa en http://localhost:8000
```

Lo que tienes que subir al hosting es el contenido de **`public/`**. No hace falta PHP ni base de datos.

## Añadir un servicio nuevo

Copia un bloque dentro de `"servicios"` en `contenido.json`, cambia el `slug` (será la URL, p. ej.
`/cerrajero-comunidades/`) y los textos. Iconos disponibles: `puerta`, `reloj`, `candado`, `escudo`, `caja`, `coche`, `llave`.

## Añadir una zona (página por ciudad)

Copia un bloque dentro de `"localidades"` en `contenido.json` y cambia `slug` (p. ej. `cerrajeros-aviles`),
`nombre`, `llegada`, textos, barrios y preguntas. Usa `{localidad}` y `{llegada}` dentro de sus textos.
**Escribe textos distintos para cada zona**: si solo cambias el nombre de la ciudad, Google lo trata como contenido duplicado.

## SEO incluido

- Una página por servicio con URL limpia, `<title>` y `meta description` propios, H1 con la ciudad
- Datos estructurados schema.org: `Locksmith` (negocio local 24h), `Service`, `FAQPage`, `BreadcrumbList`
- `sitemap.xml`, `robots.txt`, URL canónica, Open Graph
- HTML estático, sin JavaScript ni fuentes externas: carga muy rápida (Core Web Vitals)
- Páginas legales (aviso legal, privacidad, cookies) con `noindex`

## Después de publicar

1. Cambia `dominio` en `config.json` por el real y vuelve a generar la web.
2. Da de alta la web en **Google Search Console** y envía `https://tudominio/sitemap.xml`.
3. Crea o verifica la ficha de **Google Business Profile** con exactamente el mismo nombre, teléfono y dirección que en `config.json`.
4. Si el negocio no tiene local abierto al público, pon `"mostrar_direccion": false`.
   Para ocultar el email en toda la web, pon `"mostrar_email": false` (con `true` vuelve a aparecer).
