#!/usr/bin/env python3
"""
Generador de la web estática de cerrajería.

  python build.py           -> genera la web en la carpeta public/
  python build.py --serve   -> la genera y la abre en http://localhost:8000

Los datos de contacto están en config.json y los textos en contenido.json.
No necesita librerías externas (solo Python 3.8+).
"""
import datetime
import functools
import html
import http.server
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent
SALIDA = BASE / "public"
ASSETS = BASE / "assets"


def cargar(nombre):
    return json.loads((BASE / nombre).read_text(encoding="utf-8"))


CFG = cargar("config.json")
# Si "mostrar_email" es false, el email no aparece en ningún sitio de la web
if not CFG.get("mostrar_email", True):
    CFG["email"] = ""
CONT = cargar("contenido.json")
DOM = CFG["dominio"].rstrip("/")
HOY = datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# Variables y utilidades
# --------------------------------------------------------------------------
def _tel_enlace():
    if CFG.get("telefono_enlace"):
        return CFG["telefono_enlace"]
    digitos = re.sub(r"\D", "", CFG["telefono"])
    if len(digitos) == 9:  # número español sin prefijo
        digitos = "34" + digitos
    return "+" + digitos


TEL = CFG["telefono"]
TEL_E164 = _tel_enlace()
TEL_HREF = "tel:" + TEL_E164

VARS = {
    "ciudad": CFG["ciudad"],
    "provincia": CFG["provincia"],
    "telefono": TEL,
    "nombre": CFG["nombre_negocio"],
    "tiempo_llegada": CFG["tiempo_llegada"],
    "horario": CFG["horario"],
    "anios_experiencia": str(CFG["anios_experiencia"]),
    "email": CFG.get("email", ""),
}


def t(texto):
    """Sustituye {ciudad}, {telefono}... en un texto."""
    texto = str(texto)
    for k, v in VARS.items():
        texto = texto.replace("{" + k + "}", v)
    return texto


def e(texto):
    """Sustituye variables y escapa para HTML."""
    return html.escape(t(texto))


WA_NUM = re.sub(r"\D", "", CFG.get("whatsapp", ""))
WA_HREF = (
    f"https://wa.me/{WA_NUM}?text={quote(t(CFG.get('whatsapp_mensaje', '')))}"
    if WA_NUM else ""
)

ICONOS = {
    "telefono": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "llave": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    "puerta": '<path d="M13 4h3a2 2 0 0 1 2 2v14"/><path d="M2 20h3"/><path d="M13 20h9"/><path d="M10 12v.01"/><path d="M13 4.56v16.16a1 1 0 0 1-1.24.97L5 20V5.56a2 2 0 0 1 1.52-1.94l4-1A2 2 0 0 1 13 4.56z"/>',
    "candado": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "reloj": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "escudo": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "caja": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="4"/><path d="M12 8v1M12 15v1M8 12h1M15 12h1"/>',
    "coche": '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "chat": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
}


LOCALIDADES = CONT.get("localidades", [])
BARRIOS = CONT.get("barrios", [])      # barrios de la ciudad principal (una página por barrio)
GUIAS = CONT.get("guias", [])          # artículos / guías prácticas en /guias/


def tl(texto, loc):
    """Sustituye {localidad} y {llegada} de una página de zona (el resto lo hace t/e)."""
    return str(texto).replace("{localidad}", loc["nombre"]).replace("{llegada}", loc["llegada"])


def ico(nombre, clase="ico"):
    return f'<svg class="{clase}" viewBox="0 0 24 24" aria-hidden="true">{ICONOS[nombre]}</svg>'


def jsonld(obj):
    datos = json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">{datos}</script>'


def url(ruta=""):
    return f"{DOM}/{ruta}"


# --------------------------------------------------------------------------
# Datos estructurados (schema.org)
# --------------------------------------------------------------------------
NEGOCIO_ID = url("#negocio")


def schema_negocio():
    direccion = {
        "@type": "PostalAddress",
        "addressLocality": CFG["ciudad"],
        "addressRegion": CFG.get("region") or CFG["provincia"],
        "postalCode": CFG.get("codigo_postal", ""),
        "addressCountry": "ES",
    }
    if CFG.get("mostrar_direccion") and CFG.get("direccion"):
        direccion["streetAddress"] = CFG["direccion"]
    obj = {
        "@context": "https://schema.org",
        "@type": "Locksmith",
        "@id": NEGOCIO_ID,
        "name": CFG["nombre_negocio"],
        "url": url(),
        "logo": url("assets/img/logo.png"),
        "image": url("assets/img/portada.png"),
        "telephone": TEL_E164,
        "priceRange": CFG.get("rango_precios", "€€"),
        "address": direccion,
        "areaServed": [{"@type": "Place", "name": z} for z in
                       list(dict.fromkeys([CFG["ciudad"]] + [l["nombre"] for l in LOCALIDADES]
                                          + [b["nombre"] for b in BARRIOS] + CFG.get("zonas", [])))],
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Servicios de cerrajería",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": t(s["nombre"]), "url": url(s["slug"] + "/")}}
                for s in CONT["servicios"]
            ],
        },
    }
    if CFG.get("email"):
        obj["email"] = CFG["email"]
    if CFG.get("latitud") and CFG.get("longitud"):
        obj["geo"] = {"@type": "GeoCoordinates", "latitude": CFG["latitud"], "longitude": CFG["longitud"]}
    if CFG.get("abierto_24h"):
        obj["openingHoursSpecification"] = {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "opens": "00:00",
            "closes": "23:59",
        }
    return obj


