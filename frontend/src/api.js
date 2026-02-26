import { logger } from "./logger.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8008/api";
const apiLogger = logger.child("api");

export async function uploadRecipes(files) {
  apiLogger.info("upload.start", { count: files.length });
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
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
 * Upload recipes and consume SSE progress stream.
 * onProgress: (event, data) => void
 * Events: ingredient_added, upload_complete, sku_progress, stream_complete
 */
export async function uploadRecipesStream(files, onProgress, postalCode) {
  apiLogger.info("upload.stream.start", { count: files.length, postalCode });
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  if (postalCode) formData.append("postal_code", postalCode);
  const response = await fetch(`${API_URL}/recipes/upload/stream`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    apiLogger.error("upload.stream.error", { status: response.status });
    throw new Error("Upload failed");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";
    for (const chunk of lines) {
      if (chunk.startsWith("event:")) {
        const [eventLine, dataLine] = chunk.split("\n");
        const event = eventLine.replace("event:", "").trim();
        const dataStr = dataLine?.replace("data:", "").trim();
        if (dataStr) {
          try {
            const data = JSON.parse(dataStr);
            onProgress?.(event, data);
          } catch (e) {
            apiLogger.warn("upload.stream.parse_error", { event, e });
          }
        }
      }
    }
  }
  apiLogger.info("upload.stream.end");
}

export async function createPlan(targetServings, postalCode, options = {}) {
  apiLogger.info("plan.start", { targetServings, postalCode, options });
  const body = { target_servings: targetServings };
  if (postalCode) body.postal_code = postalCode;
  if (options.timeLimitSeconds != null) body.time_limit_seconds = options.timeLimitSeconds;
  if (options.batchPenalty != null) body.batch_penalty = options.batchPenalty;
  if (options.mealConfig && Object.keys(options.mealConfig).length)
    body.meal_config = options.mealConfig;
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
