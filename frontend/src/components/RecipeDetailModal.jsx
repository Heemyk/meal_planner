import { motion, AnimatePresence } from "framer-motion";
import { cn } from "../lib/utils.js";

const MEAL_EMOJI = {
  appetizer: "🥗",
  entree: "🍽️",
  dessert: "🍰",
  side: "🥬",
};

/**
 * Modal showing full recipe details — name, servings, meal type, allergens, instructions.
 */
export function RecipeDetailModal({ recipe, open, onClose }) {
  if (!open || !recipe) return null;

  const emoji = MEAL_EMOJI[recipe.meal_type] || "🍽️";
  const instructions = (recipe.instructions || "").trim();

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm"
        onClick={() => onClose?.()}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-card px-4 py-3">
            <h2 className="font-display text-lg font-semibold text-foreground truncate pr-8">
              {recipe.name}
            </h2>
            <button
              onClick={() => onClose?.()}
              className="absolute right-3 top-3 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-3xl">{emoji}</span>
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                  "bg-secondary text-secondary-foreground"
                )}
              >
                {recipe.meal_type || "entree"}
              </span>
              <span className="text-sm text-muted-foreground">
                {recipe.servings} servings
              </span>
            </div>

            {recipe.allergens?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">
                  Contains allergens
                </h3>
                <p className="text-sm text-amber-600/90">
                  {recipe.allergens.map((a) => a.replace(/_/g, " ")).join(", ")}
                </p>
              </div>
            )}

            {instructions && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">
                  Instructions
                </h3>
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                  {instructions}
                </p>
              </div>
            )}

            {recipe.has_unavailable_ingredients && recipe.unavailable_ingredient_names?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-1">
                  Unavailable ingredients
                </h3>
                <p className="text-xs text-muted-foreground">
                  {recipe.unavailable_ingredient_names.map((n) => n.replace(/_/g, " ")).join(", ")}
                </p>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
