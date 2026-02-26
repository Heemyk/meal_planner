import { motion } from "framer-motion";

/**
 * Segmented progress bar for Pricing: with_skus (primary) | unavailable (dark grey) | pending (muted).
 * value = ingredients_with_skus, unavailable = ingredients_unavailable, max = sku_total.
 */
export function SegmentedProgressBar({
  value = 0,
  unavailable = 0,
  max = 1,
  label = "Pricing",
  className = "",
}) {
  const total = Math.max(1, max);
  const pctComplete = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
  const pctUnavailable = total > 0 ? Math.min(100 - pctComplete, Math.round((unavailable / total) * 100)) : 0;
  const displayValue = `${value} / ${total}`;

  return (
    <div className={`w-full ${className}`}>
      <div className="flex justify-between text-sm text-muted-foreground mb-1.5">
        <span>{label}</span>
        <span>{displayValue}</span>
      </div>
      <div className="h-2.5 w-full rounded-full overflow-hidden flex">
        <motion.div
          className="h-full bg-primary shrink-0 min-w-0"
          initial={{ width: 0 }}
          animate={{ width: `${pctComplete}%` }}
          transition={{ type: "spring", stiffness: 50, damping: 20 }}
        />
        <motion.div
          className="h-full bg-neutral-600 shrink-0 min-w-0"
          initial={{ width: 0 }}
          animate={{ width: `${pctUnavailable}%` }}
          transition={{ type: "spring", stiffness: 50, damping: 20 }}
        />
        <div className="h-full flex-1 min-w-0 bg-secondary" />
      </div>
    </div>
  );
}

/**
 * Shimmer progress bar inspired by Aceternity UI loaders.
 */
export function ProgressBar({ value = 0, max = 100, label, showValue = true, className = "" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const displayValue = showValue ? `${value} / ${max}` : `${pct}%`;

  return (
    <div className={`w-full ${className}`}>
      {(label || showValue) && (
        <div className="flex justify-between text-sm text-muted-foreground mb-1.5">
          <span>{label}</span>
          <span>{displayValue}</span>
        </div>
      )}
      <div className="h-2.5 w-full rounded-full bg-secondary overflow-hidden relative">
        <motion.div
          className="h-full rounded-full bg-primary overflow-hidden relative"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ type: "spring", stiffness: 50, damping: 20 }}
        >
          <div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent bg-[length:200%_100%] animate-shimmer"
            aria-hidden
          />
        </motion.div>
      </div>
    </div>
  );
}
