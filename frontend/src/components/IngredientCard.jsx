import { motion } from "framer-motion";
import { cn } from "../lib/utils.js";

/**
 * Card showing an ingredient and its attached SKUs, with spotlight hover effect.
 */
export function IngredientCard({ ingredient, index = 0 }) {
  const { name, base_unit, skus = [] } = ingredient;
  const hasSkus = skus.length > 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3 }}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-zinc-700/50 bg-zinc-900/50 p-4",
        "transition-all duration-300 hover:border-violet-500/50 hover:shadow-[0_0_30px_-10px_rgba(139,92,246,0.3)]"
      )}
    >
      <div className="relative">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3 className="font-semibold text-zinc-100 capitalize">{name}</h3>
          <span className="text-xs text-zinc-500">{base_unit}</span>
        </div>
        <div className="flex items-center gap-1.5 mb-2">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              hasSkus
                ? "bg-emerald-500/20 text-emerald-400"
                : "bg-amber-500/20 text-amber-400"
            )}
          >
            {hasSkus ? `${skus.length} SKU${skus.length !== 1 ? "s" : ""}` : "Pending"}
          </span>
        </div>
        {hasSkus && (
          <ul className="space-y-1.5 mt-2 max-h-32 overflow-y-auto">
            {skus.slice(0, 6).map((sku) => (
              <li
                key={sku.id}
                className="flex justify-between items-start gap-2 text-sm py-1.5 px-2 rounded-lg bg-zinc-800/60 border border-zinc-700/30"
              >
                <div className="min-w-0 flex-1">
                  <span className="text-zinc-300 truncate block">{sku.name}</span>
                  {sku.brand && (
                    <span className="text-xs text-zinc-500">{sku.brand}</span>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <span className="text-emerald-400 font-medium">
                    ${sku.price != null ? Number(sku.price).toFixed(2) : "—"}
                    {sku.size && (
                      <span className="text-zinc-500 font-normal ml-1">/ {sku.size}</span>
                    )}
                  </span>
                  {sku.retailer_slug && (
                    <span className="text-xs text-zinc-500 block capitalize">
                      {sku.retailer_slug.replace(/-/g, " ")}
                    </span>
                  )}
                </div>
              </li>
            ))}
            {skus.length > 6 && (
              <li className="text-xs text-zinc-500 py-1">+{skus.length - 6} more</li>
            )}
          </ul>
        )}
      </div>
    </motion.div>
  );
}
