import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createPlan,
  uploadRecipesStream,
  getIngredientsWithSkus,
  getRecipes,
  getLocation,
} from "./api.js";
import { logger } from "./logger.js";
import { AuroraBackground } from "./components/AuroraBackground.jsx";
import { ProgressBar } from "./components/ProgressBar.jsx";
import { IngredientCard } from "./components/IngredientCard.jsx";
import { RecipeCard } from "./components/RecipeCard.jsx";
import { cn } from "./lib/utils.js";

const uiLogger = logger.child("ui");

export default function App() {
  const [files, setFiles] = useState([]);
  const [targetServings, setTargetServings] = useState(10);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);
  const [ingredients, setIngredients] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [ingredientsProgress, setIngredientsProgress] = useState({
    added: 0,
    total: 1,
  });
  const [pricingProgress, setPricingProgress] = useState({
    withSkus: 0,
    total: 1,
  });
  const [streamComplete, setStreamComplete] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [location, setLocation] = useState({ postal_code: null, in_us: true, error: null });
  const [lpOptions, setLpOptions] = useState({
    timeLimitSeconds: 10,
    batchPenalty: 0.0001,
  });
  const [showLpOptions, setShowLpOptions] = useState(false);
  const [mealConfig, setMealConfig] = useState({ appetizer: 0, entree: 1, dessert: 0, side: 0 });
  const [storeSlugs, setStoreSlugs] = useState([]);
  const [storeFilterInput, setStoreFilterInput] = useState("");
  const [allergens, setAllergens] = useState([]);
  const [excludeAllergens, setExcludeAllergens] = useState([]);

  const fetchLocation = useCallback(async () => {
    try {
      const data = await getLocation();
      setLocation({
        postal_code: data.postal_code || null,
        in_us: data.in_us !== false,
        error: data.error || null,
      });
    } catch (err) {
      uiLogger.warn("location.fetch_failed", err);
      setLocation({ postal_code: "10001", in_us: false, error: "Could not detect location." });
    }
  }, []);

  const fetchIngredients = useCallback(async () => {
    try {
      const data = await getIngredientsWithSkus();
      setIngredients(data);
    } catch (err) {
      uiLogger.warn("ingredients.fetch_failed", err);
    }
  }, []);

  const fetchAllergens = useCallback(async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8008/api"}/allergens`);
      if (res.ok) {
        const data = await res.json();
        setAllergens(data.allergens || []);
      }
    } catch {
      setAllergens([]);
    }
  }, []);

  const fetchRecipes = useCallback(async () => {
    try {
      const data = await getRecipes(excludeAllergens);
      setRecipes(data);
    } catch (err) {
      uiLogger.warn("recipes.fetch_failed", err);
    }
  }, [excludeAllergens]);

  useEffect(() => {
    fetchLocation();
  }, [fetchLocation]);

  useEffect(() => {
    fetchAllergens();
  }, [fetchAllergens]);

  useEffect(() => {
    fetchIngredients();
    fetchRecipes();
  }, [fetchIngredients, fetchRecipes]);


  const handleUpload = async () => {
    setError(null);
    setPlanResult(null);
    setIsUploading(true);
    setStreamComplete(false);
    setIngredientsProgress({ added: 0, total: 1 });
    setPricingProgress({ withSkus: 0, total: 1 });

    try {
      uiLogger.info("upload.click");
      await uploadRecipesStream(files, (event, data) => {
        if (event === "ingredient_added") {
          setIngredientsProgress({
            added: data.ingredients_added ?? 0,
            total: Math.max(data.ingredients_total ?? 1, data.ingredients_added ?? 1),
          });
        } else if (event === "upload_complete") {
          setIngredientsProgress({
            added: data.ingredients_created ?? 0,
            total: Math.max(data.ingredients_created ?? 1, 1),
          });
          setPricingProgress({
            withSkus: 0,
            total: data.ingredients_created ?? 1,
          });
        } else if (event === "sku_progress") {
          setPricingProgress({
            withSkus: data.ingredients_with_skus ?? 0,
            total: Math.max(data.ingredients_total ?? 1, 1),
          });
        } else if (event === "stream_complete") {
          setStreamComplete(true);
          fetchIngredients();
          fetchRecipes();
        }
      }, location.postal_code);
    } catch (err) {
      uiLogger.error("upload.failed", err);
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handlePlan = async () => {
    setError(null);
    try {
      uiLogger.info("plan.click", { targetServings });
      const result = await createPlan(Number(targetServings), location.postal_code, {
        ...lpOptions,
        mealConfig: Object.fromEntries(
          Object.entries(mealConfig).filter(([, v]) => v != null && v > 0)
        ),
        storeSlugs: storeSlugs.length ? storeSlugs : undefined,
        excludeAllergens: excludeAllergens.length ? excludeAllergens : undefined,
      });
      setPlanResult(result);
    } catch (err) {
      uiLogger.error("plan.failed", err);
      setError(err.message);
    }
  };

  const pricingDone = pricingProgress.total > 0 && pricingProgress.withSkus >= pricingProgress.total;
  const showProgressBars = isUploading || (!pricingDone && (ingredientsProgress.added > 0 || pricingProgress.withSkus > 0));

  return (
    <AuroraBackground className="min-h-screen">
      <div className="relative z-10 mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {location.error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-xl border border-amber-500/50 bg-amber-950/30 px-4 py-3 text-amber-400 text-sm"
          >
            {location.error}
            {location.postal_code && (
              <span className="ml-2 text-amber-500/80">
                (Using zip {location.postal_code})
              </span>
            )}
          </motion.div>
        )}

        <header className="mb-10 text-center">
          <motion.h1
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl font-bold tracking-tight text-zinc-50 sm:text-5xl bg-clip-text text-transparent bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400"
          >
            Tandem Recipe Planner
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="mt-2 text-zinc-400"
          >
            Upload recipes, then generate a meal plan.
          </motion.p>
        </header>

        <div className="space-y-6">
          {/* Upload section */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="rounded-2xl border border-zinc-700/50 bg-zinc-900/40 p-6 backdrop-blur-sm"
          >
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Upload Recipes</h2>
            <div className="flex flex-col sm:flex-row gap-4 items-start">
              <label
                className={cn(
                  "flex-1 w-full cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors",
                  isDragging
                    ? "border-violet-500 bg-violet-500/10 text-violet-300"
                    : "border-zinc-600 text-zinc-400 hover:border-violet-500/50 hover:bg-zinc-800/30 hover:text-zinc-300"
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsDragging(false);
                  const transfer = e.dataTransfer?.files;
                  if (!transfer?.length) return;
                  const dropped = Array.from(transfer).filter(
                    (f) => f.name?.toLowerCase().endsWith(".txt") || f.name?.toLowerCase().endsWith(".zip")
                  );
                  if (dropped.length) {
                    setFiles((prev) => (Array.isArray(prev) && prev.length ? [...prev, ...dropped] : dropped));
                    uiLogger.info("files.dropped", { count: dropped.length });
                  }
                }}
              >
                <input
                  type="file"
                  multiple
                  accept=".txt,.zip"
                  className="hidden"
                  onChange={(e) => {
                    const chosen = e.target.files || [];
                    setFiles(Array.from(chosen));
                    uiLogger.info("files.selected", { count: chosen.length });
                  }}
                />
                {files.length
                  ? `${files.length} file(s) selected`
                  : "Drag & drop .txt or .zip files, or click to browse"}
              </label>
              <button
                onClick={handleUpload}
                disabled={!files.length || isUploading}
                className={cn(
                  "shrink-0 rounded-xl px-6 py-3 font-medium transition-all duration-200",
                  files.length && !isUploading
                    ? "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white hover:from-violet-500 hover:to-fuchsia-500"
                    : "bg-zinc-700 text-zinc-500 cursor-not-allowed"
                )}
              >
                {isUploading ? "Uploading…" : "Upload"}
              </button>
            </div>

            <AnimatePresence>
              {(showProgressBars || isUploading) && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-6 space-y-4 overflow-hidden"
                >
                  <ProgressBar
                    value={ingredientsProgress.added}
                    max={ingredientsProgress.total}
                    label="Ingredients added"
                  />
                  <ProgressBar
                    value={pricingProgress.withSkus}
                    max={pricingProgress.total}
                    label="Pricings initialized"
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>

          {/* Recipes */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18 }}
            className="rounded-2xl border border-zinc-700/50 bg-zinc-900/40 p-6 backdrop-blur-sm"
          >
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="text-lg font-semibold text-zinc-100">Recipes</h2>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-zinc-500">Exclude:</span>
                {allergens.slice(0, 8).map((a) => (
                  <button
                    key={a}
                    onClick={() =>
                      setExcludeAllergens((arr) =>
                        arr.includes(a) ? arr.filter((x) => x !== a) : [...arr, a]
                      )
                    }
                    className={cn(
                      "rounded px-2 py-0.5 text-xs capitalize transition-colors",
                      excludeAllergens.includes(a)
                        ? "bg-amber-500/30 text-amber-300"
                        : "bg-zinc-700 text-zinc-400 hover:bg-zinc-600"
                    )}
                  >
                    {a.replace(/_/g, " ")}
                  </button>
                ))}
                <button
                  onClick={fetchRecipes}
                  className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
                >
                  Refresh
                </button>
              </div>
            </div>
            {recipes.length === 0 ? (
              <p className="text-zinc-500 py-8 text-center">
                No recipes yet. Upload recipe files to get started.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {recipes.map((rec, i) => (
                  <RecipeCard key={rec.id} recipe={rec} index={i} />
                ))}
              </div>
            )}
          </motion.section>

          {/* Ingredients & SKUs */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-zinc-700/50 bg-zinc-900/40 p-6 backdrop-blur-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-zinc-100">Ingredients & SKUs</h2>
              <button
                onClick={fetchIngredients}
                className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
              >
                Refresh
              </button>
            </div>
            {ingredients.length === 0 ? (
              <p className="text-zinc-500 py-8 text-center">
                No ingredients yet. Upload recipes to get started.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {ingredients.map((ing, i) => (
                  <IngredientCard key={ing.id} ingredient={ing} index={i} />
                ))}
              </div>
            )}
          </motion.section>

          {/* Plan section */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="rounded-2xl border border-zinc-700/50 bg-zinc-900/40 p-6 backdrop-blur-sm"
          >
            <h2 className="text-lg font-semibold text-zinc-100 mb-4">Create Plan</h2>
            <div className="flex flex-col gap-4">
              {/* Meal type config */}
              <div className="flex flex-wrap gap-4 items-center">
                <span className="text-sm text-zinc-400">Meal types (min each):</span>
                {["appetizer", "entree", "dessert", "side"].map((type) => {
                  const count = recipes.filter((r) => (r.meal_type || "entree") === type).length;
                  const disabled = count === 0;
                  return (
                    <label
                      key={type}
                      className={cn(
                        "flex items-center gap-2",
                        disabled && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      <span className="text-sm capitalize">{type}</span>
                      <input
                        type="number"
                        min="0"
                        value={mealConfig[type] ?? 0}
                        onChange={(e) =>
                          setMealConfig((m) => ({ ...m, [type]: parseInt(e.target.value, 10) || 0 }))
                        }
                        disabled={disabled}
                        className="w-14 rounded border border-zinc-600 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                      />
                      {disabled && (
                        <span className="text-xs text-zinc-500">(none)</span>
                      )}
                    </label>
                  );
                })}
              </div>

              {/* Store filter */}
              <div className="flex flex-col gap-2">
                <span className="text-sm text-zinc-400">Stores only (e.g. costco, walmart):</span>
                <div className="flex gap-2 flex-wrap">
                  {storeSlugs.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center gap-1 rounded-full bg-zinc-700 px-3 py-1 text-sm text-zinc-200"
                    >
                      {s}
                      <button
                        type="button"
                        onClick={() => setStoreSlugs((arr) => arr.filter((x) => x !== s))}
                        className="text-zinc-400 hover:text-zinc-200"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    placeholder="Add store..."
                    value={storeFilterInput}
                    onChange={(e) => setStoreFilterInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const v = storeFilterInput.trim().toLowerCase().replace(/\s+/g, "-");
                        if (v && !storeSlugs.includes(v)) {
                          setStoreSlugs((arr) => [...arr, v]);
                          setStoreFilterInput("");
                        }
                      }
                    }}
                    className="rounded border border-zinc-600 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 w-32"
                  />
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-4 items-start flex-wrap">
                <label className="flex flex-col gap-2">
                  <span className="text-sm text-zinc-400">Target servings</span>
                  <input
                    type="number"
                    min="1"
                    value={targetServings}
                    onChange={(e) => setTargetServings(e.target.value)}
                    className="rounded-lg border border-zinc-600 bg-zinc-800 px-4 py-2.5 text-zinc-100 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </label>
                <button
                  onClick={() => setShowLpOptions((v) => !v)}
                  className="text-sm text-violet-400 hover:text-violet-300 transition-colors self-end"
                >
                  {showLpOptions ? "Hide" : "Show"} LP options
                </button>
                <button
                  onClick={handlePlan}
                  className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-3 font-medium text-white transition-all hover:from-violet-500 hover:to-fuchsia-500"
                >
                  Generate Plan
                </button>
              </div>
              {showLpOptions && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="flex gap-6 flex-wrap rounded-lg border border-zinc-600/50 bg-zinc-800/30 p-4"
                >
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-zinc-500">Time limit (s)</span>
                    <input
                      type="number"
                      min="1"
                      max="300"
                      value={lpOptions.timeLimitSeconds}
                      onChange={(e) =>
                        setLpOptions((o) => ({
                          ...o,
                          timeLimitSeconds: parseInt(e.target.value, 10) || 10,
                        }))
                      }
                      className="rounded border border-zinc-600 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 w-24"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-zinc-500">Batch penalty</span>
                    <input
                      type="number"
                      min="0"
                      step="0.0001"
                      value={lpOptions.batchPenalty}
                      onChange={(e) =>
                        setLpOptions((o) => ({
                          ...o,
                          batchPenalty: parseFloat(e.target.value) || 0.0001,
                        }))
                      }
                      className="rounded border border-zinc-600 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 w-28"
                    />
                  </label>
                </motion.div>
              )}
            </div>
            {planResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 space-y-6 overflow-auto max-h-[70vh]"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 text-xs font-medium",
                        planResult.status === "Optimal"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : planResult.status === "Infeasible"
                            ? "bg-red-500/20 text-red-400"
                            : "bg-amber-500/20 text-amber-400"
                      )}
                    >
                      {planResult.status}
                    </span>
                    <span className="text-zinc-400 text-sm">
                      Total: ${planResult.objective?.toFixed(2) ?? "—"}
                    </span>
                  </div>
                  {planResult.infeasible_reason && (
                    <p className="text-sm text-amber-400">{planResult.infeasible_reason}</p>
                  )}
                </div>

                {/* Chosen recipes */}
                {planResult.recipe_details?.length > 0 && (
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <h3 className="font-semibold text-zinc-100 mb-3">Chosen recipes</h3>
                    <div className="space-y-2">
                      {planResult.recipe_details.map((r) => (
                        <div
                          key={r.recipe_id}
                          className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0"
                        >
                          <span className="text-zinc-200 font-medium">{r.name}</span>
                          <span className="text-zinc-500 text-sm">
                            {r.batches} batch{r.batches !== 1 ? "es" : ""} × {r.servings_per_batch} = {r.total_servings} servings
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Consolidated shopping list */}
                {planResult.consolidated_shopping_list?.length > 0 && (
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <h3 className="font-semibold text-zinc-100 mb-3">Consolidated shopping list</h3>
                    <ul className="space-y-1.5">
                      {planResult.consolidated_shopping_list.map((item, i) => (
                        <li key={i} className="flex gap-2 text-sm">
                          <span className="text-zinc-400 capitalize">{item.ingredient}</span>
                          <span className="text-zinc-300">
                            {item.quantity} {item.unit}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Generate Final Materials (post-plan) */}
                {planResult.menu_card?.length > 0 && (
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <h3 className="font-semibold text-zinc-100 mb-2">Final materials</h3>
                    <p className="text-sm text-zinc-500 mb-3">
                      Generate printable cards, descriptions, and PDF.
                    </p>
                    <button
                      onClick={() => {
                        // TODO: Open card editor, generate descriptions, PDF export
                        uiLogger.info("generate_materials.click");
                      }}
                      className="rounded-lg bg-violet-600/80 px-4 py-2 text-sm text-white hover:bg-violet-500"
                    >
                      Generate Final Materials
                    </button>
                  </div>
                )}

                {/* Menu card */}
                {planResult.menu_card?.length > 0 && (
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <h3 className="font-semibold text-zinc-100 mb-3">Menu card</h3>
                    <div className="space-y-4">
                      {planResult.menu_card.map((dish, i) => (
                        <div key={i} className="border-l-2 border-violet-500/50 pl-4">
                          <h4 className="font-medium text-zinc-100">{dish.name}</h4>
                          <p className="text-sm text-zinc-400 mt-1">{dish.description}</p>
                          <ul className="mt-2 text-sm text-zinc-500 space-y-0.5">
                            {dish.ingredients?.map((ing, j) => (
                              <li key={j}>• {ing}</li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* SKU purchase details */}
                {planResult.sku_details && Object.keys(planResult.sku_details).length > 0 && (
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <h3 className="font-semibold text-zinc-100 mb-3">Items to purchase</h3>
                    <div className="space-y-2 text-sm">
                      {Object.entries(planResult.sku_details).map(([id, detail]) => (
                        <div
                          key={id}
                          className="flex justify-between gap-4 py-2 border-b border-zinc-800 last:border-0"
                        >
                          <div>
                            <span className="text-zinc-200">{detail.name}</span>
                            {detail.brand && (
                              <span className="text-zinc-500 ml-1">({detail.brand})</span>
                            )}
                          </div>
                          <div className="text-right shrink-0">
                            <span className="text-emerald-400">
                              ${detail.price?.toFixed(2)}
                              {detail.size && (
                                <span className="text-zinc-500 font-normal"> / {detail.size}</span>
                              )}
                              {" × "}{detail.quantity}
                            </span>
                            {detail.retailer && (
                              <span className="text-zinc-500 block text-xs capitalize">
                                {detail.retailer.replace(/-/g, " ")}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </motion.section>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border border-red-500/50 bg-red-950/30 px-4 py-3 text-red-400"
          >
            {error}
          </motion.div>
        )}
      </div>
    </AuroraBackground>
  );
}
