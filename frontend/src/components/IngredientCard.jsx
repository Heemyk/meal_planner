import { motion } from "framer-motion";
import { SpotlightCard } from "./SpotlightCard.jsx";
import { cn } from "../lib/utils.js";

/**
 * Card showing an ingredient and its attached SKUs, with spotlight hover effect.
 */
export function IngredientCard({ ingredient, index = 0 }) {
  const { name, base_unit, skus = [], sku_unavailable = false } = ingredient;
  const hasSkus = skus.length > 0;
  const unavailable = sku_unavailable && !hasSkus;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      viewport={{ once: true, margin: "-50px" }}
      className="h-full"
    >
      <SpotlightCard className="group h-full p-5 transition-colors hover:border-primary/30">
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h3 className="font-display font-semibold text-lg text-card-foreground group-hover:text-primary transition-colors capitalize">
              {name}
            </h3>
            <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-md bg-secondary">
              {base_unit}
            </span>
          </div>
          <div className="flex items-center gap-2 mb-3">
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                hasSkus
                  ? "bg-step-complete/20 text-step-complete"
                  : unavailable
                    ? "bg-neutral-600/30 text-neutral-400"
                    : "bg-step-pending text-muted-foreground"
              )}
            >
              {hasSkus ? `${skus.length} SKU${skus.length !== 1 ? "s" : ""}` : unavailable ? "Not available" : "Pending"}
            </span>
          </div>
          {hasSkus && (
            <ul className="space-y-2 mt-2 max-h-32 overflow-y-auto flex-1">
              {skus.slice(0, 6).map((sku) => (
                <li
                  key={sku.id}
                  className="flex justify-between items-start gap-2 text-sm py-2 px-3 rounded-lg bg-secondary/50 border border-border/50"
                >
                  <div className="min-w-0 flex-1">
                    <span className="text-secondary-foreground truncate block font-medium">
                      {sku.name}
                    </span>
                    {sku.brand && (
                      <span className="text-xs text-muted-foreground">{sku.brand}</span>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-step-complete font-medium">
                      ${sku.price != null ? Number(sku.price).toFixed(2) : "—"}
                    </span>
                    {sku.size && (
                      <span className="text-muted-foreground font-normal ml-1">· {sku.size}</span>
                    )}
                    {sku.retailer_slug && (
                      <span className="text-xs text-muted-foreground block capitalize mt-0.5">
                        {sku.retailer_slug.replace(/-/g, " ")}
                      </span>
                    )}
                  </div>
                </li>
              ))}
              {skus.length > 6 && (
                <li className="text-xs text-muted-foreground py-1">+{skus.length - 6} more</li>
              )}
            </ul>
          )}
        </div>
      </SpotlightCard>
    </motion.div>
  );
}