def schema_faq(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": t(f["pregunta"]),
             "acceptedAnswer": {"@type": "Answer", "text": t(f["respuesta"])}}
            for f in faqs
        ],
    }


def schema_migas(migas):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": nombre, "item": url(ruta)}
            for i, (nombre, ruta) in enumerate(migas)
        ],
    }


# --------------------------------------------------------------------------
# Componentes
# --------------------------------------------------------------------------
def boton_wa(clase="btn btn--wa"):
    if not WA_HREF:
        return ""
    return f'<a class="{clase}" href="{WA_HREF}" target="_blank" rel="noopener">{ico("chat")} Escríbenos por WhatsApp</a>'


def tarjeta_telefono(etiqueta="Cerrajero disponible ahora"):
    return f"""
<div class="phonecard">
  <p class="phonecard__label"><span class="dot"></span>{e(etiqueta)}</p>
  <a class="bigphone" href="{TEL_HREF}" aria-label="Llamar al {e(TEL)}">{ico("telefono")}<span>{e(TEL)}</span></a>
  <p class="phonecard__hint">Precio cerrado por teléfono, sin compromiso</p>
  {boton_wa()}
</div>"""


def lista_checks(items, clase="checks"):
    lis = "".join(f"<li>{ico('check')}<span>{e(i)}</span></li>" for i in items)
    return f'<ul class="{clase}">{lis}</ul>'


def tarjeta_servicio(s, raiz):
    return f"""
<a class="card" href="{raiz}{s['slug']}/">
  <span class="card__ico">{ico(s['icono'])}</span>
  <h3>{e(s['nombre'])}</h3>
  <p>{e(s['resumen'])}</p>
  <span class="card__more">Ver servicio</span>
</a>"""


def tarjeta_localidad(loc, raiz):
    return f"""
<a class="card" href="{raiz}{loc['slug']}/">
  <span class="card__ico">{ico('pin')}</span>
  <h3>Cerrajeros en {e(loc['nombre'])}</h3>
  <p>Llegada en {e(loc['llegada'])} · {e(', '.join(loc['barrios'][:3]))}...</p>
  <span class="card__more">Ver zona</span>
</a>"""


def tarjeta_barrio(b, raiz):
    return f"""
<a class="card card--compact" href="{raiz}{b['slug']}/">
  <h3>{e(b['nombre'])}</h3>
  <p>Llegada en {e(b['llegada'])}</p>
  <span class="card__more">Cerrajeros en {e(b['nombre'])}</span>
</a>"""


def tarjeta_guia(g, raiz):
    return f"""
<a class="card" href="{raiz}guias/{g['slug']}/">
  <span class="card__tag">Guía</span>
  <h3>{e(g['titulo'])}</h3>
  <p>{e(g['resumen'])}</p>
  <span class="card__more">Leer guía</span>
</a>"""


def bloque_guias(guias, raiz, titulo="Guías prácticas", alt=False, max_=3):
    if not guias:
        return ""
    tarjetas = "".join(tarjeta_guia(g, raiz) for g in guias[:max_])
    return f"""
<section class="section{' section--alt' if alt else ''}">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Consejos de cerrajero</p>
      <h2>{e(titulo)}</h2>
    </div>
    <div class="cards">{tarjetas}</div>
    <p class="center"><a class="btn btn--wa" href="{raiz}guias/">Ver todas las guías</a></p>
  </div>
</section>"""


def bloque_faq(faqs, titulo="Preguntas frecuentes", id_="preguntas", alt=False):
    items = "".join(
        f"<details><summary>{e(f['pregunta'])}</summary><p>{e(f['respuesta'])}</p></details>"
        for f in faqs
    )
    return f"""
<section class="section{' section--alt' if alt else ''}" id="{id_}">
  <div class="wrap">
    <div class="section__head"><h2>{e(titulo)}</h2></div>
    <div class="faq">{items}</div>
  </div>
</section>"""


def banda_cta(titulo="¿Necesitas un cerrajero ahora?", texto="Te atendemos {horario}. Llegamos en {tiempo_llegada}."):
    return f"""
<section class="cta">
  <div class="wrap cta__in">
    <div>
      <h2>{e(titulo)}</h2>
      <p>{e(texto)}</p>
    </div>
    <a class="bigphone" href="{TEL_HREF}" aria-label="Llamar al {e(TEL)}">{ico("telefono")}<span>{e(TEL)}</span></a>
  </div>
</section>"""


def analitica():
    gid = CFG.get("google_analytics_id", "").strip()
    if not gid:
        return ""
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={html.escape(gid)}"></script>\n'
        "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
        f"gtag('js',new Date());gtag('config','{html.escape(gid)}');"
        "document.addEventListener('click',function(ev){var a=ev.target.closest('a[href^=\"tel:\"],a[href^=\"https://wa.me\"]');"
        "if(a){gtag('event',a.href.indexOf('tel:')===0?'click_llamada':'click_whatsapp',{link_url:a.href});}});</script>"
    )


