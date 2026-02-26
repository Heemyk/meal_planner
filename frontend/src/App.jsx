import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createPlan,
  uploadRecipes,
  subscribeUploadStream,
  getIngredientsWithSkus,
  getRecipes,
  getLocation,
  generateMaterials,
  clearAllData,
} from "./api.js";
import { logger } from "./logger.js";
import { AppBackground } from "./components/AppBackground.jsx";
import { ProgressBar, SegmentedProgressBar } from "./components/ProgressBar.jsx";
import { IngredientCard } from "./components/IngredientCard.jsx";
import { RecipeCard } from "./components/RecipeCard.jsx";
import { RecipeDetailModal } from "./components/RecipeDetailModal.jsx";
import { MenuCardEditor } from "./components/MenuCardEditor.jsx";
import { cn } from "./lib/utils.js";

const uiLogger = logger.child("ui");

const MENU_THEME_STYLES = {
  appetizer: { borderColor: "hsl(36 90% 45%)", accentBg: "hsl(36 90% 55% / 0.06)" },
  entree: { borderColor: "hsl(270 70% 50%)", accentBg: "hsl(270 70% 50% / 0.06)" },
  dessert: { borderColor: "hsl(340 70% 55%)", accentBg: "hsl(340 70% 55% / 0.06)" },
  side: { borderColor: "hsl(150 60% 40%)", accentBg: "hsl(150 60% 40% / 0.06)" },
};

