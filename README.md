# RAG NVIDIA — Chat Informativo de Proyectos

Aplicación RAG que utiliza los modelos del **[NVIDIA API Catalog](https://build.nvidia.com/models)** tanto para el LLM como para los embeddings, y almacenamiento vectorial en **Supabase (pgvector)**.

Backend en **FastAPI** con interfaz web para consultar, mediante **RAG (Retrieval-Augmented Generation)**, la información de proyectos. Los documentos se dividen en fragmentos, se vectorizan con un modelo de embeddings de NVIDIA y se guardan en **Supabase (pgvector)**. Cada pregunta busca los fragmentos más parecidos y un modelo de chat de NVIDIA redacta la respuesta citando sus fuentes.

La API de NVIDIA (`https://integrate.api.nvidia.com/v1`) es compatible con OpenAI, así que se usa el SDK `openai`.

## 🏗️ Cómo funciona

```
Archivos JSON ──► chunker ──► embeddings (NVIDIA) ──► Supabase (rag_chunks_nvidia)
                                                         │
Pregunta ──► embedding (NVIDIA) ──► match_chunks_nvidia ─┘
                                         │
                                         ▼
                          LLM (NVIDIA) ──► respuesta con citas
```

Modelos por defecto:

| Uso | Variable | Modelo |
|---|---|---|
| Chat | `NVIDIA_MODEL` | `google/gemma-4-31b-it` |
| Chat (respaldo) | `NVIDIA_FALLBACK_MODELS` | `mistralai/mistral-large-2-instruct`, `nvidia/nemotron-3-super-120b-a12b` |
| Embeddings | `NVIDIA_EMBED_MODEL` | `nvidia/nemotron-3-embed-1b` (2048 dimensiones) |

> Si el modelo principal falla o está saturado (`429`), se prueban los de respaldo en orden. Puedes usar cualquier modelo de chat de [build.nvidia.com/models](https://build.nvidia.com/models) copiando su identificador (p. ej. `nvidia/llama-3.1-nemotron-70b-instruct`).

> Los documentos se vectorizan con `input_type: passage` y las preguntas con `input_type: query`, como piden los modelos de recuperación de NVIDIA.

> El modelo de embeddings debe ser siempre el mismo con el que se cargaron los documentos. Si lo cambias, ajusta `VECTOR(n)` en `sql/init_supabase.sql` y `EMBEDDING_DIMENSIONS` en `.env`, y vuelve a ejecutar `/seed`.

## 📋 Requisitos

- Python 3.11 o superior
- Un proyecto **nuevo** de [Supabase](https://supabase.com)
- API key de NVIDIA: entra a [build.nvidia.com](https://build.nvidia.com), abre cualquier modelo y pulsa **Get API Key** (empieza con `nvapi-`)

## 🚀 Instalación

### 1. Crear el entorno e instalar dependencias

```powershell
cd rag-nvidia
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Crear la base en Supabase

1. Crea un proyecto en Supabase.
2. Abre **SQL Editor** → **New query**, pega `sql/init_supabase.sql` y pulsa **Run**.

Esto crea pgvector, la tabla `rag_chunks_nvidia` con `VECTOR(2048)`, las funciones `match_chunks_nvidia` y `get_chunk_stats_nvidia`, índices y políticas RLS.

El script no toca otras tablas, así que también puede ejecutarse en una base que ya tenga la tabla `rag_chunks` de un modelo de embeddings anterior: esa tabla queda intacta y la aplicación usa la nueva. Los nombres se configuran con `RAG_TABLE`, `RAG_MATCH_FUNCTION` y `RAG_STATS_FUNCTION` en `.env`; para volver a la tabla anterior basta con apuntar esas variables (y el modelo de embeddings) a ella.

### 3. Configurar `.env`

Copia `.env.example` a `.env` y rellena las credenciales del proyecto de Supabase (Settings → API) y tu clave de NVIDIA:

```env
SUPABASE_URL=https://tu-proyecto-nuevo.supabase.co
SUPABASE_ANON_KEY=tu_anon_key
SUPABASE_SERVICE_ROLE_KEY=tu_service_role_key

NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=google/gemma-4-31b-it
NVIDIA_EMBED_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=2048
```

### 4. Verificar (opcional)

```powershell
.\.venv\Scripts\python.exe test_setup.py
```

### 5. Iniciar el servidor y cargar los proyectos

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8001
Invoke-RestMethod -Method Post http://localhost:8001/seed
```

Se usa el puerto 8001 por defecto (configurable según necesidades).

- **Interfaz de chat**: http://localhost:8001/chat
- **Documentación**: http://localhost:8001/docs

## 📁 Base de conocimiento

Los documentos viven en `app/data/documents/` (`.json` de proyectos y `.md`).

### Actualizar el documento de un proyecto

En la interfaz (`/chat`), selecciona un proyecto y usa:

- **📤 Actualizar documento**: sube la nueva versión del JSON del proyecto. Se guardan los fragmentos nuevos en Supabase, se eliminan los que ya no existen y se reemplaza el archivo en `app/data/documents/` (la versión anterior queda como `<proyecto>.json.bak`).
- **🔄 Reindexar archivo actual**: vuelve a indexar el archivo que ya está en el servidor (útil si lo editaste a mano).

No hace falta reiniciar el servidor. Si la API de NVIDIA falla (p. ej. límite de peticiones por minuto), no se modifica nada en Supabase ni en disco. El documento subido debe tener el mismo `baseConocimientos.proyecto.id` que el proyecto; si no, se rechaza.

También por API: `POST /projects/{slug}/document` con `{"content": { ...json del proyecto... }}`, o con `{}` para reindexar el archivo actual.

### Archivos JSON, JSONL y Markdown (.md)

Los botones de la interfaz y la API aceptan `.json`, `.jsonl` y `.md` (Markdown):

- **Archivos Markdown (.md)**: Documentos estructurados en Markdown (por ejemplo los de la carpeta `ejemplo/`). El sistema extrae automáticamente el nombre del proyecto desde el título principal (`# ...`), metadatos clave (`**Clave del Proyecto:**`, `**Área Responsable:**`, `**Objetivo General:**`, `**Beneficiarios:**`, etc.) y divide el proyecto en secciones según sus encabezados (`## `). Cada sección se vectoriza y almacena de forma independiente manteniendo el contexto y la trazabilidad.
- **Fragmentos ya preparados (JSONL)**: si cada línea tiene `contenido` (y normalmente `id`, `titulo` y `metadatos`), cada línea se indexa tal cual. Los registros se agrupan en proyectos por `metadatos.proyectoId` / `metadatos.proyecto`. En el servidor se guarda como `{"baseConocimientos": {...}, "registros": [...]}`.
- **Archivos JSON**: formato estructurado con la clave `baseConocimientos.proyecto`.

**📤 Actualizar** acepta archivos `.json`, `.jsonl` o `.md` con un único proyecto.

### Agregar o eliminar proyectos

Para agregar un proyecto nuevo, usa **＋ Añadir** en la tarjeta «Todos los proyectos» (o sube un archivo `.json`, `.jsonl` o `.md`), o copia el archivo en `app/data/documents/`, reinicia el servidor y ejecuta `POST /seed`. `/seed` no borra fragmentos; para eliminar un proyecto, usa el botón **🗑️ Borrar** en su tarjeta o por SQL en Supabase:

```sql
DELETE FROM rag_chunks_ies WHERE chunk_id LIKE 'nombre-archivo__%';
```

## 📚 API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/chat` | Interfaz web |
| GET | `/healthz` | Estado del servicio y de la conexión a Supabase |
| GET | `/projects` | Resumen de cada proyecto |
| GET | `/documents` | Documentos cargados desde `app/data/documents/` |
| POST | `/seed` | Carga los documentos en Supabase |
| POST | `/projects/{slug}/document` | Reemplaza el documento de un proyecto y sus datos en Supabase |
| POST | `/answer` | Responde una pregunta con citas |

## 🔧 Parámetros

En `app/core/config.py`:

| Parámetro | Por defecto | Descripción |
|---|---|---|
| `chunk_size` | 400 tokens | Tamaño de cada fragmento |
| `chunk_overlap` | 60 tokens | Solapamiento entre fragmentos |
| `default_top_k` | 6 | Fragmentos que recibe el LLM |
| `temperature` | 0.1 | Creatividad del LLM |
| `embed_batch_size` | 32 | Textos por petición de embeddings |
| `embed_max_tokens` | 512 | Tokens máximos por fragmento que acepta el modelo de embeddings |
| `embedding_dimensions` | 2048 | Debe coincidir con `VECTOR(n)` en Supabase |

## 🗂️ Estructura

```
rag-nvidia/
├── app/
│   ├── core/
│   │   ├── config.py        # Variables de entorno
│   │   ├── nvidia.py        # Cliente OpenAI SDK apuntando a la API de NVIDIA
│   │   └── database.py      # Supabase: inserción y búsqueda vectorial
│   ├── data/                # Documentos y su lectura
│   ├── models/              # Esquemas Pydantic
│   ├── services/
│   │   ├── chunker.py
│   │   ├── embedding.py     # Embeddings con NVIDIA
│   │   ├── chat.py          # Respuestas con NVIDIA
│   │   └── rag.py
│   └── main.py
├── static/chat.html
├── sql/init_supabase.sql   # Crea rag_chunks_nvidia y sus funciones
├── test_setup.py
├── chatbot.py
└── Dockerfile
```

## 🛠️ Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `expected 2048 dimensions` / error de dimensiones | El modelo de embeddings no coincide con `VECTOR(n)`; ajusta SQL y `EMBEDDING_DIMENSIONS`. |
| `401` / `403` de NVIDIA | `NVIDIA_API_KEY` vacía, inválida o sin acceso a ese modelo. |
| `404` de NVIDIA | El identificador del modelo no existe en el catálogo; cópialo tal cual de build.nvidia.com. |
| `429` de NVIDIA | Límite de peticiones por minuto de la cuenta gratuita; espera un minuto. |
| Responde "I don't have enough information" a todo | La tabla está vacía: ejecuta `/seed`. |
