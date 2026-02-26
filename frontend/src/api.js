import { logger } from "./logger.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8008/api";
const apiLogger = logger.child("api");

export async function uploadRecipes(files) {
  apiLogger.info("upload.start", { count: files.length });
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_URL}/recipes/upload`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    apiLogger.error("upload.error", { status: response.status });
    throw new Error("Upload failed");
  }
  apiLogger.info("upload.success", { status: response.status });
  return response.json();
}

export async function createPlan(targetServings) {
  apiLogger.info("plan.start", { targetServings });
  const response = await fetch(`${API_URL}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_servings: targetServings })
  });
  if (!response.ok) {
    apiLogger.error("plan.error", { status: response.status });
    throw new Error("Plan request failed");
  }
  apiLogger.info("plan.success", { status: response.status });
  return response.json();
}
