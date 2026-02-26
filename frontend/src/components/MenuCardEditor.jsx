import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import JSZip from "jszip";

const THEME_STYLES = {
  appetizer: {
    borderColor: "hsl(36 90% 45%)",
    accentBg: "hsl(36 90% 55% / 0.08)",
  },
  entree: {
    borderColor: "hsl(270 70% 50%)",
    accentBg: "hsl(270 70% 50% / 0.08)",
  },
  dessert: {
    borderColor: "hsl(340 70% 55%)",
    accentBg: "hsl(340 70% 55% / 0.08)",
  },
  side: {
    borderColor: "hsl(150 60% 40%)",
    accentBg: "hsl(150 60% 40% / 0.08)",
  },
};

const DEFAULT_PRINT_META = {
  resolution: 300,
  bleed: "3mm",
  paperStock: "Matte 120gsm",
  size: "A4",
  finishes: "None",
};

/** Auto-resize textarea so content shows fully without scrollbar */
function ResizableTextarea({ value, onChange, placeholder, className, style }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(40, el.scrollHeight)}px`;
  }, [value]);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={className}
      style={style}
      rows={2}
    />
  );
}

/**
 * Printable card canvas - elegant menu layout, paper-like, no scroll.
 * Sections size to content so full descriptions show.
 */
function PrintableCardCanvas({ cards, onDescriptionChange }) {
  return (
    <div
      className="relative w-full rounded-lg shadow-lg min-h-[300px]"
      style={{
        maxWidth: 420,
        backgroundColor: "hsl(45 22% 96%)",
        boxShadow: "0 2px 20px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.9)",
      }}
    >
      <div className="absolute inset-0 rounded-lg border border-black/[0.04]" />
      <div className="p-5 flex flex-col gap-2">
        <h2
          className="font-display text-[1.1rem] font-medium tracking-[0.15em] uppercase text-black/85"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "0.12em" }}
        >
          Menu
        </h2>
        <div className="h-px w-12 bg-black/15" />
        <div className="flex flex-col gap-2">
          {cards.map((dish, i) => {
            const mealType = dish?.meal_type || "entree";
            const theme = THEME_STYLES[mealType] || THEME_STYLES.entree;
            const description = dish?.description ?? "";
            return (
              <div
                key={dish?.name ?? i}
                className="relative rounded px-2.5 py-1.5 transition-colors hover:bg-black/[0.02]"
                style={{ backgroundColor: theme.accentBg }}
              >
                <div
                  className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full"
                  style={{ backgroundColor: theme.borderColor }}
                />
                <div className="pl-3">
                  <div
                    className="font-display font-medium text-black/90 capitalize text-[13px] tracking-wide"
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {dish?.name}
                  </div>
                  <ResizableTextarea
                    value={description}
                    onChange={(e) => onDescriptionChange?.(dish?.name, e.target.value)}
                    placeholder="Brief description..."
                    className="mt-0.5 w-full resize-none border-none bg-transparent p-0 text-[10px] leading-snug text-black/60 placeholder:text-black/30 focus:outline-none focus:ring-0 overflow-hidden"
                    style={{ fontFamily: "var(--font-body)", minHeight: 40 }}
                  />
                  {dish?.allergens?.length > 0 && (
                    <p className="mt-1 text-[9px] text-amber-700/90" style={{ fontFamily: "var(--font-body)" }}>
                      Contains: {dish.allergens.map((a) => a.replace(/_/g, " ")).join(", ")}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function MenuCardEditor({ menuCard, open, onClose }) {
  const [cards, setCards] = useState([]);
  const [printMeta, setPrintMeta] = useState(DEFAULT_PRINT_META);

  useEffect(() => {
    if (open && menuCard?.length) {
      setCards(
        menuCard.map((d) => ({
          ...d,
          description: d.generated_description || d.description || "",
        }))
      );
    }
  }, [open, menuCard]);

  const handleDescriptionChange = (name, value) => {
    setCards((prev) =>
      prev.map((c) => (c.name === name ? { ...c, description: value } : c))
    );
  };

  const [exporting, setExporting] = useState(false);

  const handleExport = () => {
    const data = cards.length ? cards : menuCard || [];
    setExporting(true);
    try {
      const metadata = {
        resolution_dpi: printMeta.resolution,
        bleed: printMeta.bleed,
        paper_stock: printMeta.paperStock,
        paper_size: printMeta.size,
        finishes: printMeta.finishes,
        menu_card: data.map((d) => ({
          name: d.name,
          meal_type: d.meal_type,
          description: d.description ?? d.generated_description ?? "",
          allergens: d.allergens ?? [],
        })),
      };

      const themeColors = {
        appetizer: { border: "hsl(36 90% 45%)", bg: "hsl(36 90% 55% / 0.08)" },
        entree: { border: "hsl(270 70% 50%)", bg: "hsl(270 70% 50% / 0.08)" },
        dessert: { border: "hsl(340 70% 55%)", bg: "hsl(340 70% 55% / 0.08)" },
        side: { border: "hsl(150 60% 40%)", bg: "hsl(150 60% 40% / 0.08)" },
      };

      const dishBlocks = data.map((dish) => {
        const mealType = (dish?.meal_type || "entree").toLowerCase();
        const theme = themeColors[mealType] || themeColors.entree;
        const desc = escapeHtml((dish?.description ?? dish?.generated_description ?? "—").trim());
        const name = escapeHtml(dish?.name ?? "");
        const allergens = (dish?.allergens ?? []).map(escapeHtml).join(", ");
        const allergenHtml = allergens
          ? `<p class="allergens">Contains: ${allergens}</p>`
          : "";
        return `
  <div class="dish" style="background-color:${theme.bg}">
    <div class="dish-accent" style="background-color:${theme.border}"></div>
    <div class="dish-content">
      <div class="dish-name">${name}</div>
      <div class="dish-desc">${desc.replace(/\n/g, "<br>")}</div>
      ${allergenHtml}
    </div>
  </div>`;
      });

      const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Menu Card</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 20px; font-family: system-ui, sans-serif; background: hsl(45 22% 96%); }
    .menu { max-width: 420px; margin: 0 auto; }
    .menu-title { font-size: 1.1rem; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(0,0,0,0.85); }
    .menu-rule { height: 1px; width: 48px; background: rgba(0,0,0,0.15); margin: 8px 0 16px 0; }
    .dish { display: flex; gap: 8px; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; }
    .dish-accent { width: 2px; border-radius: 999px; flex-shrink: 0; }
    .dish-content { flex: 1; min-width: 0; }
    .dish-name { font-weight: 500; font-size: 13px; color: rgba(0,0,0,0.9); margin-bottom: 4px; }
    .dish-desc { font-size: 10px; line-height: 1.4; color: rgba(0,0,0,0.6); white-space: pre-wrap; word-break: break-word; }
    .allergens { font-size: 9px; color: rgba(180,83,9,0.9); margin-top: 4px; }
  </style>
</head>
<body>
  <div class="menu">
    <h1 class="menu-title">Menu</h1>
    <div class="menu-rule"></div>
    ${dishBlocks.join("\n")}
  </div>
</body>
</html>`;

      const zip = new JSZip();
      zip.file("menu-card.html", html);
      zip.file("metadata.json", JSON.stringify(metadata, null, 2));

      zip.generateAsync({ type: "blob" }).then((zipBlob) => {
        const url = URL.createObjectURL(zipBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "menu-card-export.zip";
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 500);
        setExporting(false);
      });
    } catch (err) {
      console.error("Export failed:", err);
      setExporting(false);
    }
  };

  if (!open) return null;

  const displayCards = cards.length ? cards : menuCard || [];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/90 backdrop-blur-sm overflow-y-auto"
        onClick={() => onClose?.()}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="relative flex w-full max-w-2xl flex-col overflow-visible rounded-2xl border border-border bg-card shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border bg-card px-4 py-3">
            <h2 className="font-display text-lg font-semibold text-foreground">
              Final Materials — Card Editor
            </h2>
            <button
              onClick={() => onClose?.()}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              ✕
            </button>
          </div>

          <div className="flex-1 space-y-4 p-4 overflow-visible">
            {/* Card canvas - Figma-style WYSIWYG */}
            <div className="flex flex-col gap-2">
              <span className="text-sm text-muted-foreground">Card preview</span>
              <div className="flex justify-center">
                <PrintableCardCanvas
                  cards={displayCards}
                  onDescriptionChange={handleDescriptionChange}
                />
              </div>
            </div>

            {/* Print metadata */}
            <div className="rounded-xl border border-border bg-secondary/30 p-4 space-y-3">
              <h3 className="text-sm font-medium text-muted-foreground">Print options</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Resolution (DPI)</span>
                  <input
                    type="number"
                    min="150"
                    max="600"
                    value={printMeta.resolution}
                    onChange={(e) =>
                      setPrintMeta((m) => ({ ...m, resolution: parseInt(e.target.value, 10) || 300 }))
                    }
                    className="rounded-lg border border-input bg-background px-3 py-2 text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Bleed</span>
                  <input
                    type="text"
                    value={printMeta.bleed}
                    onChange={(e) => setPrintMeta((m) => ({ ...m, bleed: e.target.value }))}
                    className="rounded-lg border border-input bg-background px-3 py-2 text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Paper size</span>
                  <select
                    value={printMeta.size}
                    onChange={(e) => setPrintMeta((m) => ({ ...m, size: e.target.value }))}
                    className="rounded-lg border border-input bg-background px-3 py-2 text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="A4">A4</option>
                    <option value="Letter">Letter</option>
                    <option value="5x7">5×7"</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-muted-foreground">Paper stock</span>
                  <input
                    type="text"
                    value={printMeta.paperStock}
                    onChange={(e) =>
                      setPrintMeta((m) => ({ ...m, paperStock: e.target.value }))
                    }
                    className="rounded-lg border border-input bg-background px-3 py-2 text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                <label className="flex flex-col gap-1 col-span-2">
                  <span className="text-muted-foreground">Finishes</span>
                  <input
                    type="text"
                    value={printMeta.finishes}
                    onChange={(e) => setPrintMeta((m) => ({ ...m, finishes: e.target.value }))}
                    placeholder="e.g. Matte, Glossy"
                    className="rounded-lg border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleExport}
                disabled={exporting}
                className="flex-1 rounded-xl bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 glow-primary disabled:opacity-60 disabled:cursor-wait"
              >
                {exporting ? "Exporting…" : "Download All (.zip with HTML + metadata)"}
              </button>
              <button
                onClick={() => onClose?.()}
                className="rounded-xl border border-border px-4 py-3 text-foreground transition-colors hover:bg-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