# --------------------------------------------------------------------------
# Plantilla general
# --------------------------------------------------------------------------
def plantilla(titulo, descripcion, ruta, cuerpo, raiz, schemas=(), indexar=True):
    canonical = url(ruta)
    servicios_footer = "".join(
        f'<li><a href="{raiz}{s["slug"]}/">{e(s["nombre"])}</a></li>' for s in CONT["servicios"]
    )
    zonas_footer = "".join(
        f'<li><a href="{raiz}{l["slug"]}/">Cerrajeros en {e(l["nombre"])}</a></li>' for l in LOCALIDADES
    ) or "".join(f"<li>{e(z)}</li>" for z in CFG.get("zonas", [])[:8])
    if BARRIOS:
        zonas_footer = f'<li><a href="{raiz}#barrios">Barrios de {e(CFG["ciudad"])}</a></li>' + zonas_footer
    guias_footer = f'<li><a href="{raiz}guias/">Guías y consejos</a></li>' if GUIAS else ""
    guias_nav = f'<a href="{raiz}guias/">Guías</a>' if GUIAS else ""
    if CFG.get("mostrar_direccion") and CFG.get("direccion"):
        direccion = f'{e(CFG["direccion"])}, {e(CFG.get("codigo_postal", ""))} {e(CFG["ciudad"])} ({e(CFG["provincia"])})'
    else:
        direccion = f'Servicio en {e(CFG["ciudad"])} y alrededores'
    email = (
        f'<li><a href="mailto:{e(CFG["email"])}">{e(CFG["email"])}</a></li>' if CFG.get("email") else ""
    )
    wa_barra = (
        f'<a class="callbar__wa" href="{WA_HREF}" target="_blank" rel="noopener" aria-label="WhatsApp">{ico("chat")}</a>'
        if WA_HREF else ""
    )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<meta name="robots" content="{'index,follow' if indexar else 'noindex,follow'}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_ES">
<meta property="og:site_name" content="{e(CFG['nombre_negocio'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{url('assets/img/portada.png')}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="675">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#10233A">
<meta name="format-detection" content="telephone=yes">
<link rel="icon" href="{raiz}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{raiz}assets/styles.css">
{''.join(jsonld(s) for s in schemas)}
{analitica()}
</head>
<body>
<a class="skip" href="#contenido">Saltar al contenido</a>
<div class="topbar"><span class="dot"></span>Atención {e(CFG['horario'])} · Llegada en {e(CFG['tiempo_llegada'])}<span class="topbar__extra"> · Precio cerrado antes de salir</span></div>
<header class="header">
  <div class="wrap header__in">
    <a class="logo" href="{raiz or './'}"><span class="logo__ico">{ico("llave")}</span><span>{e(CFG['nombre_negocio'])}</span></a>
    <nav class="nav" aria-label="Principal">
      <a href="{raiz}#servicios">Servicios</a>
      <a href="{raiz}#zonas">Zonas</a>
      {guias_nav}
      <a href="{raiz}#preguntas">Preguntas</a>
      <a href="{raiz}#contacto">Contacto</a>
    </nav>
    <a class="btn btn--call header__call" href="{TEL_HREF}" aria-label="Llamar al {e(TEL)}">{ico("telefono")}<span>{e(TEL)}</span></a>
  </div>
</header>

<main id="contenido">
{cuerpo}
</main>

<footer class="footer">
  <div class="wrap">
    <div class="footer__grid">
      <div>
        <p class="footer__title">{e(CFG['nombre_negocio'])}</p>
        <p>Servicio técnico de cerrajería urgente en {e(CFG['ciudad'])} y alrededores, {e(CFG['horario'])}.</p>
        <a class="footer__phone" href="{TEL_HREF}">{ico("telefono")}{e(TEL)}</a>
        <ul>
          <li>{direccion}</li>
          {email}
        </ul>
      </div>
      <div>
        <p class="footer__title">Servicios</p>
        <ul>{servicios_footer}</ul>
      </div>
      <div>
        <p class="footer__title">Zonas</p>
        <ul>{zonas_footer}<li><a href="{raiz}#zonas">Ver todas</a></li></ul>
      </div>
      <div>
        <p class="footer__title">Información</p>
        <ul>
          {guias_footer}
          <li><a href="{raiz}aviso-legal/">Aviso legal</a></li>
          <li><a href="{raiz}privacidad/">Política de privacidad</a></li>
          <li><a href="{raiz}cookies/">Política de cookies</a></li>
        </ul>
      </div>
    </div>
    <div class="footer__bottom">
      <span>© {datetime.date.today().year} {e(CFG['nombre_negocio'])}</span>
      <span>Cerrajeros en {e(CFG['ciudad'])} · {e(CFG['horario'])}</span>
    </div>
  </div>
</footer>

