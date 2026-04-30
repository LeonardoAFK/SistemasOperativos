# Laboratorio de concurrencia con contenedores

Proyecto base usando:

- Python
- PostgreSQL
- Docker Compose
- 5 workers concurrentes
- Locks transaccionales en base de datos
- Lock de archivo con `fcntl.flock`
- Volumen compartido entre contenedores

## Arquitectura

```txt
PostgreSQL
   ↑
worker-1
worker-2
worker-3
worker-4
worker-5
   ↓
shared volume: /shared/worker-log.txt
```

Cada worker:

1. Busca un registro `pending` en la tabla `input`.
2. Lo bloquea con `FOR UPDATE SKIP LOCKED`.
3. Lo marca como `in_process`.
4. Procesa el dato.
5. Inserta el resultado en la tabla común `result`.
6. Marca el dato como `processed`.
7. Escribe logs en un archivo compartido usando `flock`.

## Levantar el proyecto

Desde la carpeta raíz:

```bash
docker compose up --build --scale worker=5
```

## Ver contenedores

```bash
docker compose ps
```

## Ver logs de workers

```bash
docker compose logs -f worker
```

## Consultar resultados en PostgreSQL

En PowerShell:

```powershell
Get-Content .\scripts\check-results.sql | docker compose exec -T postgres psql -U lab_user -d concurrency_lab
```

En Git Bash, WSL o Linux:

```bash
docker compose exec -T postgres psql -U lab_user -d concurrency_lab < scripts/check-results.sql
```

## Ver archivo compartido

```bash
docker compose --profile tools run --rm logs-reader
```

## Reiniciar completamente el laboratorio

Esto borra la base de datos y el volumen compartido:

```bash
docker compose down -v
docker compose up --build --scale worker=5
```

## Evidencias sugeridas

Tomar capturas de:

1. `docker compose ps`
2. `docker compose logs -f worker`
3. Consulta de conteo de resultados.
4. Consulta de duplicados, que debería salir vacía.
5. Consulta agrupada por worker.
6. Archivo compartido `/shared/worker-log.txt`.

## Mecanismos de concurrencia usados

### Base de datos

Se usa:

```sql
SELECT id, description
FROM input
WHERE status = 'pending'
ORDER BY id
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

Esto evita que dos contenedores procesen el mismo registro.

### Archivo compartido

Se usa:

```python
fcntl.flock(file, fcntl.LOCK_EX)
```

Esto evita que dos workers escriban al mismo tiempo sobre el archivo compartido.

## Autoincremental

PostgreSQL maneja los IDs automáticamente usando `SERIAL`:

```sql
id SERIAL PRIMARY KEY
```

Los workers no calculan manualmente el último ID.
