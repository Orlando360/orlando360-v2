from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import anthropic, json, os, re, io, requests
from bs4 import BeautifulSoup
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF

app = Flask(__name__, static_folder='public', static_url_path='')
API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
limiter = Limiter(get_remote_address, app=app, default_limits=[], on_breach=lambda limit: (jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429))

# ═══ COLORES ═══
NEGRO   = colors.HexColor('#0A0A0A')
NEGRO2  = colors.HexColor('#111111')
NEGRO3  = colors.HexColor('#1A1A1A')
DORADO  = colors.HexColor('#F5C518')
DORADO2 = colors.HexColor('#C9A227')
BLANCO  = colors.HexColor('#FFFFFF')
GRIS    = colors.HexColor('#777777')
GRIS2   = colors.HexColor('#2A2A2A')
VERDE   = colors.HexColor('#3DBA7A')
NARANJA = colors.HexColor('#F07C3A')
ROJO    = colors.HexColor('#E84545')
TEXTO   = colors.HexColor('#E0E0E0')
TEXTO2  = colors.HexColor('#AAAAAA')

def sc(s):
    if s>=70: return VERDE
    if s>=40: return DORADO
    return ROJO

def sn(s):
    if s>=70: return 'SÓLIDO'
    if s>=40: return 'EN TRABAJO'
    return 'CRÍTICO'

def semaforo_color(sem):
    if sem=='verde': return VERDE
    if sem=='rojo': return ROJO
    return DORADO