<div class="callbar">
  <a class="callbar__call" href="{TEL_HREF}">{ico("telefono")}<span>Llamar <strong>{e(TEL)}</strong></span></a>
  {wa_barra}
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Páginas
# --------------------------------------------------------------------------
def pagina_inicio():
    ini = CONT["inicio"]
    raiz = ""
    tarjetas = "".join(tarjeta_servicio(s, raiz) for s in CONT["servicios"])
    pasos = "".join(
        f'<li class="step"><h3>{e(p["titulo"])}</h3><p>{e(p["texto"])}</p></li>' for p in ini["pasos"]
    )
    parrafos = "".join(f"<p>{e(p)}</p>" for p in ini["texto"])
    con_pagina = {b["nombre"].lower() for b in BARRIOS} | {l["nombre"].lower() for l in LOCALIDADES}
    zonas = "".join(f'<li>{ico("pin")}{e(z)}</li>' for z in CFG.get("zonas", []) if z.lower() not in con_pagina)
    bloque_barrios = (
        f'<h3 class="subhead" id="barrios">Barrios de {e(CFG["ciudad"])}</h3>'
        f'<div class="cards cards--4">{"".join(tarjeta_barrio(b, raiz) for b in BARRIOS)}</div>'
        f'<h3 class="subhead">Otras localidades de {e(CFG["provincia"])}</h3>'
        if BARRIOS else ""
    )
    tarjetas_loc = (
        f'<div class="cards" style="margin-bottom:2rem">{"".join(tarjeta_localidad(l, raiz) for l in LOCALIDADES)}</div>'
        if LOCALIDADES else ""
    )

    if CFG.get("mostrar_direccion") and CFG.get("direccion"):
        etiqueta_dir = "Dirección"
        direccion = f'{e(CFG["direccion"])}<br>{e(CFG.get("codigo_postal", ""))} {e(CFG["ciudad"])} ({e(CFG["provincia"])})'
    else:
        etiqueta_dir = "Zona de servicio"
        direccion = f'{e(CFG["ciudad"])} y alrededores ({e(CFG["provincia"])})'
    contacto_email = (
        f'<div class="contact__item">{ico("mail")}<div><strong>Email</strong>'
        f'<a href="mailto:{e(CFG["email"])}">{e(CFG["email"])}</a></div></div>'
        if CFG.get("email") else ""
    )
    contacto_wa = (
        f'<div class="contact__item">{ico("chat")}<div><strong>WhatsApp</strong>'
        f'<a href="{WA_HREF}" target="_blank" rel="noopener">Enviar mensaje</a></div></div>'
        if WA_HREF else ""
    )

    cuerpo = f"""
<section class="hero">
  <div class="wrap hero__in">
    <div class="hero__text">
      <p class="eyebrow">Cerrajería urgente en {e(CFG['ciudad'])} y alrededores</p>
      <h1>{e(ini['h1_inicio'])} <span class="hl">{e(ini['h1_destacado'])}</span></h1>
      <p class="lead">{e(ini['subtitulo'])}</p>
    </div>
    <div class="hero__cta">{tarjeta_telefono()}</div>
    <div class="hero__ticks">{lista_checks(ini['ventajas'], 'ticks')}</div>
  </div>
</section>

<section class="stats" aria-label="Datos del servicio">
  <div class="wrap stats__in">
    <div class="stat"><strong>365</strong><span>días al año</span></div>
    <div class="stat"><strong>{e(CFG['tiempo_llegada'])}</strong><span>tiempo de llegada</span></div>
    <div class="stat"><strong>+{e(CFG['anios_experiencia'])} años</strong><span>de experiencia</span></div>
    <div class="stat"><strong>0 €</strong><span>presupuesto sin compromiso</span></div>
  </div>
</section>

<section class="section" id="servicios">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Nuestros servicios</p>
      <h2>Servicios de cerrajería en {e(CFG['ciudad'])}</h2>
      <p>Urgencias, aperturas, cambios de cerradura y seguridad para tu hogar o negocio.</p>
    </div>
    <div class="cards">{tarjetas}</div>
  </div>
</section>

<section class="section section--alt">
  <div class="wrap split">
    <div class="prose">
      <h2>{e(ini['texto_titulo'])}</h2>
      {parrafos}
      <a class="btn btn--call btn--lg" href="{TEL_HREF}">{ico("telefono")}Llamar al {e(TEL)}</a>
    </div>
    <aside class="box">
      <h3>{e(ini['por_que_titulo'])}</h3>
      {lista_checks(ini['por_que'])}
    </aside>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Así de fácil</p>
      <h2>Cómo trabajamos</h2>
    </div>
    <ol class="steps">{pasos}</ol>
  </div>
</section>

{banda_cta("¿Te has quedado fuera de casa?", "Llama ahora y un cerrajero sale hacia tu dirección en {ciudad}.")}

<section class="section" id="zonas">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Zonas de servicio</p>
      <h2>Cerrajeros en {e(CFG['ciudad'])} y alrededores</h2>
      <p>Damos servicio en todos los barrios de {e(CFG['ciudad'])} y en las localidades cercanas de {e(CFG['provincia'])}.</p>
    </div>
    {bloque_barrios}
    {tarjetas_loc}
    <ul class="chips">{zonas}</ul>
  </div>
</section>

{bloque_faq(CONT['faqs'], alt=True)}

{bloque_guias(GUIAS, raiz, "Guías prácticas de cerrajería")}

<section class="section" id="contacto">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Contacto</p>
      <h2>Llámanos, te atendemos al momento</h2>
    </div>
    <div class="contact">
      <div class="contact__main">{tarjeta_telefono("Atención inmediata " + CFG['horario'])}</div>
      <div class="contact__list">
        <div class="contact__item">{ico("telefono")}<div><strong>Teléfono</strong><a href="{TEL_HREF}">{e(TEL)}</a></div></div>
        {contacto_wa}
        {contacto_email}
        <div class="contact__item">{ico("pin")}<div><strong>{etiqueta_dir}</strong><span>{direccion}</span></div></div>
        <div class="contact__item">{ico("reloj")}<div><strong>Horario</strong><span>{e(CFG['horario'])}</span></div></div>
      </div>
    </div>
  </div>
</section>
"""
    schemas = [
        schema_negocio(),
        {"@context": "https://schema.org", "@type": "WebSite", "name": CFG["nombre_negocio"], "url": url()},
        schema_faq(CONT["faqs"]),
    ]
    return plantilla(ini["titulo_seo"], ini["descripcion_meta"], "", cuerpo, raiz, schemas)


