# Shinobi Tech Core — Seguimiento a egresados

Aplicación web Django para registrar egresados certificados, mantener su información vigente, gestionar encuestas y consultar indicadores institucionales.

## Requisitos y ejecución local

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

El portal queda disponible en `http://127.0.0.1:8000/`. El superusuario crea en Django Admin los grupos `Administrador`, `funcionario`, `egresado` y `visor`, asigna sus permisos y vincula las cuentas con los perfiles correspondientes. La aplicación no crea esos grupos automáticamente.

### Cuentas y datos ficticios para revisar pantallas

En una base de datos local o de desarrollo ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py crear_demo
```

El comando crea los cuatro grupos de acceso, una cuenta por grupo y perfiles, una encuesta, un aviso, una trayectoria y un acompañamiento ficticios. Imprime contraseñas aleatorias una sola vez; cópialas para iniciar sesión. No altera datos si detecta que ya existen las cuentas reservadas `demo_*` o los documentos `DEMO-1001`/`DEMO-1002`. Los perfiles de demostración no deben usarse en producción.

## Capacidades implementadas

- Registro individual y carga transaccional de egresados certificados desde CSV o Excel `.xlsx`.
- Consentimiento de tratamiento de datos con fecha, firma declarada, dirección IP y agente de usuario.
- Edición limitada de datos personales por el egresado, con bloqueo de los campos académicos inmutables.
- Historial laboral, académico y de emprendimiento ligado al autor.
- Encuestas con preguntas de texto, párrafo, número, selección única y múltiple; asignación por programa y centro.
- Paneles filtrables, alertas, notas de acompañamiento y exportación de indicadores a CSV, Excel y PDF.
- Inactivación lógica de perfiles y bloqueo de eliminación física desde las vistas y Django Admin.

## Actualización diaria de vigencia

El comando marca como desactualizados los perfiles activos cuya última actualización supera los 180 días:

```powershell
.\.venv\Scripts\python.exe manage.py actualizar_egresados
```

En producción debe programarse una ejecución diaria mediante el Programador de tareas de Windows o el scheduler del sistema operativo del servidor.

## Importación CSV / Excel

La primera fila debe usar estos encabezados:

`document_type, document_number, first_name, last_name, email, phone, address, municipality, program, center, certified_on, academic_status`

Son obligatorios `document_type`, `document_number`, `first_name`, `last_name`, `program`, `certified_on` y `academic_status`; la fecha usa `AAAA-MM-DD` y el estado debe ser `Certificado`. Si alguna fila es inválida o el documento ya existe, el lote completo se rechaza.

## Diseño de encuestas

Cada línea del campo de preguntas usa `pregunta | tipo | obligatorio/opcional | opción1, opción2 | negativa1, negativa2`. Los tipos disponibles son `text`, `textarea`, `number`, `radio` y `checkbox`; los dos últimos requieren opciones. Las respuestas negativas son opcionales y deben coincidir con una de las opciones, para que las alertas de seguimiento sean configurables y explícitas.

## Política de tratamiento

La carpeta `docs/` no incluye el texto íntegro ni la URL de la versión vigente de la Política de Tratamiento de Datos Personales del SENA. La pantalla de consentimiento explica el propósito del portal y advierte que debe consultarse el texto oficial; antes de producción, el administrador institucional debe incorporar allí la versión oficial aplicable y validar el aviso con el responsable de protección de datos.

## Configuración de producción

Definir `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS` antes del despliegue. En producción se habilitan cookies seguras, redirección HTTPS y almacenamiento estático con hash. Para PostgreSQL, definir `DATABASE_ENGINE=django.db.backends.postgresql`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST` y `DATABASE_PORT`; los modelos usan exclusivamente el ORM de Django.
