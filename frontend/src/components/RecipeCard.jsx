import { motion } from "framer-motion";

/**
 * Card showing a single recipe.
 */
export function RecipeCard({ recipe, index = 0 }) {
  const { name, servings, instructions, meal_type, allergens } = recipe;
  const preview = (instructions || "").slice(0, 120);
  const truncated = instructions && instructions.length > 120 ? `${preview}...` : preview;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className="rounded-xl border border-zinc-700/50 bg-zinc-900/50 p-4 transition-all duration-300 hover:border-violet-500/50"
    >
      <h3 className="font-semibold text-zinc-100 capitalize">{name}</h3>
      <p className="text-xs text-zinc-500 mt-1">
        {servings} servings
        {meal_type && (
          <span className="ml-2 capitalize text-zinc-400">• {meal_type}</span>
        )}
      </p>
      {allergens?.length > 0 && (
        <p className="text-xs text-amber-500/80 mt-1">
          Allergens: {allergens.map((a) => a.replace(/_/g, " ")).join(", ")}
        </p>
      )}
      {truncated && (
        <p className="text-sm text-zinc-400 mt-2 line-clamp-3">{truncated}</p>
      )}
    </motion.div>
  );
}
