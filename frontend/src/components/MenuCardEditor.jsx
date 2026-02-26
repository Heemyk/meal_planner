import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import JSZip from "jszip";
import { cn } from "../lib/utils.js";

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

const PAPER_OPTIONS = {
  a4: { w: 210, h: 297 },
  letter: { w: 216, h: 279 },
  "5x7": { w: 127, h: 178 },
};

const DEFAULT_PRINT_META = {
  resolution: 300,
  bleed: "3mm",
  paperStock: "Matte 120gsm",
  size: "A4",
  finishes: "None",
};

/**
 * Printable card canvas - elegant menu layout, paper-like, no scroll.
 * Styled like a fine-dining menu with written-text typography.
 */
function PrintableCardCanvas({ cards, onDescriptionChange }) {
  return (
    <div
      className="relative w-full overflow-hidden rounded-lg shadow-lg"
      style={{
        aspectRatio: "210 / 297",
        maxWidth: 400,
        backgroundColor: "hsl(45 22% 96%)",
        boxShadow: "0 2px 20px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.9)",
      }}
    >
      <div className="absolute inset-0 rounded-lg border border-black/[0.04]" />
      <div className="absolute inset-5 flex flex-col gap-2">
        <h2
          className="font-display text-[1.1rem] font-medium tracking-[0.15em] uppercase text-black/85"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "0.12em" }}
        >
          Menu
        </h2>
        <div className="h-px w-12 bg-black/15" />
        <div className="flex flex-1 flex-col gap-1.5 overflow-visible">
          {cards.map((dish, i) => {
            const mealType = dish?.meal_type || "entree";
            const theme = THEME_STYLES[mealType] || THEME_STYLES.entree;
            const description = dish?.description ?? "";
            return (
              <div
                key={dish?.name ?? i}
                className="relative flex-shrink-0 rounded px-2.5 py-1.5 transition-colors hover:bg-black/[0.02]"
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
                  <textarea
                    value={description}
                    onChange={(e) => onDescriptionChange?.(dish?.name, e.target.value)}
                    className="mt-0.5 w-full resize-none border-none bg-transparent p-0 text-[10px] leading-snug text-black/60 placeholder:text-black/30 focus:outline-none focus:ring-0"
                    rows={2}
                    placeholder="Brief description..."
                    style={{ fontFamily: "var(--font-body)" }}
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

/**
 * Static card for html2canvas capture - no interactive elements.
 * Sleek menu typography, succinct descriptions.
 */
function CardForCapture({ cards }) {
  return (
    <div
      className="w-[420px] overflow-hidden"
      style={{
        aspectRatio: "210 / 297",
        backgroundColor: "hsl(45 22% 96%)",
      }}
    >
      <div className="flex h-full w-full flex-col gap-2 p-5">
        <h2
          className="font-display text-[1.1rem] font-medium tracking-[0.15em] uppercase text-black/85"
          style={{ letterSpacing: "0.12em" }}
        >
          Menu
        </h2>
        <div className="h-px w-12 bg-black/15" />
        <div className="flex flex-1 flex-col gap-1.5">
          {cards.map((dish, i) => {
            const mealType = dish?.meal_type || "entree";
            const theme = THEME_STYLES[mealType] || THEME_STYLES.entree;
            const desc = (dish?.description || "—").trim();
            return (
              <div
                key={dish?.name ?? i}
                className="flex flex-shrink-0 gap-2 rounded px-2.5 py-1.5"
                style={{ backgroundColor: theme.accentBg }}
              >
                <div
                  className="w-0.5 shrink-0 self-stretch rounded-full"
                  style={{ backgroundColor: theme.borderColor }}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-display font-medium text-black/90 capitalize text-[13px] tracking-wide">
                    {dish?.name}
                  </div>
                  <p className="mt-0.5 text-[10px] leading-snug text-black/60 line-clamp-2">
                    {desc}
                  </p>
                  {dish?.allergens?.length > 0 && (
                    <p className="mt-0.5 text-[9px] text-amber-700/90">
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

export function MenuCardEditor({ menuCard, open, onClose }) {
  const [cards, setCards] = useState([]);
  const [printMeta, setPrintMeta] = useState(DEFAULT_PRINT_META);
  const captureRef = useRef(null);

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

  const handleExport = async () => {
    const container = captureRef.current?.firstElementChild ?? captureRef.current;
    if (!container) {
      console.error("Export: capture ref not found");
      return;
    }

    setExporting(true);
    try {
      // Clone into viewport so html2canvas can render it (opacity 1, off-screen for reliable capture)
      const clone = container.cloneNode(true);
      clone.style.cssText =
        "position:fixed;left:-9999px;top:0;z-index:9999;opacity:1;pointer-events:none;width:420px;";
      document.body.appendChild(clone);
      let canvas;
      try {
        canvas = await html2canvas(clone, {
          scale: printMeta.resolution / 96,
          useCORS: true,
          backgroundColor: "hsl(40 25% 97%)",
          logging: false,
        });
      } finally {
        document.body.removeChild(clone);
      }

      const imgData = canvas.toDataURL("image/png");
      const sizeKey = printMeta.size.toLowerCase().replace(/\s/g, "");
      const paper = PAPER_OPTIONS[sizeKey] || PAPER_OPTIONS.a4;

      const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: [paper.w, paper.h],
      });
      const margin = 10;
      const maxW = paper.w - 2 * margin;
      const maxH = paper.h - 2 * margin;
      const scale = Math.min(maxW / canvas.width, maxH / canvas.height);
      doc.addImage(imgData, "PNG", margin, margin, canvas.width * scale, canvas.height * scale);
      doc.setProperties({
        title: "Menu Card",
        subject: `Print: ${printMeta.resolution}dpi, bleed ${printMeta.bleed}, ${printMeta.paperStock}`,
        creator: "Tandem Recipe Planner",
      });

      // jsPDF 4 returns a Promise for output("blob") — must await
      const pdfBlob = await doc.output("blob");

      const metadata = {
        resolution_dpi: printMeta.resolution,
        bleed: printMeta.bleed,
        paper_stock: printMeta.paperStock,
        paper_size: printMeta.size,
        finishes: printMeta.finishes,
        menu_card: (cards.length ? cards : menuCard || []).map((d) => ({
          name: d.name,
          meal_type: d.meal_type,
          description: d.description ?? d.generated_description ?? "",
          allergens: d.allergens ?? [],
        })),
      };

      const zip = new JSZip();
      zip.file("menu-card.pdf", pdfBlob);
      zip.file("metadata.json", JSON.stringify(metadata, null, 2));

      const zipBlob = await zip.generateAsync({ type: "blob" });
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
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
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

          <div className="flex-1 min-h-0 overflow-y-auto space-y-4 p-4">
            {/* Card canvas - Figma-style WYSIWYG */}
            <div className="flex flex-col gap-2">
              <span className="text-sm text-muted-foreground">Card preview</span>
              <div className="flex justify-center">
                <PrintableCardCanvas
                  cards={displayCards}
                  onDescriptionChange={handleDescriptionChange}
                />
              </div>
              {/* Invisible clone for capture - in-viewport so html2canvas can render it */}
              <div
                ref={captureRef}
                className="fixed left-0 top-0 w-[420px] opacity-0 pointer-events-none -z-10"
                style={{ aspectRatio: "210 / 297" }}
                aria-hidden
              >
                <CardForCapture cards={displayCards} />
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
                {exporting ? "Exporting…" : "Download All (.zip with PDF + metadata)"}
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