def pagina_servicio(s):
    raiz = "../"
    ruta = s["slug"] + "/"
    secciones = "".join(
        f"<h2>{e(sec['titulo'])}</h2>" + "".join(f"<p>{e(p)}</p>" for p in sec["texto"])
        for sec in s["secciones"]
    )
    otros = "".join(tarjeta_servicio(o, raiz) for o in CONT["servicios"] if o["slug"] != s["slug"])
    faqs = s.get("faqs", [])
    guias_rel = [g for g in GUIAS if g.get("servicio_relacionado") == s["slug"]]

    cuerpo = f"""
<section class="hero hero--page">
  <div class="wrap hero__in">
    <div class="hero__text">
      <nav class="crumbs" aria-label="Migas de pan"><ol>
        <li><a href="{raiz}">Inicio</a></li>
        <li><a href="{raiz}#servicios">Servicios</a></li>
        <li aria-current="page">{e(s['nombre'])}</li>
      </ol></nav>
      <h1>{e(s['h1'])}</h1>
      <p class="lead">{e(s['resumen'])}</p>
    </div>
    <div class="hero__cta">{tarjeta_telefono()}</div>
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <article class="prose">
      {secciones}
      <h2>¿Qué incluye el servicio?</h2>
      {lista_checks(s['puntos'])}
      <a class="btn btn--call btn--lg" href="{TEL_HREF}">{ico("telefono")}Llamar al {e(TEL)}</a>
    </article>
    <aside class="box">
      <h3>¿Lo necesitas ahora?</h3>
      <p>Llámanos y te damos precio cerrado al momento.</p>
      <a class="bigphone bigphone--sm" href="{TEL_HREF}">{ico("telefono")}<span>{e(TEL)}</span></a>
      {lista_checks(['Llegada en {tiempo_llegada}', 'Servicio {horario}', 'Factura y garantía'])}
      {boton_wa()}
    </aside>
  </div>
</section>

{banda_cta()}

{bloque_faq(faqs, "Preguntas frecuentes sobre " + s['nombre'].lower(), "preguntas", alt=True) if faqs else ""}

{bloque_guias(guias_rel, raiz, "Guías relacionadas")}

<section class="section">
  <div class="wrap">
    <div class="section__head"><h2>Otros servicios de cerrajería en {e(CFG['ciudad'])}</h2></div>
    <div class="cards">{otros}</div>
  </div>
</section>
"""
    schemas = [
        schema_negocio(),
        {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": t(s["h1"]),
            "serviceType": t(s["nombre"]),
            "description": t(s["descripcion_meta"]),
            "url": url(ruta),
            "provider": {"@id": NEGOCIO_ID},
            "areaServed": {"@type": "City", "name": CFG["ciudad"]},
        },
        schema_migas([("Inicio", ""), (t(s["nombre"]), ruta)]),
    ]
    if faqs:
        schemas.append(schema_faq(faqs))
    return plantilla(s["titulo_seo"], s["descripcion_meta"], ruta, cuerpo, raiz, schemas)


