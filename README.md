# Orlando Iguarán 360™ · Suite de Diagnóstico IA v2

## Qué incluye
- 5 agentes IA paralelos mejorados (Web, Redes, SEO, Competencia, Pauta)
- 6 pilares con semáforo rojo/amarillo/verde
- Benchmarking vs 3 competidores reales
- Recomendaciones de influencers por sector
- Sección de alianzas estratégicas Método 360™
- Plan de acción 30-60-90 días
- Reporte PDF negro y dorado con tu marca
- Dashboard con historial de todos los clientes

## Deploy en Vercel (5 minutos)

### 1. Copia estos archivos a una carpeta nueva
```
orlando360-v2/
  app.py
  requirements.txt
  vercel.json
  public/
    index.html
```

### 2. Sube a GitHub
```bash
cd orlando360-v2
git init
git add .
git commit -m "suite auditoria v2"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/orlando360-v2.git
git push -u origin main
```

### 3. Conecta Vercel
1. Ve a vercel.com → New Project
2. Importa el repo `orlando360-v2`
3. En **Environment Variables** agrega:
   - Nombre: `ANTHROPIC_API_KEY`
   - Valor: tu API key de Anthropic
4. Clic en Deploy

### 4. Listo
Tu link queda así: `https://orlando360-v2.vercel.app`

## Correr local
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
# Abre http://127.0.0.1:7360
```
