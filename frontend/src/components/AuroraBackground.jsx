import { cn } from "../lib/utils.js";

/**
 * Aurora-style background effect inspired by Aceternity UI.
 */
export function AuroraBackground({ className, children, ...props }) {
  return (
    <div
      className={cn(
        "relative flex min-h-screen flex-col overflow-hidden bg-zinc-950 text-zinc-50",
        className
      )}
      {...props}
    >
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute -inset-[10px] opacity-50"
          style={{
            background:
              "linear-gradient(180deg, transparent 0%, rgba(120, 119, 198, 0.15) 40%, rgba(236, 72, 153, 0.1) 60%, transparent 100%)",
            backgroundSize: "400% 400%",
            animation: "aurora 30s ease-in-out infinite",
          }}
        />
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-20 blur-[100px]"
          style={{
            background: "radial-gradient(circle, rgba(139, 92, 246, 0.3) 0%, transparent 70%)",
          }}
        />
      </div>
      <div className="relative z-10">{children}</div>
    </div>
  );
}
