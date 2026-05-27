# Propuestas de Corrección: UI, UX y Accesibilidad (WCAG)

Durante la auditoría del Dashboard en Next.js (`frontend/dashboard`), se identificaron varias oportunidades de mejora críticas, tanto a nivel de rendimiento como de accesibilidad.

### Hallazgo 1: Problema N+1 y Renderizado Bloqueante en `page.tsx`
**Problema:** La página principal (`app/page.tsx`) carga los pacientes y luego hace una iteración `for...of` con `await getLatestScore()` secuencial para cada paciente. Si un médico tiene 30 pacientes, se realizan 30 llamadas a la API de forma secuencial, bloqueando la UI con un spinner prolongado. Además, el componente es `"use client"`, por lo que el SEO y el *First Contentful Paint (FCP)* se ven afectados.
**Parche Sugerido:** 
- Usar `Promise.all()` para paralelizar las llamadas a `getLatestScore` y `getScoreHistory`.
- Lo ideal en Next.js 14 es realizar este *data-fetching* en un *Server Component* asíncrono y pasar la data inicial a un *Client Component* si se requiere interactividad (como el gráfico de Recharts).

```typescript
// En lugar de iterar secuencialmente:
// for (const p of patientList) { const s = await getLatestScore(p.id); ... }

// Usar Promise.all para disparar peticiones en paralelo:
const scoresPromises = patientList.map(p => getLatestScore(p.id).catch(() => ({ score: 0 })));
const historiesPromises = patientList.map(p => getScoreHistory(p.id, 21).catch(() => ({ scores: [] })));

const [scoresResults, historiesResults] = await Promise.all([
  Promise.all(scoresPromises),
  Promise.all(historiesPromises)
]);
```

### Hallazgo 2: Accesibilidad (WCAG) nula en `PatientCard.tsx`
**Problema:** Las tarjetas de pacientes usan `<div onClick={onClick}>` para la navegación. Esto es inaccesible mediante teclado (no recibe el foco tabular ni responde al "Enter"). Además, la barra visual de score no está etiquetada como *progressbar* para lectores de pantalla.
**Parche Sugerido:**
- Reemplazar el `<div>` contenedor por un `<button>` o un `<Link href="...">` de Next.js.
- Añadir roles ARIA a la barra de puntuación.

```tsx
// Reemplazo sugerido en PatientCard.tsx
import Link from 'next/link';

export default function PatientCard({ name, score, coaching, patientId }) {
  // ... (cálculo de colores)
  return (
    <Link
      href={`/patient?id=${patientId}`}
      className="group flex items-center gap-4 rounded-2xl border bg-white p-4..."
      aria-label={`Fiche de ${name}, score de ${score} sur 100`}
    >
      {/* ... */}
      <div 
        role="progressbar" 
        aria-valuenow={score} 
        aria-valuemin={0} 
        aria-valuemax={100}
        className={`mt-2 h-1.5 w-full rounded-full ${barBg}`}
      >
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${score}%` }} />
      </div>
      {/* ... */}
    </Link>
  );
}
```

### Hallazgo 3: Componentes de Layout renderizados en Cliente
**Problema:** `app/layout.tsx` tiene la directiva `"use client"` para manejar un estado de autenticación de Zustand global en un `useEffect`. Al ser el *RootLayout* un componente de cliente, deshabilita la exportación nativa de `metadata` y fuerza a toda la aplicación a renderizarse en el lado del cliente (CSR), mitigando los beneficios de SSR de Next.js.
**Recomendación:** Mover la protección de rutas al **Middleware** (`middleware.ts`) para redireccionar `/` a `/login` si no hay cookie/token, permitiendo que `layout.tsx` sea un Server Component.
