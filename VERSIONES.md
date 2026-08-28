# Evaluador Resolución 3280 – DUSAKAWI EPSI
## Registro de Versiones

---

### v1.0 — Agosto 2026 *(versión actual)*
**Archivos:** `versiones/v1.0/evaluador_3280.py` + `versiones/v1.0/res3280_standard.json`

**Funcionalidades:**
- Lee automáticamente la Herramienta de Seguimiento xlsx (hoja "A3 COMPLETO")
- Extrae totales por programa: Primera Infancia, Infancia, Adolescencia, Jóvenes, Adultez, Vejez, PAI, Materno Perinatal, Posparto, Demanda Inducida, RCV
- PAI se lee desde la hoja "LMA" (VACUNACION)
- Demanda Inducida: descuento = $0 (regla contractual)
- GUI tkinter: 3 pestañas (Herramienta & Datos, Programas, Generar Acta)
- Tabla editable (doble clic) con semáforo de cumplimiento
- Genera acta Excel con gráfica de barras, textos legales y bloques de firma
- Estándar Res. 3280 en JSON (`res3280_standard.json`)

**Programas evaluados:**
| ID | Nombre en Acta |
|----|----------------|
| PRIMERA_INFANCIA | Individuales para Niños y Niñas en Primera Infancia 1M - 5A |
| INFANCIA | Individuales para Niños y Niñas en Infancia 6 - 11 Años |
| ADOLESCENCIA | Individuales para los Adolescentes 12 - 17 Años |
| JOVENES | Individuales para los Jóvenes 18 - 28 Años |
| ADULTEZ | Individuales para los Adultos 29 - 59 Años |
| VEJEZ | Individuales para los Adultos Mayores 60 a 80 y Más |
| PAI | PAI (Vacunación - sin descuento) |
| MATERNO_PERINATAL | Materno Perinatal |
| POSPARTO | Atención Posparto |
| DEMANDA_INDUCIDA | Demanda Inducida (sin descuento) |
| RCV | Ruta Riesgo Cardiovascular Baja |

---

## Cómo restaurar o usar una versión

Para volver a v1.0:
```
cp versiones/v1.0/evaluador_3280.py ./evaluador_3280.py
cp versiones/v1.0/res3280_standard.json ./res3280_standard.json
```

## Cómo correr la app

```
python3 evaluador_3280.py
```

Requiere: `pip install openpyxl`
