import { motion } from "framer-motion";
import { SpotlightCard } from "./SpotlightCard.jsx";
import { cn } from "../lib/utils.js";

const MEAL_EMOJI = {
  appetizer: "🥗",
  entree: "🍽️",
  dessert: "🍰",
  side: "🥬",
};

/**
 * Recipe preview card with emoji, meal-type badge, metadata. Uses SpotlightCard for hover effect.
 * When has_unavailable_ingredients, card is greyed out (excluded from plan, ingredients have no SKUs).
 */
export function RecipeCard({ recipe, index = 0, onClick }) {
  const { name, servings, instructions, meal_type, allergens, has_unavailable_ingredients, unavailable_ingredient_names } = recipe;
  const emoji = MEAL_EMOJI[meal_type] || "🍽️";
  const preview = (instructions || "").slice(0, 120);
  const truncated = instructions && instructions.length > 120 ? `${preview}...` : preview;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      viewport={{ once: true, margin: "-50px" }}
      className="h-full"
    >
      <SpotlightCard
        onClick={has_unavailable_ingredients ? undefined : onClick}
        className={cn(
          "group h-full p-5 transition-colors",
          has_unavailable_ingredients
            ? "opacity-60 grayscale border-muted"
            : "hover:border-primary/30"
        )}
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl shrink-0">{emoji}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                  "bg-secondary text-secondary-foreground"
                )}
              >
                {meal_type || "entree"}
              </span>
            </div>
            <h3 className="font-display font-semibold text-lg text-card-foreground group-hover:text-primary transition-colors line-clamp-2">
              {name}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {servings} servings
            </p>
            {allergens?.length > 0 && (
              <p className="text-xs text-amber-500/90 mt-1">
                Allergens: {allergens.map((a) => a.replace(/_/g, " ")).join(", ")}
              </p>
            )}
            {has_unavailable_ingredients && unavailable_ingredient_names?.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">
                Unavailable: {unavailable_ingredient_names.map((n) => n.replace(/_/g, " ")).join(", ")}
              </p>
            )}
            {truncated && (
              <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{truncated}</p>
            )}
          </div>
        </div>
      </SpotlightCard>
    </motion.div>
  );
}