/** Strip rationale/extra text from unit; return canonical unit only. */
function sanitizeUnit(unit) {
  if (unit == null || typeof unit !== "string") return "";
  const s = unit.trim().toLowerCase();
  const canonical = ["g", "ml", "count", "tbsp", "tsp", "units"];
  const first = s.split(/\s|\(|,|\)/)[0]?.trim() ?? "";
  return canonical.includes(first) ? first : (first || "units");
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [targetServings, setTargetServings] = useState(10);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);
  const [ingredients, setIngredients] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [fileProgress, setFileProgress] = useState([]);
  const [progressExpanded, setProgressExpanded] = useState(false);
  const [streamComplete, setStreamComplete] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [location, setLocation] = useState({ postal_code: null, in_us: true, error: null });
  const [manualPostalCode, setManualPostalCode] = useState("");
  const [lpOptions, setLpOptions] = useState({
    timeLimitSeconds: 10,
    batchPenalty: 0.0001,
  });
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [mealConfig, setMealConfig] = useState({ appetizer: 0, entree: 1, dessert: 0, side: 0 });
  const [includeEveryRecipe, setIncludeEveryRecipe] = useState(true);
  const [requiredRecipeIds, setRequiredRecipeIds] = useState([]);
  const [storeSlugs, setStoreSlugs] = useState([]);
  const [allergens, setAllergens] = useState([]);
  const [excludeAllergens, setExcludeAllergens] = useState([]);
  const [materialsEditorOpen, setMaterialsEditorOpen] = useState(false);
  const [materialsData, setMaterialsData] = useState(null);
  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [expandedInstructions, setExpandedInstructions] = useState(-1);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [search, setSearch] = useState("");
  const [activeMealFilter, setActiveMealFilter] = useState("all");
  const [clearing, setClearing] = useState(false);

  const filteredRecipes = recipes.filter((r) => {
    const matchesSearch = !search.trim() || (r.name || "").toLowerCase().includes(search.toLowerCase());
    const matchesMeal = activeMealFilter === "all" || (r.meal_type || "entree") === activeMealFilter;
    return matchesSearch && matchesMeal;
  });

  const mealTypes = ["all", "appetizer", "entree", "dessert", "side"];

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

  // Stores from current SKUs (ingredients data) — used for store filter dropdown
  const storesFromSkus = useMemo(() => {
    const slugToName = new Map();
    ingredients.forEach((ing) => {
      ing.skus?.forEach((sku) => {
        const slug = sku.retailer_slug?.trim?.();
        if (slug && !slugToName.has(slug)) {
          slugToName.set(slug, slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
        }
      });
    });
    return [...slugToName.entries()].sort((a, b) => a[1].localeCompare(b[1])).map(([slug, name]) => ({ slug, name }));
  }, [ingredients]);

  useEffect(() => {
    fetchAllergens();
  }, [fetchAllergens]);

  useEffect(() => {
    fetchIngredients();
    fetchRecipes();
  }, [fetchIngredients, fetchRecipes]);

  // Include-every-recipe: default on for single file, off when multiple files
  useEffect(() => {
    if (fileProgress.length === 1) setIncludeEveryRecipe(true);
    else if (fileProgress.length > 1) setIncludeEveryRecipe(false);
  }, [fileProgress.length]);


  const handleUpload = async () => {
    setError(null);
    setPlanResult(null);
    setIsUploading(true);
    setStreamComplete(false);
    setFileProgress([]);
    setProgressExpanded(false);
    const postalCode = manualPostalCode.trim() || location.postal_code;

    try {
      uiLogger.info("upload.click", { count: files.length });
      const { job_id: jobId, files: filesProgress } = await uploadRecipes(files, postalCode);
      setFileProgress((filesProgress || []).map((f, i) => ({ ...f, _id: `${f.name}-${i}` })));

      await subscribeUploadStream(jobId, (event, data) => {
        if (data.files?.length && ["upload_started", "ingredient_added", "upload_complete", "sku_progress"].includes(event)) {
          setFileProgress((prev) =>
            data.files.map((f, i) => {
              const existing = prev.find((p) => p.name === f.name && (p.ingredients_total ?? 0) === (f.ingredients_total ?? 0));
              return { ...f, _id: existing?._id ?? `${f.name}-${i}` };
            })
          );
        }
        if (event === "stream_complete") {
          setStreamComplete(true);
          fetchIngredients();
          fetchRecipes();
        }
      });
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
      const singleFile = fileProgress.length === 1;
      const menuRecipeIds = singleFile && includeEveryRecipe
        ? recipes
          .filter((r) => r.source_file === fileProgress[0]?.name && !r.has_unavailable_ingredients)
          .map((r) => r.id)
        : [];
      const result = await createPlan(Number(targetServings), manualPostalCode.trim() || location.postal_code, {
        ...lpOptions,
        mealConfig: Object.fromEntries(
          Object.entries(mealConfig).filter(([, v]) => v != null && v > 0)
        ),
        includeEveryRecipeIds: menuRecipeIds.length ? menuRecipeIds : undefined,
        requiredRecipeIds: requiredRecipeIds.length ? requiredRecipeIds : undefined,
        storeSlugs: storeSlugs.length ? storeSlugs : undefined,
        excludeAllergens: excludeAllergens.length ? excludeAllergens : undefined,
      });
      setPlanResult(result);
      setMaterialsData(null);
      setExpandedInstructions(-1);
    } catch (err) {
      uiLogger.error("plan.failed", err);
      setError(err.message);
    }
  };

  const sortedFileProgress = [...fileProgress].sort((a, b) => {
    const skuTotalA = a.sku_total || a.ingredients_total || 1;
    const skuTotalB = b.sku_total || b.ingredients_total || 1;
    const pricingDoneA = (a.ingredients_with_skus ?? 0) + (a.ingredients_unavailable ?? 0) >= skuTotalA;
    const pricingDoneB = (b.ingredients_with_skus ?? 0) + (b.ingredients_unavailable ?? 0) >= skuTotalB;
    const doneA = (a.ingredients_added >= (a.ingredients_total || 1)) && pricingDoneA;
    const doneB = (b.ingredients_added >= (b.ingredients_total || 1)) && pricingDoneB;
    if (doneA && !doneB) return 1;
    if (!doneA && doneB) return -1;
    const pricingScoreA = ((a.ingredients_with_skus ?? 0) + (a.ingredients_unavailable ?? 0)) / skuTotalA;
    const pricingScoreB = ((b.ingredients_with_skus ?? 0) + (b.ingredients_unavailable ?? 0)) / skuTotalB;
    const scoreA = ((a.ingredients_added || 0) / (a.ingredients_total || 1) + pricingScoreA) / 2;
    const scoreB = ((b.ingredients_added || 0) / (b.ingredients_total || 1) + pricingScoreB) / 2;
    return scoreA - scoreB;
  });
  const allDone = fileProgress.length > 0 && fileProgress.every(
    (f) => {
      const skuTotal = f.sku_total || f.ingredients_total || 1;
      const pricingDone = (f.ingredients_with_skus ?? 0) + (f.ingredients_unavailable ?? 0) >= skuTotal;
      return (f.ingredients_added >= (f.ingredients_total || 1)) && pricingDone;
    }
  );
  const showProgressBars = isUploading || (!allDone && fileProgress.length > 0);
  const showExpandable = fileProgress.length > 2;
  const visibleFiles = showExpandable && !progressExpanded ? sortedFileProgress.slice(0, 2) : sortedFileProgress;

  return (
    <AppBackground>
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Location bar - compact */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 rounded-xl border border-border bg-card/80 backdrop-blur-sm px-4 py-3 flex flex-wrap items-center gap-4"
        >
          {location.error && (
            <span className="text-muted-foreground text-sm">{location.error}</span>
          )}
          {!location.error && location.postal_code && (
            <span className="text-sm text-muted-foreground">Location: {location.postal_code}</span>
          )}
          {!location.error && !location.postal_code && (
            <span className="text-sm text-muted-foreground">Detecting location…</span>
          )}
          <label className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Postal code</span>
            <input
              type="text"
              placeholder={location.postal_code || "e.g. 10001"}
              value={manualPostalCode}
              onChange={(e) => setManualPostalCode(e.target.value)}
              className="rounded-lg border border-input bg-secondary px-3 py-1.5 text-sm text-foreground w-28 focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </label>
          {(manualPostalCode.trim() || location.postal_code) && (
            <span className="text-muted-foreground text-sm">
              Using for SKU pricing
            </span>
          )}
          <button
            type="button"
            onClick={async () => {
              if (!window.confirm("Clear all recipes, ingredients, SKUs, and plans? This cannot be undone."))
                return;
              setClearing(true);
              try {
                await clearAllData();
                setFiles([]);
                setPlanResult(null);
                setIngredients([]);
                setRecipes([]);
                setFileProgress([]);
                setStreamComplete(false);
                setMaterialsData(null);
                setMaterialsEditorOpen(false);
                setError(null);
              } catch (err) {
                setError(err?.message || "Clear failed");
              } finally {
                setClearing(false);
              }
            }}
            disabled={clearing}
            className="ml-auto rounded-lg border border-destructive/50 px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {clearing ? "Clearing…" : "Clear All"}
          </button>
        </motion.div>

        {/* Hero */}
        <header className="mb-12 text-center">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="inline-block rounded-full px-4 py-1 text-lg text-muted-foreground mb-4"
          >
            Your Meal Planning Journey
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="font-display text-4xl font-bold tracking-tight sm:text-5xl text-gradient"
          >
            Tandem Recipe Planner
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="mt-3 text-muted-foreground text-lg max-w-xl mx-auto"
          >
            Upload recipes, optimize your shopping list, and generate meal plans.
          </motion.p>
        </header>

        <div className="space-y-6">
          {/* Upload section */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="rounded-2xl border border-border bg-card p-6"
          >
            <h2 className="font-display text-xl font-semibold text-foreground mb-4">Upload Recipes</h2>
            <div className="flex flex-col sm:flex-row gap-4 items-start">
              <label
                className={cn(
                  "flex-1 w-full cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors",
                  isDragging
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-primary/50 hover:bg-secondary/30 hover:text-foreground"
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
                  isUploading
                    ? "bg-primary text-primary-foreground glow-primary animate-pulse-glow cursor-wait"
                    : files.length
                      ? "bg-primary text-primary-foreground hover:opacity-90 glow-primary"
                      : "bg-secondary text-muted-foreground cursor-not-allowed"
                )}
              >
                {isUploading ? "Uploading…" : "Upload"}
              </button>
            </div>

            <AnimatePresence>
              {showProgressBars && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-6 space-y-4 overflow-hidden"
                >
                  <div className="space-y-4">
                    {visibleFiles.map((fp) => (
                      <motion.div
                        key={fp._id ?? `${fp.name}-${fp.ingredients_total ?? 0}`}
                        layout
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="space-y-2 rounded-lg border border-border bg-secondary/30 p-3"
                      >
                        <div className="text-sm font-medium text-foreground truncate">
                          {fp.name}
                        </div>
                        <ProgressBar
                          value={fp.ingredients_added ?? 0}
                          max={fp.ingredients_total || 1}
                          label="Ingredients"
                        />
                        <SegmentedProgressBar
                          value={fp.ingredients_with_skus ?? 0}
                          unavailable={fp.ingredients_unavailable ?? 0}
                          max={fp.sku_total || fp.ingredients_total || 1}
                          label="Pricing"
                        />
                      </motion.div>
                    ))}
                  </div>
                  {showExpandable && (
                    <button
                      type="button"
                      onClick={() => setProgressExpanded((e) => !e)}
                      className="text-sm text-primary hover:text-accent transition-colors mt-2"
                    >
                      {progressExpanded ? "Show less" : `See all (${fileProgress.length} files)`}
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>

          {/* Recipes */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18 }}
            className="rounded-2xl border border-border bg-card p-6"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <h2 className="font-display text-xl font-semibold text-foreground">Recipes</h2>
              <div className="flex flex-col sm:flex-row gap-3 flex-1 sm:justify-end">
                <input
                  type="search"
                  placeholder="Search recipes…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="rounded-lg border border-input bg-secondary px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring sm:w-56"
                />
                <button
                  onClick={fetchRecipes}
                  className="text-sm text-primary hover:text-accent transition-colors self-start sm:self-center"
                >
                  Refresh
                </button>
              </div>
            </div>
            {recipes.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-2 mb-6 scrollbar-thin">
                {mealTypes.map((type) => (
                  <button
                    key={type}
                    onClick={() => setActiveMealFilter(type)}
                    className={cn(
                      "shrink-0 rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                      activeMealFilter === type
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                    )}
                  >
                    {type === "all" ? "All" : type.charAt(0).toUpperCase() + type.slice(1)}
                  </button>
                ))}
              </div>
            )}
            {recipes.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">
                No recipes yet. Upload recipe files to get started.
              </p>
            ) : filteredRecipes.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">
                No recipes match your search or filter.
              </p>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {filteredRecipes.map((rec, i) => (
                  <RecipeCard
                    key={rec.id}
                    recipe={rec}
                    index={i}
                    onClick={() => setSelectedRecipe(rec)}
                  />
                ))}
              </div>
            )}
          </motion.section>

          {/* Ingredients & SKUs */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-border bg-card p-6"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-xl font-semibold text-foreground">Ingredients & SKUs</h2>
              <button
                onClick={fetchIngredients}
                className="text-sm text-primary hover:text-accent transition-colors"
              >
                Refresh
              </button>
            </div>
            {ingredients.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">
                No ingredients yet. Upload recipes to get started.
              </p>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
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
            className="rounded-2xl border border-border bg-card p-6"
          >
            <h2 className="font-display text-xl font-semibold text-foreground mb-6">Create Plan</h2>
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-4 items-end">
                <label className="flex flex-col gap-2">
                  <span className="text-sm text-muted-foreground">Target servings</span>
                  <input
                    type="number"
                    min="1"
                    value={targetServings}
                    onChange={(e) => setTargetServings(e.target.value)}
                    className="rounded-lg border border-input bg-secondary px-4 py-2.5 text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                <button
                  onClick={handlePlan}
                  className="rounded-xl bg-primary text-primary-foreground px-6 py-3 font-medium hover:opacity-90 glow-primary transition-opacity"
                >
                  Generate Plan
                </button>
                <button
                  type="button"
                  onClick={() => setFiltersOpen((v) => !v)}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Filters
                </button>
              </div>

              <AnimatePresence>
                {filtersOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="flex flex-col gap-4 rounded-lg border border-border bg-secondary/30 p-4"
                  >
                  <div className="flex flex-wrap gap-2 items-center">
                    <span className="text-sm text-muted-foreground">Exclude allergens:</span>
                    {allergens.slice(0, 10).map((a) => (
                      <button
                        key={a}
                        onClick={() =>
                          setExcludeAllergens((arr) =>
                            arr.includes(a) ? arr.filter((x) => x !== a) : [...arr, a]
                          )
                        }
                        className={cn(
                          "rounded-full px-3 py-1 text-xs capitalize transition-colors",
                          excludeAllergens.includes(a)
                            ? "bg-accent/30 text-accent"
                            : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                        )}
                      >
                        {a.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                  {fileProgress.length === 1 && (
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={includeEveryRecipe}
                        onChange={(e) => setIncludeEveryRecipe(e.target.checked)}
                        className="rounded border-input"
                      />
                      <span className="text-sm text-foreground">Include every recipe (each person gets 1 serving of each)</span>
                    </label>
                  )}
                  <div className="flex flex-wrap gap-4 items-center">
                    <span className="text-sm text-muted-foreground">Meal types (per person):</span>
                {["appetizer", "entree", "dessert", "side"].map((type) => {
                  const count = recipes.filter(
                    (r) =>
                      (r.meal_type || "entree") === type && !r.has_unavailable_ingredients
                  ).length;
                  const disabled = count === 0;
                  return (
                    <label
                      key={type}
                      className={cn(
                        "flex items-center gap-2",
                        disabled && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      <span className="text-sm capitalize text-foreground">{type}</span>
                      <input
                        type="number"
                        min="0"
                        value={mealConfig[type] ?? 0}
                        onChange={(e) =>
                          setMealConfig((m) => ({ ...m, [type]: parseInt(e.target.value, 10) || 0 }))
                        }
                        disabled={disabled}
                        className="w-14 rounded-lg border border-input bg-secondary px-2 py-1 text-sm text-foreground"
                      />
                      {disabled && (
                        <span className="text-xs text-muted-foreground">(none)</span>
                      )}
                    </label>
                  );
                })}
                  </div>

                  <div className="flex flex-col gap-2">
                    <span className="text-sm text-muted-foreground">Must include recipes:</span>
                    <div className="flex gap-2 flex-wrap items-center">
                      {requiredRecipeIds.map((rid) => {
                        const recipe = recipes.find((r) => r.id === rid);
                        return (
                          <span
                            key={rid}
                            className="inline-flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-sm text-secondary-foreground"
                          >
                            {recipe?.name ?? `Recipe ${rid}`}
                            <button
                              type="button"
                              onClick={() => setRequiredRecipeIds((arr) => arr.filter((x) => x !== rid))}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              ×
                            </button>
                          </span>
                        );
                      })}
                      <select
                        value=""
                        onChange={(e) => {
                          const id = parseInt(e.target.value, 10);
                          if (id && !requiredRecipeIds.includes(id)) {
                            setRequiredRecipeIds((arr) => [...arr, id]);
                          }
                          e.target.value = "";
                        }}
                        className="rounded-lg border border-input bg-secondary px-3 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring min-w-[180px]"
                      >
                        <option value="">Add recipe…</option>
                        {recipes
                          .filter((r) => !r.has_unavailable_ingredients && !requiredRecipeIds.includes(r.id))
                          .map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.name}
                            </option>
                          ))}
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <span className="text-sm text-muted-foreground">Stores only:</span>
                <div className="flex gap-2 flex-wrap items-center">
                  {storeSlugs.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-sm text-secondary-foreground"
                    >
                      {storesFromSkus.find((st) => st.slug === s)?.name || s.replace(/-/g, " ")}
                      <button
                        type="button"
                        onClick={() => setStoreSlugs((arr) => arr.filter((x) => x !== s))}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <select
                    value=""
                    onChange={(e) => {
                      const slug = e.target.value;
                      if (slug && !storeSlugs.includes(slug)) {
                        setStoreSlugs((arr) => [...arr, slug]);
                      }
                      e.target.value = "";
                    }}
                    className="rounded-lg border border-input bg-secondary px-3 py-1.5 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring min-w-[140px]"
                  >
                    <option value="">Add store…</option>
                    {storesFromSkus
                      .filter((st) => st.slug && !storeSlugs.includes(st.slug))
                      .map((st) => (
                        <option key={st.slug} value={st.slug}>
                          {st.name || st.slug}
                        </option>
                      ))}
                  </select>
                </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground">LP options:</span>
                <div className="flex gap-6 flex-wrap">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Time limit (s)</span>
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
                      className="rounded-lg border border-input bg-secondary px-3 py-1.5 text-sm text-foreground w-24"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Batch penalty</span>
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
                      className="rounded-lg border border-input bg-secondary px-3 py-1.5 text-sm text-foreground w-28"
                    />
                  </label>
                </div>
                  </div>
                </motion.div>
                )}
              </AnimatePresence>
            </div>
            {planResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-8 space-y-6"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-medium",
                        planResult.status === "Optimal"
                          ? "bg-step-complete/20 text-step-complete"
                          : planResult.status === "Infeasible"
                            ? "bg-destructive/20 text-destructive"
                            : "bg-primary/20 text-primary"
                      )}
                    >
                      {planResult.status}
                    </span>
                    <span className="text-muted-foreground text-sm">
                      Total: ${planResult.objective?.toFixed(2) ?? "—"}
                    </span>
                  </div>
                  {planResult.infeasible_reason && (
                    <p className="text-sm text-accent">{planResult.infeasible_reason}</p>
                  )}
                </div>

                {/* Chosen recipes */}
                {planResult.recipe_details?.length > 0 && (
                  <div className="rounded-xl border border-border bg-secondary/30 p-5">
                    <h3 className="font-display font-semibold text-foreground mb-4">Chosen recipes</h3>
                    <div className="space-y-3">
                      {planResult.recipe_details.map((r) => (
                        <div
                          key={r.recipe_id}
                          className="flex justify-between items-center py-2 border-b border-border last:border-0"
                        >
                          <span className="text-foreground font-medium">{r.name}</span>
                          <span className="text-muted-foreground text-sm">
                            {r.batches} batch{r.batches !== 1 ? "es" : ""} × {r.servings_per_batch} = {r.total_servings} servings
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Consolidated shopping list */}
                {planResult.consolidated_shopping_list?.length > 0 && (
                  <div className="rounded-xl border border-border bg-secondary/30 p-5">
                    <h3 className="font-display font-semibold text-foreground mb-4">Consolidated shopping list</h3>
                    <ul className="space-y-2">
                      {planResult.consolidated_shopping_list.map((item, i) => {
                        const qty = Number(item.quantity);
                        const unit = sanitizeUnit(item.unit);
                        const displayQty = Number.isFinite(qty) ? (qty % 1 === 0 ? qty : qty.toFixed(2)) : item.quantity;
                        return (
                          <li key={i} className="relative flex items-center gap-3 py-2 px-3 rounded-lg bg-secondary/50 border border-border/50">
                            <span className="text-muted-foreground capitalize flex-1">{item.ingredient}</span>
                            <span className="text-foreground font-medium tabular-nums shrink-0">
                              {displayQty}{unit ? ` ${unit}` : ""}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                {/* Generate Final Materials (post-plan) */}
                {planResult.menu_card?.length > 0 && (
                  <div className="rounded-xl border border-border bg-secondary/30 p-5">
                    <h3 className="font-display font-semibold text-foreground mb-2">Final materials</h3>
                    <p className="text-sm text-muted-foreground mb-4">
                      Generate printable cards, descriptions, and PDF. Descriptions and cards are
                      generated only when you click below.
                    </p>
                    <button
                      onClick={async () => {
                        uiLogger.info("generate_materials.click");
                        setMaterialsLoading(true);
                        try {
                          const res = await generateMaterials(planResult.menu_card);
                          setMaterialsData(res.menu_card);
                          setMaterialsEditorOpen(true);
                        } catch (err) {
                          setError(err?.message || "Failed to generate materials");
                        } finally {
                          setMaterialsLoading(false);
                        }
                      }}
                      disabled={materialsLoading}
                      className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {materialsLoading ? "Generating…" : "Generate Final Materials"}
                    </button>
                  </div>
                )}

                {/* Instructions — full text per dish, no scroll */}
                {planResult.menu_card?.length > 0 && (
                  <div className="rounded-xl border border-border bg-secondary/30 p-5">
                    <h3 className="font-display font-semibold text-foreground mb-4">Instructions</h3>
                    <div className="space-y-3">
                      {planResult.menu_card.map((dish, i) => {
                        const mealType = dish?.meal_type || "entree";
                        const materialsDish = materialsData?.[i]?.name === dish?.name ? materialsData[i] : null;
                        const theme = materialsDish?.background_color
                          ? { accentBg: materialsDish.background_color, borderColor: materialsDish.border_color || "hsl(0 0% 80%)" }
                          : MENU_THEME_STYLES[mealType] || MENU_THEME_STYLES.entree;
                        const instructions = (dish.instructions || "").trim();
                        return (
                          <div
                            key={i}
                            className="rounded-lg border px-3 py-3"
                            style={{ backgroundColor: theme.accentBg, borderColor: theme.borderColor, borderWidth: "1px" }}
                          >
                            <div className="font-display font-medium text-foreground text-sm tracking-wide mb-2">{dish.name}</div>
                            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{instructions || "—"}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* SKU purchase details */}
                {planResult.sku_details && Object.keys(planResult.sku_details).length > 0 && (
                  <div className="rounded-xl border border-border bg-secondary/30 p-5">
                    <h3 className="font-display font-semibold text-foreground mb-4">Items to purchase</h3>
                    <div className="space-y-3 text-sm">
                      {Object.entries(planResult.sku_details).map(([id, detail]) => (
                        <div
                          key={id}
                          className="flex justify-between gap-4 py-2 border-b border-border last:border-0"
                        >
                          <div>
                            <span className="text-foreground font-medium">{detail.name}</span>
                            {detail.brand && (
                              <span className="text-muted-foreground ml-1">({detail.brand})</span>
                            )}
                          </div>
                          <div className="text-right shrink-0">
                            <span className="text-step-complete font-medium">
                              ${detail.price?.toFixed(2)}
                              {detail.size && (
                                <span className="text-muted-foreground font-normal"> · {detail.size}</span>
                              )}
                              {" × "}{detail.quantity}
                            </span>
                            {detail.retailer && (
                              <span className="text-muted-foreground block text-xs capitalize mt-0.5">
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
            className="mt-6 rounded-xl border border-destructive/50 bg-destructive/10 px-4 py-3 text-destructive"
          >
            {error}
          </motion.div>
        )}

        <RecipeDetailModal
          recipe={selectedRecipe}
          open={!!selectedRecipe}
          onClose={() => setSelectedRecipe(null)}
        />
        <MenuCardEditor
          menuCard={materialsData}
          shoppingList={planResult?.consolidated_shopping_list ?? []}
          itemsToPurchase={planResult?.sku_details ?? {}}
          open={materialsEditorOpen}
          onClose={() => setMaterialsEditorOpen(false)}
        />
      </div>
    </AppBackground>
  );
}
