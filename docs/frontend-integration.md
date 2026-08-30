---
icon: lucide/blocks
---

# Frontend Integration

If you are wiring up the client application (React, Vue, or vanilla TS) to the HexCode API, this guide covers the architectural patterns you need. 

The backend does not serve HTML or manage UI state. It strictly consumes JSON/form-data and emits JSON.

## 1. Type Generation (Stop Hand-Writing Interfaces)

The FastAPI backend automatically maintains a live OpenAPI 3.1 specification. Do not write your TypeScript interfaces manually—they will fall out of sync when we update the database schema.

Use `openapi-typescript` to pull the schema directly from the running backend and generate strict, exhaustive TS interfaces.

```bash
# Run this whenever the backend API changes
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts
```

You can then import these definitions directly into your fetch wrappers or state managers (Redux/Zustand) to get full intellisense for payloads like `SensorEvidence` and `AnomalyReport`.

---

## 2. Dealing with Async Workers (Polling)

Endpoints like `/ingest-lidar` and `/ingest-drone` punt heavy machine learning workloads to Celery background workers. They will not return the processed geometry directly. Instead, they immediately return a `200 OK` with a `job_id`.

You must implement a polling loop on the frontend to query `/job-status/{job_id}` until the worker finishes.

Here is a robust, drop-in polling implementation using standard `fetch`:

```typescript
/**
 * Uploads a survey file and polls the Celery broker until completion.
 */
export async function uploadAndPollSurvey(
  file: File, 
  ulpinId: string,
  onProgress?: (status: string) => void
): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);

  // 1. Dispatch the payload to the async queue
  const initRes = await fetch(`http://localhost:8000/api/v1/cadastre/ingest-drone?ulpin_id=${ulpinId}`, {
    method: "POST",
    body: formData,
  });
  
  if (!initRes.ok) throw new Error("Failed to queue task on backend.");
  const { job_id, status_endpoint } = await initRes.json();

  // 2. Poll the broker state
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const statusRes = await fetch(`http://localhost:8000${status_endpoint}`);
        const task = await statusRes.json();

        if (onProgress) onProgress(task.status); // Hook for UI loading bars

        if (task.status === "COMPLETED") {
          clearInterval(interval);
          resolve(task.result); // Yields the parsed geometry and height
        } else if (task.status === "FAILED") {
          clearInterval(interval);
          reject(new Error(task.error || "Celery worker faulted."));
        }
      } catch (err) {
        clearInterval(interval);
        reject(new Error("Network error while polling broker."));
      }
    }, 1500); // 1.5s interval avoids hammering the Redis queue
  });
}
```

---

## 3. Rendering 3D Parcels (Parsing WKT)

When you hit `GET /api/v1/cadastre/parcels` to hydrate your map UI, the backend returns the 3D footprint as a `geometry_wkt` (Well-Known Text) string. It looks like this:

`POLYHEDRALSURFACE Z (((712000 3170000 0, 712050 3170000 0, ...)))`

Most modern web mapping engines (like CesiumJS, deck.gl, or Mapbox GL JS) prefer **GeoJSON** over WKT. Instead of writing custom Regex to parse the WKT, use a lightweight library like `wkx` or `terraformer-wkt-parser` to translate it on the fly:

```bash
npm install wkx

```

```typescript
import wkx from 'wkx';

export async function fetchAndParseParcels() {
  const res = await fetch("http://localhost:8000/api/v1/cadastre/parcels");
  const data = await res.json();

  return data.parcels.map(parcel => {
    // Convert WKT string to a standard GeoJSON object
    const geometry = wkx.Geometry.parse(parcel.geometry_wkt);
    const geojson = geometry.toGeoJSON();

    return {
      ...parcel,
      geojson, 
    };
  });
}
```

### A Note on Bounding Boxes

The `/parcels` endpoint also provides a `bounds` object (`x_min`, `y_max`, `z_max`, etc.). Use these coordinates to compute the spatial center of the parcel. This allows you to automatically snap or transition your 3D camera to focus on the infrastructure when a user clicks on a specific ULPIN in a sidebar list.

---

## 4. CORS Configuration

In local development, the FastAPI backend is configured to accept Cross-Origin Resource Sharing (CORS) requests from `localhost` to unblock your local dev server (e.g., Vite on `:5173` or Next.js on `:3000`).

Before deploying to production, ensure you sync with the backend team to restrict the `allow_origins` array in `main.py` strictly to your production frontend domain.