# ═══════════════════════════════════════════════════
#  SCRAPER REAL — extrae datos de la URL del cliente
# ═══════════════════════════════════════════════════
def scrape_url(url):
    if not url or not url.startswith('http'):
        return {'ok': False, 'razon': 'URL no valida.'}
    headers = {'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36'}
    try:
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {'ok': False, 'razon': f'Error de red: {str(e)}'}
    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = str(soup.title.string).strip() if soup.title and soup.title.string else ''
        meta_desc = meta_kw = og_title = og_desc = ''
        for tag in soup.find_all('meta'):
            try:
                n = str(tag.get('name') or '').lower()
                p = str(tag.get('property') or '').lower()
                c = str(tag.get('content') or '')
                if n == 'description': meta_desc = c[:300]
                elif n == 'keywords': meta_kw = c[:200]
                elif p == 'og:title': og_title = c[:150]
                elif p == 'og:description': og_desc = c[:300]
            except Exception: continue
        h1s = [h.get_text(strip=True) for h in soup.find_all('h1')][:5]
        h2s = [h.get_text(strip=True) for h in soup.find_all('h2')][:8]
        dominio = url.split('/')[2] if len(url.split('/')) > 2 else ''
        all_links = []
        for a in soup.find_all('a'):
            try:
                h = a.get('href')
                if h and isinstance(h, str): all_links.append(h)
            except Exception: continue
        internal_links = [h for h in all_links if h.startswith('/') or dominio in h]
        external_links = [h for h in all_links if h.startswith('http') and dominio not in h]
        imgs = soup.find_all('img')
        imgs_sin_alt = sum(1 for i in imgs if not i.get('alt'))
        for tag in soup(['script','style','noscript','header','footer','nav']):
            try: tag.decompose()
            except Exception: pass
        texto_visible = ' '.join(soup.get_text(separator=' ').split())[:1500]
        redes = []
        for h in all_links:
            for red in ['instagram','facebook','tiktok','youtube','twitter','linkedin','pinterest']:
                if red in h.lower() and red not in redes: redes.append(red)
        return {
            'ok': True, 'url': url, 'titulo': title,
            'meta_descripcion': meta_desc, 'meta_keywords': meta_kw,
            'og_title': og_title, 'og_descripcion': og_desc,
            'h1': h1s, 'h2': h2s,
            'total_links': len(all_links),
            'links_internos': len(internal_links),
            'links_externos': len(external_links),
            'total_imagenes': len(imgs),
            'imagenes_sin_alt': imgs_sin_alt,
            'redes_sociales_detectadas': redes,
            'tiene_whatsapp': any('whatsapp' in h.lower() or 'wa.me' in h for h in all_links),
            'tiene_tel': any('tel:' in h for h in all_links),
            'tiene_email': any('mailto:' in h for h in all_links),
            'es_https': url.startswith('https://'),
            'tamano_pagina_kb': round(len(resp.content)/1024, 1),
            'texto_visible_muestra': texto_visible,
        }
    except Exception as e:
        return {'ok': False, 'razon': f'Error al procesar: {str(e)}'}


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/api/auditoria', methods=['POST'])
@limiter.limit('10 per hour')
def auditoria():
    if not API_KEY:
        return jsonify({'error': 'API key no configurada'}), 500

    data = request.json
    empresa = data.get('empresa', '')
    sector  = data.get('sector', '')
    url     = data.get('url', '').strip()

    # ── SCRAPING REAL ──
    scrape = scrape_url(url)

    if scrape['ok']:
        contexto_web = f"""
DATOS REALES EXTRAÍDOS DE LA URL {url}:
- Título de la página: {scrape['titulo']}
- Meta descripción: {scrape['meta_descripcion'] or 'No tiene'}
- Meta keywords: {scrape['meta_keywords'] or 'No tiene'}
- OG Title: {scrape['og_title'] or 'No tiene'}
- OG Description: {scrape['og_descripcion'] or 'No tiene'}
- H1 encontrados: {scrape['h1'] or 'Ninguno'}
- H2 encontrados: {scrape['h2'] or 'Ninguno'}
- Total links: {scrape['total_links']} ({scrape['links_internos']} internos, {scrape['links_externos']} externos)
- Imágenes: {scrape['total_imagenes']} ({scrape['imagenes_sin_alt']} sin atributo alt)
- Redes sociales vinculadas: {scrape['redes_sociales_detectadas'] or 'Ninguna detectada'}
- WhatsApp en la web: {'Sí' if scrape['tiene_whatsapp'] else 'No'}
- Teléfono en la web: {'Sí' if scrape['tiene_tel'] else 'No'}
- Email de contacto: {'Sí' if scrape['tiene_email'] else 'No'}
- HTTPS: {'Sí' if scrape['es_https'] else 'NO — problema de seguridad'}
- Tamaño de página: {scrape['tamano_pagina_kb']} KB
- Muestra de contenido visible: {scrape['texto_visible_muestra']}
"""
    else:
        contexto_web = f"""
ADVERTENCIA: No fue posible acceder a la URL para hacer scraping.
Motivo: {scrape['razon']}
Instrucción: Basa el análisis web en lo que puedas inferir del nombre de la empresa y sector.
Indica explícitamente en el campo 'hallazgo' del pilar WEB que no se pudo acceder al sitio
y por qué, para que el cliente sepa que el análisis de ese pilar es inferido, no medido.
"""

    prompt_base = data.get('prompt', '')
    prompt_final = f"{contexto_web}\n\n{prompt_base}"

    try:
        client = anthropic.Anthropic(api_key=API_KEY)
        msg = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=5000,
            messages=[{'role': 'user', 'content': prompt_final}]
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        resultado = json.loads(raw)

        # Fijar scores del cliente en competidores[2]
        p = resultado.get('pilares', [])
        comps = resultado.get('competidores', [])
        if len(comps) >= 3 and len(p) >= 3:
            comps[2]['scores'] = {
                'web':   p[0].get('score', 50),
                'redes': p[1].get('score', 50),
                'seo':   p[2].get('score', 50),
            }

        return jsonify(resultado)

    except json.JSONDecodeError as e:
        return jsonify({'error': f'Error de parsing JSON: {e}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf', methods=['POST'])
@limiter.limit('20 per hour')
def pdf():
    data = request.json
    if not data:
        return jsonify({'error': 'Sin datos'}), 400
    try:
        pdf_bytes = generar_pdf(data)
        empresa = data.get('empresa', 'cliente').replace(' ', '-').lower()
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'auditoria-{empresa}-360.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════
#  GENERADOR PDF NEGRO Y DORADO — ORLANDO 360™
# ═══════════════════════════════════════════════════
def generar_pdf(data):
    buf = io.BytesIO()
    W, H = A4
    ANCHO = W - 36*mm

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=14*mm, bottomMargin=14*mm,
    )

    empresa   = data.get('empresa', 'Cliente')
    sector    = data.get('sector', '')
    url       = data.get('url', '')
    sg        = data.get('scoreGlobal', 0)
    resumen   = data.get('resumenEjecutivo', '')
    pilares   = data.get('pilares', [])
    comps     = data.get('competidores', [])
    infs      = data.get('influencers', [])
    alianza   = data.get('alianza', {})
    plan      = data.get('plan', {})
    fecha     = datetime.now().strftime('%d de %B de %Y')

    def p(txt, **kw):
        defaults = dict(fontName='Helvetica', fontSize=9, textColor=TEXTO,
                        leading=14, spaceAfter=0, spaceBefore=0, alignment=TA_LEFT)
        defaults.update(kw)
        return Paragraph(txt, ParagraphStyle('x', **defaults))

    def barra(score, w, color, h=4):
        d = Drawing(w, h+2)
        d.add(Rect(0, 0, w, h, fillColor=GRIS2, strokeColor=None))
        d.add(Rect(0, 0, max(2, score/100*w), h, fillColor=color, strokeColor=None))
        return d

    def seccion(titulo):
        t = Table(
            [[p(f'  {titulo}', fontName='Helvetica-Bold', fontSize=7,
               textColor=NEGRO, leading=9)]],
            colWidths=[ANCHO], rowHeights=[6*mm]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),DORADO),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        return t

    story = []

    # ── BARRA SUPERIOR ──
    top = Table([[p('  ORLANDO IGUARÁN 360™  ·  AUDITORÍA DE MARKETING DIGITAL  ·  MÉTODO 360™',
                    fontName='Helvetica-Bold', fontSize=6, textColor=NEGRO, leading=8)]],
                colWidths=[ANCHO], rowHeights=[5.5*mm])
    top.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),DORADO),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(top)
    story.append(Spacer(1, 6*mm))

    # ── PORTADA ──
    col_sc = sc(sg)
    portada = Table([
        [p(f'REPORTE DE AUDITORÍA IA', fontSize=7, textColor=GRIS, letterSpacing=2),
         p(f'{sg}', fontName='Helvetica-Bold', fontSize=56, textColor=col_sc, leading=56, alignment=TA_RIGHT)],
        [p(empresa, fontName='Helvetica-Bold', fontSize=22, textColor=BLANCO, leading=26),
         p(f'/100  ·  {sn(sg)}', fontSize=9, textColor=col_sc, alignment=TA_RIGHT)],
        [p(url, fontName='Courier', fontSize=9, textColor=GRIS),
         p(sector, fontSize=9, textColor=GRIS, alignment=TA_RIGHT)],
        [p(f'Generado el {fecha}', fontSize=7, textColor=GRIS2), ''],
    ], colWidths=[ANCHO*0.65, ANCHO*0.35])
    portada.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),NEGRO2),
        ('TOPPADDING',(0,0),(-1,-1),3),
        ('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(0,-1),14),
        ('RIGHTPADDING',(-1,0),(-1,-1),14),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(portada)
    story.append(Spacer(1, 5*mm))

    story.append(HRFlowable(width='100%', thickness=1.5, color=DORADO2, spaceAfter=4*mm))

    if resumen:
        r = Table([[p(resumen, fontSize=9, textColor=TEXTO2, leading=16)]],
                  colWidths=[ANCHO])
        r.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),NEGRO3),
            ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),
            ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
            ('LINEBEFORE',(0,0),(0,-1),3,DORADO2),
        ]))
        story.append(r)
        story.append(Spacer(1, 7*mm))

    # ── PILARES ──
    story.append(seccion('ANÁLISIS POR PILAR'))
    story.append(Spacer(1, 3*mm))

    for p_ in pilares:
        ps = p_.get('score', 0)
        col = semaforo_color(p_.get('semaforo','amarillo'))
        sem_txt = {'verde':'● SÓLIDO','amarillo':'● EN TRABAJO','rojo':'● CRÍTICO'}.get(p_.get('semaforo','amarillo'),'—')

        rows = [
            [p(p_['nombre'].upper(), fontName='Helvetica-Bold', fontSize=8, textColor=BLANCO),
             p(sem_txt, fontSize=7, textColor=col, alignment=TA_RIGHT),
             p(str(ps), fontName='Helvetica-Bold', fontSize=18, textColor=col, alignment=TA_RIGHT)],
            [barra(ps, ANCHO*0.65-20, col), '', ''],
            [p(p_.get('hallazgo',''), fontSize=8, textColor=TEXTO2, leading=13), '', ''],
            [p(f'→  {p_.get("accion","")}', fontSize=8, textColor=col, leading=13), '', ''],
        ]
        tbl = Table(rows, colWidths=[ANCHO*0.65, ANCHO*0.17, ANCHO*0.18])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),NEGRO2),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('LEFTPADDING',(0,0),(0,-1),12),('RIGHTPADDING',(-1,0),(-1,-1),12),
            ('SPAN',(0,1),(2,1)),('SPAN',(0,2),(2,2)),('SPAN',(0,3),(2,3)),
            ('LINEABOVE',(0,0),(-1,0),0.5,GRIS2),
            ('VALIGN',(0,0),(-1,0),'MIDDLE'),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 5*mm))

    # ── COMPETENCIA ──
    story.append(seccion('BENCHMARKING COMPETITIVO'))
    story.append(Spacer(1, 3*mm))

    if comps:
        header = [[
            p('EMPRESA', fontName='Helvetica-Bold', fontSize=6, textColor=GRIS),
            p('TIPO', fontName='Helvetica-Bold', fontSize=6, textColor=GRIS),
            p('WEB', fontName='Helvetica-Bold', fontSize=6, textColor=GRIS, alignment=TA_CENTER),
            p('REDES', fontName='Helvetica-Bold', fontSize=6, textColor=GRIS, alignment=TA_CENTER),
            p('SEO', fontName='Helvetica-Bold', fontSize=6, textColor=GRIS, alignment=TA_CENTER),
        ]]
        filas = []
        for i, c in enumerate(comps):
            sc_ = c.get('scores', {})
            es_cliente = i == 2
            nombre_txt = c.get('nombre','') + (' ← CLIENTE' if es_cliente else '')
            fila = [
                p(nombre_txt, fontName='Helvetica-Bold' if es_cliente else 'Helvetica',
                  fontSize=8, textColor=DORADO if es_cliente else BLANCO),
                p(c.get('tipo',''), fontSize=7, textColor=GRIS),
            ]
            for k in ['web','redes','seo']:
                v = sc_.get(k, 0)
                fila.append(p(str(v), fontName='Helvetica-Bold', fontSize=11,
                              textColor=sc(v), alignment=TA_CENTER))
            filas.append(fila)

        all_rows = header + filas
        cw = [ANCHO*0.32, ANCHO*0.23, ANCHO*0.15, ANCHO*0.15, ANCHO*0.15]
        ct = Table(all_rows, colWidths=cw)
        ct_style = [
            ('BACKGROUND',(0,0),(-1,0),GRIS2),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('LEFTPADDING',(0,0),(-1,-1),8),
            ('LINEBELOW',(0,0),(-1,-1),0.5,GRIS2),
        ]
        for i,_ in enumerate(comps):
            bg = NEGRO3 if i==2 else NEGRO2
            ct_style.append(('BACKGROUND',(0,i+1),(-1,i+1),bg))
            if i==2:
                ct_style.append(('LINEABOVE',(0,i+1),(-1,i+1),1,DORADO2))
                ct_style.append(('LINEBELOW',(0,i+1),(-1,i+1),1,DORADO2))
        ct.setStyle(TableStyle(ct_style))
        story.append(ct)

    story.append(Spacer(1, 7*mm))

    # ── INFLUENCERS ──
    story.append(seccion('INFLUENCERS RECOMENDADOS'))
    story.append(Spacer(1, 3*mm))

    if infs:
        inf_rows = [infs[i:i+3] for i in range(0,len(infs),3)]
        for row in inf_rows:
            celdas = []
            for inf in row:
                celda = Table([
                    [p(inf.get('tipo',''), fontSize=6, textColor=DORADO, fontName='Helvetica-Bold', letterSpacing=1)],
                    [p(inf.get('nombre',''), fontName='Helvetica-Bold', fontSize=9, textColor=BLANCO)],
                    [p(inf.get('handle',''), fontName='Courier', fontSize=8, textColor=DORADO)],
                    [p(f"Seg: {inf.get('seguidores','—')}  ·  Eng: {inf.get('engagement','—')}", fontSize=7, textColor=GRIS)],
                    [p(inf.get('fit',''), fontSize=7, textColor=TEXTO2, leading=11)],
                    [p(f"Costo: {inf.get('costoEstimado','—')}", fontSize=7, textColor=VERDE)],
                ], colWidths=[ANCHO/3 - 6*mm])
                celda.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),NEGRO2),
                    ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                    ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
                    ('LINEABOVE',(0,0),(-1,0),2,DORADO2),
                ]))
                celdas.append(celda)
            while len(celdas)<3: celdas.append('')
            rt = Table([celdas], colWidths=[ANCHO/3]*3)
            rt.setStyle(TableStyle([
                ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),4*mm),
            ]))
            story.append(rt)
            story.append(Spacer(1,2*mm))

    story.append(Spacer(1, 5*mm))

    # ── ALIANZAS ──
    story.append(seccion('ALIANZAS ESTRATÉGICAS · MÉTODO 360™'))
    story.append(Spacer(1, 3*mm))

    if alianza:
        at = Table([
            [p('TIPO:', fontSize=6, textColor=GRIS)],
            [p(alianza.get('tipoRecomendado',''), fontName='Helvetica-Bold', fontSize=8, textColor=DORADO)],
            [Spacer(1,3)],
            [p(alianza.get('descripcion',''), fontSize=8, textColor=TEXTO2, leading=13)],
            [Spacer(1,3)],
            [p('BENEFICIOS', fontSize=6, textColor=GRIS, fontName='Helvetica-Bold')],
            [p('  ·  '.join(['✓ '+b for b in alianza.get('beneficios',[])]), fontSize=7, textColor=DORADO, leading=13)],
            [Spacer(1,3)],
            [p('📞  Contactar a Orlando: wa.link/33ogyz', fontName='Helvetica-Bold', fontSize=8, textColor=DORADO)],
        ], colWidths=[ANCHO])
        at.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),NEGRO2),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),
            ('LINEBEFORE',(0,0),(0,-1),3,DORADO),
        ]))
        story.append(at)

        casos = alianza.get('casosExito', [])
        if casos:
            story.append(Spacer(1,3*mm))
            caso_celdas = []
            for c in casos[:2]:
                cc = Table([
                    [p(c.get('marca',''), fontName='Helvetica-Bold', fontSize=8, textColor=BLANCO)],
                    [p('📈 '+c.get('resultado',''), fontSize=7, textColor=VERDE)],
                    [p(c.get('descripcion',''), fontSize=7, textColor=TEXTO2, leading=11)],
                ], colWidths=[ANCHO/2 - 5*mm])
                cc.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),NEGRO3),
                    ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                    ('LEFTPADDING',(0,0),(-1,-1),10),
                    ('LINEABOVE',(0,0),(-1,0),1,GRIS2),
                ]))
                caso_celdas.append(cc)
            while len(caso_celdas)<2: caso_celdas.append('')
            ct2 = Table([caso_celdas], colWidths=[ANCHO/2]*2)
            ct2.setStyle(TableStyle([
                ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),4*mm),
            ]))
            story.append(ct2)

    story.append(Spacer(1, 7*mm))

    # ── PLAN DE ACCIÓN ──
    story.append(seccion('PLAN DE ACCIÓN PRIORITARIO'))
    story.append(Spacer(1, 3*mm))

    fases = [
        ('01', 'QUICK WINS', 'Esta semana', plan.get('semana1',[]), DORADO),
        ('02', 'MEDIO PLAZO', '1 — 3 meses', plan.get('mes1a3',[]), NARANJA),
        ('03', 'ESTRATÉGICO', '3 — 6 meses', plan.get('mes3a6',[]), VERDE),
    ]
    fase_celdas = []
    for num, titulo, periodo, items, col in fases:
        items_p = [p(f'→  {item}', fontSize=7, textColor=TEXTO2, leading=12) for item in items]
        contenido = [
            [p(num, fontName='Helvetica-Bold', fontSize=20, textColor=NEGRO, leading=22, alignment=TA_CENTER)],
            [p(titulo, fontName='Helvetica-Bold', fontSize=7, textColor=NEGRO, leading=9, alignment=TA_CENTER)],
            [p(periodo, fontSize=6, textColor=NEGRO, leading=8, alignment=TA_CENTER)],
            [Spacer(1,3)],
        ] + [[ip] for ip in items_p]

        ft = Table(contenido, colWidths=[ANCHO/3 - 5*mm])
        ft.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,2),col),
            ('BACKGROUND',(0,3),(-1,-1),NEGRO2),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('LINEBELOW',(0,2),(-1,2),2,NEGRO3),
        ]))
        fase_celdas.append(ft)

    plan_t = Table([fase_celdas], colWidths=[ANCHO/3]*3)
    plan_t.setStyle(TableStyle([
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),3*mm),
    ]))
    story.append(plan_t)
    story.append(Spacer(1, 8*mm))

    # ── FOOTER ──
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRIS2, spaceAfter=4*mm))
    ft = Table([[
        p('Orlando Iguarán 360™  ·  Método 360™  ·  Diagnóstico Real  ·  Estrategia Real  ·  Resultados Reales',
          fontSize=6, textColor=GRIS2),
        p(f'Generado: {fecha}  ·  orlandoiguaran360.com', fontSize=6, textColor=GRIS2, alignment=TA_RIGHT),
    ]], colWidths=[ANCHO*0.65, ANCHO*0.35])
    ft.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(ft)

    doc.build(story)
    return buf.getvalue()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7360))
    app.run(host='0.0.0.0', port=port, debug=False)
