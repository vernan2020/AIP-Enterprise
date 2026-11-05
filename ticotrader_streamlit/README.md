# TicoTrader Atlas — piloto privado sin VPS

Entrada: `ticotrader_streamlit/app.py`. Python 3.13 en Streamlit Community Cloud.
El piloto admite hasta 20 correos explícitamente autorizados y funciona sin
registro público. No cargar datos internos de Coopealianza en este despliegue.

## Despliegue

1. En Streamlit Community Cloud, crear una aplicación desde
   `vernan2020/AIP-Enterprise`, rama `feature/ticotrader-financial-macro`.
2. Elegir `ticotrader_streamlit/app.py` y Python 3.13. Las dependencias están
   en `ticotrader_streamlit/requirements.txt`, junto a la entrada.
3. Configurar la aplicación como privada y sus correos autorizados en Sharing.
4. Crear un cliente OAuth de tipo aplicación web en Google. Registrar exactamente
   `https://NOMBRE.streamlit.app/oauth2callback` como URI de redirección.
5. Copiar `secrets.example.toml` a Settings → Secrets y sustituir los marcadores:
   cliente Google, secreto de cookie aleatorio, correos autorizados y token
   PERSONAL BCCR. Nunca guardar estos valores en el repositorio o en el chat.
6. Si Google mantiene el proyecto en Testing, registrar también allí los usuarios
   de prueba. La autorización de Atlas es una segunda restricción explícita.
7. Validar con administrador, lector y correo no autorizado antes de habilitar
   al grupo. Confirmar descargas oficiales, histórico y proyecciones con el token.

Localmente, desde la raíz del repositorio:

```sh
python -m pip install -r ticotrader_streamlit/requirements.txt
streamlit run ticotrader_streamlit/app.py
```

## Operación

- Identidad Google validada por Streamlit; Atlas exige correo verificado,
  audiencia esperada, sesión vigente y pertenencia a la lista autorizada.
- Las credenciales personales se obtienen exclusivamente de Secrets. El proceso
  de consulta no lee configuraciones institucionales para construir las fuentes.
- Una consulta en ejecución; hasta 20 pendientes, máximo 2 por usuario.
  Consultas idénticas comparten cálculo y resultados durante 15 minutos.
- Procesos aislados con máximo de 180 segundos y vigilancia de RSS de 600 MiB,
  revisada cada 100 ms. Es un umbral de cancelación, no una reserva de memoria
  ni un límite del sistema operativo. El consumo del servidor padre es adicional.
- Resultados limitados a 4 MiB por consulta, retención objetivo de 12 completados;
  la cola puede retener hasta 20 entradas mientras finaliza el trabajo acumulado.
- Forecast: TBP, FX compra/venta, TRI CRC/USD por plazo; cuatro modelos,
  12 orígenes y horizontes 1/3/6/12 meses. Se solicita solo el histórico de la
  serie elegida (hasta diez años) y se conserva en almacenamiento temporal.
- Si no hay datos suficientes, el motor informa esa condición; no fabrica valores.
- El administrador puede forzar actualización; los lectores usan consulta normal.
- Excel y JSON exportan resultados disponibles. Excel neutraliza fórmulas en
  textos provenientes de fuentes externas. Plotly permite descargar cada gráfico.

## Validación y límites

Pruebas automatizadas: autorización, aislamiento de credenciales, deduplicación
con 5/10/20 usuarios simulados, cola serial de 20 consultas distintas, cancelación
por tiempo, descarga de una sola serie con respuesta controlada y renderizado
Streamlit sin fuentes disponibles. No equivalen a carga real sobre Community Cloud.

Pendiente hasta configurar cuentas: login real Google, token BCCR personal,
calidad y latencia con fuentes oficiales y prueba de carga del alojamiento.
Las series almacenadas pueden perderse al reiniciar el alojamiento; se reconstruyen
consultando BCCR. El escenario aprobado puede permanecer no disponible porque el
piloto no importa bases ni escenarios institucionales.

Referencia de autenticación:
https://docs.streamlit.io/develop/tutorials/authentication/google