def pagina_localidad(loc, es_barrio=False):
    raiz = "../"
    ruta = loc["slug"] + "/"
    secciones = "".join(
        f"<h2>{e(tl(sec['titulo'], loc))}</h2>" + "".join(f"<p>{e(tl(p, loc))}</p>" for p in sec["texto"])
        for sec in loc["secciones"]
    )
    barrios = "".join(f'<li>{ico("pin")}{e(b)}</li>' for b in loc["barrios"])
    tarjetas = "".join(tarjeta_servicio(s, raiz) for s in CONT["servicios"])
    faqs = [{"pregunta": tl(f["pregunta"], loc), "respuesta": tl(f["respuesta"], loc)} for f in loc.get("faqs", [])]
    nombre = loc["nombre"]
    ciudad = CFG["ciudad"]
    if es_barrio:
        otras = "".join(tarjeta_barrio(o, raiz) for o in BARRIOS if o["slug"] != loc["slug"])
        titulo_otras = f"Cerrajeros en otros barrios de {ciudad}"
        clase_otras = "cards cards--4"
        miga_padre = f'<li><a href="{raiz}#barrios">Barrios de {e(ciudad)}</a></li>'
        titulo_chips = f"Calles y zonas de {nombre} donde trabajamos"
        area = {"@type": "Place", "name": f"{nombre}, {ciudad}",
                "containedInPlace": {"@type": "City", "name": ciudad}}
    else:
        otras = "".join(tarjeta_localidad(o, raiz) for o in LOCALIDADES if o["slug"] != loc["slug"])
        titulo_otras = f"Cerrajeros en otras zonas de {CFG['provincia']}"
        clase_otras = "cards"
        miga_padre = f'<li><a href="{raiz}#zonas">Zonas</a></li>'
        titulo_chips = f"Barrios y localidades donde trabajamos en {nombre}"
        area = {"@type": "City", "name": nombre}

    cuerpo = f"""
<section class="hero hero--page">
  <div class="wrap hero__in">
    <div class="hero__text">
      <nav class="crumbs" aria-label="Migas de pan"><ol>
        <li><a href="{raiz}">Inicio</a></li>
        {miga_padre}
        <li aria-current="page">{e(nombre)}</li>
      </ol></nav>
      <h1>{e(tl(loc['h1'], loc))}</h1>
      <p class="lead">{e(tl(loc['intro'], loc))}</p>
    </div>
    <div class="hero__cta">{tarjeta_telefono("Cerrajero disponible en " + nombre)}</div>
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <article class="prose">
      {secciones}
      <a class="btn btn--call btn--lg" href="{TEL_HREF}">{ico("telefono")}Llamar al {e(TEL)}</a>
    </article>
    <aside class="box">
      <h3>Cerrajero en {e(nombre)}</h3>
      <p>Llámanos y te damos precio cerrado al momento.</p>
      <a class="bigphone bigphone--sm" href="{TEL_HREF}">{ico("telefono")}<span>{e(TEL)}</span></a>
      {lista_checks(['Llegada en ' + loc['llegada'], 'Servicio {horario}', 'Precio cerrado antes de salir', 'Factura y garantía'])}
      {boton_wa()}
    </aside>
  </div>
</section>

<section class="section section--alt">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Zonas de servicio</p>
      <h2>{e(titulo_chips)}</h2>
    </div>
    <ul class="chips">{barrios}</ul>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="section__head">
      <p class="kicker">Servicios</p>
      <h2>Servicios de cerrajería en {e(nombre)}</h2>
    </div>
    <div class="cards">{tarjetas}</div>
  </div>
</section>

{banda_cta("¿Necesitas un cerrajero en " + nombre + "?", "Te atendemos {horario}. Llegamos en " + loc['llegada'] + ".")}

{bloque_faq(faqs, "Preguntas frecuentes sobre cerrajeros en " + nombre, "preguntas", alt=True) if faqs else ""}

<section class="section">
  <div class="wrap">
    <div class="section__head"><h2>{e(titulo_otras)}</h2></div>
    <div class="{clase_otras}">{otras}</div>
  </div>
</section>
"""
    schemas = [
        schema_negocio(),
        {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": f"Cerrajeros en {nombre}",
            "serviceType": "Cerrajería",
            "description": t(tl(loc["descripcion_meta"], loc)),
            "url": url(ruta),
            "provider": {"@id": NEGOCIO_ID},
            "areaServed": area,
        },
        schema_migas([("Inicio", ""), (f"Cerrajeros en {nombre}", ruta)]),
    ]
    if faqs:
        schemas.append(schema_faq(faqs))
    return plantilla(tl(loc["titulo_seo"], loc), tl(loc["descripcion_meta"], loc), ruta, cuerpo, raiz, schemas)


