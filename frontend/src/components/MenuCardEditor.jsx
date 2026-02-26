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
 * Printable card canvas - Figma-style layout, paper-like, with editable text.
 * Styled to look like the actual printed output.
 */
function PrintableCardCanvas({ cards, onDescriptionChange }) {
  return (
    <div
      className="relative w-full overflow-hidden rounded-lg shadow-lg"
      style={{
        aspectRatio: "210 / 297",
        maxWidth: 400,
        backgroundColor: "hsl(40 25% 97%)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.8)",
      }}
    >
      {/* Paper texture / subtle border */}
      <div className="absolute inset-0 rounded-lg border border-black/5" />
      <div className="absolute inset-4 flex flex-col gap-3 overflow-auto">
        <h2
          className="font-display text-xl font-bold tracking-tight text-black/90"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Menu
        </h2>
        <div className="h-px bg-black/10" />
        {cards.map((dish, i) => {
          const mealType = dish?.meal_type || "entree";
          const theme = THEME_STYLES[mealType] || THEME_STYLES.entree;
          const description = dish?.description ?? "";
          return (
            <div
              key={dish?.name ?? i}
              className="relative rounded-md px-3 py-2 transition-colors hover:bg-black/[0.02]"
              style={{ backgroundColor: theme.accentBg }}
            >
              <div
                className="absolute left-0 top-2 bottom-2 w-1 rounded-full"
                style={{ backgroundColor: theme.borderColor }}
              />
              <div className="pl-4">
                <div
                  className="font-display font-semibold text-black/90 capitalize text-sm tracking-wide"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {dish?.name}
                </div>
                <textarea
                  value={description}
                  onChange={(e) => onDescriptionChange?.(dish?.name, e.target.value)}
                  className="mt-1 w-full resize-none border-none bg-transparent p-0 text-xs leading-relaxed text-black/70 placeholder:text-black/40 focus:outline-none focus:ring-0"
                  rows={3}
                  placeholder="Description..."
                  style={{ fontFamily: "var(--font-body)" }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Static card for html2canvas capture - no interactive elements.
 * Rendered off-screen so it doesn't flash; html2canvas can still capture it.
 */
function CardForCapture({ cards }) {
  return (
    <div
      className="w-[420px] overflow-hidden"
      style={{
        aspectRatio: "210 / 297",
        backgroundColor: "hsl(40 25% 97%)",
      }}
    >
      <div className="flex h-full w-full flex-col gap-3 p-6">
        <h2 className="font-display text-xl font-bold tracking-tight text-black/90">Menu</h2>
        <div className="h-px bg-black/10" />
        {cards.map((dish, i) => {
          const mealType = dish?.meal_type || "entree";
          const theme = THEME_STYLES[mealType] || THEME_STYLES.entree;
          return (
            <div
              key={dish?.name ?? i}
              className="rounded-md px-3 py-2"
              style={{ backgroundColor: theme.accentBg }}
            >
              <div className="flex gap-3">
                <div
                  className="w-1 shrink-0 rounded-full"
                  style={{ backgroundColor: theme.borderColor }}
                />
                <div>
                  <div className="font-display font-semibold text-black/90 capitalize text-sm">
                    {dish?.name}
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-black/70">
                    {dish?.description || "—"}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
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

  const handleExport = async () => {
    const container = captureRef.current?.firstElementChild ?? captureRef.current;
    if (!container) {
      console.error("Export: capture ref not found");
      return;
    }

    try {
      const canvas = await html2canvas(container, {
        scale: printMeta.resolution / 96,
        useCORS: true,
        backgroundColor: "hsl(40 25% 97%)",
        logging: false,
      });

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

      const pdfBlob = doc.output("blob");

      const metadata = {
        resolution_dpi: printMeta.resolution,
        bleed: printMeta.bleed,
        paper_stock: printMeta.paperStock,
        paper_size: printMeta.size,
        finishes: printMeta.finishes,
      };

      const zip = new JSZip();
      zip.file("menu-card.pdf", pdfBlob);
      zip.file("metadata.json", JSON.stringify(metadata, null, 2));

      const zipBlob = await zip.generateAsync({ type: "blob" });
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "menu-card-export.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
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

          <div className="flex-1 space-y-4 overflow-auto p-4">
            {/* Card canvas - Figma-style WYSIWYG */}
            <div className="flex flex-col gap-2">
              <span className="text-sm text-muted-foreground">Card preview</span>
              <div className="flex justify-center">
                <PrintableCardCanvas
                  cards={displayCards}
                  onDescriptionChange={handleDescriptionChange}
                />
              </div>
              {/* Off-screen clone for capture (static, no textareas) */}
              <div
                ref={captureRef}
                className="fixed -left-[9999px] top-0 z-[-1]"
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
                className="flex-1 rounded-xl bg-primary px-4 py-3 font-medium text-primary-foreground transition-opacity hover:opacity-90 glow-primary"
              >
                Export (.zip with PDF + metadata)
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
