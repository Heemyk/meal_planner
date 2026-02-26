import { logger } from "./logger.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8008/api";
const apiLogger = logger.child("api");

/**
 * Upload recipes. Returns 202 with { job_id, files } (real ingredient counts).
 * Connect to subscribeUploadStream(jobId, onProgress) for SSE events.
 */
export async function uploadRecipes(files, postalCode) {
  apiLogger.info("upload.start", { count: files.length });
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  if (postalCode) formData.append("postal_code", postalCode);
  const response = await fetch(`${API_URL}/recipes/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    apiLogger.error("upload.error", { status: response.status });
    throw new Error("Upload failed");
  }
  apiLogger.info("upload.success", { status: response.status });
  return response.json();
}

/**
 * Subscribe to SSE stream for an upload job.
 * onProgress: (event, data) => void
 * Events: upload_started, ingredient_added, upload_complete, sku_progress, stream_complete
 * Returns a promise that resolves when stream_complete is received.
 *
 * If the SSE connection drops (e.g. during LLM backoff/retry), falls back to polling
 * /progress until complete so the job is never left hanging.
 */
export function subscribeUploadStream(jobId, onProgress) {
  return new Promise((resolve) => {
    let resolved = false;
    const finish = () => {
      if (resolved) return;
      resolved = true;
      resolve();
    };

    const pollUntilComplete = async () => {
      const pollInterval = 2000;
      const maxPolls = 180; // ~6 min
      for (let i = 0; i < maxPolls; i++) {
        const progress = await getProgress(jobId);
        if (progress?.complete) {
          onProgress?.("stream_complete", { files: progress.files || [] });
          finish();
          return;
        }
        if (progress?.files?.length) {
          onProgress?.("sku_progress", { files: progress.files });
        }
        await new Promise((r) => setTimeout(r, pollInterval));
      }
      finish();
    };

    const url = `${API_URL}/recipes/upload/stream/${encodeURIComponent(jobId)}`;
    const es = new EventSource(url);
    const events = ["upload_started", "ingredient_added", "upload_complete", "sku_progress", "stream_complete"];
    const handle = (e) => {
      try {
        const data = JSON.parse(e.data || "{}");
        onProgress?.(e.type, data);
        if (e.type === "stream_complete") {
          es.close();
          finish();
        }
      } catch (err) {
        if (e.type === "stream_complete") {
          es.close();
          finish();
        }
      }
    };
    for (const ev of events) {
      es.addEventListener(ev, handle);
    }
    es.onerror = () => {
      es.close();
      // Connection dropped (e.g. timeout during backoff) — poll until complete instead of failing
      pollUntilComplete();
    };
  });
}

/**
 * Get progress for an upload job (for polling).
 * Returns { files: [{ name, ingredients_added, ingredients_total, ingredients_with_skus, sku_total }], complete }
 */
export async function getProgress(jobId) {
  const res = await fetch(`${API_URL}/progress/${jobId}`);
  if (!res.ok) return null;
  return res.json();
}


export async function createPlan(targetServings, postalCode, options = {}) {
  apiLogger.info("plan.start", { targetServings, postalCode, options });
  const body = { target_servings: targetServings };
  if (postalCode) body.postal_code = postalCode;
  if (options.timeLimitSeconds != null) body.time_limit_seconds = options.timeLimitSeconds;
  if (options.batchPenalty != null) body.batch_penalty = options.batchPenalty;
  if (options.mealConfig && Object.keys(options.mealConfig).length)
    body.meal_config = options.mealConfig;
  if (options.includeEveryRecipeIds?.length) body.include_every_recipe_ids = options.includeEveryRecipeIds;
  if (options.requiredRecipeIds?.length) body.required_recipe_ids = options.requiredRecipeIds;
  if (options.storeSlugs?.length) body.store_slugs = options.storeSlugs;
  if (options.excludeAllergens?.length) body.exclude_allergens = options.excludeAllergens;
  const response = await fetch(`${API_URL}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    apiLogger.error("plan.error", { status: response.status });
    throw new Error("Plan request failed");
  }
  apiLogger.info("plan.success", { status: response.status });
  return response.json();
}

export async function getRecipes(excludeAllergens) {
  apiLogger.info("recipes.fetch", { excludeAllergens });
  const url = new URL(`${API_URL}/recipes`);
  if (excludeAllergens?.length) url.searchParams.set("exclude_allergens", excludeAllergens.join(","));
  const response = await fetch(url);
  if (!response.ok) {
    apiLogger.error("recipes.error", { status: response.status });
    throw new Error("Failed to fetch recipes");
  }
  return response.json();
}

export async function getIngredientsWithSkus() {
  apiLogger.info("ingredients.fetch");
  const response = await fetch(`${API_URL}/ingredients-with-skus`);
  if (!response.ok) {
    apiLogger.error("ingredients.error", { status: response.status });
    throw new Error("Failed to fetch ingredients");
  }
  return response.json();
}

/**
 * Generate final materials (descriptions, card metadata) for menu_card.
 * Returns enriched menu_card with generated_description, theme.
 */
export async function generateMaterials(menuCard) {
  apiLogger.info("materials.generate", { count: menuCard?.length });
  const response = await fetch(`${API_URL}/generate-materials`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ menu_card: menuCard }),
  });
  if (!response.ok) {
    apiLogger.error("materials.error", { status: response.status });
    throw new Error("Generate materials failed");
  }
  apiLogger.info("materials.success");
  return response.json();
}

/**
 * Get available stores for store filter dropdown.
 */
export async function getStores(postalCode) {
  apiLogger.info("stores.fetch", { postalCode });
  const url = new URL(`${API_URL}/stores`);
  if (postalCode) url.searchParams.set("postal_code", postalCode);
  const response = await fetch(url);
  if (!response.ok) {
    apiLogger.error("stores.error", { status: response.status });
    return { stores: [] };
  }
  return response.json();
}

/**
 * Get location (postal code) from IP for Instacart pricing.
 * Returns { postal_code, in_us, error? }.
 * If outside US, error is set and default postal is used.
 */
export async function getLocation() {
  apiLogger.info("location.fetch");
  const response = await fetch(`${API_URL}/location`);
  if (!response.ok) {
    throw new Error("Failed to fetch location");
  }
  return response.json();
}