def pagina_guia(g):
    raiz = "../../"
    ruta = f"guias/{g['slug']}/"
    indice = "".join(
        f'<li><a href="#s{i}">{e(sec["titulo"])}</a></li>' for i, sec in enumerate(g["secciones"], 1)
    )
    secciones = "".join(
        f'<h2 id="s{i}">{e(sec["titulo"])}</h2>' + "".join(f"<p>{e(p)}</p>" for p in sec["texto"])
        for i, sec in enumerate(g["secciones"], 1)
    )
    pasos = ""
    if g.get("pasos"):
        pasos = '<div class="note"><h2>Resumen rápido</h2><ol>' + "".join(
            f"<li>{e(p)}</li>" for p in g["pasos"]) + "</ol></div>"
    serv = next((s for s in CONT["servicios"] if s["slug"] == g.get("servicio_relacionado")), None)
    caja_serv = (
        f'<p>Servicio relacionado: <a href="{raiz}{serv["slug"]}/">{e(serv["nombre"])} en {e(CFG["ciudad"])}</a></p>'
        if serv else ""
    )
    otras = [o for o in GUIAS if o["slug"] != g["slug"]]
    faqs = g.get("faqs", [])

    cuerpo = f"""
<section class="hero hero--page hero--article">
  <div class="wrap">
    <nav class="crumbs" aria-label="Migas de pan"><ol>
      <li><a href="{raiz}">Inicio</a></li>
      <li><a href="{raiz}guias/">Guías</a></li>
      <li aria-current="page">{e(g['titulo'])}</li>
    </ol></nav>
    <h1>{e(g['titulo'])}</h1>
    <p class="lead">{e(g['resumen'])}</p>
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <article class="prose">
      <nav class="toc" aria-label="En esta guía"><p>En esta guía</p><ol>{indice}</ol></nav>
      {pasos}
      {secciones}
    </article>
    <aside class="box">
      <h3>¿Necesitas un cerrajero ahora?</h3>
      <p>Te damos precio cerrado por teléfono antes de salir.</p>
      <a class="bigphone bigphone--sm" href="{TEL_HREF}">{ico("telefono")}<span>{e(TEL)}</span></a>
      {lista_checks(['Llegada en {tiempo_llegada}', 'Servicio {horario}', 'Factura válida para el seguro'])}
      {caja_serv}
      {boton_wa()}
    </aside>
  </div>
</section>

{bloque_faq(faqs, "Preguntas frecuentes", "preguntas", alt=True) if faqs else ""}

{bloque_guias(otras, raiz, "Otras guías que te pueden servir")}

{banda_cta()}
"""
    schemas = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": t(g["titulo"]),
            "description": t(g["descripcion_meta"]),
            "url": url(ruta),
            "inLanguage": "es-ES",
            "dateModified": HOY,
            "author": {"@id": NEGOCIO_ID},
            "publisher": {"@id": NEGOCIO_ID},
            "mainEntityOfPage": url(ruta),
        },
        schema_negocio(),
        schema_migas([("Inicio", ""), ("Guías", "guias/"), (t(g["titulo"]), ruta)]),
    ]
    if faqs:
        schemas.append(schema_faq(faqs))
    return plantilla(g["titulo_seo"], g["descripcion_meta"], ruta, cuerpo, raiz, schemas)


def pagina_guias():
    raiz = "../"
    tarjetas = "".join(tarjeta_guia(g, raiz) for g in GUIAS)
    cuerpo = f"""
<section class="hero hero--page hero--article">
  <div class="wrap">
    <nav class="crumbs" aria-label="Migas de pan"><ol>
      <li><a href="{raiz}">Inicio</a></li>
      <li aria-current="page">Guías</li>
    </ol></nav>
    <h1>Guías prácticas de cerrajería</h1>
    <p class="lead">Qué hacer en una urgencia, cómo elegir cerrajero sin sorpresas y cómo mejorar la seguridad de tu puerta. Explicado por cerrajeros de {e(CFG['ciudad'])}.</p>
  </div>
</section>
<section class="section">
  <div class="wrap"><div class="cards">{tarjetas}</div></div>
</section>
{banda_cta()}
"""
    schemas = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Guías prácticas de cerrajería",
         "url": url("guias/"),
         "hasPart": [{"@type": "Article", "headline": t(g["titulo"]), "url": url(f"guias/{g['slug']}/")} for g in GUIAS]},
        schema_migas([("Inicio", ""), ("Guías", "guias/")]),
    ]
    return plantilla(f"Guías de cerrajería: consejos prácticos | {CFG['nombre_negocio']}",
                     f"Guías de cerrajeros de {CFG['ciudad']}: qué hacer si te quedas fuera, cómo evitar timos, bombines antibumping y más.",
                     "guias/", cuerpo, raiz, schemas)


def pagina_legal(slug, titulo, parrafos):
    raiz = "../"
    contenido = "".join(
        f"<h2>{e(p[1:])}</h2>" if p.startswith("#") else f"<p>{e(p)}</p>" for p in parrafos
    )
    cuerpo = f"""
<section class="section">
  <div class="wrap legal prose">
    <h1>{e(titulo)}</h1>
    {contenido}
  </div>
</section>
{banda_cta()}
"""
    return plantilla(f"{titulo} | {CFG['nombre_negocio']}", f"{titulo} de {CFG['nombre_negocio']}.",
                     slug + "/", cuerpo, raiz, indexar=False)


