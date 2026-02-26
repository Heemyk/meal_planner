import { cn } from "../lib/utils.js";

/**
 * Background with subtle grid pattern and ambient glow (example_ui style).
 */
export function AppBackground({ className, children, ...props }) {
  return (
    <div
      className={cn(
        "relative flex min-h-screen flex-col overflow-hidden bg-background text-foreground",
        className
      )}
      {...props}
    >
      {/* Subtle grid overlay */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.3] bg-grid"
        aria-hidden
      />
      {/* Ambient glow blob */}
      <div
        className="pointer-events-none fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-[0.05] blur-[120px]"
        style={{
          background: "radial-gradient(circle, hsl(36 90% 55%) 0%, transparent 70%)",
        }}
        aria-hidden
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