def paginas_legales():
    titular = CFG.get("titular_legal", "")
    nif = CFG.get("nif", "")
    dom_legal = f"{CFG.get('direccion', '')}, {CFG.get('codigo_postal', '')} {CFG['ciudad']} ({CFG['provincia']})"
    ga = bool(CFG.get("google_analytics_id", "").strip())
    email = CFG.get("email", "")
    return {
        "aviso-legal": ("Aviso legal", [
            "En cumplimiento de la Ley 34/2002, de Servicios de la Sociedad de la Información y de Comercio Electrónico (LSSI-CE), se informa de los datos del titular de este sitio web:",
            f"Titular: {titular}. NIF/CIF: {nif}. Domicilio: {dom_legal}. Teléfono: {TEL}." + (f" Email: {email}." if email else ""),
            "#Condiciones de uso",
            "El acceso a este sitio web es gratuito y atribuye la condición de usuario. El usuario se compromete a hacer un uso adecuado de los contenidos y a no emplearlos para actividades ilícitas.",
            "#Propiedad intelectual",
            "Los textos, diseños y logotipos de este sitio son propiedad del titular o se utilizan con autorización. Queda prohibida su reproducción sin consentimiento.",
            "#Responsabilidad",
            "El titular no se hace responsable de los daños derivados del uso de la información de esta web ni de los contenidos de sitios enlazados de terceros.",
        ]),
        "privacidad": ("Política de privacidad", [
            f"Responsable del tratamiento: {titular} (NIF {nif}), con domicilio en {dom_legal}" + (f" y email {email}." if email else "."),
            "#Qué datos tratamos",
            "Esta web no dispone de formularios. Solo tratamos los datos que nos facilitas al contactarnos por teléfono, WhatsApp" + (" o email" if email else "") + " (nombre, teléfono, dirección del servicio), con la única finalidad de atender tu solicitud, prestar el servicio y emitir la factura.",
            "#Legitimación y conservación",
            "La base legal es la ejecución del servicio que solicitas y el cumplimiento de obligaciones legales (fiscales). Los datos se conservan durante el tiempo necesario para ello y no se ceden a terceros salvo obligación legal.",
            "#Tus derechos",
            "Puedes ejercer tus derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad " + (f"escribiendo al email indicado" if email else "contactando por los medios indicados") + ". También puedes reclamar ante la Agencia Española de Protección de Datos (www.aepd.es).",
        ]),
        "cookies": ("Política de cookies", [
            "#Uso de cookies",
            ("Este sitio utiliza Google Analytics para obtener estadísticas anónimas de uso. Estas cookies solo se instalan si das tu consentimiento."
             if ga else
             "Este sitio web no utiliza cookies propias ni de terceros para analizar tu navegación ni con fines publicitarios."),
            "Puedes configurar tu navegador para bloquear o eliminar las cookies en cualquier momento.",
        ]),
    }


def pagina_404():
    cuerpo = f"""
<section class="hero hero--page">
  <div class="wrap hero__in">
    <div class="hero__text">
      <p class="eyebrow">Error 404</p>
      <h1>Esta página no existe</h1>
      <p class="lead">Pero si necesitas un cerrajero, estamos disponibles ahora mismo.</p>
      <p><a class="btn btn--call" href="/">Volver al inicio</a></p>
    </div>
    <div class="hero__cta">{tarjeta_telefono()}</div>
  </div>
</section>
"""
    return plantilla(f"Página no encontrada | {CFG['nombre_negocio']}", "Página no encontrada.",
                     "404.html", cuerpo, "/", indexar=False)


# --------------------------------------------------------------------------
# Construcción
# --------------------------------------------------------------------------
def escribir(ruta_rel, contenido):
    destino = SALIDA / ruta_rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")


def construir():
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir()
    shutil.copytree(ASSETS, SALIDA / "assets")

    escribir("index.html", pagina_inicio())
    rutas_sitemap = [("", "1.0")]
    for s in CONT["servicios"]:
        escribir(f"{s['slug']}/index.html", pagina_servicio(s))
        rutas_sitemap.append((s["slug"] + "/", "0.8"))
    for loc in LOCALIDADES:
        escribir(f"{loc['slug']}/index.html", pagina_localidad(loc))
        rutas_sitemap.append((loc["slug"] + "/", "0.9"))
    for b in BARRIOS:
        escribir(f"{b['slug']}/index.html", pagina_localidad(b, es_barrio=True))
        rutas_sitemap.append((b["slug"] + "/", "0.8"))
    if GUIAS:
        escribir("guias/index.html", pagina_guias())
        rutas_sitemap.append(("guias/", "0.6"))
        for g in GUIAS:
            escribir(f"guias/{g['slug']}/index.html", pagina_guia(g))
            rutas_sitemap.append((f"guias/{g['slug']}/", "0.6"))
    slugs = [s["slug"] for s in CONT["servicios"]] + [l["slug"] for l in LOCALIDADES] + [b["slug"] for b in BARRIOS]
    repetidos = {x for x in slugs if slugs.count(x) > 1}
    if repetidos:
        sys.exit(f"ERROR: slugs repetidos en contenido.json: {', '.join(sorted(repetidos))}")
    for slug, (titulo, parrafos) in paginas_legales().items():
        escribir(f"{slug}/index.html", pagina_legal(slug, titulo, parrafos))
    escribir("404.html", pagina_404())

    urls = "".join(
        f"  <url><loc>{url(r)}</loc><lastmod>{HOY}</lastmod><priority>{p}</priority></url>\n"
        for r, p in rutas_sitemap
    )
    escribir("sitemap.xml",
             f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    escribir("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {url('sitemap.xml')}\n")

    print(f"Web generada en {SALIDA}  ({len(rutas_sitemap)} páginas indexables)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # acentos en la consola de Windows
    except AttributeError:
        pass
    construir()
    if "--serve" in sys.argv:
        manejador = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SALIDA))
        print("Vista previa en http://localhost:8000  (Ctrl+C para parar)")
        http.server.ThreadingHTTPServer(("127.0.0.1", 8000), manejador).serve_forever()
